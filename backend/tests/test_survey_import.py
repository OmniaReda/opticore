"""Survey Excel upload → background processing → survey rows linked to the drawing's Building IDs."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.rules import SurveyColumnRules
from tests import cad_samples as cs
from tests import survey_samples as ss
from tests.test_kml_import import file_state, new_project, upload


def survey(client: TestClient, pid: str) -> dict[str, Any]:
    r = client.get(f"/projects/{pid}/survey")
    assert r.status_code == 200, r.text
    return r.json()


def test_survey_rows_are_read_by_header_name(client: TestClient) -> None:
    pid = new_project(client)
    f = upload(client, pid, "مسح ميداني.xlsx", ss.workbook_bytes())

    state = file_state(client, pid, f["id"])
    assert state["status"] == "processed", state
    assert state["note"] == (
        "Sheet 'Survey' · 6 rows · 1 rows without ID skipped · GPS missing on 1 rows, invalid on 1"
        " · unreadable cells: Floors (excl. GF) (1)"
    )

    layer = survey(client, pid)
    assert layer["source_file_id"] == f["id"]
    assert layer["provisional"] is True
    assert layer["has_drawing"] is False
    assert [r["code"] for r in layer["records"]] == ["1", "3", "3-2", "5", "6", "7"]  # natural order
    first = layer["records"][0]
    assert first["row_number"] == 2
    assert first["visit_date"] == "2026-01-05"
    assert first["street_name"] == "شارع تجريبي"  # whitespace normalised, Arabic kept
    assert (first["floors"], first["users_per_floor"], first["gf_users"], first["total_users"]) == (4, 2, 2, 10)
    assert first["latitude"] == pytest.approx(ss.LAT)
    by_code = {r["code"]: r for r in layer["records"]}
    assert (by_code["3-2"]["floors"], by_code["3-2"]["total_users"]) == (5, 5)  # numbers typed as text
    assert by_code["3"]["building_number"] == "171"
    assert by_code["6"]["floors"] is None  # 'many' → unreadable, row kept
    assert layer["summary"]["missing_gps"] == 2  # '7' no GPS, '5' invalid latitude
    assert layer["summary"]["total_users"] == 10 + 5 + 3 + 2


def test_personal_data_is_not_imported(client: TestClient) -> None:
    pid = new_project(client)
    upload(client, pid, "survey.xlsx", ss.workbook_bytes())
    assert ss.PERSONAL_NAME not in client.get(f"/projects/{pid}/survey").text


def test_survey_linked_to_drawing(client: TestClient) -> None:
    pid = new_project(client)
    upload(client, pid, "drawing.dxf", cs.drawing())
    upload(client, pid, "survey.xlsx", ss.workbook_bytes())
    layer = survey(client, pid)
    assert layer["has_drawing"] is True
    assert layer["summary"] | {"total_users": 0} == {
        "rows": 6,
        "in_drawing": 5,
        "not_in_drawing": 1,
        "drawing_ids_without_survey": 2,
        "missing_gps": 2,
        "total_users": 0,
    }
    assert layer["not_in_drawing"] == ["7"]
    assert layer["drawing_ids_without_survey"] == ["2", "9"]
    assert {r["code"]: r["in_drawing"] for r in layer["records"]}["7"] is False


def test_new_survey_replaces_old_and_delete_clears(client: TestClient) -> None:
    pid = new_project(client)
    first = upload(client, pid, "v1.xlsx", ss.workbook_bytes())
    second = upload(client, pid, "v2.xlsx", ss.workbook_bytes())
    assert "replaced survey from a previous file" in file_state(client, pid, second["id"])["note"]
    assert survey(client, pid)["summary"]["rows"] == 6  # not doubled

    client.delete(f"/projects/{pid}/files/{first['id']}")
    assert survey(client, pid)["summary"]["rows"] == 6
    client.delete(f"/projects/{pid}/files/{second['id']}")
    layer = survey(client, pid)
    assert layer["records"] == [] and layer["source_file_id"] is None


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (ss.workbook_bytes(sheet="Sheet1"), "Sheet 'Survey' not found. Sheets in this file: Sheet1, Daily"),
        (ss.workbook_bytes(drop_column=ss.COLUMNS["latitude"]), "Required columns not found: Building GPS N."),
        (b"not an excel file", "Not a readable Excel (.xlsx) file"),
    ],
)
def test_bad_survey_files_fail_with_clear_message(client: TestClient, content: bytes, message: str) -> None:
    pid = new_project(client)
    f = upload(client, pid, "survey.xlsx", content)
    state = file_state(client, pid, f["id"])
    assert state["status"] == "failed"
    assert message in state["error"]
    assert survey(client, pid)["records"] == []


def test_survey_rules_require_building_id() -> None:
    base: dict[str, Any] = {
        "source": "test",
        "approved_by": None,
        "status": "TBC",
        "sheet": "S",
        "header_row": 1,
        "columns": {"code": "ID", "latitude": "N"},
        "required": ["code", "latitude"],
    }
    SurveyColumnRules.model_validate(base)
    for broken in (
        {**base, "required": ["latitude"]},  # Building ID must be required
        {**base, "required": ["code", "longitude"]},  # required but not mapped
        {**base, "columns": {**base["columns"], "surveyor_name": "Surveyor"}},  # unknown field
    ):
        with pytest.raises(ValueError):
            SurveyColumnRules.model_validate(broken)
