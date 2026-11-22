"""Project exports: KMZ (Google Earth), Excel, DXF (AutoCAD, UTM 36N metres).

Content: project boundary, buildings with review status / Building IDs / survey users, IDs outside buildings.
Built from the same data as the UI (buildings.building_layer + survey rows).
"""

import io
import zipfile
from dataclasses import dataclass

from ezdxf.filemanagement import new as new_dxf
from lxml import etree
from openpyxl import Workbook
from openpyxl.styles import Font
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import geo
from app.models import Project, SurveyRecord
from app.schemas import BuildingLayer, BuildingRead
from app.services import buildings as buildings_service
from app.services import layers as layers_service

KML_NS = "http://www.opengis.net/kml/2.2"
# KML colours are aabbggrr (same colours as the map legend).
_KML_COLOR = {"ok": "ff548719", "multiple_ids": "ff147efd", "no_id": "ff7d756c", "orphan": "ff8433d6"}
_STATUS_TEXT = {"ok": "One ID", "multiple_ids": "Several IDs", "no_id": "No ID"}
# Layer → AutoCAD Color Index.
_DXF_LAYERS = {
    "OPTICORE_BOUNDARY": 5,
    "OPTICORE_BUILDING_OK": 3,
    "OPTICORE_BUILDING_SEVERAL_IDS": 30,
    "OPTICORE_BUILDING_NO_ID": 8,
    "OPTICORE_BUILDING_ID": 7,
    "OPTICORE_ID_OUTSIDE_BUILDING": 6,
}
_DXF_BUILDING_LAYER = {
    "ok": "OPTICORE_BUILDING_OK",
    "multiple_ids": "OPTICORE_BUILDING_SEVERAL_IDS",
    "no_id": "OPTICORE_BUILDING_NO_ID",
}


@dataclass
class _Data:
    boundary: BaseGeometry | None
    buildings: BuildingLayer
    survey: dict[str, SurveyRecord]


def _load(db: Session, project: Project) -> _Data:
    layers = layers_service.project_layers(db, project)
    boundary = shape(layers.boundary.geometry.model_dump()) if layers.boundary else None
    rows = db.scalars(select(SurveyRecord).where(SurveyRecord.project_id == project.id))
    return _Data(boundary, buildings_service.building_layer(db, project), {r.code: r for r in rows})


def _users(b: BuildingRead, survey: dict[str, SurveyRecord]) -> int | None:
    rows = [survey[c] for c in b.codes if c in survey]
    return sum(r.total_users or 0 for r in rows) if rows else None


# --- KMZ -----------------------------------------------------------------------------------------


def _el(parent: etree._Element, tag: str, text: str | None = None) -> etree._Element:
    child = etree.SubElement(parent, f"{{{KML_NS}}}{tag}")
    if text is not None:
        child.text = text
    return child


def _coords(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.8f},{y:.8f}" for x, y in points)


def _kml_polygon(parent: etree._Element, geom: BaseGeometry) -> None:
    polygons = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
    target = _el(parent, "MultiGeometry") if len(polygons) > 1 else parent
    for poly in polygons:
        p = _el(target, "Polygon")
        _el(_el(_el(p, "outerBoundaryIs"), "LinearRing"), "coordinates", _coords(list(poly.exterior.coords)))
        for hole in poly.interiors:
            _el(_el(_el(p, "innerBoundaryIs"), "LinearRing"), "coordinates", _coords(list(hole.coords)))


def _style(doc: etree._Element, sid: str, line: str, fill: str) -> None:
    style = _el(doc, "Style")
    style.set("id", sid)
    _el(_el(style, "IconStyle"), "color", line)
    ls = _el(style, "LineStyle")
    _el(ls, "color", line)
    _el(ls, "width", "2")
    _el(_el(style, "PolyStyle"), "color", fill)


def _extended_data(placemark: etree._Element, values: dict[str, object]) -> None:
    ext = _el(placemark, "ExtendedData")
    for name, value in values.items():
        if value is not None:
            d = _el(ext, "Data")
            d.set("name", name)
            _el(d, "value", str(value))


def to_kmz(db: Session, project: Project) -> bytes:
    data = _load(db, project)
    kml = etree.Element(f"{{{KML_NS}}}kml", nsmap={None: KML_NS})  # type: ignore[dict-item]  # lxml: None = default ns
    doc = _el(kml, "Document")
    _el(doc, "name", project.name)
    _style(doc, "boundary", "ffff6e0d", "00000000")
    for status, color in _KML_COLOR.items():
        _style(doc, status, color, "66" + color[2:])

    if data.boundary is not None:
        pm = _el(doc, "Placemark")
        _el(pm, "name", "Project boundary")
        _el(pm, "styleUrl", "#boundary")
        _kml_polygon(pm, data.boundary)

    folder = _el(doc, "Folder")
    _el(folder, "name", f"Buildings ({len(data.buildings.buildings)})")
    for b in data.buildings.buildings:
        pm = _el(folder, "Placemark")
        _el(pm, "name", ", ".join(b.codes) or "No ID")
        _el(pm, "styleUrl", f"#{b.status.value}")
        _extended_data(
            pm,
            {
                "Building ID": ", ".join(b.codes) or None,
                "Review": _STATUS_TEXT[b.status.value],
                "Area m2": b.area_m2,
                "Boundary": b.boundary_position.value if b.boundary_position else None,
                "Total Users": _users(b, data.survey),
            },
        )
        _kml_polygon(pm, shape(b.geometry.model_dump()))

    if data.buildings.orphan_labels:
        folder = _el(doc, "Folder")
        _el(folder, "name", f"IDs outside buildings ({len(data.buildings.orphan_labels)})")
        for o in data.buildings.orphan_labels:
            pm = _el(folder, "Placemark")
            _el(pm, "name", o.code)
            _el(pm, "styleUrl", "#orphan")
            x, y = o.geometry.coordinates[:2]
            _el(_el(pm, "Point"), "coordinates", f"{x:.8f},{y:.8f}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.kml", etree.tostring(kml, xml_declaration=True, encoding="UTF-8", pretty_print=True))
    return buf.getvalue()


# --- Excel ---------------------------------------------------------------------------------------

_XLSX_HEADER = [
    "Building ID",
    "Review",
    "Boundary",
    "Area (m²)",
    "Latitude",
    "Longitude",
    "Street",
    "Floors (excl. GF)",
    "Total Users",
]


def to_xlsx(db: Session, project: Project) -> bytes:
    data = _load(db, project)
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Buildings"
    ws.append(_XLSX_HEADER)
    for b in data.buildings.buildings:
        point = shape(b.geometry.model_dump()).representative_point()
        single = data.survey.get(b.codes[0]) if len(b.codes) == 1 else None
        ws.append(
            [
                ", ".join(b.codes) or None,
                _STATUS_TEXT[b.status.value],
                b.boundary_position.value if b.boundary_position else None,
                b.area_m2,
                round(point.y, 7),
                round(point.x, 7),
                single.street_name if single else None,
                single.floors if single else None,
                _users(b, data.survey),
            ]
        )
    orphans = wb.create_sheet("IDs outside buildings")
    orphans.append(["Building ID", "Latitude", "Longitude"])
    for o in data.buildings.orphan_labels:
        x, y = o.geometry.coordinates[:2]
        orphans.append([o.code, round(y, 7), round(x, 7)])
    for sheet, widths in ((ws, [14, 13, 11, 10, 12, 12, 30, 16, 11]), (orphans, [14, 12, 12])):
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for i, width in enumerate(widths):
            sheet.column_dimensions[chr(ord("A") + i)].width = width
        sheet.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# --- DXF -----------------------------------------------------------------------------------------


def _utm_rings(geom: BaseGeometry) -> list[list[tuple[float, float]]]:
    utm = geo.to_measure_crs(geom)
    polygons = list(utm.geoms) if utm.geom_type == "MultiPolygon" else [utm]
    return [[(x, y) for x, y, *_ in ring.coords] for p in polygons for ring in [p.exterior, *p.interiors]]


def to_dxf(db: Session, project: Project) -> bytes:
    """AutoCAD 2010 DXF in UTM 36N metres (the Design Team's CAD CRS), one layer per review status."""
    data = _load(db, project)
    doc = new_dxf("R2010")
    doc.header["$INSUNITS"] = 6  # metres (DXF code 6)
    for name, color in _DXF_LAYERS.items():
        doc.layers.add(name, color=color)
    msp = doc.modelspace()

    def text(value: str, at: BaseGeometry, layer: str) -> None:
        p = geo.to_measure_crs(at)
        msp.add_text(value, height=1.0, dxfattribs={"layer": layer, "insert": (p.x, p.y)})

    if data.boundary is not None:
        for ring in _utm_rings(data.boundary):
            msp.add_lwpolyline(ring, close=True, dxfattribs={"layer": "OPTICORE_BOUNDARY"})
    for b in data.buildings.buildings:
        polygon = shape(b.geometry.model_dump())
        for ring in _utm_rings(polygon):
            msp.add_lwpolyline(ring, close=True, dxfattribs={"layer": _DXF_BUILDING_LAYER[b.status.value]})
        if b.codes:
            text(", ".join(b.codes), polygon.representative_point(), "OPTICORE_BUILDING_ID")
    for o in data.buildings.orphan_labels:
        text(o.code, shape(o.geometry.model_dump()), "OPTICORE_ID_OUTSIDE_BUILDING")

    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue().encode("utf-8")
