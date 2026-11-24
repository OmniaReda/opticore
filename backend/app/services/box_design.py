"""Network Box placement for a project.

Where the users are, in order of preference:
- drawing + survey: users of a building = sum of the survey's Total Users over its Building IDs;
- no drawing: the filled Streets & numbers Excel, where each OpenStreetMap house number is a point with
  the Total Users the field team wrote next to it.
Buildings / addresses without users are not served and are listed in the summary.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from geoalchemy2.shape import to_shape
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import geo, rules
from app.design import box_placement as bp
from app.errors import ConflictError, InvalidInputError
from app.models import AddressPoint, Project, SurveyRecord
from app.schemas import (
    BoundaryPosition,
    BoxDesign,
    BoxDesignDefaults,
    BoxDesignRequest,
    BoxDesignSummary,
    BoxTypeCount,
    BoxTypeIn,
    BuildingLayer,
    DesignSource,
    GeoJsonGeometry,
    NetworkBoxRead,
    ServedBuilding,
)
from app.services import addresses, survey_template
from app.services import buildings as buildings_service
from app.services.buildings import natural_key

_to_wgs = Transformer.from_crs(geo.MEASURE_SRID, geo.STORAGE_SRID, always_xy=True).transform

METHOD = (
    "Prototype method (not a Design Team rule): nearby buildings are grouped while their users fit in the "
    "largest box and every building stays within the drop limit; the box goes on the group's building closest "
    "to its users and is the smallest type that holds them. Distances are straight lines, not along streets."
)


def defaults() -> BoxDesignDefaults:
    cfg = rules.network_boxes()
    return BoxDesignDefaults(
        provisional=cfg.provisional,
        source=cfg.source,
        box_types=[BoxTypeIn(name=t.name, capacity=t.capacity) for t in cfg.box_types],
        max_drop_m=cfg.max_drop_m,
        spare_percent=cfg.spare_percent,
    )


@dataclass
class _Input:
    source: DesignSource
    demands: list[bp.Demand] = field(default_factory=list)
    codes_of: dict[str, list[str]] = field(default_factory=dict)
    without_users: list[str] = field(default_factory=list)
    without_id: int = 0
    outside: int = 0


def _from_buildings(layer: BuildingLayer, totals: dict[str, int], include_outside: bool) -> _Input:
    """Drawing + survey: users of a building = sum of Total Users over its Building IDs."""
    data = _Input(DesignSource.buildings)
    for b in layer.buildings:
        if b.boundary_position == BoundaryPosition.outside and not include_outside:
            data.outside += 1
            continue
        if not b.codes:
            data.without_id += 1
            continue
        users = sum(totals[c] for c in b.codes if c in totals)
        if users <= 0:
            data.without_users.extend(b.codes)
            continue
        key = str(b.id)
        data.codes_of[key] = b.codes
        data.demands.append(bp.Demand(key, geo.to_measure_crs(shape(b.geometry.model_dump())), users))
    return data


def _from_addresses(project: Project, points: list[AddressPoint], include_outside: bool) -> _Input:
    """No drawing: the filled Streets & numbers Excel. Each house number is a point with its Total Users."""
    data = _Input(DesignSource.addresses)
    boundary = to_shape(project.boundary) if project.boundary is not None else None
    for p in points:
        point = to_shape(p.geometry)
        if boundary is not None and not include_outside and not boundary.covers(point):
            data.outside += 1
            continue
        if not p.total_users:
            data.without_users.append(addresses.label(p))
            continue
        key = str(p.id)
        data.codes_of[key] = [addresses.label(p)]
        data.demands.append(bp.Demand(key, geo.to_measure_crs(point), p.total_users))
    return data


def _input(db: Session, project: Project, include_outside: bool) -> _Input:
    layer = buildings_service.building_layer(db, project)
    totals = {
        r.code: r.total_users
        for r in db.scalars(select(SurveyRecord).where(SurveyRecord.project_id == project.id))
        if r.total_users is not None
    }
    if layer.buildings and totals:
        return _from_buildings(layer, totals, include_outside)
    points = addresses.points(db, project)
    if any(p.total_users for p in points):
        return _from_addresses(project, points, include_outside)
    if layer.buildings:
        raise ConflictError("Upload the survey Excel first: boxes are sized by each building's Total Users.")
    raise ConflictError(
        "Upload the drawing (DXF/DWG) and the survey Excel, or (without a drawing) the Streets & numbers "
        "Excel with Total Users filled in."
    )


def design(db: Session, project: Project, request: BoxDesignRequest) -> BoxDesign:
    data = _input(db, project, request.include_outside)
    demands, codes_of = data.demands, data.codes_of

    types = [bp.BoxType(t.name, t.capacity) for t in request.box_types]
    try:
        placed = bp.place(demands, types, request.max_drop_m, request.spare_percent)
    except bp.PlacementError as e:
        raise InvalidInputError(str(e)) from None

    centre = {d.key: d.outline.representative_point() for d in demands}
    placed.sort(key=lambda p: natural_key(codes_of[p.host][0]))
    boxes = [
        NetworkBoxRead(
            label=f"NB-{i:03d}",
            box_type=p.box_type.name,
            capacity=p.box_type.capacity,
            usable=p.usable,
            users=p.users,
            host_codes=codes_of[p.host],
            dedicated=p.dedicated,
            geometry=_wgs(p.location),
            served=[
                ServedBuilding(
                    codes=codes_of[s.key], users=s.users, distance_m=s.distance_m, geometry=_wgs(centre[s.key])
                )
                for s in sorted(p.served, key=lambda s: natural_key(codes_of[s.key][0]))
            ],
        )
        for i, p in enumerate(placed, start=1)
    ]

    count = Counter(box.box_type for box in boxes)
    users_by_type = Counter[str]()
    for box in boxes:
        users_by_type[box.box_type] += box.users
    drops = [s.distance_m for box in boxes for s in box.served]
    summary = BoxDesignSummary(
        boxes=len(boxes),
        by_type=[
            BoxTypeCount(box_type=t.name, capacity=t.capacity, count=count[t.name], users=users_by_type[t.name])
            for t in sorted(request.box_types, key=lambda t: t.capacity)
        ],
        users=sum(box.users for box in boxes),
        buildings_served=len(demands),
        longest_drop_m=max(drops) if drops else None,
        without_users=sorted(data.without_users, key=natural_key),
        without_id=data.without_id,
        outside_skipped=data.outside,
    )
    return BoxDesign(provisional=True, source=data.source, request=request, summary=summary, boxes=boxes)


def _wgs(point: Point) -> GeoJsonGeometry:
    lonlat = transform(_to_wgs, point)
    return geo.to_geojson(Point(round(lonlat.x, 7), round(lonlat.y, 7)))


def _sheet(ws: Worksheet, titles: list[str], widths: list[int]) -> None:
    ws.append(titles)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = "A2"


def to_xlsx(project: Project, result: BoxDesign) -> bytes:
    """Sheets: Boxes, Buildings (which box serves each building), Not served, Settings."""
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Boxes"
    _sheet(
        ws,
        [
            "Box",
            "Box type",
            "Capacity",
            "Usable (after spare)",
            "Users",
            "Free",
            "On" if result.source == DesignSource.addresses else "On Building ID",
            "Served",
            "Addresses served" if result.source == DesignSource.addresses else "Building IDs served",
            "Longest drop (m)",
            "Latitude",
            "Longitude",
        ],
        [10, 18, 10, 12, 8, 8, 16, 10, 40, 12, 12, 12],
    )
    for b in result.boxes:
        lon, lat = b.geometry.coordinates
        ws.append(
            [
                b.label,
                b.box_type,
                b.capacity,
                b.usable,
                b.users,
                b.usable - b.users,
                ", ".join(b.host_codes),
                len(b.served),
                ", ".join(c for s in b.served for c in s.codes),
                max(s.distance_m for s in b.served),
                lat,
                lon,
            ]
        )

    ws = wb.create_sheet("Buildings")
    what = "Address" if result.source == DesignSource.addresses else "Building ID"
    _sheet(ws, [what, "Users", "Box", "Box type", "Distance to box (m)"], [30, 8, 10, 18, 14])
    rows = [(s, b) for b in result.boxes for s in b.served]
    rows.sort(key=lambda r: natural_key(r[0].codes[0]))
    for s, b in rows:
        ws.append([", ".join(s.codes), s.users, b.label, b.box_type, s.distance_m])

    ws = wb.create_sheet("Not served")
    _sheet(ws, [what, "Reason"], [30, 60])
    reason = "No Total Users filled in" if result.source == DesignSource.addresses else "No Total Users in the survey"
    for code in result.summary.without_users:
        ws.append([code, reason])
    if result.summary.without_id:
        ws.append([None, f"{result.summary.without_id} buildings without a Building ID on the drawing"])
    if result.summary.outside_skipped:
        ws.append([None, f"{result.summary.outside_skipped} buildings outside the project boundary (left out)"])

    info = wb.create_sheet("Settings")
    r = result.request
    info.append(["Status", "PROVISIONAL — prototype placement, values not confirmed by the Design Team"])
    info.append(["Project", project.name])
    source = "Streets & numbers Excel (OpenStreetMap house numbers + field data)"
    info.append(["Users from", source if result.source == DesignSource.addresses else "Drawing + survey Excel"])
    for t in r.box_types:
        info.append(["Box type", f"{t.name}: {t.capacity} users"])
    info.append(["Max drop (m)", r.max_drop_m if r.max_drop_m is not None else "no limit"])
    info.append(["Spare (%)", r.spare_percent])
    info.append(["Outside buildings", "served" if r.include_outside else "left out"])
    info.append(["Boxes", result.summary.boxes])
    info.append(["Users served", result.summary.users])
    info.append(["Method", METHOD])
    info.append(["Made", datetime.now(UTC).strftime("%Y-%m-%d")])
    info.column_dimensions["A"].width = 18
    info.column_dimensions["B"].width = 100
    return survey_template.save(wb)
