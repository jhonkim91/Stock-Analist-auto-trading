"""add indicator pullback ema fields

Revision ID: f6d4a2c9e8b1
Revises: c5b7d9a1e4f2
Create Date: 2026-05-24 18:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f6d4a2c9e8b1"
down_revision = "c5b7d9a1e4f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("indicator_snapshot", schema=None) as batch_op:
        batch_op.add_column(sa.Column("low", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("ema20", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("indicator_snapshot", schema=None) as batch_op:
        batch_op.drop_column("ema20")
        batch_op.drop_column("low")
