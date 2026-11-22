"""Uploaded project files: store on disk + record in the DB, schedule background processing."""

import uuid
from typing import BinaryIO

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storage
from app.errors import ConflictError, EmptyFileError, NotFoundError, UnsupportedFileTypeError
from app.models import FileStatus, Project, ProjectFile
from app.services import processing, projects


def get(db: Session, project: Project, file_id: uuid.UUID) -> ProjectFile:
    record = db.get(ProjectFile, file_id)
    if record is None or record.project_id != project.id:
        raise NotFoundError("File not found")
    return record


def list_for(db: Session, project: Project) -> list[ProjectFile]:
    return list(
        db.scalars(select(ProjectFile).where(ProjectFile.project_id == project.id).order_by(ProjectFile.uploaded_at))
    )


def _schedule_processing(record: ProjectFile, tasks: BackgroundTasks) -> None:
    """Queue automatic processing for file kinds that have an importer."""
    if processing.has_importer(record.kind):
        record.status, record.error, record.note = FileStatus.processing, None, None
        tasks.add_task(processing.process_file, record.id)


def upload(db: Session, project: Project, filename: str, content: BinaryIO, tasks: BackgroundTasks) -> ProjectFile:
    filename = filename.strip()
    kind = storage.kind_for(filename)
    if kind is None:
        allowed = ", ".join(sorted(storage.EXTENSION_KIND))
        raise UnsupportedFileTypeError(f"Unsupported file type. Allowed: {allowed}")

    file_id = uuid.uuid4()
    stored_path, size, sha256 = storage.save(content, project.id, file_id, filename)
    if size == 0:
        storage.delete_file(stored_path)
        raise EmptyFileError("File is empty")

    record = ProjectFile(
        id=file_id,
        project_id=project.id,
        kind=kind,
        original_filename=filename[:255],
        stored_path=stored_path,
        size_bytes=size,
        sha256=sha256,
        status=FileStatus.uploaded,
    )
    db.add(record)
    _schedule_processing(record, tasks)
    projects.touch(project)
    try:
        db.commit()
    except Exception:
        storage.delete_file(stored_path)
        raise
    db.refresh(record)
    return record


def reprocess(db: Session, record: ProjectFile, tasks: BackgroundTasks) -> ProjectFile:
    """Re-run processing (e.g. after a failure or an importer update)."""
    if not processing.has_importer(record.kind):
        raise ConflictError(f"No importer for '{record.kind.value}' files yet")
    if record.status == FileStatus.processing:
        raise ConflictError("File is already being processed")
    _schedule_processing(record, tasks)
    db.commit()
    db.refresh(record)
    return record


def delete(db: Session, project: Project, record: ProjectFile) -> None:
    stored_path = record.stored_path
    if project.boundary_file_id == record.id:
        # The boundary came from this file → it goes with it. (Features/buildings are removed by FK cascade.)
        project.boundary, project.boundary_file_id = None, None
    db.delete(record)
    projects.touch(project)
    db.commit()
    storage.delete_file(stored_path)
