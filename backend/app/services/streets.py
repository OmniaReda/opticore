"""Streets inside the project boundary, with their OpenStreetMap names, as an Excel file.

Available as soon as the project KML gives a boundary (Stage 01). The OSM answer is cached on disk per
boundary file, so repeated downloads do not query OpenStreetMap again.
"""

import io
import logging
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from geoalchemy2.shape import to_shape
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

from app import geo, storage
from app.config import get_settings
from app.errors import ConflictError, ExternalServiceError
from app.importers import osm
from app.models import Project
from app.services.buildings import natural_key

log = logging.getLogger(__name__)

_USER_AGENT = "OPTICORE-prototype/0.1 (FTTH design tool)"
# The main OSM API refuses areas over 0.25 square degrees; stay well below and above it use Overpass only.
_MAX_API_BBOX_DEG2 = 0.05
ATTRIBUTION = "© OpenStreetMap contributors — data available under the Open Database License (ODbL)"


@dataclass
class StreetRow:
    name_ar: str
    name_en: str | None
    types: set[str] = field(default_factory=set)
    length_m: float = 0.0
    segments: int = 0


def _bbox(boundary: BaseGeometry) -> tuple[float, float, float, float]:
    """(south, west, north, east) with a small margin so streets on the boundary line are complete."""
    minx, miny, maxx, maxy = boundary.bounds
    pad = 0.0005  # ≈ 50 m
    return miny - pad, minx - pad, maxy + pad, maxx + pad


def _get(request: urllib.request.Request) -> bytes:
    with urllib.request.urlopen(request, timeout=get_settings().osm_timeout_s) as response:
        data: bytes = response.read()
    return data


def _download(bbox: tuple[float, float, float, float]) -> bytes:
    """OSM XML with named highways in the bbox: Overpass servers first, then the main API for small areas."""
    s, w, n, e = bbox
    bbox_q = f"({s},{w},{n},{e})"
    # Named streets + every element with a house number (the numbers shown on the OSM map), with their nodes.
    query = (
        f'[out:xml][timeout:25];(way["highway"]["name"]{bbox_q};node["addr:housenumber"]{bbox_q};'
        f'way["addr:housenumber"]{bbox_q};);(._;>;);out body;'
    )
    settings = get_settings()
    failures: list[str] = []
    for url in settings.osm_overpass_urls:
        body = urllib.parse.urlencode({"data": query}).encode()
        request = urllib.request.Request(url, data=body, headers={"User-Agent": _USER_AGENT})
        try:
            data = _get(request)
            if data.lstrip().startswith(b"<?xml") or data.lstrip().startswith(b"<osm"):
                return data
            failures.append(f"{urllib.parse.urlparse(url).hostname}: unexpected answer")
        except (urllib.error.URLError, TimeoutError, OSError) as ex:
            failures.append(f"{urllib.parse.urlparse(url).hostname}: {ex}")
    if settings.osm_api_map_url and (n - s) * (e - w) <= _MAX_API_BBOX_DEG2:
        url = f"{settings.osm_api_map_url}?bbox={w},{s},{e},{n}"
        try:
            return _get(urllib.request.Request(url, headers={"User-Agent": _USER_AGENT}))
        except (urllib.error.URLError, TimeoutError, OSError) as ex:
            failures.append(f"{urllib.parse.urlparse(url).hostname}: {ex}")
    log.warning("OpenStreetMap not reachable: %s", "; ".join(failures))
    raise ExternalServiceError("OpenStreetMap is not reachable right now (servers busy). Try again in a few minutes.")


def _cache_path(project: Project) -> Path:
    return storage.project_dir(project.id) / f"osm-v2-{project.boundary_file_id}.xml"  # v2: streets + addresses


def _osm_xml(project: Project, boundary: BaseGeometry) -> bytes:
    cache = _cache_path(project)
    if cache.is_file():
        return cache.read_bytes()
    data = _download(_bbox(boundary))
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(data)
    return data


def osm_streets(project: Project) -> list[osm.OsmStreet]:
    """All named OSM streets around the project boundary (cached). Raises ConflictError without boundary."""
    if project.boundary is None:
        raise ConflictError("Upload the project KML first: streets are taken inside the project boundary.")
    return osm.parse(_osm_xml(project, to_shape(project.boundary)))


@dataclass
class NearestStreet:
    name_ar: str
    name_en: str | None
    distance_m: float


class StreetFinder:
    """Nearest named street to a geometry, measured in UTM 36N metres."""

    def __init__(self, streets: list[osm.OsmStreet]) -> None:
        self._streets = streets
        self._lines = [geo.to_measure_crs(s.line) for s in streets]
        self._tree = STRtree(self._lines) if self._lines else None

    def nearest(self, geom: BaseGeometry) -> NearestStreet | None:
        if self._tree is None:
            return None
        utm = geo.to_measure_crs(geom)
        i = int(self._tree.nearest(utm))
        street = self._streets[i]
        return NearestStreet(street.name_ar, street.name_en, float(utm.distance(self._lines[i])))


def streets_in_boundary(project: Project) -> list[StreetRow]:
    """Named streets clipped to the boundary, grouped by name, longest first. Lengths in UTM 36N metres."""
    if project.boundary is None:
        raise ConflictError("Upload the project KML first: streets are taken inside the project boundary.")
    boundary = to_shape(project.boundary)
    rows: dict[tuple[str, str | None], StreetRow] = {}
    names_en: dict[str, set[str]] = defaultdict(set)
    for street in osm.parse(_osm_xml(project, boundary)):
        inside = street.line.intersection(boundary)
        if inside.is_empty or inside.length == 0:
            continue
        if street.name_en:
            names_en[street.name_ar].add(street.name_en)
        row = rows.setdefault((street.name_ar, None), StreetRow(street.name_ar, None))
        row.types.add(street.highway)
        row.length_m += geo.length_m(inside)
        row.segments += 1
    for row in rows.values():
        row.name_en = " / ".join(sorted(names_en.get(row.name_ar, set()))) or None
    return sorted(rows.values(), key=lambda r: (-r.length_m, r.name_ar))


@dataclass
class AddressRow:
    street_ar: str | None
    street_en: str | None
    housenumber: str
    district: str | None
    postcode: str | None
    lat: float
    lon: float
    street_source: str | None  # "OpenStreetMap address" | "nearest OSM street" | None


def addresses_in_boundary(project: Project) -> list[AddressRow]:
    """OSM house numbers inside the boundary, with their street (the address's own, else the nearest street)."""
    if project.boundary is None:
        raise ConflictError("Upload the project KML first: addresses are taken inside the project boundary.")
    boundary = to_shape(project.boundary)
    xml = _osm_xml(project, boundary)
    finder = StreetFinder(osm.parse(xml))
    rows: list[AddressRow] = []
    for a in osm.parse_addresses(xml):
        if not boundary.covers(a.point):
            continue
        street_ar, street_en, source = a.street_ar, a.street_en, "OpenStreetMap address" if a.street_ar else None
        if not street_ar and (nearest := finder.nearest(a.point)):
            street_ar, street_en, source = nearest.name_ar, nearest.name_en, "nearest OSM street"
        rows.append(
            AddressRow(
                street_ar,
                street_en,
                a.housenumber,
                a.district,
                a.postcode,
                round(a.point.y, 7),
                round(a.point.x, 7),
                source,
            )
        )
    return sorted(rows, key=lambda r: (r.street_ar or "~", natural_key(r.housenumber)))


def _header(ws: Worksheet, titles: list[str], widths: list[int]) -> None:
    ws.append(titles)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = "A2"


def to_xlsx(project: Project) -> bytes:
    """Sheets: Addresses (house numbers + street), Streets (names + length), Source (attribution)."""
    rows = streets_in_boundary(project)
    addresses = addresses_in_boundary(project)
    wb = Workbook()
    addr = wb.active
    assert addr is not None
    addr.title = "Addresses"
    _header(
        addr,
        [
            "Street (Arabic)",
            "Street (English)",
            "House number",
            "District",
            "Postcode",
            "Latitude",
            "Longitude",
            "Street from",
        ],
        [34, 34, 14, 26, 11, 13, 13, 22],
    )
    for a in addresses:
        addr.append([a.street_ar, a.street_en, a.housenumber, a.district, a.postcode, a.lat, a.lon, a.street_source])

    ws = wb.create_sheet("Streets")
    _header(
        ws,
        ["Street (Arabic)", "Street (English)", "Type", "Length in boundary (m)", "OSM segments", "House numbers"],
        [40, 40, 22, 22, 14, 15],
    )
    numbers = Counter(a.street_ar for a in addresses)
    for r in rows:
        ws.append(
            [
                r.name_ar,
                r.name_en,
                ", ".join(sorted(r.types)),
                round(r.length_m, 1),
                r.segments,
                numbers.get(r.name_ar, 0),
            ]
        )

    info = wb.create_sheet("Source")
    info.append(["Source", ATTRIBUTION])
    info.append(["Project", project.name])
    info.append(["House numbers", len(addresses)])
    info.append(["Streets", len(rows)])
    info.append(["Area", "OSM house numbers and named streets inside the project boundary"])
    info.append(["Note", "House numbers are street numbers (Building Number), not the drawing's Building IDs"])
    fetched = datetime.fromtimestamp(_cache_path(project).stat().st_mtime, UTC)
    info.append(["Downloaded", fetched.strftime("%Y-%m-%d")])
    info.column_dimensions["A"].width = 14
    info.column_dimensions["B"].width = 90

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
