"""Process an uploaded DXF/DWG: building polygons + Building ID labels.

The most recently imported drawing is THE building layer of the project: importing a drawing
replaces the buildings that came from any earlier drawing.
"""
import tempfile
from collections import Counter
from pathlib import Path

from geoalchemy2.shape import from_shape
from pyproj import Transformer
from shapely.ops import transform
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import geo, rules, storage
from app.importers import cad, dwg
from app.models import Building, BuildingLabel, FileKind, Project, ProjectFile

CAD_KINDS = {FileKind.dxf, FileKind.dwg}

_to_storage = Transformer.from_crs(geo.MEASURE_SRID, geo.STORAGE_SRID, always_xy=True).transform


def _read(record: ProjectFile) -> tuple[cad.CadBuildings, str | None]:
    """Extract buildings; DWG is converted to a temporary DXF first. Returns (result, converter)."""
    cad_rules = rules.cad_layers()
    source = storage.absolute_path(record.stored_path)
    if record.kind == FileKind.dxf:
        return cad.extract(cad.read_dxf(source), cad_rules), None
    with tempfile.TemporaryDirectory(prefix="opticore-dwg-") as tmp:
        dxf_path = Path(tmp) / "converted.dxf"
        converter = dwg.convert(source, dxf_path)
        return cad.extract(cad.read_dxf(dxf_path), cad_rules), converter


def import_cad(db: Session, record: ProjectFile) -> str:
    """Import into the DB session (not committed). Returns the note shown to the user."""
    result, converter = _read(record)

    # Lock the project row: two drawings processed at once must not mix their buildings.
    db.get_one(Project, record.project_id, with_for_update=True)
    previous = db.scalars(select(Building.source_file_id).where(Building.project_id == record.project_id)
                          .distinct()).all()
    db.execute(delete(BuildingLabel).where(BuildingLabel.project_id == record.project_id))
    db.execute(delete(Building).where(Building.project_id == record.project_id))

    buildings = [Building(project_id=record.project_id, source_file_id=record.id,
                          geometry=from_shape(transform(_to_storage, p), srid=geo.STORAGE_SRID))
                 for p in result.polygons]
    db.add_all(buildings)
    db.flush()  # assign building ids for the labels
    db.add_all(BuildingLabel(project_id=record.project_id, source_file_id=record.id, code=lab.building_id,
                             building_id=None if lab.building_index is None else buildings[lab.building_index].id,
                             geometry=from_shape(transform(_to_storage, lab.point), srid=geo.STORAGE_SRID))
               for lab in result.labels)

    per_building = Counter(lab.building_index for lab in result.labels if lab.building_index is not None)
    one = sum(1 for n in per_building.values() if n == 1)
    several = sum(1 for n in per_building.values() if n > 1)
    orphans = sum(1 for lab in result.labels if lab.building_index is None)
    duplicates = sum(1 for n in Counter(lab.building_id for lab in result.labels).values() if n > 1)

    parts = [f"Layers: {result.profile.name}",
             f"{len(result.polygons)} buildings: {one} with 1 ID, {several} with several IDs, "
             f"{len(result.polygons) - len(per_building)} without ID",
             f"{orphans} IDs outside any building"]
    if duplicates:
        parts.append(f"{duplicates} IDs used more than once")
    if result.unreadable_labels:
        parts.append(f"{result.unreadable_labels} unreadable ID labels")
    if any(f != record.id for f in previous):
        parts.append("replaced buildings from a previous drawing")
    if converter:
        parts.append(f"converted with {converter}")
    return " · ".join(parts)
