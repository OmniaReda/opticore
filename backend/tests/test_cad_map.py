"""AutoCAD street map (DXF) on SAMPLE data — OpenStreetMap is never called. Box types are TEST values."""

import io
from typing import Any

import pytest
from ezdxf.document import Drawing
from ezdxf.entities.lwpolyline import LWPolyline
from ezdxf.filemanagement import read as read_stream
from fastapi.testclient import TestClient

from app import storage
from app.errors import ExternalServiceError
from app.services import streets
from tests import cad_samples as cs
from tests import kml_samples as ks
from tests import survey_samples as ss
from tests.test_address_import import filled
from tests.test_kml_import import new_project, upload
from tests.test_streets_export import _osm_xml

TYPES = [{"name": "Test-16", "capacity": 16}]


@pytest.fixture
def pid(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(streets, "_download", lambda _bbox: _osm_xml())
    pid = new_project(client)
    upload(client, pid, "boundary.kml", ks.GOOGLE_EARTH_KML)
    return pid


def read_dxf(content: bytes) -> Drawing:
    return read_stream(io.StringIO(content.decode("utf-8")))


def texts(doc: Drawing, layer: str) -> list[str]:
    return [str(e.dxf.text) for e in doc.modelspace().query(f'TEXT[layer=="{layer}"]')]


def count(doc: Drawing, query: str) -> int:
    return len(doc.modelspace().query(query))


def test_street_map_from_the_kml_only(client: TestClient, pid: str) -> None:
    r = client.get(f"/projects/{pid}/export/street-map-dxf")
    assert r.status_code == 200, r.text
    assert 'filename="street-map.dxf"' in r.headers["content-disposition"]
    doc = read_dxf(r.content)
    assert doc.header["$INSUNITS"] == 6  # metres

    [boundary] = doc.modelspace().query('LWPOLYLINE[layer=="OPTICORE_BOUNDARY"]')
    assert isinstance(boundary, LWPolyline)
    x, y = boundary.get_points("xy")[0]
    assert abs(x - ks._X0) < 1 and abs(y - ks._Y0) < 1  # UTM 36N metres, not degrees

    assert count(doc, 'LWPOLYLINE[layer=="OSM_STREETS"]') == 3  # 2 segments + the one crossing the edge
    assert set(texts(doc, "OSM_STREET_NAMES_AR")) == {"شارع تجريبي", "حارة جانبية"}
    assert texts(doc, "OSM_STREET_NAMES_EN") == ["Test St."]
    assert sorted(texts(doc, "OSM_HOUSE_NUMBERS")) == ["12", "3", "7"]
    assert count(doc, 'POINT[layer=="OSM_HOUSE_NUMBERS"]') == 3
    assert texts(doc, "FIELD_DATA") == [] and texts(doc, "NETWORK_BOXES") == []


def test_field_data_and_drawing_buildings(client: TestClient, pid: str) -> None:
    upload(client, pid, "streets.xlsx", filled(client, pid, {"12": (4, 10), "3": (2, None)}))
    upload(client, pid, "drawing.dxf", cs.drawing())
    doc = read_dxf(client.get(f"/projects/{pid}/export/street-map-dxf").content)
    assert sorted(texts(doc, "FIELD_DATA")) == ["F2", "F4 U10"]
    assert count(doc, 'LWPOLYLINE[layer=="DRAWING_BUILDINGS"]') == 6  # the 1 m square is dropped as noise


def test_box_design_in_autocad(client: TestClient, pid: str) -> None:
    upload(client, pid, "drawing.dxf", cs.drawing())
    upload(client, pid, "survey.xlsx", ss.workbook_bytes())
    r = client.post(f"/projects/{pid}/network-boxes/design/dxf", json={"box_types": TYPES})
    assert r.status_code == 200, r.text
    assert 'filename="network-boxes.dxf"' in r.headers["content-disposition"]
    doc = read_dxf(r.content)
    assert sorted(texts(doc, "NETWORK_BOXES")) == ["NB-001 Test-16 10/16", "NB-002 Test-16 8/16"]
    assert count(doc, 'LWPOLYLINE[layer=="NETWORK_BOXES"]') == 2
    assert texts(doc, "OSM_STREET_NAMES_AR")  # over the street map


def test_box_design_without_openstreetmap(client: TestClient, pid: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def down(_bbox: Any) -> bytes:
        raise ExternalServiceError("busy")

    monkeypatch.setattr(streets, "_download", down)
    monkeypatch.setattr(streets, "_cache_path", lambda p: storage.project_dir(p.id) / "none.xml")
    upload(client, pid, "drawing.dxf", cs.drawing())
    upload(client, pid, "survey.xlsx", ss.workbook_bytes())
    r = client.post(f"/projects/{pid}/network-boxes/design/dxf", json={"box_types": TYPES})
    assert r.status_code == 200
    assert texts(read_dxf(r.content), "NETWORK_BOXES")
    assert client.get(f"/projects/{pid}/export/street-map-dxf").status_code == 502


def test_needs_a_boundary(client: TestClient) -> None:
    pid = new_project(client)
    r = client.get(f"/projects/{pid}/export/street-map-dxf")
    assert r.status_code == 409 and "KML" in r.json()["detail"]
