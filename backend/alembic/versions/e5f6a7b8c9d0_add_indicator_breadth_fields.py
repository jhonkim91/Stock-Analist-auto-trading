"""add indicator breadth fields

Revision ID: e5f6a7b8c9d0
Revises: e4f5a6b7c8d9
Create Date: 2026-05-26 20:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "e5f6a7b8c9d0"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("indicator_snapshot", schema=None) as batch_op:
        batch_op.add_column(sa.Column("breadth_advance_decline_ratio", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column("breadth_advance_decline_available", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("breadth_52w_high_low_ratio", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column("breadth_52w_high_low_available", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("breadth_ma50_participation", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column("breadth_ma50_participation_available", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("breadth_score", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("breadth_score_available", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("indicator_snapshot", schema=None) as batch_op:
        batch_op.drop_column("breadth_score_available")
        batch_op.drop_column("breadth_score")
        batch_op.drop_column("breadth_ma50_participation_available")
        batch_op.drop_column("breadth_ma50_participation")
        batch_op.drop_column("breadth_52w_high_low_available")
        batch_op.drop_column("breadth_52w_high_low_ratio")
        batch_op.drop_column("breadth_advance_decline_available")
        batch_op.drop_column("breadth_advance_decline_ratio")
