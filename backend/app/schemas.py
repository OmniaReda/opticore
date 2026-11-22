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
