"""add earnings events

Revision ID: d9e3f0a1b2c4
Revises: b8e2c1d4a6f0
Create Date: 2026-05-26 01:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "d9e3f0a1b2c4"
down_revision = "b8e2c1d4a6f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "earnings_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("earnings_date", sa.Date(), nullable=False),
        sa.Column("release_ts", sa.DateTime(), nullable=True),
        sa.Column("session", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "earnings_date", "session", name="uq_earnings_symbol_date_session"),
    )
    op.create_index(op.f("ix_earnings_events_earnings_date"), "earnings_events", ["earnings_date"], unique=False)
    op.create_index(op.f("ix_earnings_events_symbol"), "earnings_events", ["symbol"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_earnings_events_symbol"), table_name="earnings_events")
    op.drop_index(op.f("ix_earnings_events_earnings_date"), table_name="earnings_events")
    op.drop_table("earnings_events")
