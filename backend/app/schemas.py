import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

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
    uploaded_at: datetime


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    status: ProjectStatus
    file_count: int
    created_at: datetime
    updated_at: datetime
