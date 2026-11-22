import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import storage
from app.db import get_db
from app.models import Project, ProjectFile
from app.schemas import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])

Db = Annotated[Session, Depends(get_db)]


def get_project_or_404(db: Session, project_id: uuid.UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


def _file_count(db: Session, project_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).where(ProjectFile.project_id == project_id)) or 0


def _read(project: Project, file_count: int) -> ProjectRead:
    return ProjectRead.model_validate({**project.__dict__, "file_count": file_count,
                                       "has_boundary": project.boundary is not None})


@router.get("", response_model=list[ProjectRead])
def list_projects(db: Db) -> list[ProjectRead]:
    counts = (
        select(ProjectFile.project_id, func.count().label("n"))
        .group_by(ProjectFile.project_id)
        .subquery()
    )
    rows = db.execute(
        select(Project, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.project_id == Project.id)
        .order_by(Project.updated_at.desc())
    ).all()
    return [_read(p, n) for p, n in rows]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, db: Db) -> ProjectRead:
    project = Project(name=body.name, description=body.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return _read(project, 0)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: uuid.UUID, db: Db) -> ProjectRead:
    project = get_project_or_404(db, project_id)
    return _read(project, _file_count(db, project_id))


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(project_id: uuid.UUID, body: ProjectUpdate, db: Db) -> ProjectRead:
    project = get_project_or_404(db, project_id)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("name", "") is None or changes.get("status", "") is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "name and status cannot be null")
    for field, value in changes.items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return _read(project, _file_count(db, project_id))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: uuid.UUID, db: Db) -> None:
    project = get_project_or_404(db, project_id)
    db.delete(project)
    db.commit()
    storage.delete_project_dir(project_id)
