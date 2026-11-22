import hashlib
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

KML = b'<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"/>'


def new_project(client: TestClient) -> str:
    return client.post("/projects", json={"name": "مشروع تجريبي"}).json()["id"]


def upload(client: TestClient, pid: str, name: str, content: bytes = KML):
    return client.post(f"/projects/{pid}/files", files={"file": (name, content)})


def test_upload_arabic_filename(client: TestClient, storage_dir: Path) -> None:
    pid = new_project(client)
    r = upload(client, pid, "حدود المنطقة.KML")
    assert r.status_code == 201, r.text
    f = r.json()
    assert f["kind"] == "kml"
    assert f["original_filename"] == "حدود المنطقة.KML"
    assert f["size_bytes"] == len(KML)
    assert f["sha256"] == hashlib.sha256(KML).hexdigest()
    assert f["status"] == "uploaded"

    # Stored under a safe name (file id), content intact.
    stored = storage_dir / "projects" / pid / f"{f['id']}.kml"
    assert stored.read_bytes() == KML

    assert [x["id"] for x in client.get(f"/projects/{pid}/files").json()] == [f["id"]]
    assert client.get(f"/projects/{pid}").json()["file_count"] == 1
    assert client.get("/projects").json()[0]["file_count"] == 1


def test_kind_detected_from_extension(client: TestClient) -> None:
    pid = new_project(client)
    expected = {"a.kmz": "kmz", "b.dxf": "dxf", "c.dwg": "dwg", "survey.xlsx": "survey_xlsx", "map.pdf": "other"}
    for name, kind in expected.items():
        assert upload(client, pid, name, b"x").json()["kind"] == kind


def test_rejects_unsupported_type(client: TestClient, storage_dir: Path) -> None:
    pid = new_project(client)
    for name in ("virus.exe", "noextension", "old.xls"):
        assert upload(client, pid, name, b"x").status_code == 415
    assert client.get(f"/projects/{pid}/files").json() == []
    assert not any((storage_dir / "projects" / pid).glob("*"))


def test_rejects_empty_file(client: TestClient, storage_dir: Path) -> None:
    pid = new_project(client)
    assert upload(client, pid, "empty.kml", b"").status_code == 400
    assert not any((storage_dir / "projects" / pid).glob("*"))


def test_rejects_too_large(client: TestClient, storage_dir: Path) -> None:
    pid = new_project(client)  # limit is 1 MB in tests
    assert upload(client, pid, "big.dxf", b"0" * (1024 * 1024 + 1)).status_code == 413
    assert not any((storage_dir / "projects" / pid).glob("*"))


def test_upload_to_missing_project(client: TestClient) -> None:
    assert upload(client, str(uuid.uuid4()), "a.kml").status_code == 404


def test_delete_file(client: TestClient, storage_dir: Path) -> None:
    pid = new_project(client)
    fid = upload(client, pid, "a.kml").json()["id"]
    assert client.delete(f"/projects/{pid}/files/{fid}").status_code == 204
    assert client.get(f"/projects/{pid}/files").json() == []
    assert not (storage_dir / "projects" / pid / f"{fid}.kml").exists()
    assert client.delete(f"/projects/{pid}/files/{fid}").status_code == 404


def test_cannot_delete_file_via_other_project(client: TestClient) -> None:
    a, b = new_project(client), new_project(client)
    fid = upload(client, a, "a.kml").json()["id"]
    assert client.delete(f"/projects/{b}/files/{fid}").status_code == 404
    assert len(client.get(f"/projects/{a}/files").json()) == 1


def test_delete_project_removes_files(client: TestClient, storage_dir: Path) -> None:
    pid = new_project(client)
    upload(client, pid, "a.kml")
    upload(client, pid, "b.dxf", b"0")
    assert client.delete(f"/projects/{pid}").status_code == 204
    assert not (storage_dir / "projects" / pid).exists()
    assert client.get(f"/projects/{pid}/files").status_code == 404
