"""KML import: project features, boundary source file, file processing note

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-22
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("project_file", sa.Column("note", sa.Text(), nullable=True))

    op.add_column("project", sa.Column("boundary_file_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_project_boundary_file", "project", "project_file",
                          ["boundary_file_id"], ["id"], ondelete="SET NULL")

    op.create_table(
        "project_feature",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_file_id", sa.Uuid(), sa.ForeignKey("project_file.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("geometry", Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=False),
    )
    op.create_index("ix_project_feature_project_id", "project_feature", ["project_id"])
    op.create_index("ix_project_feature_source_file_id", "project_feature", ["source_file_id"])
    op.create_index("ix_project_feature_geometry", "project_feature", ["geometry"], postgresql_using="gist")


def downgrade() -> None:
    op.drop_table("project_feature")
    op.drop_constraint("fk_project_boundary_file", "project", type_="foreignkey")
    op.drop_column("project", "boundary_file_id")
    op.drop_column("project_file", "note")
