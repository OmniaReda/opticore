"""The whole map as a survey sheet: one row per Building ID, template columns, street names filled in.

Uses the SAMPLE drawing (IDs 1, 2, 3, 3-2, 5, 6, orphan 9, one outline without ID), the SAMPLE survey
(IDs 1, 3, 3-2, 5, 6, 7; only row 1 has a street name) and SAMPLE OSM streets (never the real OSM).
"""

import io
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app import rules, storage
from app.errors import ExternalServiceError
from app.services import map_sheet, streets
from tests import cad_samples as cs
from tests import kml_samples as ks
from tests import survey_samples as ss
from tests.test_kml_import import file_state, new_project, upload
from tests.test_streets_export import _osm_xml


@pytest.fixture
def pid(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(streets, "_download", lambda _bbox: _osm_xml())
    pid = new_project(client)
    upload(client, pid, "boundary.kml", ks.GOOGLE_EARTH_KML)
    upload(client, pid, "drawing.dxf", cs.drawing())
    upload(client, pid, "survey.xlsx", ss.workbook_bytes())
    return pid


def sheet(client: TestClient, pid: str) -> tuple[dict[str | None, dict[str, Any]], list[tuple[Any, ...]], bytes]:
    r = client.get(f"/projects/{pid}/export/survey-sheet")
    assert r.status_code == 200, r.text
    assert 'filename="survey-sheet.xlsx"' in r.headers["content-disposition"]
    cfg = rules.survey_columns()
    wb = load_workbook(io.BytesIO(r.content))
    rows = list(wb[cfg.sheet].iter_rows(values_only=True))
    header = [str(h) for h in rows[cfg.header_row - 1]]
    assert list(header) == [*cfg.columns.values(), *map_sheet.EXTRA_COLUMNS]  # template columns first
    by_code: dict[str | None, dict[str, Any]] = {}
    for values in rows[cfg.header_row :]:
        code = values[0]
        by_code[None if code is None else str(code)] = dict(zip(header, values, strict=True))
    return by_code, list(wb["Instructions"].iter_rows(values_only=True)), r.content


def test_one_row_per_building_id_with_all_known_data(client: TestClient, pid: str) -> None:
    rows, info, _ = sheet(client, pid)
    col = rules.survey_columns().columns
    assert list(rows) == ["1", "2", "3", "3-2", "5", "6", "9", None, "7"]  # drawing order, no-ID, survey only

    one = rows["1"]  # on the drawing and in the survey (with a street name)
    assert one[col["street_name"]] == "شارع تجريبي"
    assert one["Street source"] == "survey"
    assert (one[col["floors"]], one[col["total_users"]]) == (4, 10)
    assert one[col["latitude"]] == pytest.approx(ss.LAT)
    assert one["Drawing review"] == "One ID"
    assert one["Area (m²)"] == pytest.approx(200, abs=0.5)

    two = rows["2"]  # on the drawing only → street from the nearest OSM street, GPS from the drawing
    assert two[col["street_name"]] == "Test St."
    assert two["Street source"] == "OpenStreetMap"
    assert two["OSM street (Arabic)"] == "شارع تجريبي"
    assert two["Distance to OSM street (m)"] == pytest.approx(30, abs=0.5)
    assert 30 < two[col["latitude"]] < 31 and 31 < two[col["longitude"]] < 32
    assert two[col["total_users"]] is None

    assert rows["3-2"]["Drawing review"] == "Several IDs in one outline"
    assert rows["9"]["Drawing review"] == "ID outside any building"
    assert rows[None]["Drawing review"] == "No ID"
    assert rows["7"]["Drawing review"] == "Survey only (ID not on the drawing)"
    assert ss.PERSONAL_NAME not in str(rows)

    text = " ".join(str(c) for r in info for c in r if c)
    assert "OpenStreetMap contributors" in text


def test_sheet_can_be_uploaded_back_as_the_survey(client: TestClient, pid: str) -> None:
    _, _, content = sheet(client, pid)
    f = upload(client, pid, "survey-sheet.xlsx", content)
    state = file_state(client, pid, f["id"])
    assert state["status"] == "processed", state
    assert "8 rows" in state["note"]  # the outline without an ID has no row to import
    records = {r["code"]: r for r in client.get(f"/projects/{pid}/survey").json()["records"]}
    assert records["2"]["street_name"] == "Test St."


def test_without_openstreetmap_streets_come_from_the_survey(
    client: TestClient, pid: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def down(_bbox: Any) -> bytes:
        raise ExternalServiceError("busy")

    monkeypatch.setattr(streets, "_download", down)
    monkeypatch.setattr(streets, "_cache_path", lambda _p: storage.project_dir(_p.id) / "none.xml")
    rows, info, _ = sheet(client, pid)
    col = rules.survey_columns().columns
    assert rows["1"][col["street_name"]] == "شارع تجريبي"
    assert rows["2"][col["street_name"]] is None
    assert "not reachable" in " ".join(str(c) for r in info for c in r if c)


def test_needs_a_drawing(client: TestClient) -> None:
    pid = new_project(client)
    r = client.get(f"/projects/{pid}/export/survey-sheet")
    assert r.status_code == 409
    assert r.json()["detail"].startswith("Upload the drawing")
