from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db import get_db
from app.main import app


def test_health_ok(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


class _BrokenSession:
    def execute(self, *_args: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))


def _broken_db() -> Iterator[_BrokenSession]:
    yield _BrokenSession()


def test_health_reports_unreachable_database(client: TestClient) -> None:
    app.dependency_overrides[get_db] = _broken_db
    try:
        r = client.get("/health")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503
    assert r.json() == {"status": "error", "database": "unreachable"}


def test_domain_errors_use_fastapi_error_shape(client: TestClient) -> None:
    r = client.get("/projects/00000000-0000-4000-8000-000000000000")
    assert r.status_code == 404
    assert r.json() == {"detail": "Project not found"}
