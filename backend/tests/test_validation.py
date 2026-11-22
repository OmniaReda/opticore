"""Stage 03 consistency report: drawing Building IDs vs survey Excel."""

import io
from typing import Any

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from tests import cad_samples as cs
from tests import survey_samples as ss
from tests.test_kml_import import new_project, upload

DRAWING_RULES = {"id_outside_building", "duplicate_drawing_id", "multiple_ids", "building_without_id"}


def report(client: TestClient, pid: str) -> dict[str, Any]:
    r = client.get(f"/projects/{pid}/validation")
    assert r.status_code == 200, r.text
    return r.json()


def counts(rep: dict[str, Any]) -> dict[str, int]:
    return {r["rule"]: r["count"] for r in rep["rules"]}


def issues(rep: dict[str, Any], rule: str) -> list[dict[str, Any]]:
    return [i for i in rep["issues"] if i["rule"] == rule]


def test_empty_project_has_no_checks(client: TestClient) -> None:
    rep = report(client, new_project(client))
    assert (rep["has_drawing"], rep["has_survey"], rep["rules"], rep["issues"]) == (False, False, [], [])
    assert rep["provisional"] is True
    assert rep["gps_max_distance_m"] == 25


def test_drawing_only_runs_drawing_checks(client: TestClient) -> None:
    pid = new_project(client)
    upload(client, pid, "drawing.dxf", cs.drawing())
    rep = report(client, pid)
    assert counts(rep) == {
        "id_outside_building": 1,
        "duplicate_drawing_id": 0,
        "multiple_ids": 1,
        "building_without_id": 1,
    }
    assert issues(rep, "id_outside_building")[0]["code"] == "9"
    assert issues(rep, "multiple_ids")[0]["message"] == "IDs 3, 3-2 are in one outline (missing dividing line?)"
    assert issues(rep, "building_without_id")[0]["message"] == "Outline of 200 m² has no Building ID"


def test_drawing_and_survey(client: TestClient) -> None:
    pid = new_project(client)
    upload(client, pid, "drawing.dxf", cs.drawing())
    upload(client, pid, "survey.xlsx", ss.workbook_bytes(with_problems=True))
    rep = report(client, pid)
    assert counts(rep) == {
        "id_outside_building": 1,
        "duplicate_drawing_id": 0,
        "survey_not_in_drawing": 1,
        "duplicate_survey_id": 1,
        "multiple_ids": 1,
        "drawing_id_without_survey": 1,
        "gps_missing": 2,
        "gps_far_from_building": 3,
        "total_users_formula": 1,
        "total_users_missing": 2,
        "building_without_id": 1,
        "home_pass_differs": 1,
        "needs_decision": 1,
    }
    # Errors first, then warnings, then info.
    order = {"error": 0, "warning": 1, "info": 2}
    severities = [order[i["severity"]] for i in rep["issues"]]
    assert severities == sorted(severities)

    assert [i["code"] for i in issues(rep, "survey_not_in_drawing")] == ["7"]
    assert [i["code"] for i in issues(rep, "drawing_id_without_survey")] == ["9"]
    assert [i["code"] for i in issues(rep, "duplicate_survey_id")] == ["6"]
    far = {i["code"]: i["message"] for i in issues(rep, "gps_far_from_building")}
    assert set(far) == {"3", "3-2", "6"}  # sample GPS is in building 1
    assert far["3"] == "GPS is 50 m from building 3 (limit 25 m)"  # measured in UTM, to the outline
    formula = issues(rep, "total_users_formula")[0]
    assert (formula["code"], formula["message"]) == ("2", "Total Users 9, but 3 × 2 + 1 = 7")
    assert formula["row_number"] == 10
    assert issues(rep, "needs_decision")[0]["message"] == "TE Comment: Delete · HP: Not Count"
    assert issues(rep, "home_pass_differs")[0]["message"] == "QTY of Home Pass 8, Total Users 9"

    point = issues(rep, "gps_far_from_building")[0]["geometry"]
    assert point["type"] == "Point" and 31 < point["coordinates"][0] < 32


def test_survey_only_skips_drawing_checks(client: TestClient) -> None:
    pid = new_project(client)
    upload(client, pid, "survey.xlsx", ss.workbook_bytes())
    rules = set(counts(report(client, pid)))
    assert not rules & (DRAWING_RULES | {"survey_not_in_drawing", "gps_far_from_building"})
    assert "gps_missing" in rules


def test_excel_export(client: TestClient) -> None:
    pid = new_project(client)
    upload(client, pid, "drawing.dxf", cs.drawing())
    upload(client, pid, "survey.xlsx", ss.workbook_bytes(with_problems=True))
    r = client.get(f"/projects/{pid}/validation/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml")
    assert 'filename="validation-report.xlsx"' in r.headers["content-disposition"]

    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Summary", "Issues"]
    issue_rows = list(wb["Issues"].iter_rows(values_only=True))
    assert issue_rows[0][:5] == ("Severity", "Check", "Building ID", "Survey row", "Details")
    assert len(issue_rows) - 1 == len(report(client, pid)["issues"])
    assert "مشروع تجريبي" in str(wb["Summary"]["A1"].value)  # project name, Arabic kept
