"""Read KML / KMZ into 2D shapely geometries (EPSG:4326).

Handles both files the Design Team produces:
- Google Earth exports: KML 2.2 namespace, gx:CascadingStyle, Polygon + Point placemarks.
- CAD-Earth exports from AutoCAD: no XML namespace, many LineString / LinearRing in MultiGeometry.

Styles, LookAt, ExtendedData etc. are ignored. Altitude (Z) is dropped.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field

from lxml import etree
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry

from app.importers import FileContentError

MAX_KMZ_UNCOMPRESSED = 200 * 1024 * 1024  # guard against zip bombs


class KmlError(FileContentError):
    """The file cannot be read as KML. Message is shown to the user."""


@dataclass
class Placemark:
    name: str | None
    description: str | None
    geometry: BaseGeometry


@dataclass
class KmlContent:
    document_name: str | None
    placemarks: list[Placemark] = field(default_factory=list)
    skipped: int = 0  # geometries dropped as degenerate (e.g. a line with one point)


def _local(tag: object) -> str:
    # Works with and without namespace ("{http://www.opengis.net/kml/2.2}Point" → "Point").
    return etree.QName(tag).localname if isinstance(tag, str) else ""


def _children(el: etree._Element, name: str) -> list[etree._Element]:
    return [c for c in el if _local(c.tag) == name]


def _child_text(el: etree._Element, name: str) -> str | None:
    for c in _children(el, name):
        text = (c.text or "").strip()
        return text or None
    return None


def _coords(el: etree._Element) -> list[tuple[float, float]]:
    node = next((c for c in el.iter() if _local(c.tag) == "coordinates"), None)
    if node is None or not node.text:
        return []
    out: list[tuple[float, float]] = []
    for token in node.text.split():
        parts = token.split(",")
        if len(parts) < 2:
            raise KmlError(f"Bad coordinate '{token}'")
        try:
            lon, lat = float(parts[0]), float(parts[1])  # Z (parts[2]) dropped: 2D only
        except ValueError:
            raise KmlError(f"Bad coordinate '{token}'") from None
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise KmlError(f"Coordinate out of lon/lat range: {lon},{lat}")
        out.append((lon, lat))
    return out


def _ring(el: etree._Element) -> list[tuple[float, float]] | None:
    pts = _coords(el)
    if len(pts) >= 3 and pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts if len(pts) >= 4 else None


def _geometries(el: etree._Element, content: KmlContent) -> list[BaseGeometry]:
    kind = _local(el.tag)
    if kind == "MultiGeometry":
        return [g for child in el for g in _geometries(child, content)]
    if kind == "Point":
        pts = _coords(el)
        if pts:
            return [Point(pts[0])]
    elif kind in ("LineString", "LinearRing"):
        # A standalone LinearRing (CAD-Earth) is kept as a closed line: whether it is an
        # area (e.g. a building) is decided by the importer that understands the layer.
        pts = _coords(el)
        if len(set(pts)) >= 2:
            return [LineString(pts)]
    elif kind == "Polygon":
        outer = next((_ring(r) for b in _children(el, "outerBoundaryIs") for r in _children(b, "LinearRing")), None)
        if outer:
            holes = [h for b in _children(el, "innerBoundaryIs") for r in _children(b, "LinearRing") if (h := _ring(r))]
            return [Polygon(outer, holes)]
    else:
        return []
    content.skipped += 1
    return []


GEOMETRY_TAGS = {"Point", "LineString", "LinearRing", "Polygon", "MultiGeometry"}


def parse_kml(data: bytes) -> KmlContent:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True, recover=False)
    try:
        root = etree.fromstring(data, parser=parser)
    except etree.XMLSyntaxError as e:
        raise KmlError(f"Not a valid KML/XML file: {e}") from None
    if _local(root.tag) != "kml":
        raise KmlError("Not a KML file (root element is not <kml>)")

    doc = next((e for e in root.iter() if _local(e.tag) == "Document"), root)
    content = KmlContent(document_name=_child_text(doc, "name"))
    for pm in (e for e in root.iter() if _local(e.tag) == "Placemark"):
        name, description = _child_text(pm, "name"), _child_text(pm, "description")
        for g_el in (c for c in pm if _local(c.tag) in GEOMETRY_TAGS):
            for geom in _geometries(g_el, content):
                content.placemarks.append(Placemark(name, description, geom))
    return content


def read_kmz(data: bytes) -> bytes:
    """Return the main KML document inside a KMZ (doc.kml, else the first .kml)."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise KmlError("Not a valid KMZ (zip) file") from None
    with zf:
        kmls = [i for i in zf.infolist() if i.filename.lower().endswith(".kml")]
        if not kmls:
            raise KmlError("KMZ contains no .kml file")
        main = next((i for i in kmls if i.filename.lower() == "doc.kml"), kmls[0])
        if main.file_size > MAX_KMZ_UNCOMPRESSED:
            raise KmlError("KML inside KMZ is too large")
        return zf.read(main)


def load(data: bytes, is_kmz: bool) -> KmlContent:
    return parse_kml(read_kmz(data) if is_kmz else data)
