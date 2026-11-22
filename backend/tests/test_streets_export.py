"""Streets export: OpenStreetMap street names inside the project boundary, as Excel.

OpenStreetMap is never called in tests: `_download` / `_get` are replaced by SAMPLE OSM XML (synthetic,
built in UTM around the KML test boundary, a 200 m × 300 m rectangle at X0, Y0).
"""

import io
import urllib.error
import urllib.request
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from pyproj import Transformer

from app.config import get_settings
from app.errors import ExternalServiceError
from app.importers import osm
from app.services import streets
from tests import kml_samples as ks
from tests.test_kml_import import new_project, upload

_to_wgs = Transformer.from_crs(32636, 4326, always_xy=True).transform


def _osm_xml() -> bytes:
    """Ways (UTM offsets from the boundary corner):
    'شارع تجريبي' / 'Test St.' — two segments fully inside: 160 m + 100 m
    'حارة جانبية' — crosses the top edge (y 300): 50 m inside
    'شارع بعيد' — outside · an unnamed highway · a named building (not a street)
    """
    nodes: list[str] = []
    ways: list[str] = []

    def way(wid: int, pts: list[tuple[float, float]], tags: dict[str, str]) -> None:
        refs = []
        for i, (dx, dy) in enumerate(pts):
            nid = wid * 10 + i
            lon, lat = _to_wgs(ks._X0 + dx, ks._Y0 + dy)
            nodes.append(f'<node id="{nid}" lat="{lat:.8f}" lon="{lon:.8f}"/>')
            refs.append(f'<nd ref="{nid}"/>')
        tag_xml = "".join(f'<tag k="{k}" v="{v}"/>' for k, v in tags.items())
        ways.append(f'<way id="{wid}">{"".join(refs)}{tag_xml}</way>')

    way(1, [(20, 50), (180, 50)], {"highway": "residential", "name": "شارع تجريبي", "name:en": "Test St."})
    way(2, [(20, 100), (120, 100)], {"highway": "residential", "name:ar": "شارع تجريبي", "name": "شارع تجريبي"})
    way(3, [(100, 250), (100, 350)], {"highway": "footway", "name": "حارة جانبية"})
    way(4, [(300, 50), (400, 50)], {"highway": "residential", "name": "شارع بعيد"})
    way(5, [(20, 150), (180, 150)], {"highway": "service"})
    way(6, [(30, 30), (40, 30), (40, 40)], {"building": "yes", "name": "مبنى"})
    # House numbers: with street · without street (nearest street fills it) · outside · on a building way.
    addr = [
        (900, 60, 55, {"addr:housenumber": "12", "addr:street": "شارع تجريبي", "addr:street:en": "Test St."}),
        (901, 100, 105, {"addr:housenumber": "3", "addr:district": "حي تجريبي"}),
        (902, 350, 60, {"addr:housenumber": "99", "addr:street": "شارع بعيد"}),
    ]
    for nid, dx, dy, tags in addr:
        lon, lat = _to_wgs(ks._X0 + dx, ks._Y0 + dy)
        tag_xml = "".join(f'<tag k="{k}" v="{v}"/>' for k, v in tags.items())
        nodes.append(f'<node id="{nid}" lat="{lat:.8f}" lon="{lon:.8f}">{tag_xml}</node>')
    way(
        7,
        [(140, 260), (150, 260), (150, 270), (140, 270)],
        {"building": "yes", "addr:housenumber": "7", "addr:street": "حارة جانبية"},
    )
    body = "".join(nodes) + "".join(ways)
    return f'<?xml version="1.0" encoding="UTF-8"?><osm version="0.6">{body}</osm>'.encode()


@pytest.fixture
def fake_osm(monkeypatch: pytest.MonkeyPatch) -> list[tuple[float, float, float, float]]:
    calls: list[tuple[float, float, float, float]] = []

    def download(bbox: tuple[float, float, float, float]) -> bytes:
        calls.append(bbox)
        return _osm_xml()

    monkeypatch.setattr(streets, "_download", download)
    return calls


def rows_of(content: bytes) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    wb = load_workbook(io.BytesIO(content))
    assert wb.sheetnames == ["Addresses", "Streets", "Source"]
    return tuple(list(wb[name].iter_rows(values_only=True)) for name in wb.sheetnames)  # type: ignore[return-value]


def test_streets_after_first_kml(client: TestClient, fake_osm: list[Any]) -> None:
    pid = new_project(client)
    upload(client, pid, "boundary.kml", ks.GOOGLE_EARTH_KML)  # the only file: just a boundary
    r = client.get(f"/projects/{pid}/export/streets")
    assert r.status_code == 200, r.text
    assert 'filename="streets.xlsx"' in r.headers["content-disposition"]

    addresses, rows, source = rows_of(r.content)
    assert addresses[0][:3] == ("Street (Arabic)", "Street (English)", "House number")
    by_number = {a[2]: a for a in addresses[1:]}
    assert set(by_number) == {"12", "3", "7"}  # '99' is outside the boundary
    assert by_number["12"][:3] == ("شارع تجريبي", "Test St.", "12")
    assert by_number["12"][7] == "OpenStreetMap address"
    assert by_number["3"][0] == "شارع تجريبي" and by_number["3"][7] == "nearest OSM street"  # 5 m away
    assert by_number["3"][3] == "حي تجريبي"
    assert by_number["7"][0] == "حارة جانبية"  # a building way with a number → its centre
    assert 30 < by_number["12"][5] < 31 and 31 < by_number["12"][6] < 32  # lat, lon

    assert rows[0] == (
        "Street (Arabic)",
        "Street (English)",
        "Type",
        "Length in boundary (m)",
        "OSM segments",
        "House numbers",
    )
    assert [row[:3] for row in rows[1:]] == [
        ("شارع تجريبي", "Test St.", "residential"),
        ("حارة جانبية", None, "footway"),
    ]
    assert rows[1][3] == pytest.approx(260, abs=1)  # measured in UTM, two segments summed
    assert rows[1][4] == 2
    assert rows[1][5] == 2  # house numbers on that street: 12 and 3
    assert rows[2][3] == pytest.approx(50, abs=1)  # clipped at the boundary
    assert "OpenStreetMap contributors" in str(source[0][1])  # ODbL attribution

    south, west, north, east = fake_osm[0]
    assert south < north and west < east and 29 < south < 31 and 31 < west < 32  # lat/lon bbox of the boundary


def test_osm_is_asked_once_per_boundary(client: TestClient, fake_osm: list[Any]) -> None:
    pid = new_project(client)
    upload(client, pid, "boundary.kml", ks.GOOGLE_EARTH_KML)
    for _ in range(2):
        assert client.get(f"/projects/{pid}/export/streets").status_code == 200
    assert len(fake_osm) == 1  # cached
    upload(client, pid, "new-boundary.kml", ks.GOOGLE_EARTH_KML)  # a new boundary file → asked again
    assert client.get(f"/projects/{pid}/export/streets").status_code == 200
    assert len(fake_osm) == 2


def test_needs_a_boundary(client: TestClient, fake_osm: list[Any]) -> None:
    pid = new_project(client)
    r = client.get(f"/projects/{pid}/export/streets")
    assert r.status_code == 409
    assert r.json()["detail"].startswith("Upload the project KML first")
    assert fake_osm == []


def test_osm_unreachable(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def down(_bbox: Any) -> bytes:
        raise ExternalServiceError("OpenStreetMap is not reachable right now (servers busy). Try again later.")

    monkeypatch.setattr(streets, "_download", down)
    pid = new_project(client)
    upload(client, pid, "boundary.kml", ks.GOOGLE_EARTH_KML)
    r = client.get(f"/projects/{pid}/export/streets")
    assert r.status_code == 502
    assert "not reachable" in r.json()["detail"]


# --- which OpenStreetMap server answers ---

BBOX = (30.10, 31.30, 30.11, 31.31)


def test_download_uses_next_server_then_main_api(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[str] = []

    def get(request: urllib.request.Request) -> bytes:
        asked.append(request.full_url.split("/")[2])
        if "overpass-a" in request.full_url:
            raise urllib.error.URLError("busy")
        if "overpass-b" in request.full_url:
            return b"<html>at capacity</html>"  # an error page is not data
        return b'<?xml version="1.0"?><osm/>'

    monkeypatch.setattr(streets, "_get", get)
    settings = get_settings()
    monkeypatch.setattr(settings, "osm_overpass_urls", ["https://overpass-a/api", "https://overpass-b/api"])
    monkeypatch.setattr(settings, "osm_api_map_url", "https://osm-api/map")
    assert streets._download(BBOX).endswith(b"<osm/>")
    assert asked == ["overpass-a", "overpass-b", "osm-api"]


def test_main_api_not_used_for_large_areas(monkeypatch: pytest.MonkeyPatch) -> None:
    def get(request: urllib.request.Request) -> bytes:
        raise urllib.error.URLError("busy")

    monkeypatch.setattr(streets, "_get", get)
    monkeypatch.setattr(get_settings(), "osm_overpass_urls", ["https://overpass-a/api"])
    with pytest.raises(ExternalServiceError):
        streets._download((30.0, 31.0, 30.5, 31.5))  # 0.25 square degrees


def test_parse_rejects_non_osm() -> None:
    with pytest.raises(osm.OsmError):
        osm.parse(b"<html>busy</html>")
    with pytest.raises(osm.OsmError):
        osm.parse(b"not xml")
