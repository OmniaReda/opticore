"""Read named streets from OpenStreetMap XML (the format of both Overpass `out:xml` and the OSM API `/map`)."""

from __future__ import annotations

from dataclasses import dataclass

from lxml import etree
from shapely.geometry import LineString

from app.importers import FileContentError


class OsmError(FileContentError):
    pass


@dataclass
class OsmStreet:
    """One OSM way with a highway tag and a name. Geometry in lon/lat (EPSG:4326)."""

    name_ar: str  # `name:ar`, else `name` (in Egypt `name` is normally Arabic)
    name_en: str | None
    highway: str  # residential, primary, footway, …
    line: LineString


def parse(xml: bytes) -> list[OsmStreet]:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    try:
        root = etree.fromstring(xml, parser)
    except etree.XMLSyntaxError as e:
        raise OsmError(f"OpenStreetMap answer is not valid XML: {e}") from None
    if root.tag != "osm":
        raise OsmError(f"OpenStreetMap answer is not OSM XML (root <{root.tag}>)")

    nodes: dict[str, tuple[float, float]] = {}
    for n in root.iter("node"):
        lat, lon = n.get("lat"), n.get("lon")
        if lat is not None and lon is not None:
            nodes[n.get("id", "")] = (float(lon), float(lat))

    streets: list[OsmStreet] = []
    for way in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in way.iter("tag")}
        highway = tags.get("highway")
        name = tags.get("name:ar") or tags.get("name")
        if not highway or not name:
            continue
        points = [nodes[ref] for nd in way.iter("nd") if (ref := nd.get("ref", "")) in nodes]
        if len(points) < 2:
            continue
        streets.append(
            OsmStreet(name.strip(), (tags.get("name:en") or "").strip() or None, highway, LineString(points))
        )
    return streets
