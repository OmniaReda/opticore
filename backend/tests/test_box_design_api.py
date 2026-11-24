"""Network Box design API on the SAMPLE drawing + SAMPLE survey. Box types are TEST values, not real ones.

Sample users per building: 1 → 10 · (3, 3-2) → 3 + 5 = 8 · 2 and 5 → no Total Users · 6 → outside the
boundary · one outline without ID. Buildings 1 and (3, 3-2) are 50 m apart.
"""

import io

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from tests import cad_samples as cs
from tests import kml_samples as ks
from tests import survey_samples as ss
from tests.test_kml_import import new_project, upload

TYPES = [{"name": "Test-16", "capacity": 16}, {"name": "Test-8", "capacity": 8}]


def project(client: TestClient, with_problems: bool = False) -> str:
    pid = new_project(client)
    upload(client, pid, "boundary.kml", ks.GOOGLE_EARTH_KML)
    upload(client, pid, "drawing.dxf", cs.drawing())
    upload(client, pid, "survey.xlsx", ss.workbook_bytes(with_problems=with_problems))
    return pid


def test_boxes_sized_by_survey_users(client: TestClient) -> None:
    pid = project(client)
    r = client.post(f"/projects/{pid}/network-boxes/design", json={"box_types": TYPES})
    assert r.status_code == 200, r.text
    design = r.json()
    assert design["provisional"] is True
    boxes = design["boxes"]
    # 10 + 8 do not fit in one 16-user box → two boxes, each the smallest type that holds its users
    assert [(b["label"], b["host_codes"], b["box_type"], b["users"]) for b in boxes] == [
        ("NB-001", ["1"], "Test-16", 10),
        ("NB-002", ["3", "3-2"], "Test-8", 8),
    ]
    assert boxes[0]["served"][0]["distance_m"] == 0
    assert boxes[0]["geometry"]["type"] == "Point"
    s = design["summary"]
    assert (s["boxes"], s["users"], s["buildings_served"]) == (2, 18, 2)
    assert [(t["box_type"], t["count"]) for t in s["by_type"]] == [("Test-8", 1), ("Test-16", 1)]
    assert (s["without_users"], s["without_id"], s["outside_skipped"]) == (["2", "5"], 1, 1)


def test_one_box_when_they_fit_and_drop_limit(client: TestClient) -> None:
    pid = project(client)
    big = [{"name": "Test-32", "capacity": 32}]
    one = client.post(f"/projects/{pid}/network-boxes/design", json={"box_types": big}).json()
    assert [b["users"] for b in one["boxes"]] == [18]
    assert one["summary"]["longest_drop_m"] > 40
    split = client.post(f"/projects/{pid}/network-boxes/design", json={"box_types": big, "max_drop_m": 20}).json()
    assert len(split["boxes"]) == 2


def test_outside_buildings_on_request(client: TestClient) -> None:
    pid = project(client, with_problems=True)  # adds users on 2 (9) and on 6 (4, outside)
    body = {"box_types": TYPES, "include_outside": True}
    s = client.post(f"/projects/{pid}/network-boxes/design", json=body).json()["summary"]
    assert (s["buildings_served"], s["users"], s["outside_skipped"]) == (4, 31, 0)


def test_excel(client: TestClient) -> None:
    pid = project(client)
    r = client.post(f"/projects/{pid}/network-boxes/design/xlsx", json={"box_types": TYPES, "max_drop_m": 60})
    assert r.status_code == 200, r.text
    assert 'filename="network-boxes.xlsx"' in r.headers["content-disposition"]
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Boxes", "Buildings", "Not served", "Settings"]
    boxes = list(wb["Boxes"].iter_rows(values_only=True))
    assert boxes[1][:7] == ("NB-001", "Test-16", 16, 16, 10, 6, "1")
    buildings = list(wb["Buildings"].iter_rows(values_only=True))
    assert [row[:3] for row in buildings[1:]] == [("1", 10, "NB-001"), ("3, 3-2", 8, "NB-002")]
    settings = " ".join(str(c) for row in wb["Settings"].iter_rows(values_only=True) for c in row if c)
    assert "PROVISIONAL" in settings and "Test-8: 8 users" in settings and "60" in settings


def test_needs_drawing_and_survey(client: TestClient) -> None:
    pid = new_project(client)
    r = client.post(f"/projects/{pid}/network-boxes/design", json={"box_types": TYPES})
    assert r.status_code == 409 and "drawing" in r.json()["detail"]
    upload(client, pid, "drawing.dxf", cs.drawing())
    r = client.post(f"/projects/{pid}/network-boxes/design", json={"box_types": TYPES})
    assert r.status_code == 409 and "survey" in r.json()["detail"]


def test_bad_values(client: TestClient) -> None:
    pid = project(client)
    url = f"/projects/{pid}/network-boxes/design"
    assert client.post(url, json={"box_types": []}).status_code == 422
    twice = [{"name": "A", "capacity": 8}, {"name": "a", "capacity": 16}]
    assert client.post(url, json={"box_types": twice}).status_code == 422
    r = client.post(url, json={"box_types": [{"name": "A", "capacity": 1}], "spare_percent": 50})
    assert r.status_code == 422 and "usable" in r.json()["detail"]


def test_defaults_are_empty_until_the_design_team_confirms(client: TestClient) -> None:
    d = client.get("/network-boxes/defaults").json()
    assert d["provisional"] is True
    assert d["box_types"] == [] and d["max_drop_m"] is None
