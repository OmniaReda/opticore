import enum
import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ProjectStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class FileKind(str, enum.Enum):
    kml = "kml"
    kmz = "kmz"
    dxf = "dxf"
    dwg = "dwg"
    survey_xlsx = "survey_xlsx"
    other = "other"


class FileStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    processed = "processed"
    failed = "failed"


def _enum(e: type[enum.Enum], name: str) -> Enum:
    # Stored as VARCHAR + CHECK constraint (easier to extend than native PG enums).
    return Enum(e, name=name, native_enum=False, create_constraint=True, length=20,
                values_callable=lambda cls: [m.value for m in cls])


class Project(Base):
    __tablename__ = "project"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProjectStatus] = mapped_column(_enum(ProjectStatus, "project_status"),
                                                  default=ProjectStatus.draft)
    # Project boundary, EPSG:4326. Set from the Polygon placemarks of an imported KML/KMZ.
    boundary = mapped_column(Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=True)
    # File the boundary came from (cleared together with the boundary if that file is deleted).
    boundary_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project_file.id", ondelete="SET NULL", use_alter=True, name="fk_project_boundary_file"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())

    files: Mapped[list["ProjectFile"]] = relationship(back_populates="project", cascade="all, delete-orphan",
                                                      passive_deletes=True, order_by="ProjectFile.uploaded_at",
                                                      foreign_keys="ProjectFile.project_id")

    __table_args__ = (Index("ix_project_boundary", "boundary", postgresql_using="gist"),)


class ProjectFile(Base):
    __tablename__ = "project_file"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)
    kind: Mapped[FileKind] = mapped_column(_enum(FileKind, "file_kind"))
    original_filename: Mapped[str] = mapped_column(String(255))
    # Relative to settings.storage_dir.
    stored_path: Mapped[str] = mapped_column(String(500))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[FileStatus] = mapped_column(_enum(FileStatus, "file_status"), default=FileStatus.uploaded)
    error: Mapped[str | None] = mapped_column(Text)
    # Human-readable result of processing, e.g. "Boundary: 1 polygon (36.1 ha) · 1 point".
    note: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="files", foreign_keys=[project_id])


class ProjectFeature(Base):
    """A raw geometry imported from a project file (e.g. a KML placemark), EPSG:4326, 2D.

    Not interpreted: a point is just a named point until a later stage gives it meaning.
    """

    __tablename__ = "project_feature"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_file.id", ondelete="CASCADE"),
                                                      index=True)
    name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    geometry = mapped_column(Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=False)

    __table_args__ = (Index("ix_project_feature_geometry", "geometry", postgresql_using="gist"),)


class Building(Base):
    """A building polygon extracted from a CAD drawing (EPSG:4326).

    The review status is not stored: it follows from how many BuildingLabels point at the building.
    """

    __tablename__ = "building"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_file.id", ondelete="CASCADE"),
                                                      index=True)
    geometry = mapped_column(Geometry("POLYGON", srid=4326, spatial_index=False), nullable=False)

    __table_args__ = (Index("ix_building_geometry", "geometry", postgresql_using="gist"),)


class BuildingLabel(Base):
    """A Building ID label placed on a CAD drawing (e.g. '12', '12-2').

    building_id is the polygon the label lies in; NULL = the label is not inside any building.
    """

    __tablename__ = "building_label"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_file.id", ondelete="CASCADE"),
                                                      index=True)
    building_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("building.id", ondelete="SET NULL"),
                                                          index=True)
    code: Mapped[str] = mapped_column(String(50))
    geometry = mapped_column(Geometry("POINT", srid=4326, spatial_index=False), nullable=False)
