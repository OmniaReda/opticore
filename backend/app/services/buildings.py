"""Building layer of a project: polygons from the latest drawing, review status, boundary position."""

import re
import uuid
from collections import defaultdict

from geoalchemy2.shape import to_shape
from shapely.geometry.base import BaseGeometry
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import geo, rules
from app.models import Building, BuildingLabel, Project
from app.schemas import (
    BoundaryPosition,
    BuildingLayer,
    BuildingRead,
    BuildingStatus,
    BuildingSummary,
    OrphanLabelRead,
)


def natural_key(code: str) -> list[int | str]:
    """'2-10' sorts after '2-9' and '10' after '9'."""
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", code)]


def review_status(codes: list[str]) -> BuildingStatus:
    if not codes:
        return BuildingStatus.no_id
    return BuildingStatus.ok if len(codes) == 1 else BuildingStatus.multiple_ids


def boundary_position(polygon: BaseGeometry, boundary: BaseGeometry | None) -> BoundaryPosition | None:
    if boundary is None:
        return None
    if boundary.contains(polygon):
        return BoundaryPosition.inside
    return BoundaryPosition.crossing if boundary.intersects(polygon) else BoundaryPosition.outside


def _summary(buildings: list[BuildingRead], orphans: int, has_boundary: bool) -> BuildingSummary:
    def by_status(s: BuildingStatus) -> int:
        return sum(1 for b in buildings if b.status == s)

    def by_position(p: BoundaryPosition) -> int | None:
        return sum(1 for b in buildings if b.boundary_position == p) if has_boundary else None

    return BuildingSummary(
        total=len(buildings),
        ok=by_status(BuildingStatus.ok),
        multiple_ids=by_status(BuildingStatus.multiple_ids),
        no_id=by_status(BuildingStatus.no_id),
        orphan_ids=orphans,
        inside=by_position(BoundaryPosition.inside),
        crossing=by_position(BoundaryPosition.crossing),
        outside=by_position(BoundaryPosition.outside),
    )


def building_layer(db: Session, project: Project) -> BuildingLayer:
    boundary = to_shape(project.boundary) if project.boundary is not None else None

    codes: dict[uuid.UUID, list[str]] = defaultdict(list)
    orphans: list[OrphanLabelRead] = []
    for label in db.scalars(select(BuildingLabel).where(BuildingLabel.project_id == project.id)):
        if label.building_id is None:
            orphans.append(
                OrphanLabelRead(id=label.id, code=label.code, geometry=geo.to_geojson(to_shape(label.geometry)))
            )
        else:
            codes[label.building_id].append(label.code)
    orphans.sort(key=lambda o: natural_key(o.code))

    buildings: list[BuildingRead] = []
    source_file_id = None
    for b in db.scalars(select(Building).where(Building.project_id == project.id)):
        source_file_id = b.source_file_id
        polygon = to_shape(b.geometry)
        own = sorted(codes.get(b.id, []), key=natural_key)
        buildings.append(
            BuildingRead(
                id=b.id,
                codes=own,
                status=review_status(own),
                boundary_position=boundary_position(polygon, boundary),
                area_m2=round(geo.area_m2(polygon), 1),
                geometry=geo.to_geojson(polygon),
            )
        )
    # By Building ID; buildings without an ID last.
    buildings.sort(key=lambda b: (0, natural_key(b.codes[0])) if b.codes else (1, []))

    return BuildingLayer(
        source_file_id=source_file_id,
        provisional=rules.cad_layers().provisional,
        summary=_summary(buildings, len(orphans), boundary is not None),
        buildings=buildings,
        orphan_labels=orphans,
    )
