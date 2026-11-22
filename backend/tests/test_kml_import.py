"""KML/KMZ upload → background processing → boundary + features on the project map."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests import kml_samples as s


def new_project(client: TestClient) -> str:
    return client.post("/projects", json={"name": "مشروع تجريبي"}).json()["id"]


def upload(client: TestClient, pid: str, name: str, content: bytes) -> dict[str, Any]:
    r = client.post(f"/projects/{pid}/files", files={"file": (name, content)})
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "processing"  # response is sent before the background job runs
    return r.json()


def file_state(client: TestClient, pid: str, fid: str) -> dict[str, Any]:
    return next(f for f in client.get(f"/projects/{pid}/files").json() if f["id"] == fid)


def test_kml_sets_boundary_and_features(client: TestClient) -> None:
    pid = new_project(client)
    f = upload(client, pid, "حدود المنطقة.kml", s.GOOGLE_EARTH_KML)

    state = file_state(client, pid, f["id"])
    assert state["status"] == "processed", state
    assert state["error"] is None
    assert "1 polygon, 6.0 ha, perimeter 1.00 km" in state["note"]
    assert "1 point" in state["note"]

    layers = client.get(f"/projects/{pid}/layers").json()
    b = layers["boundary"]
    assert b["geometry"]["type"] == "MultiPolygon"
    assert b["source_file_id"] == f["id"]
    assert b["area_m2"] == pytest.approx(s.RECT_AREA_M2, abs=0.5)
    assert b["perimeter_m"] == pytest.approx(s.RECT_PERIMETER_M, abs=0.5)
    assert [(x["name"], x["geometry"]["type"]) for x in layers["features"]] == [(s.POINT_NAME, "Point")]
    assert len(layers["features"][0]["geometry"]["coordinates"]) == 2  # 2D

    assert client.get(f"/projects/{pid}").json()["has_boundary"] is True


def test_kmz_upload(client: TestClient) -> None:
    pid = new_project(client)
    f = upload(client, pid, "area.KMZ", s.kmz(s.GOOGLE_EARTH_KML))
    assert file_state(client, pid, f["id"])["status"] == "processed"
    assert client.get(f"/projects/{pid}/layers").json()["boundary"] is not None


def test_file_without_polygon_keeps_boundary(client: TestClient) -> None:
    pid = new_project(client)
    upload(client, pid, "boundary.kml", s.GOOGLE_EARTH_KML)
    f = upload(client, pid, "cad export.kml", s.CAD_EXPORT_KML)

    state = file_state(client, pid, f["id"])
    assert state["status"] == "processed"
    assert "No boundary polygon" in state["note"]
    assert "2 lines" in state["note"] and "1 empty/degenerate" in state["note"]

    layers = client.get(f"/projects/{pid}/layers").json()
    assert layers["boundary"] is not None
    assert sorted(x["geometry"]["type"] for x in layers["features"]) == ["LineString", "LineString", "Point"]


@pytest.mark.parametrize(
    "content, message",
    [
        (s.INVALID_POLYGON_KML, "is invalid"),
        (s.EMPTY_KML, "No geometry"),
        (b"<html>oops</html>", "root element is not <kml>"),
    ],
)
def test_bad_files_fail_with_reason(client: TestClient, content: bytes, message: str) -> None:
    pid = new_project(client)
    f = upload(client, pid, "bad.kml", content)
    state = file_state(client, pid, f["id"])
    assert state["status"] == "failed"
    assert message in state["error"]
    assert state["note"] is None
    layers = client.get(f"/projects/{pid}/layers").json()
    assert layers == {"boundary": None, "features": []}


def test_new_boundary_replaces_old(client: TestClient) -> None:
    pid = new_project(client)
    upload(client, pid, "v1.kml", s.GOOGLE_EARTH_KML)
    f2 = upload(client, pid, "v2.kml", s.GOOGLE_EARTH_KML)
    assert "replaced previous boundary" in file_state(client, pid, f2["id"])["note"]
    assert client.get(f"/projects/{pid}/layers").json()["boundary"]["source_file_id"] == f2["id"]


def test_reprocess_is_idempotent(client: TestClient) -> None:
    pid = new_project(client)
    f = upload(client, pid, "a.kml", s.GOOGLE_EARTH_KML)
    r = client.post(f"/projects/{pid}/files/{f['id']}/process")
    assert r.status_code == 202
    assert file_state(client, pid, f["id"])["status"] == "processed"
    assert "replaced" not in file_state(client, pid, f["id"])["note"]
    assert len(client.get(f"/projects/{pid}/layers").json()["features"]) == 1


def test_process_rejects_files_without_importer(client: TestClient) -> None:
    pid = new_project(client)
    fid = client.post(f"/projects/{pid}/files", files={"file": ("map.pdf", b"%PDF")}).json()["id"]
    assert client.post(f"/projects/{pid}/files/{fid}/process").status_code == 409


def test_deleting_source_file_removes_its_boundary_and_features(client: TestClient) -> None:
    pid = new_project(client)
    f = upload(client, pid, "a.kml", s.GOOGLE_EARTH_KML)
    assert client.delete(f"/projects/{pid}/files/{f['id']}").status_code == 204
    assert client.get(f"/projects/{pid}/layers").json() == {"boundary": None, "features": []}
    assert client.get(f"/projects/{pid}").json()["has_boundary"] is False


def test_delete_project_with_boundary(client: TestClient) -> None:
    pid = new_project(client)
    upload(client, pid, "a.kml", s.GOOGLE_EARTH_KML)
    assert client.delete(f"/projects/{pid}").status_code == 204
    assert client.get(f"/projects/{pid}/layers").status_code == 404
