"""The Streets & numbers Excel filled in the field (Floors, Total Users) and uploaded back.

Uses SAMPLE OSM data (tests.test_streets_export) — OpenStreetMap is never called. Box types are TEST values.
"""

import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app import rules
from app.services import streets
from tests import cad_samples as cs
from tests import kml_samples as ks
from tests import survey_samples as ss
from tests.test_kml_import import file_state, new_project, upload
from tests.test_streets_export import _osm_xml

TYPES = [{"name": "Test-16", "capacity": 16}]


@pytest.fixture
def pid(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(streets, "_download", lambda _bbox: _osm_xml())
    pid = new_project(client)
    upload(client, pid, "boundary.kml", ks.GOOGLE_EARTH_KML)  # only the boundary: no drawing
    return pid


def filled(client: TestClient, pid: str, values: dict[str, tuple[int | str | None, int | str | None]]) -> bytes:
    """The streets export with Floors / Total Users typed in for some house numbers."""
    wb = load_workbook(io.BytesIO(client.get(f"/projects/{pid}/export/streets").content))
    ws = wb["Addresses"]
    header = [c.value for c in ws[1]]
    cols = rules.survey_columns().columns
    f, u = header.index(cols["floors"]) + 1, header.index(cols["total_users"]) + 1
    for r, number in enumerate(ws.iter_rows(min_row=2, min_col=3, max_col=3, values_only=True), start=2):
        if isinstance(number[0], str) and number[0] in values:
            ws.cell(r, f, values[number[0]][0])
            ws.cell(r, u, values[number[0]][1])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_filled_streets_excel_becomes_address_points(client: TestClient, pid: str) -> None:
    content = filled(client, pid, {"12": (4, 10), "3": ("2", None), "7": (5, "x")})
    f = upload(client, pid, "streets.xlsx", content)
    state = file_state(client, pid, f["id"])
    assert state["status"] == "processed", state
    assert state["note"].startswith("Addresses (Streets & numbers): 3 rows with data · 10 users")
    assert "1 cells that are not whole numbers" in state["note"]

    layer = client.get(f"/projects/{pid}/addresses").json()
    assert layer["summary"] == {"rows": 3, "total_users": 10, "without_users": 2}
    twelve = next(p for p in layer["points"] if p["house_number"] == "12")
    assert (twelve["street_ar"], twelve["floors"], twelve["total_users"]) == ("شارع تجريبي", 4, 10)
    assert twelve["geometry"]["type"] == "Point"
    assert client.get(f"/projects/{pid}/survey").json()["summary"]["rows"] == 0  # the survey is not touched


def test_boxes_from_addresses_without_a_drawing(client: TestClient, pid: str) -> None:
    upload(client, pid, "streets.xlsx", filled(client, pid, {"12": (4, 10), "3": (2, 4), "7": (1, None)}))
    r = client.post(f"/projects/{pid}/network-boxes/design", json={"box_types": TYPES})
    assert r.status_code == 200, r.text
    design = r.json()
    assert design["source"] == "addresses"
    assert design["summary"]["users"] == 14
    assert design["summary"]["without_users"] == ["7 حارة جانبية"]
    [box] = design["boxes"]  # 12 and 3 are 50 m apart: one 16-user box without a drop limit
    assert box["users"] == 14
    assert sorted(c for s in box["served"] for c in s["codes"]) == ["12 شارع تجريبي", "3 شارع تجريبي"]

    xlsx = client.post(f"/projects/{pid}/network-boxes/design/xlsx", json={"box_types": TYPES})
    wb = load_workbook(io.BytesIO(xlsx.content))
    assert next(wb["Buildings"].iter_rows(values_only=True))[0] == "Address"


def test_drawing_and_survey_come_first(client: TestClient, pid: str) -> None:
    upload(client, pid, "streets.xlsx", filled(client, pid, {"12": (4, 10)}))
    upload(client, pid, "drawing.dxf", cs.drawing())
    upload(client, pid, "survey.xlsx", ss.workbook_bytes())
    design = client.post(f"/projects/{pid}/network-boxes/design", json={"box_types": TYPES}).json()
    assert design["source"] == "buildings"


def test_nothing_filled_in(client: TestClient, pid: str) -> None:
    f = upload(client, pid, "streets.xlsx", filled(client, pid, {}))
    state = file_state(client, pid, f["id"])
    assert state["status"] == "failed"
    assert "no row has" in state["error"]
    r = client.post(f"/projects/{pid}/network-boxes/design", json={"box_types": TYPES})
    assert r.status_code == 409 and "Streets & numbers" in r.json()["detail"]
