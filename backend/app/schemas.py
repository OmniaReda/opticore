import enum
import uuid
from datetime import date, datetime
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models import FileKind, FileStatus, ProjectStatus

ProjectName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ProjectCreate(BaseModel):
    name: ProjectName
    description: str | None = None


class ProjectUpdate(BaseModel):
    """Partial update: only fields that are sent are changed. name / status may be omitted, not null."""

    name: ProjectName | None = None
    description: str | None = None
    status: ProjectStatus | None = None

    @model_validator(mode="after")
    def _no_null_required_fields(self) -> Self:
        for field in ("name", "status"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


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


class BuildingStatus(enum.StrEnum):
    ok = "ok"  # exactly one Building ID inside
    multiple_ids = "multiple_ids"  # several IDs → probably a missing dividing line
    no_id = "no_id"  # courtyard, gap, or building without a label


class BoundaryPosition(enum.StrEnum):
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


class SurveyRecordRead(BaseModel):
    """One survey Excel row (personal data excluded)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    row_number: int = Field(description="Row number in the Excel sheet")
    code: str = Field(description="Building ID")
    in_drawing: bool = Field(default=False, description="The Building ID exists on the imported drawing")
    visit_date: date | None
    street_name: str | None
    building_name: str | None
    building_number: str | None
    latitude: float | None
    longitude: float | None
    floors: int | None
    users_per_floor: int | None
    gf_users: int | None
    total_users: int | None
    hp_te_required: int | None
    comments: str | None
    sub_category: str | None
    final_category: str | None
    placemark_id: str | None
    entrance_length_m: float | None
    entrance_marked: str | None
    msan_note: str | None
    void_core: str | None
    hp_count: str | None
    qty_home_pass: int | None
    te_comment: str | None


class SurveySummary(BaseModel):
    rows: int
    in_drawing: int = Field(description="Rows whose Building ID is on the drawing")
    not_in_drawing: int = Field(description="Rows whose Building ID is not on the drawing")
    drawing_ids_without_survey: int = Field(description="Building IDs on the drawing with no survey row")
    missing_gps: int = Field(description="Rows without valid GPS")
    total_users: int = Field(description="Sum of Total Users")


class SurveyLayer(BaseModel):
    source_file_id: uuid.UUID | None = Field(description="Survey file the rows were imported from")
    provisional: bool = Field(description="True while the survey column rules are not approved (status TBC)")
    has_drawing: bool = Field(description="False until a drawing with Building IDs is imported")
    summary: SurveySummary
    records: list[SurveyRecordRead]
    not_in_drawing: list[str] = Field(description="Survey Building IDs missing on the drawing")
    drawing_ids_without_survey: list[str] = Field(description="Drawing Building IDs missing in the survey")
