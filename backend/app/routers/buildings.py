import re
import uuid
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import geo, rules
from app.db import get_db
from app.models import Building, BuildingLabel
from app.routers.projects import get_project_or_404
from app.schemas import (
    BoundaryPosition,
    BuildingLayer,
    BuildingRead,
    BuildingStatus,
    BuildingSummary,
    GeoJsonGeometry,
    OrphanLabelRead,
)

router = APIRouter(prefix="/projects/{project_id}/buildings", tags=["buildings"])

Db = Annotated[Session, Depends(get_db)]


def _geojson(geom: BaseGeometry) -> GeoJsonGeometry:
    return GeoJsonGeometry.model_validate(mapping(geom))


def natural_key(code: str) -> list[int | str]:
    """'2-10' sorts after '2-9' and '10' after '9'."""
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", code)]


def _status(codes: list[str]) -> BuildingStatus:
    if not codes:
        return BuildingStatus.no_id
    return BuildingStatus.ok if len(codes) == 1 else BuildingStatus.multiple_ids


def _position(polygon: BaseGeometry, boundary: BaseGeometry | None) -> BoundaryPosition | None:
    if boundary is None:
        return None
    if boundary.contains(polygon):
        return BoundaryPosition.inside
    return BoundaryPosition.crossing if boundary.intersects(polygon) else BoundaryPosition.outside


@router.get("", response_model=BuildingLayer)
def get_buildings(project_id: uuid.UUID, db: Db) -> BuildingLayer:
    """Buildings from the latest imported drawing, with review status (EPSG:4326 GeoJSON)."""
    project = get_project_or_404(db, project_id)
    boundary = to_shape(project.boundary) if project.boundary is not None else None

    codes: dict[uuid.UUID, list[str]] = defaultdict(list)
    orphans: list[OrphanLabelRead] = []
    for label in db.scalars(select(BuildingLabel).where(BuildingLabel.project_id == project_id)):
        if label.building_id is None:
            orphans.append(OrphanLabelRead(id=label.id, code=label.code, geometry=_geojson(to_shape(label.geometry))))
        else:
            codes[label.building_id].append(label.code)
    orphans.sort(key=lambda o: natural_key(o.code))

    buildings: list[BuildingRead] = []
    source_file_id = None
    for b in db.scalars(select(Building).where(Building.project_id == project_id)):
        source_file_id = b.source_file_id
        polygon = to_shape(b.geometry)
        own = sorted(codes.get(b.id, []), key=natural_key)
        buildings.append(BuildingRead(id=b.id, codes=own, status=_status(own),
                                      boundary_position=_position(polygon, boundary),
                                      area_m2=round(geo.area_m2(polygon), 1), geometry=_geojson(polygon)))
    buildings.sort(key=lambda b: (0, natural_key(b.codes[0])) if b.codes else (1, []))

    def count_status(s: BuildingStatus) -> int:
        return sum(1 for b in buildings if b.status == s)

    def count_position(p: BoundaryPosition) -> int | None:
        return None if boundary is None else sum(1 for b in buildings if b.boundary_position == p)

    summary = BuildingSummary(total=len(buildings), ok=count_status(BuildingStatus.ok),
                              multiple_ids=count_status(BuildingStatus.multiple_ids),
                              no_id=count_status(BuildingStatus.no_id), orphan_ids=len(orphans),
                              inside=count_position(BoundaryPosition.inside),
                              crossing=count_position(BoundaryPosition.crossing),
                              outside=count_position(BoundaryPosition.outside))
    return BuildingLayer(source_file_id=source_file_id, provisional=rules.cad_layers().provisional,
                         summary=summary, buildings=buildings, orphan_labels=orphans)
