"""Address points: the filled Streets & numbers Excel (house number + floors + users, by location)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "address_point",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "source_file_id", sa.Uuid(), sa.ForeignKey("project_file.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("street_ar", sa.Text(), nullable=True),
        sa.Column("street_en", sa.Text(), nullable=True),
        sa.Column("house_number", sa.String(50), nullable=True),
        sa.Column("floors", sa.Integer(), nullable=True),
        sa.Column("total_users", sa.Integer(), nullable=True),
        sa.Column("geometry", Geometry("POINT", srid=4326, spatial_index=False), nullable=False),
    )
    op.create_index("ix_address_point_project_id", "address_point", ["project_id"])
    op.create_index("ix_address_point_source_file_id", "address_point", ["source_file_id"])
    op.create_index("ix_address_point_geometry", "address_point", ["geometry"], postgresql_using="gist")


def downgrade() -> None:
    op.drop_table("address_point")
