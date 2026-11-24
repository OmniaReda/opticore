"""Process an uploaded KML/KMZ: Polygon placemarks → project boundary, everything else → project features.

A file with no polygon (e.g. exported from AutoCAD, where the boundary is an open polyline) gets its boundary
from its lines: they are joined end to end, and a line whose ends almost meet is closed into a polygon.
"""

from collections import Counter

from geoalchemy2.shape import from_shape
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.ops import linemerge, unary_union
from shapely.validation import explain_validity
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app import geo, storage
from app.config import get_settings
from app.importers import kml
from app.models import FileKind, Project, ProjectFeature, ProjectFile

KML_KINDS = {FileKind.kml, FileKind.kmz}


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _close_lines(lines: list[kml.Placemark]) -> tuple[Polygon, float] | None:
    """The boundary drawn as lines: all the file's lines must join into ONE line whose ends meet (within the
    gap tolerance). Anything else (several shapes, building outlines, loose lines) is not a boundary."""
    if not lines:
        return None
    merged = linemerge([p.geometry for p in lines])
    if not isinstance(merged, LineString) or len(merged.coords) < 4:
        return None
    start, end = merged.coords[0], merged.coords[-1]
    gap = geo.length_m(LineString([start, end])) if start != end else 0.0
    if gap > get_settings().kml_close_gap_m:
        return None
    polygon = Polygon(merged.coords)  # shapely closes the ring
    if not polygon.is_valid or geo.area_m2(polygon) <= 0:
        return None
    return polygon, gap


def import_kml(db: Session, record: ProjectFile) -> str:
    """Import into the DB session (not committed). Returns the note shown to the user.

    Raises kml.KmlError for problems the user must fix in the file.
    """
    content = kml.load(storage.read_bytes(record.stored_path), is_kmz=record.kind == FileKind.kmz)
    polygons = [p for p in content.placemarks if p.geometry.geom_type == "Polygon"]
    others = [p for p in content.placemarks if p.geometry.geom_type != "Polygon"]
    if not content.placemarks:
        raise kml.KmlError("No geometry found in this file")
    closed_note = None
    if not polygons:
        lines = [p for p in others if p.geometry.geom_type == "LineString"]
        closed = _close_lines(lines)
        if closed:
            polygon, gap = closed
            polygons = [kml.Placemark(lines[0].name, lines[0].description, polygon)]
            others = [p for p in others if p.geometry.geom_type != "LineString"]
            how = f"closed a {gap:.1f} m gap" if gap else "already closed"
            closed_note = f"boundary built from {_plural(len(lines), 'line')} ({how})"

    for p in polygons:
        if not p.geometry.is_valid:
            raise kml.KmlError(f"Boundary polygon '{p.name or '?'}' is invalid: {explain_validity(p.geometry)}")

    # Re-processing replaces what this file imported before.
    db.execute(delete(ProjectFeature).where(ProjectFeature.source_file_id == record.id))
    db.add_all(
        ProjectFeature(
            project_id=record.project_id,
            source_file_id=record.id,
            name=p.name,
            description=p.description,
            geometry=from_shape(p.geometry, srid=geo.STORAGE_SRID),
        )
        for p in others
    )

    parts: list[str] = []
    if polygons:
        merged = unary_union([p.geometry for p in polygons])
        boundary = merged if isinstance(merged, MultiPolygon) else MultiPolygon([merged])
        project = db.get_one(Project, record.project_id)
        replaced = project.boundary is not None and project.boundary_file_id != record.id
        project.boundary = from_shape(boundary, srid=geo.STORAGE_SRID)
        project.boundary_file_id = record.id
        parts.append(
            f"Boundary: {_plural(len(polygons), 'polygon')}, {geo.area_m2(boundary) / 10_000:.1f} ha, "
            f"perimeter {geo.length_m(boundary) / 1000:.2f} km" + (" (replaced previous boundary)" if replaced else "")
        )
        if closed_note:
            parts.append(closed_note)
    else:
        parts.append(
            "No boundary polygon in this file, and its lines do not close into one (project boundary unchanged)"
        )

    counts = Counter(p.geometry.geom_type for p in others)
    if counts["Point"]:
        parts.append(_plural(counts["Point"], "point"))
    if counts["LineString"]:
        parts.append(_plural(counts["LineString"], "line"))
    if content.skipped:
        parts.append(f"{content.skipped} empty/degenerate geometries skipped")
    return " · ".join(parts)
