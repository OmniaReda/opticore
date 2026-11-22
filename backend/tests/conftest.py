"""Tests run against a real PostGIS database `opticore_test` (created automatically)
on the docker-compose server. Start it first: `docker compose up -d db`."""

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

TEST_DB = "opticore_test"
SERVER = os.environ.get("OPTICORE_TEST_SERVER", "opticore:opticore_dev@localhost:5432")
os.environ["OPTICORE_DATABASE_URL"] = f"postgresql+psycopg://{SERVER}/{TEST_DB}"
os.environ["OPTICORE_STORAGE_DIR"] = tempfile.mkdtemp(prefix="opticore-test-storage-")
os.environ["OPTICORE_MAX_UPLOAD_MB"] = "1"

from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import get_engine  # noqa: E402
from app.main import app  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _recreate_test_db() -> None:
    with psycopg.connect(f"postgresql://{SERVER}/postgres", autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        conn.execute(f"CREATE DATABASE {TEST_DB} ENCODING 'UTF8'")


@pytest.fixture(scope="session", autouse=True)
def database() -> Iterator[None]:
    _recreate_test_db()
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    yield
    get_engine().dispose()


@pytest.fixture(autouse=True)
def clean_tables() -> Iterator[None]:
    yield
    with get_engine().begin() as conn:
        conn.execute(text("TRUNCATE building_label, building, project_feature, project_file, project CASCADE"))


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def storage_dir() -> Path:
    return get_settings().storage_dir
