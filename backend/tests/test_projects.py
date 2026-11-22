import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import get_engine

ARABIC_NAME = "مشروع تجريبي 2026"


def create(client: TestClient, **body) -> dict:
    r = client.post("/projects", json={"name": ARABIC_NAME, **body})
    assert r.status_code == 201, r.text
    return r.json()


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_create_with_arabic_name_round_trips(client: TestClient) -> None:
    p = create(client, description="وصف تجريبي بالعربي & رموز")
    assert p["name"] == ARABIC_NAME
    assert p["status"] == "draft"
    assert p["file_count"] == 0

    got = client.get(f"/projects/{p['id']}").json()
    assert got["name"] == ARABIC_NAME
    assert got["description"] == "وصف تجريبي بالعربي & رموز"

    # Stored as real UTF-8 text in Postgres, not escaped.
    with get_engine().connect() as conn:
        assert conn.scalar(text("SELECT name FROM project WHERE id = :id"), {"id": p["id"]}) == ARABIC_NAME


def test_name_is_trimmed_and_required(client: TestClient) -> None:
    assert create(client, name="  Sample  ")["name"] == "Sample"
    assert client.post("/projects", json={"name": "   "}).status_code == 422
    assert client.post("/projects", json={}).status_code == 422
    assert client.post("/projects", json={"name": "x" * 201}).status_code == 422


def test_list_newest_first(client: TestClient) -> None:
    a = create(client, name="A")
    b = create(client, name="B")
    ids = [p["id"] for p in client.get("/projects").json()]
    assert ids == [b["id"], a["id"]]


def test_partial_update(client: TestClient) -> None:
    p = create(client, description="keep me")
    r = client.patch(f"/projects/{p['id']}", json={"status": "active"})
    assert r.status_code == 200
    assert r.json()["status"] == "active"
    assert r.json()["name"] == ARABIC_NAME
    assert r.json()["description"] == "keep me"

    r = client.patch(f"/projects/{p['id']}", json={"description": None})
    assert r.json()["description"] is None


def test_update_rejects_bad_values(client: TestClient) -> None:
    p = create(client)
    assert client.patch(f"/projects/{p['id']}", json={"status": "done"}).status_code == 422
    assert client.patch(f"/projects/{p['id']}", json={"name": None}).status_code == 422
    assert client.patch(f"/projects/{p['id']}", json={"status": None}).status_code == 422


def test_missing_project_is_404(client: TestClient) -> None:
    missing = uuid.uuid4()
    assert client.get(f"/projects/{missing}").status_code == 404
    assert client.patch(f"/projects/{missing}", json={"name": "x"}).status_code == 404
    assert client.delete(f"/projects/{missing}").status_code == 404


def test_delete(client: TestClient) -> None:
    p = create(client)
    assert client.delete(f"/projects/{p['id']}").status_code == 204
    assert client.get(f"/projects/{p['id']}").status_code == 404
    assert client.get("/projects").json() == []
