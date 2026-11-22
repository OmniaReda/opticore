"""Local file storage for uploaded project files (prototype: disk, not DB/S3)."""

import hashlib
import shutil
import uuid
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from app.config import get_settings
from app.errors import FileTooLargeError
from app.models import FileKind

CHUNK = 1024 * 1024

EXTENSION_KIND: dict[str, FileKind] = {
    ".kml": FileKind.kml,
    ".kmz": FileKind.kmz,
    ".dxf": FileKind.dxf,
    ".dwg": FileKind.dwg,
    ".xlsx": FileKind.survey_xlsx,
    ".pdf": FileKind.other,  # survey maps / plots — stored only
}


def kind_for(filename: str) -> FileKind | None:
    return EXTENSION_KIND.get(Path(filename).suffix.lower())


def project_dir(project_id: uuid.UUID) -> Path:
    return get_settings().storage_dir / "projects" / str(project_id)


def save(src: BinaryIO, project_id: uuid.UUID, file_id: uuid.UUID, filename: str) -> tuple[str, int, str]:
    """Stream src to disk. Returns (relative stored path, size in bytes, sha256 hex).
    Raises FileTooLargeError above the configured limit (nothing is left on disk).

    The stored name is the file id + original extension, so Arabic / unsafe
    original names never reach the filesystem.
    """
    max_mb = get_settings().max_upload_mb
    max_bytes = max_mb * 1024 * 1024
    rel = PurePosixPath("projects", str(project_id), f"{file_id}{Path(filename).suffix.lower()}")
    dest = get_settings().storage_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)

    digest, size = hashlib.sha256(), 0
    try:
        with dest.open("wb") as out:
            while chunk := src.read(CHUNK):
                size += len(chunk)
                if size > max_bytes:
                    raise FileTooLargeError(f"File exceeds {max_mb} MB")
                digest.update(chunk)
                out.write(chunk)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    return str(rel), size, digest.hexdigest()


def absolute_path(stored_path: str) -> Path:
    return get_settings().storage_dir / stored_path


def read_bytes(stored_path: str) -> bytes:
    return (get_settings().storage_dir / stored_path).read_bytes()


def delete_file(stored_path: str) -> None:
    (get_settings().storage_dir / stored_path).unlink(missing_ok=True)


def delete_project_dir(project_id: uuid.UUID) -> None:
    shutil.rmtree(project_dir(project_id), ignore_errors=True)
