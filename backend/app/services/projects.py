"""Projects: create / read / update / delete, with the number of uploaded files."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import storage
from app.errors import NotFoundError
from app.models import Project, ProjectFile
from app.schemas import ProjectCreate, ProjectRead, ProjectUpdate


def get(db: Session, project_id: uuid.UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project not found")
    return project


def to_read(project: Project, file_count: int) -> ProjectRead:
    return ProjectRead(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        file_count=file_count,
        has_boundary=project.boundary is not None,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _file_count(db: Session, project_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).where(ProjectFile.project_id == project_id)) or 0


def read(db: Session, project: Project) -> ProjectRead:
    return to_read(project, _file_count(db, project.id))


def list_all(db: Session) -> list[ProjectRead]:
    """All projects, most recently updated first."""
    counts = select(ProjectFile.project_id, func.count().label("n")).group_by(ProjectFile.project_id).subquery()
    rows = db.execute(
        select(Project, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.project_id == Project.id)
        .order_by(Project.updated_at.desc())
    ).tuples()
    return [to_read(project, count) for project, count in rows]


def create(db: Session, body: ProjectCreate) -> ProjectRead:
    project = Project(name=body.name, description=body.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return to_read(project, 0)


def update(db: Session, project: Project, body: ProjectUpdate) -> ProjectRead:
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return read(db, project)


def delete(db: Session, project: Project) -> None:
    project_id = project.id
    db.delete(project)
    db.commit()
    storage.delete_project_dir(project_id)


def touch(project: Project) -> None:
    """Bump updated_at so the project list reflects file activity (committed by the caller)."""
    project.updated_at = func.now()  # SQL expression, evaluated by the DB on flush
