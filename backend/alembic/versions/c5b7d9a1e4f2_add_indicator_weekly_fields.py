"""add indicator weekly fields

Revision ID: c5b7d9a1e4f2
Revises: da9ab5998e36
Create Date: 2026-05-23 22:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c5b7d9a1e4f2"
down_revision = "da9ab5998e36"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("indicator_snapshot", schema=None) as batch_op:
        batch_op.add_column(sa.Column("weekly_close", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("weekly_sma30", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("weekly_sma30_slope", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("indicator_snapshot", schema=None) as batch_op:
        batch_op.drop_column("weekly_sma30_slope")
        batch_op.drop_column("weekly_sma30")
        batch_op.drop_column("weekly_close")
