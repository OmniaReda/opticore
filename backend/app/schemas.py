import enum
import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import FileKind, FileStatus, ProjectStatus

ProjectName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ProjectCreate(BaseModel):
    name: ProjectName
    description: str | None = None


class ProjectUpdate(BaseModel):
    """Partial update: only fields that are sent are changed."""

    name: ProjectName | None = None
    description: str | None = None
    status: ProjectStatus | None = None


class ProjectFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    kind: FileKind
    original_filename: str
    size_bytes: int
    sha256: str
    status: FileStatus
    error: str | None
    note: str | None
    uploaded_at: datetime


class GeoJsonGeometry(BaseModel):
    """GeoJSON geometry in EPSG:4326 (lon, lat)."""

    type: str
    coordinates: list[Any]


class BoundaryRead(BaseModel):
    geometry: GeoJsonGeometry
    source_file_id: uuid.UUID | None
    area_m2: float = Field(description="Measured in EPSG:32636 (UTM 36N)")
    perimeter_m: float = Field(description="Measured in EPSG:32636 (UTM 36N)")


class FeatureRead(BaseModel):
    id: uuid.UUID
    source_file_id: uuid.UUID
    name: str | None
    description: str | None
    geometry: GeoJsonGeometry


class ProjectLayers(BaseModel):
    boundary: BoundaryRead | None
    features: list[FeatureRead]


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    status: ProjectStatus
    file_count: int
    has_boundary: bool
    created_at: datetime
    updated_at: datetime


class BuildingStatus(str, enum.Enum):
    ok = "ok"  # exactly one Building ID inside
    multiple_ids = "multiple_ids"  # several IDs → probably a missing dividing line
    no_id = "no_id"  # courtyard, gap, or building without a label


class BoundaryPosition(str, enum.Enum):
    inside = "inside"
    crossing = "crossing"
    outside = "outside"


class BuildingRead(BaseModel):
    id: uuid.UUID
    codes: list[str] = Field(description="Building IDs whose label lies inside this polygon")
    status: BuildingStatus
    boundary_position: BoundaryPosition | None = Field(description="None when the project has no boundary")
    area_m2: float = Field(description="Measured in EPSG:32636 (UTM 36N)")
    geometry: GeoJsonGeometry


class OrphanLabelRead(BaseModel):
    """A Building ID label that is not inside any building polygon."""

    id: uuid.UUID
    code: str
    geometry: GeoJsonGeometry


class BuildingSummary(BaseModel):
    total: int
    ok: int
    multiple_ids: int
    no_id: int
    orphan_ids: int
    inside: int | None
    crossing: int | None
    outside: int | None


class BuildingLayer(BaseModel):
    source_file_id: uuid.UUID | None = Field(description="Drawing the buildings were imported from")
    provisional: bool = Field(description="True while the CAD reading rules are not approved (status TBC)")
    summary: BuildingSummary
    buildings: list[BuildingRead]
    orphan_labels: list[OrphanLabelRead]
