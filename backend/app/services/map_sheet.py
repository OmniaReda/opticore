"""The whole map as a survey sheet: one row per Building ID, in the survey template's columns.

Each row is filled with everything known about that building:
- from the drawing: Building ID, location (GPS = a point inside the building), review status, area;
- from the survey Excel (if uploaded): every survey column;
- from OpenStreetMap: the nearest named street, used as Street Name when the survey has none.
The file keeps the template's headers, so it can be completed in the field and uploaded back as the survey.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from geoalchemy2.shape import to_shape
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import rules
from app.errors import ConflictError, ExternalServiceError
from app.models import Project, SurveyRecord
from app.services import buildings as buildings_service
from app.services import streets, survey_template
from app.services.buildings import natural_key

EXTRA_COLUMNS = [
    "Drawing review",
    "Area (m²)",
    "Boundary",
    "Street source",
    "OSM street (Arabic)",
    "OSM street (English)",
    "Distance to OSM street (m)",
]
_REVIEW = {
    "ok": "One ID",
    "multiple_ids": "Several IDs in one outline",
    "no_id": "No ID",
    "orphan": "ID outside any building",
    "survey_only": "Survey only (ID not on the drawing)",
}


@dataclass
class _Row:
    code: str | None
    where: BaseGeometry | None  # lon/lat
    review: str
    area_m2: float | None
    boundary: str | None


def _drawing_rows(db: Session, project: Project) -> list[_Row]:
    layer = buildings_service.building_layer(db, project)
    rows: list[_Row] = []
    for b in layer.buildings:
        polygon = shape(b.geometry.model_dump())
        position = b.boundary_position.value if b.boundary_position else None
        codes: list[str | None] = list(b.codes) or [None]
        for code in codes:
            rows.append(_Row(code, polygon, b.status.value, b.area_m2, position))
    for o in layer.orphan_labels:
        rows.append(_Row(o.code, shape(o.geometry.model_dump()), "orphan", None, None))
    rows.sort(key=lambda r: (0, natural_key(r.code)) if r.code else (1, []))
    return rows


def to_xlsx(db: Session, project: Project) -> bytes:
    rows = _drawing_rows(db, project)
    if not rows:
        raise ConflictError("Upload the drawing (DXF/DWG) first: the sheet has one row per building on the drawing.")
    survey = {r.code: r for r in db.scalars(select(SurveyRecord).where(SurveyRecord.project_id == project.id))}
    on_drawing = {r.code for r in rows if r.code}
    for code in sorted(set(survey) - on_drawing, key=natural_key):
        gps = survey[code].geometry
        rows.append(_Row(code, to_shape(gps) if gps is not None else None, "survey_only", None, None))

    finder: streets.StreetFinder | None = None
    osm_note = "OpenStreetMap: nearest named street to each building (Street Name when the survey has none)"
    if project.boundary is None:
        osm_note = "OpenStreetMap: not used (no project boundary yet — upload the KML)"
    else:
        try:
            finder = streets.StreetFinder(streets.osm_streets(project))
        except ExternalServiceError:
            osm_note = "OpenStreetMap: not reachable when this file was made — Street Name only from the survey"

    cfg = rules.survey_columns()
    wb, ws = survey_template.new_workbook(EXTRA_COLUMNS)
    from_survey = from_osm = 0
    for row in rows:
        record = survey.get(row.code) if row.code else None
        values: dict[str, Any] = {f: getattr(record, f) for f in cfg.columns if f != "code"} if record else {}
        values["code"] = row.code
        point = row.where.representative_point() if row.where is not None else None
        if point is not None and (values.get("latitude") is None or values.get("longitude") is None):
            values["latitude"], values["longitude"] = round(point.y, 7), round(point.x, 7)

        nearest = finder.nearest(row.where) if finder and row.where is not None else None
        source = None
        if values.get("street_name"):
            source, from_survey = "survey", from_survey + 1
        elif nearest:
            values["street_name"] = nearest.name_en or nearest.name_ar
            source, from_osm = "OpenStreetMap", from_osm + 1

        ws.append(
            [values.get(f) for f in cfg.columns]
            + [
                _REVIEW[row.review],
                row.area_m2,
                row.boundary,
                source,
                nearest.name_ar if nearest else None,
                nearest.name_en if nearest else None,
                round(nearest.distance_m, 1) if nearest else None,
            ]
        )

    info = wb["Instructions"]
    info.append([])
    info.append(["This file", f"Map of project '{project.name}' — one row per Building ID on the drawing"])
    info.append(["Rows", len(rows)])
    info.append(["Street Name", f"{from_survey} from the survey Excel, {from_osm} from OpenStreetMap"])
    info.append(["Sources", "Drawing (IDs, location, review) · survey Excel (if uploaded) · " + osm_note])
    if finder is not None:
        info.append(["Attribution", streets.ATTRIBUTION])
    info.append(["Made", datetime.now(UTC).strftime("%Y-%m-%d")])
    return survey_template.save(wb)
