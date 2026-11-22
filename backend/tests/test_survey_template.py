"""Survey template download: same columns the importer reads, and it can be filled and imported back."""

import io

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app import rules
from tests.test_kml_import import file_state, new_project, upload


def test_template_has_the_configured_columns(client: TestClient) -> None:
    r = client.get("/survey/template")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml")
    assert 'filename="survey-template.xlsx"' in r.headers["content-disposition"]

    cfg = rules.survey_columns()
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == [cfg.sheet, "Instructions"]
    header = [c.value for c in wb[cfg.sheet][cfg.header_row]]
    assert header == list(cfg.columns.values())
    required = {c.value for c in wb[cfg.sheet][cfg.header_row] if c.comment is not None}
    assert required == {cfg.columns[f] for f in cfg.required}


def test_filled_template_imports(client: TestClient) -> None:
    cfg = rules.survey_columns()
    wb = load_workbook(io.BytesIO(client.get("/survey/template").content))
    ws = wb[cfg.sheet]
    values = {"code": "12-2", "latitude": 30.1, "longitude": 31.3, "floors": 3, "users_per_floor": 2, "total_users": 6}
    ws.append([values.get(f) for f in cfg.columns])
    buf = io.BytesIO()
    wb.save(buf)

    pid = new_project(client)
    f = upload(client, pid, "filled.xlsx", buf.getvalue())
    assert file_state(client, pid, f["id"])["status"] == "processed"
    rows = client.get(f"/projects/{pid}/survey").json()["records"]
    assert [(r["code"], r["floors"], r["total_users"]) for r in rows] == [("12-2", 3, 6)]
