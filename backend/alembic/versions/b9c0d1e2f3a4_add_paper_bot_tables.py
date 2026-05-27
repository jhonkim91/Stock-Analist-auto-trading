"""add paper bot tables

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-05-27 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b9c0d1e2f3a4"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_bot_runs",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("auto_submit_requested", sa.Boolean(), nullable=False),
        sa.Column("auto_submit_allowed", sa.Boolean(), nullable=False),
        sa.Column("decision_count", sa.Integer(), nullable=False),
        sa.Column("submitted_count", sa.Integer(), nullable=False),
        sa.Column("reason_codes_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_table(
        "paper_bot_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("strategy_tag", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("total_score", sa.Float(), nullable=True),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("limit_price", sa.Float(), nullable=True),
        sa.Column("stop_price", sa.Float(), nullable=True),
        sa.Column("target_price", sa.Float(), nullable=True),
        sa.Column("risk_passed", sa.Boolean(), nullable=False),
        sa.Column("reason_codes_json", sa.Text(), nullable=False),
        sa.Column("paper_order_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("paper_bot_decisions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_paper_bot_decisions_run_id"), ["run_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_paper_bot_decisions_symbol"), ["symbol"], unique=False)
        batch_op.create_index(batch_op.f("ix_paper_bot_decisions_strategy_tag"), ["strategy_tag"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("paper_bot_decisions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_paper_bot_decisions_strategy_tag"))
        batch_op.drop_index(batch_op.f("ix_paper_bot_decisions_symbol"))
        batch_op.drop_index(batch_op.f("ix_paper_bot_decisions_run_id"))
    op.drop_table("paper_bot_decisions")
    op.drop_table("paper_bot_runs")
