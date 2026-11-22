from fastapi import APIRouter, BackgroundTasks, UploadFile, status

from app.api.deps import DbSession, ProjectDep, ProjectFileDep
from app.schemas import ProjectFileRead
from app.services import files

router = APIRouter(prefix="/projects/{project_id}/files", tags=["files"])


@router.get("")
def list_files(project: ProjectDep, db: DbSession) -> list[ProjectFileRead]:
    return [ProjectFileRead.model_validate(f) for f in files.list_for(db, project)]


@router.post("", status_code=status.HTTP_201_CREATED)
def upload_file(project: ProjectDep, file: UploadFile, db: DbSession, tasks: BackgroundTasks) -> ProjectFileRead:
    """Store the file; KML/KMZ/DXF/DWG are then imported in the background (status `processing`)."""
    return ProjectFileRead.model_validate(files.upload(db, project, file.filename or "", file.file, tasks))


@router.post("/{file_id}/process", status_code=status.HTTP_202_ACCEPTED)
def process_file(record: ProjectFileDep, db: DbSession, tasks: BackgroundTasks) -> ProjectFileRead:
    """Re-run processing of a file (e.g. after a failure or an importer update)."""
    return ProjectFileRead.model_validate(files.reprocess(db, record, tasks))


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(project: ProjectDep, record: ProjectFileDep, db: DbSession) -> None:
    files.delete(db, project, record)
