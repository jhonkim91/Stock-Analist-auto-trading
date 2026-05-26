"""add indicator pattern engine fields

Revision ID: b8e2c1d4a6f0
Revises: a7f4c2d9e1b8
Create Date: 2026-05-26 00:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b8e2c1d4a6f0"
down_revision = "a7f4c2d9e1b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("indicator_snapshot", schema=None) as batch_op:
        batch_op.add_column(sa.Column("contraction_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(
            sa.Column("contraction_count_available", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("pullback_depth_last", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column("pullback_depth_last_available", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("pullback_depth_prev", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column("pullback_depth_prev_available", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("box_age_days", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("box_age_days_available", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("box_redefinition_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(
            sa.Column("box_redefinition_count_available", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("weekly_breakout", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(
            sa.Column("weekly_breakout_available", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("weekly_volume_ratio", sa.Float(), nullable=False, server_default="0.0"))
        batch_op.add_column(
            sa.Column("weekly_volume_ratio_available", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("weekly_rs_score", sa.Float(), nullable=False, server_default="0.0"))
        batch_op.add_column(
            sa.Column("weekly_rs_score_available", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("indicator_snapshot", schema=None) as batch_op:
        batch_op.drop_column("weekly_rs_score_available")
        batch_op.drop_column("weekly_rs_score")
        batch_op.drop_column("weekly_volume_ratio_available")
        batch_op.drop_column("weekly_volume_ratio")
        batch_op.drop_column("weekly_breakout_available")
        batch_op.drop_column("weekly_breakout")
        batch_op.drop_column("box_redefinition_count_available")
        batch_op.drop_column("box_redefinition_count")
        batch_op.drop_column("box_age_days_available")
        batch_op.drop_column("box_age_days")
        batch_op.drop_column("pullback_depth_prev_available")
        batch_op.drop_column("pullback_depth_prev")
        batch_op.drop_column("pullback_depth_last_available")
        batch_op.drop_column("pullback_depth_last")
        batch_op.drop_column("contraction_count_available")
        batch_op.drop_column("contraction_count")
