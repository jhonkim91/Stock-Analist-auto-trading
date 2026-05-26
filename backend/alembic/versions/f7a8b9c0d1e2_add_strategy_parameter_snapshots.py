"""add strategy parameter snapshots

Revision ID: f7a8b9c0d1e2
Revises: e5f6a7b8c9d0
Create Date: 2026-05-26 22:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f7a8b9c0d1e2"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategy_parameter_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("strategy_name", sa.String(length=64), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("parameter_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "strategy_name",
            "snapshot_date",
            "effective_date",
            "config_hash",
            name="uq_strategy_parameter_snapshot_identity",
        ),
    )
    for column_name in ("strategy_name", "config_hash", "snapshot_date", "effective_date"):
        op.create_index(
            op.f(f"ix_strategy_parameter_snapshots_{column_name}"),
            "strategy_parameter_snapshots",
            [column_name],
            unique=False,
        )


def downgrade() -> None:
    for column_name in ("effective_date", "snapshot_date", "config_hash", "strategy_name"):
        op.drop_index(op.f(f"ix_strategy_parameter_snapshots_{column_name}"), table_name="strategy_parameter_snapshots")
    op.drop_table("strategy_parameter_snapshots")
