"""SAMPLE DXF drawings for tests — synthetic, built with ezdxf, not customer data.

All coordinates are UTM 36N metres around the same origin as kml_samples, so the KML test boundary
(200 m × 300 m rectangle at X0, Y0) can be used to test inside / crossing / outside.
Layer names come from the profiles in app/rules/cad_layers.yaml.
"""
import io

import ezdxf

from app import rules
from tests.kml_samples import _X0, _Y0

VALIDATED = rules.cad_layers().profiles[0]
BASE = rules.cad_layers().profiles[1]


def _rect(x: float, y: float, w: float, h: float) -> list[tuple[float, float]]:
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def _to_bytes(doc: ezdxf.document.Drawing) -> bytes:
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue().encode("utf-8")


def drawing(building_layer: str = VALIDATED.building_layer, id_layer: str = VALIDATED.id_layer,
            id_prefix: str = "", x0: float = _X0, y0: float = _Y0) -> bytes:
    """Expected result:
    1 → closed rectangle, ok, inside      | 2 → drawn as 4 separate open lines, ok, inside
    3 + 3-2 → one polygon, multiple_ids   | (no label) → no_id, inside
    5 → crosses the boundary              | 6 → outside the boundary
    9 → label not inside any building     | 'note' → unreadable label | 1×1 m square → dropped as noise
    """
    doc = ezdxf.new("R2010")
    doc.layers.add(building_layer)
    doc.layers.add(id_layer)
    msp = doc.modelspace()
    b = {"layer": building_layer}

    msp.add_lwpolyline(_rect(x0 + 10, y0 + 10, 20, 10), close=True, dxfattribs=b)
    corners = _rect(x0 + 40, y0 + 10, 20, 10)
    for i in range(4):  # open lines, like most outlines in real drawings
        msp.add_lwpolyline([corners[i], corners[(i + 1) % 4]], dxfattribs=b)
    msp.add_lwpolyline(_rect(x0 + 70, y0 + 10, 30, 10), close=True, dxfattribs=b)
    msp.add_lwpolyline(_rect(x0 + 110, y0 + 10, 20, 10), close=True, dxfattribs=b)
    msp.add_lwpolyline(_rect(x0 + 190, y0 + 50, 20, 10), close=True, dxfattribs=b)
    msp.add_lwpolyline(_rect(x0 + 250, y0 + 50, 20, 10), close=True, dxfattribs=b)
    msp.add_lwpolyline(_rect(x0 + 5, y0 + 100, 1, 1), close=True, dxfattribs=b)

    labels = {"1": (20, 15), "2": (50, 15), "3": (75, 15), "3-2": (95, 15), "5": (200, 55), "6": (260, 55),
              "9": (150, 150)}
    for code, (dx, dy) in labels.items():
        msp.add_text(f"{id_prefix}{code}", dxfattribs={"layer": id_layer, "insert": (x0 + dx, y0 + dy)})
    msp.add_text("note", dxfattribs={"layer": id_layer, "insert": (x0 + 22, y0 + 12)})
    # Other layers are ignored.
    msp.add_lwpolyline(_rect(x0, y0, 5, 5), close=True, dxfattribs={"layer": "frame"})
    return _to_bytes(doc)


def base_drawing() -> bytes:
    """Base-drawing convention: Arabic building layer, IDs written as 'ERA <n>'. '3-2' does not match its
    ID pattern (digits only), so it counts as unreadable there."""
    return drawing(BASE.building_layer, BASE.id_layer, id_prefix="ERA ")


def local_coordinates_drawing() -> bytes:
    """Not georeferenced: drawn around (0, 0)."""
    return drawing(x0=0, y0=0)


def unknown_layers_drawing() -> bytes:
    return drawing(building_layer="walls", id_layer="numbers")
