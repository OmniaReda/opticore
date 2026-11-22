"""CAD import: buildings and Building ID labels

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-22
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "building",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_file_id", sa.Uuid(), sa.ForeignKey("project_file.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("geometry", Geometry("POLYGON", srid=4326, spatial_index=False), nullable=False),
    )
    op.create_index("ix_building_project_id", "building", ["project_id"])
    op.create_index("ix_building_source_file_id", "building", ["source_file_id"])
    op.create_index("ix_building_geometry", "building", ["geometry"], postgresql_using="gist")

    op.create_table(
        "building_label",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_file_id", sa.Uuid(), sa.ForeignKey("project_file.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("building_id", sa.Uuid(), sa.ForeignKey("building.id", ondelete="SET NULL"), nullable=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("geometry", Geometry("POINT", srid=4326, spatial_index=False), nullable=False),
    )
    op.create_index("ix_building_label_project_id", "building_label", ["project_id"])
    op.create_index("ix_building_label_source_file_id", "building_label", ["source_file_id"])
    op.create_index("ix_building_label_building_id", "building_label", ["building_id"])


def downgrade() -> None:
    op.drop_table("building_label")
    op.drop_table("building")
