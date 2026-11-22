"""Background processing of uploaded files: picks the importer for the file kind and records the outcome."""
import logging
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.db import get_sessionmaker
from app.importers import FileContentError
from app.models import FileKind, FileStatus, ProjectFile
from app.services import cad_import, kml_import

log = logging.getLogger(__name__)

Importer = Callable[[Session, ProjectFile], str]

IMPORTERS: dict[FileKind, Importer] = {
    **{kind: kml_import.import_kml for kind in kml_import.KML_KINDS},
    **{kind: cad_import.import_cad for kind in cad_import.CAD_KINDS},
}


def has_importer(kind: FileKind) -> bool:
    return kind in IMPORTERS


def process_file(file_id: uuid.UUID) -> None:
    """Background job: import one file and record status / note / error on it."""
    with get_sessionmaker()() as db:
        record = db.get(ProjectFile, file_id)
        if record is None or record.kind not in IMPORTERS:
            return
        try:
            note = IMPORTERS[record.kind](db, record)
            record.status, record.error, record.note = FileStatus.processed, None, note
            db.commit()
        except Exception as e:  # noqa: BLE001 — any failure must end up visible on the file
            db.rollback()
            if isinstance(e, FileContentError):
                message = str(e)
            else:
                log.exception("Import failed for file %s", file_id)
                message = f"Unexpected error while importing: {e}"
            record = db.get_one(ProjectFile, file_id)
            record.status, record.error, record.note = FileStatus.failed, message, None
            db.commit()
