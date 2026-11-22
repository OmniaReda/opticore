from fastapi import APIRouter, status

from app.api.deps import DbSession, ProjectDep
from app.schemas import ProjectCreate, ProjectRead, ProjectUpdate
from app.services import projects

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects(db: DbSession) -> list[ProjectRead]:
    return projects.list_all(db)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, db: DbSession) -> ProjectRead:
    return projects.create(db, body)


@router.get("/{project_id}")
def get_project(project: ProjectDep, db: DbSession) -> ProjectRead:
    return projects.read(db, project)


@router.patch("/{project_id}")
def update_project(project: ProjectDep, body: ProjectUpdate, db: DbSession) -> ProjectRead:
    return projects.update(db, project, body)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project: ProjectDep, db: DbSession) -> None:
    projects.delete(db, project)
