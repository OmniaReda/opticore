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
    # Project boundary, EPSG:4326. Filled from the KML import (Day 2).
    boundary = mapped_column(Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())

    files: Mapped[list["ProjectFile"]] = relationship(back_populates="project", cascade="all, delete-orphan",
                                                      passive_deletes=True, order_by="ProjectFile.uploaded_at")

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
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="files")
