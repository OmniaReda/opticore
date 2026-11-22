"""Read buildings and Building IDs from a Design Team DXF drawing.

Drawings are in UTM zone 36N metres (EPSG:32636). Building outlines are mostly OPEN polylines,
so polygons are rebuilt with `polygonize`; each ID label is linked to the polygon that contains it.
Which layers to read comes from a profile in app/rules/cad_layers.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ezdxf import recover
from ezdxf.document import Drawing
from ezdxf.lldxf.const import DXFStructureError
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union
from shapely.strtree import STRtree

from app.importers import FileContentError
from app.rules import CadLayerRules, CadProfile

# Plausible UTM coordinates (northern hemisphere): easting 166–834 km, northing 0–9,330 km.
# Anything else is not a georeferenced UTM drawing (e.g. a drawing in local coordinates).
_UTM_X = (100_000.0, 900_000.0)
_UTM_Y = (0.0, 9_400_000.0)


class CadError(FileContentError):
    pass


@dataclass
class Label:
    building_id: str
    point: Point
    building_index: int | None  # index into CadBuildings.polygons; None = not inside any polygon


@dataclass
class CadBuildings:
    """Result in the drawing CRS (EPSG:32636, metres)."""

    profile: CadProfile
    polygons: list[Polygon]
    labels: list[Label]
    unreadable_labels: int  # texts on the ID layer that do not match the profile's ID pattern
    small_polygons: int  # dropped as drawing noise (< min_building_area_m2)


def read_dxf(path: Path) -> Drawing:
    try:
        doc, _auditor = recover.readfile(str(path))
    except (OSError, DXFStructureError) as e:
        raise CadError(f"Not a readable DXF file: {e}") from None
    return doc


def detect_profile(doc: Drawing, rules: CadLayerRules) -> CadProfile:
    """First profile whose building and ID layers both exist in the drawing."""
    layers = {layer.dxf.name for layer in doc.layers}
    for profile in rules.profiles:
        if profile.building_layer in layers and profile.id_layer in layers:
            return profile
    expected = "; ".join(f"'{p.building_layer}' + '{p.id_layer}'" for p in rules.profiles)
    found = ", ".join(sorted(layers)[:40])
    raise CadError(f"No known building/ID layers in this drawing. Expected one of: {expected}. Layers found: {found}")


def _building_lines(doc: Drawing, layer: str) -> list[LineString]:
    lines: list[LineString] = []
    msp = doc.modelspace()
    for e in msp.query("LWPOLYLINE POLYLINE LINE").layer == layer:
        if e.dxftype() == "LINE":
            pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        elif e.dxftype() == "LWPOLYLINE":
            pts = [(p[0], p[1]) for p in e.get_points("xy")]  # 2D only: elevation dropped
        elif e.is_2d_polyline or e.is_3d_polyline:
            pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
        else:
            continue  # polyface / mesh: not a building outline
        if getattr(e, "is_closed", False) and pts:
            pts.append(pts[0])
        if len(set(pts)) >= 2:
            lines.append(LineString(pts))
    return lines


def _check_utm(lines: list[LineString]) -> None:
    minx, miny, maxx, maxy = unary_union(lines).bounds
    if not (_UTM_X[0] <= minx and maxx <= _UTM_X[1] and _UTM_Y[0] <= miny and maxy <= _UTM_Y[1]):
        raise CadError(
            f"Coordinates ({minx:.0f}, {miny:.0f}) – ({maxx:.0f}, {maxy:.0f}) do not look like "
            "UTM zone 36N metres. The drawing must be georeferenced in WGS 84 / UTM 36N (EPSG:32636)."
        )


def extract(doc: Drawing, rules: CadLayerRules, profile: CadProfile | None = None) -> CadBuildings:
    profile = profile or detect_profile(doc, rules)
    lines = _building_lines(doc, profile.building_layer)
    if not lines:
        raise CadError(f"Layer '{profile.building_layer}' has no building outlines")
    _check_utm(lines)

    all_polygons = list(polygonize(unary_union(lines)))
    polygons = [p for p in all_polygons if p.area >= rules.min_building_area_m2]
    tree = STRtree(polygons)

    labels: list[Label] = []
    unreadable = 0
    for e in doc.modelspace().query("TEXT MTEXT").layer == profile.id_layer:
        text = e.dxf.text if e.dxftype() == "TEXT" else e.plain_text()
        building_id = profile.match_id(text)
        if building_id is None:
            unreadable += 1
            continue
        point = Point(e.dxf.insert.x, e.dxf.insert.y)
        hits = tree.query(point, predicate="within")
        labels.append(Label(building_id, point, int(hits[0]) if len(hits) else None))

    return CadBuildings(
        profile=profile,
        polygons=polygons,
        labels=labels,
        unreadable_labels=unreadable,
        small_polygons=len(all_polygons) - len(polygons),
    )
