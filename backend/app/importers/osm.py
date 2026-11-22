"""Read named streets and house-number addresses from OpenStreetMap XML.

The XML is what both Overpass (`out:xml`) and the main OSM API (`/map`) return.
"""

from __future__ import annotations

from dataclasses import dataclass

from lxml import etree
from shapely.geometry import LineString, MultiPoint, Point

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


def _root(xml: bytes) -> etree._Element:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    try:
        root = etree.fromstring(xml, parser)
    except etree.XMLSyntaxError as e:
        raise OsmError(f"OpenStreetMap answer is not valid XML: {e}") from None
    if root.tag != "osm":
        raise OsmError(f"OpenStreetMap answer is not OSM XML (root <{root.tag}>)")
    return root


def _nodes(root: etree._Element) -> dict[str, tuple[float, float]]:
    nodes: dict[str, tuple[float, float]] = {}
    for n in root.iter("node"):
        lat, lon = n.get("lat"), n.get("lon")
        if lat is not None and lon is not None:
            nodes[n.get("id", "")] = (float(lon), float(lat))
    return nodes


def parse(xml: bytes) -> list[OsmStreet]:
    """Named streets (ways with `highway` and a name)."""
    root = _root(xml)
    nodes = _nodes(root)

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


@dataclass
class OsmAddress:
    """An OSM address: a node (or the centre of a way) with `addr:housenumber`. Point in lon/lat."""

    housenumber: str
    street_ar: str | None  # `addr:street` (Arabic in Egypt)
    street_en: str | None  # `addr:street:en`
    district: str | None
    postcode: str | None
    point: Point


def parse_addresses(xml: bytes) -> list[OsmAddress]:
    root = _root(xml)
    nodes = _nodes(root)
    addresses: list[OsmAddress] = []
    for el in root:
        if el.tag not in ("node", "way"):
            continue
        tags = {t.get("k"): t.get("v") for t in el.iter("tag")}
        number = (tags.get("addr:housenumber") or "").strip()
        if not number:
            continue
        if el.tag == "node":
            if el.get("id", "") not in nodes:
                continue
            point = Point(nodes[el.get("id", "")])
        else:
            points = [nodes[ref] for nd in el.iter("nd") if (ref := nd.get("ref", "")) in nodes]
            if not points:
                continue
            point = MultiPoint(points).centroid
        addresses.append(
            OsmAddress(
                number,
                _clean(tags.get("addr:street")),
                _clean(tags.get("addr:street:en")),
                _clean(tags.get("addr:district") or tags.get("addr:suburb")),
                _clean(tags.get("addr:postcode")),
                point,
            )
        )
    return addresses


def _clean(value: str | None) -> str | None:
    return " ".join((value or "").split()) or None  # also folds non-breaking spaces from OSM
