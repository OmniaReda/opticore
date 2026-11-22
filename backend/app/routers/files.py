import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import storage
from app.config import get_settings
from app.db import get_db
from app.models import FileStatus, Project, ProjectFile
from app.routers.projects import get_project_or_404
from app.schemas import ProjectFileRead
from app.services import kml_import

router = APIRouter(prefix="/projects/{project_id}/files", tags=["files"])

Db = Annotated[Session, Depends(get_db)]


def _get_file_or_404(db: Session, project_id: uuid.UUID, file_id: uuid.UUID) -> ProjectFile:
    record = db.get(ProjectFile, file_id)
    if record is None or record.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    return record


def _schedule_processing(record: ProjectFile, tasks: BackgroundTasks) -> None:
    """Queue automatic processing for file kinds that have an importer (KML/KMZ for now)."""
    if record.kind in kml_import.KML_KINDS:
        record.status, record.error, record.note = FileStatus.processing, None, None
        tasks.add_task(kml_import.process_file, record.id)


@router.get("", response_model=list[ProjectFileRead])
def list_files(project_id: uuid.UUID, db: Db) -> list[ProjectFile]:
    get_project_or_404(db, project_id)
    return list(db.scalars(
        select(ProjectFile).where(ProjectFile.project_id == project_id).order_by(ProjectFile.uploaded_at)
    ))


@router.post("", response_model=ProjectFileRead, status_code=status.HTTP_201_CREATED)
def upload_file(project_id: uuid.UUID, file: UploadFile, db: Db, tasks: BackgroundTasks) -> ProjectFile:
    project = get_project_or_404(db, project_id)
    filename = (file.filename or "").strip()
    kind = storage.kind_for(filename)
    if kind is None:
        allowed = ", ".join(sorted(storage.EXTENSION_KIND))
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Unsupported file type. Allowed: {allowed}")

    file_id = uuid.uuid4()
    try:
        stored_path, size, sha256 = storage.save(file.file, project_id, file_id, filename)
    except storage.FileTooLarge:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            f"File exceeds {get_settings().max_upload_mb} MB") from None
    if size == 0:
        storage.delete_file(stored_path)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is empty")

    record = ProjectFile(id=file_id, project_id=project_id, kind=kind, original_filename=filename[:255],
                         stored_path=stored_path, size_bytes=size, sha256=sha256, status=FileStatus.uploaded)
    db.add(record)
    _schedule_processing(record, tasks)
    _touch(project)
    try:
        db.commit()
    except Exception:
        storage.delete_file(stored_path)
        raise
    db.refresh(record)
    return record


@router.post("/{file_id}/process", response_model=ProjectFileRead, status_code=status.HTTP_202_ACCEPTED)
def process_file(project_id: uuid.UUID, file_id: uuid.UUID, db: Db, tasks: BackgroundTasks) -> ProjectFile:
    """Re-run processing of a file (e.g. after a failure or an importer update)."""
    get_project_or_404(db, project_id)
    record = _get_file_or_404(db, project_id, file_id)
    if record.kind not in kml_import.KML_KINDS:
        raise HTTPException(status.HTTP_409_CONFLICT, f"No importer for '{record.kind.value}' files yet")
    if record.status == FileStatus.processing:
        raise HTTPException(status.HTTP_409_CONFLICT, "File is already being processed")
    _schedule_processing(record, tasks)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(project_id: uuid.UUID, file_id: uuid.UUID, db: Db) -> None:
    project = get_project_or_404(db, project_id)
    record = _get_file_or_404(db, project_id, file_id)
    stored_path = record.stored_path
    if project.boundary_file_id == record.id:
        # The boundary came from this file → it goes with it. (Features are removed by FK cascade.)
        project.boundary, project.boundary_file_id = None, None
    db.delete(record)
    _touch(project)
    db.commit()
    storage.delete_file(stored_path)


def _touch(project: Project) -> None:
    # Bump updated_at so the project list reflects file activity.
    project.updated_at = func.now()
