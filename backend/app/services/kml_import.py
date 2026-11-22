"""Process an uploaded KML/KMZ: Polygon placemarks → project boundary, everything else → project features."""
import logging
import uuid
from collections import Counter

from geoalchemy2.shape import from_shape
from shapely.geometry import MultiPolygon
from shapely.ops import unary_union
from shapely.validation import explain_validity
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app import geo, storage
from app.db import get_sessionmaker
from app.importers import kml
from app.models import FileKind, FileStatus, Project, ProjectFeature, ProjectFile

log = logging.getLogger(__name__)

KML_KINDS = {FileKind.kml, FileKind.kmz}


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def import_kml(db: Session, record: ProjectFile) -> str:
    """Import into the DB session (not committed). Returns the note shown to the user.

    Raises kml.KmlError for problems the user must fix in the file.
    """
    content = kml.load(storage.read_bytes(record.stored_path), is_kmz=record.kind == FileKind.kmz)
    polygons = [p for p in content.placemarks if p.geometry.geom_type == "Polygon"]
    others = [p for p in content.placemarks if p.geometry.geom_type != "Polygon"]
    if not content.placemarks:
        raise kml.KmlError("No geometry found in this file")

    for p in polygons:
        if not p.geometry.is_valid:
            raise kml.KmlError(f"Boundary polygon '{p.name or '?'}' is invalid: {explain_validity(p.geometry)}")

    # Re-processing replaces what this file imported before.
    db.execute(delete(ProjectFeature).where(ProjectFeature.source_file_id == record.id))
    db.add_all(ProjectFeature(project_id=record.project_id, source_file_id=record.id, name=p.name,
                              description=p.description, geometry=from_shape(p.geometry, srid=geo.STORAGE_SRID))
               for p in others)

    parts: list[str] = []
    if polygons:
        merged = unary_union([p.geometry for p in polygons])
        boundary = merged if isinstance(merged, MultiPolygon) else MultiPolygon([merged])
        project = db.get_one(Project, record.project_id)
        replaced = project.boundary is not None and project.boundary_file_id != record.id
        project.boundary = from_shape(boundary, srid=geo.STORAGE_SRID)
        project.boundary_file_id = record.id
        parts.append(f"Boundary: {_plural(len(polygons), 'polygon')}, {geo.area_m2(boundary) / 10_000:.1f} ha, "
                     f"perimeter {geo.length_m(boundary) / 1000:.2f} km"
                     + (" (replaced previous boundary)" if replaced else ""))
    else:
        parts.append("No boundary polygon in this file (project boundary unchanged)")

    counts = Counter(p.geometry.geom_type for p in others)
    if counts["Point"]:
        parts.append(_plural(counts["Point"], "point"))
    if counts["LineString"]:
        parts.append(_plural(counts["LineString"], "line"))
    if content.skipped:
        parts.append(f"{content.skipped} empty/degenerate geometries skipped")
    return " · ".join(parts)


def process_file(file_id: uuid.UUID) -> None:
    """Background job: process one uploaded KML/KMZ and record the outcome on the file."""
    with get_sessionmaker()() as db:
        record = db.get(ProjectFile, file_id)
        if record is None or record.kind not in KML_KINDS:
            return
        try:
            note = import_kml(db, record)
            record.status, record.error, record.note = FileStatus.processed, None, note
            db.commit()
        except Exception as e:  # noqa: BLE001 — any failure must end up visible on the file
            db.rollback()
            if not isinstance(e, kml.KmlError):
                log.exception("KML import failed for file %s", file_id)
            record = db.get_one(ProjectFile, file_id)
            message = str(e) if isinstance(e, kml.KmlError) else f"Unexpected error while importing: {e}"
            record.status, record.error, record.note = FileStatus.failed, message, None
            db.commit()
