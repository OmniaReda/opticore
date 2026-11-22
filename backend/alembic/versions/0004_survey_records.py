"""Survey import: one row per survey Excel line

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "survey_record",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "source_file_id", sa.Uuid(), sa.ForeignKey("project_file.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("visit_date", sa.Date(), nullable=True),
        sa.Column("street_name", sa.Text(), nullable=True),
        sa.Column("building_name", sa.Text(), nullable=True),
        sa.Column("building_number", sa.String(50), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("floors", sa.Integer(), nullable=True),
        sa.Column("users_per_floor", sa.Integer(), nullable=True),
        sa.Column("gf_users", sa.Integer(), nullable=True),
        sa.Column("total_users", sa.Integer(), nullable=True),
        sa.Column("hp_te_required", sa.Integer(), nullable=True),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("sub_category", sa.String(100), nullable=True),
        sa.Column("final_category", sa.String(100), nullable=True),
        sa.Column("placemark_id", sa.String(100), nullable=True),
        sa.Column("entrance_length_m", sa.Float(), nullable=True),
        sa.Column("entrance_marked", sa.String(20), nullable=True),
        sa.Column("msan_note", sa.String(50), nullable=True),
        sa.Column("void_core", sa.String(20), nullable=True),
        sa.Column("hp_count", sa.String(20), nullable=True),
        sa.Column("qty_home_pass", sa.Integer(), nullable=True),
        sa.Column("te_comment", sa.Text(), nullable=True),
        sa.Column("geometry", Geometry("POINT", srid=4326, spatial_index=False), nullable=True),
    )
    op.create_index("ix_survey_record_project_id", "survey_record", ["project_id"])
    op.create_index("ix_survey_record_source_file_id", "survey_record", ["source_file_id"])
    op.create_index("ix_survey_record_code", "survey_record", ["code"])
    op.create_index("ix_survey_record_geometry", "survey_record", ["geometry"], postgresql_using="gist")


def downgrade() -> None:
    op.drop_table("survey_record")
