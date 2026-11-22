"""Shared FastAPI dependencies."""

import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Project, ProjectFile
from app.services import files, projects

DbSession = Annotated[Session, Depends(get_db)]


def get_project(project_id: uuid.UUID, db: DbSession) -> Project:
    """The project from the `{project_id}` path parameter, or 404."""
    return projects.get(db, project_id)


ProjectDep = Annotated[Project, Depends(get_project)]


def get_project_file(file_id: uuid.UUID, project: ProjectDep, db: DbSession) -> ProjectFile:
    """The file from the `{file_id}` path parameter; 404 if it belongs to another project."""
    return files.get(db, project, file_id)


ProjectFileDep = Annotated[ProjectFile, Depends(get_project_file)]
