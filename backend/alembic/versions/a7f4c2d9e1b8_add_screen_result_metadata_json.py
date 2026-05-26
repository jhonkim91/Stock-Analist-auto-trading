"""add screen result metadata json fields

Revision ID: a7f4c2d9e1b8
Revises: f6d4a2c9e8b1
Create Date: 2026-05-26 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a7f4c2d9e1b8"
down_revision = "f6d4a2c9e8b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("screen_results", schema=None) as batch_op:
        batch_op.add_column(sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"))
        batch_op.add_column(sa.Column("risk_flags_json", sa.Text(), nullable=False, server_default="{}"))
        batch_op.add_column(sa.Column("score_breakdown_json", sa.Text(), nullable=False, server_default="{}"))
        batch_op.add_column(sa.Column("data_quality_flags_json", sa.Text(), nullable=False, server_default="{}"))


def downgrade() -> None:
    with op.batch_alter_table("screen_results", schema=None) as batch_op:
        batch_op.drop_column("data_quality_flags_json")
        batch_op.drop_column("score_breakdown_json")
        batch_op.drop_column("risk_flags_json")
        batch_op.drop_column("metadata_json")
