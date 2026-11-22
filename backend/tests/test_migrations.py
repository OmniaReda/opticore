from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app import models  # noqa: F401
from app.db import Base, get_engine

POSTGIS_TABLES = {"spatial_ref_sys", "topology", "layer"}


def test_migrations_match_models() -> None:
    """Fails if a model changes without a matching Alembic migration."""
    with get_engine().connect() as conn:
        ctx = MigrationContext.configure(conn, opts={
            "include_object": lambda o, name, type_, r, c: not (type_ == "table" and name in POSTGIS_TABLES),
        })
        diff = compare_metadata(ctx, Base.metadata)
    assert diff == []
