"""Project exports (KMZ / Excel / DXF), read back with the same libraries the importers use."""

import io
import zipfile

import pytest
from ezdxf import recover
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.importers import kml
from tests import cad_samples as cs
from tests import kml_samples as ks
from tests import survey_samples as ss
from tests.test_kml_import import new_project, upload


@pytest.fixture
def pid(client: TestClient) -> str:
    pid = new_project(client)
    upload(client, pid, "boundary.kml", ks.GOOGLE_EARTH_KML)
    upload(client, pid, "drawing.dxf", cs.drawing())
    upload(client, pid, "survey.xlsx", ss.workbook_bytes())
    return pid


def get(client: TestClient, pid: str, fmt: str, media_type: str, filename: str) -> bytes:
    r = client.get(f"/projects/{pid}/export/{fmt}")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith(media_type)
    assert f'filename="{filename}"' in r.headers["content-disposition"]
    return r.content


def test_kmz(client: TestClient, pid: str) -> None:
    content = get(client, pid, "kmz", "application/vnd.google-earth.kmz", "project.kmz")
    assert zipfile.ZipFile(io.BytesIO(content)).namelist() == ["doc.kml"]
    parsed = kml.load(content, is_kmz=True)  # our own importer reads it back
    names = [p.name for p in parsed.placemarks]
    assert names[0] == "Project boundary"
    assert {"1", "2", "3, 3-2", "5", "6", "No ID", "9"} <= set(names)
    building_1 = next(p for p in parsed.placemarks if p.name == "1")
    assert building_1.geometry.geom_type == "Polygon"
    assert building_1.geometry.area > 0
    assert b"Total Users" in zipfile.ZipFile(io.BytesIO(content)).read("doc.kml")


def test_xlsx(client: TestClient, pid: str) -> None:
    content = get(client, pid, "xlsx", "application/vnd.openxmlformats", "buildings.xlsx")
    wb = load_workbook(io.BytesIO(content))
    assert wb.sheetnames == ["Buildings", "IDs outside buildings"]
    rows = list(wb["Buildings"].iter_rows(values_only=True))
    assert rows[0][:4] == ("Building ID", "Review", "Boundary", "Area (m²)")
    by_id = {r[0]: r for r in rows[1:]}
    assert by_id["1"][1:4] == ("One ID", "inside", 200)
    assert by_id["1"][6:9] == ("شارع تجريبي", 4, 10)  # survey street, floors, users
    assert by_id["3, 3-2"][8] == 3 + 5  # users summed over both IDs
    assert by_id[None][1] == "No ID"
    assert [r[0] for r in wb["IDs outside buildings"].iter_rows(min_row=2, values_only=True)] == ["9"]


def test_dxf_is_utm_metres(client: TestClient, pid: str) -> None:
    content = get(client, pid, "dxf", "application/dxf", "project.dxf")
    path = io.BytesIO(content)
    doc, _ = recover.read(path)
    assert doc.header["$INSUNITS"] == 6
    msp = doc.modelspace()
    ok = msp.query('LWPOLYLINE[layer=="OPTICORE_BUILDING_OK"]')
    assert len(ok) == 4  # 1, 2, 5, 6
    x, y = ok[0].get_points("xy")[0]
    assert 300_000 < x < 400_000 and 3_300_000 < y < 3_400_000  # UTM 36N, not degrees
    assert len(msp.query('LWPOLYLINE[layer=="OPTICORE_BOUNDARY"]')) == 1
    ids = sorted(t.dxf.text for t in msp.query('TEXT[layer=="OPTICORE_BUILDING_ID"]'))
    assert ids == ["1", "2", "3, 3-2", "5", "6"]
    assert [t.dxf.text for t in msp.query('TEXT[layer=="OPTICORE_ID_OUTSIDE_BUILDING"]')] == ["9"]


def test_export_empty_project(client: TestClient) -> None:
    pid = new_project(client)
    for fmt in ("kmz", "xlsx", "dxf"):
        assert client.get(f"/projects/{pid}/export/{fmt}").status_code == 200
