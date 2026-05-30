"""add paper account snapshots

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-05-28 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c0d1e2f3a4b5"
down_revision = "b9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("paper_account_snapshots"):
        return
    op.create_table(
        "paper_account_snapshots",
        sa.Column("snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("snapshot_ts", sa.DateTime(), nullable=False),
        sa.Column("account_alias", sa.String(length=64), nullable=True),
        sa.Column("cash_balance", sa.Float(), nullable=True),
        sa.Column("buying_power", sa.Float(), nullable=True),
        sa.Column("market_value", sa.Float(), nullable=True),
        sa.Column("total_equity", sa.Float(), nullable=True),
        sa.Column("unrealized_pnl", sa.Float(), nullable=True),
        sa.Column("realized_pnl", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("snapshot_id"),
    )


def downgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("paper_account_snapshots"):
        return
    op.drop_table("paper_account_snapshots")
