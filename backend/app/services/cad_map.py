"""AutoCAD (DXF) street map: what is known about the area as a drawing, in UTM 36N metres.

Layers (each can be switched off in AutoCAD):
- OPTICORE_BOUNDARY: the project boundary (KML)
- OSM_STREETS, OSM_STREET_NAMES_AR, OSM_STREET_NAMES_EN: OpenStreetMap streets inside the boundary
- OSM_HOUSE_NUMBERS: OpenStreetMap house numbers (point + number)
- FIELD_DATA: Floors / Total Users from the filled Streets & numbers Excel
- DRAWING_BUILDINGS: building outlines, when a drawing was uploaded
- NETWORK_BOXES, BOX_DROPS: a Network Box design (provisional) and the line from each box to what it serves
OpenStreetMap has almost no building outlines in Egypt, so without a drawing there are no buildings here.
"""

import io
import math

from ezdxf.document import Drawing
from ezdxf.enums import TextEntityAlignment
from ezdxf.filemanagement import new as new_dxf
from ezdxf.layouts.layout import Modelspace
from geoalchemy2.shape import to_shape
from shapely.geometry import LineString, MultiLineString, Point, shape
from shapely.geometry.base import BaseGeometry
from sqlalchemy.orm import Session

from app import geo
from app.errors import ConflictError, ExternalServiceError
from app.importers import osm
from app.models import Project
from app.schemas import BoxDesign
from app.services import addresses, streets
from app.services import buildings as buildings_service

# AutoCAD colour index per layer.
LAYERS = {
    "OPTICORE_BOUNDARY": 5,
    "OSM_STREETS": 8,
    "OSM_STREET_NAMES_AR": 7,
    "OSM_STREET_NAMES_EN": 7,
    "OSM_HOUSE_NUMBERS": 30,
    "FIELD_DATA": 3,
    "DRAWING_BUILDINGS": 9,
    "NETWORK_BOXES": 6,
    "BOX_DROPS": 6,
}
TEXT_STYLE = "OPTICORE_TEXT"  # a TrueType font, so Arabic names show in AutoCAD
# Drafting sizes in metres (how the drawing looks, not engineering values).
STREET_NAME_HEIGHT = 3.0
NUMBER_HEIGHT = 1.5
MIN_LABELLED_STREET_M = 30.0
BOX_SIZE = 3.0


def _utm(geom: BaseGeometry) -> BaseGeometry:
    return geo.to_measure_crs(geom)


def _readable(angle: float) -> float:
    """Text angle in degrees, turned so it never reads upside down."""
    if angle > 90:
        return angle - 180
    if angle < -90:
        return angle + 180
    return angle


class _Dxf:
    def __init__(self) -> None:
        self.doc: Drawing = new_dxf("R2010")
        self.doc.header["$INSUNITS"] = 6  # metres
        self.doc.styles.add(TEXT_STYLE, font="arial.ttf")
        for name, color in LAYERS.items():
            self.doc.layers.add(name, color=color)
        self.msp: Modelspace = self.doc.modelspace()

    def text(self, value: str, at: Point, layer: str, height: float, angle: float = 0.0) -> None:
        entity = self.msp.add_text(
            value, height=height, rotation=angle, dxfattribs={"layer": layer, "style": TEXT_STYLE}
        )
        entity.set_placement((at.x, at.y), align=TextEntityAlignment.MIDDLE_CENTER)

    def lines(self, geom: BaseGeometry, layer: str, close: bool = False) -> None:
        parts = geom.geoms if hasattr(geom, "geoms") else [geom]
        for part in parts:
            if part.geom_type == "Polygon":
                for ring in [part.exterior, *part.interiors]:
                    self.msp.add_lwpolyline(list(ring.coords)[:-1], close=True, dxfattribs={"layer": layer})
            elif part.geom_type == "LineString" and len(part.coords) >= 2:
                self.msp.add_lwpolyline(list(part.coords), close=close, dxfattribs={"layer": layer})

    def save(self) -> bytes:
        stream = io.StringIO()
        self.doc.write(stream)
        return stream.getvalue().encode("utf-8")


def _street_names(dxf: _Dxf, street: osm.OsmStreet, inside: BaseGeometry) -> None:
    pieces = inside.geoms if isinstance(inside, MultiLineString) else [inside]
    for piece in pieces:
        if not isinstance(piece, LineString) or piece.length < MIN_LABELLED_STREET_M:
            continue
        middle = piece.interpolate(0.5, normalized=True)
        ahead = piece.interpolate(min(piece.length, piece.project(middle) + 1.0))
        behind = piece.interpolate(max(0.0, piece.project(middle) - 1.0))
        angle = _readable(math.degrees(math.atan2(ahead.y - behind.y, ahead.x - behind.x)))
        # Arabic above the centre line, English below it.
        normal = math.radians(angle + 90)
        offset = STREET_NAME_HEIGHT * 0.9
        above = Point(middle.x + offset * math.cos(normal), middle.y + offset * math.sin(normal))
        below = Point(middle.x - offset * math.cos(normal), middle.y - offset * math.sin(normal))
        dxf.text(street.name_ar, above, "OSM_STREET_NAMES_AR", STREET_NAME_HEIGHT, angle)
        if street.name_en:
            dxf.text(street.name_en, below, "OSM_STREET_NAMES_EN", STREET_NAME_HEIGHT, angle)


def _osm_map(dxf: _Dxf, project: Project, boundary: BaseGeometry) -> None:
    boundary_utm = _utm(boundary)
    for street in streets.osm_streets(project):
        inside = _utm(street.line).intersection(boundary_utm)
        if inside.is_empty or inside.length == 0:
            continue
        dxf.lines(inside, "OSM_STREETS")
        _street_names(dxf, street, inside)
    for a in streets.addresses_in_boundary(project):
        at = _utm(Point(a.lon, a.lat))
        dxf.msp.add_point((at.x, at.y), dxfattribs={"layer": "OSM_HOUSE_NUMBERS"})
        dxf.text(a.housenumber, Point(at.x, at.y + NUMBER_HEIGHT), "OSM_HOUSE_NUMBERS", NUMBER_HEIGHT)


def _field_data(dxf: _Dxf, db: Session, project: Project) -> None:
    for p in addresses.points(db, project):
        at = _utm(to_shape(p.geometry))
        parts = []
        if p.floors is not None:
            parts.append(f"F{p.floors}")
        if p.total_users is not None:
            parts.append(f"U{p.total_users}")
        dxf.text(" ".join(parts), Point(at.x, at.y - NUMBER_HEIGHT), "FIELD_DATA", NUMBER_HEIGHT)


def _drawing_buildings(dxf: _Dxf, db: Session, project: Project) -> None:
    for b in buildings_service.building_layer(db, project).buildings:
        dxf.lines(_utm(shape(b.geometry.model_dump())), "DRAWING_BUILDINGS")


def _boxes(dxf: _Dxf, design: BoxDesign) -> None:
    half = BOX_SIZE / 2
    for box in design.boxes:
        at = _utm(shape(box.geometry.model_dump()))
        assert isinstance(at, Point)
        square = [
            (at.x - half, at.y - half),
            (at.x + half, at.y - half),
            (at.x + half, at.y + half),
            (at.x - half, at.y + half),
        ]
        dxf.msp.add_lwpolyline(square, close=True, dxfattribs={"layer": "NETWORK_BOXES"})
        label = f"{box.label} {box.box_type} {box.users}/{box.usable}"
        dxf.text(label, Point(at.x, at.y + BOX_SIZE), "NETWORK_BOXES", NUMBER_HEIGHT)
        for served in box.served:
            if served.distance_m > 0:
                to = _utm(shape(served.geometry.model_dump()))
                assert isinstance(to, Point)
                dxf.msp.add_line((at.x, at.y), (to.x, to.y), dxfattribs={"layer": "BOX_DROPS"})


def to_dxf(db: Session, project: Project, design: BoxDesign | None = None) -> bytes:
    """The street map (needs the boundary), plus a box design when given."""
    boundary = to_shape(project.boundary) if project.boundary is not None else None
    if boundary is None and design is None:
        raise ConflictError("Upload the project KML first: the map is drawn inside the project boundary.")
    dxf = _Dxf()
    if boundary is not None:
        dxf.lines(_utm(boundary), "OPTICORE_BOUNDARY")
        try:
            _osm_map(dxf, project, boundary)
        except ExternalServiceError:
            if design is None:
                raise
            # A box design is still useful without the OSM streets.
    _field_data(dxf, db, project)
    _drawing_buildings(dxf, db, project)
    if design is not None:
        _boxes(dxf, design)
    return dxf.save()
