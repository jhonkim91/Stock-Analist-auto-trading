"""add backtest trade ledger

Revision ID: e4f5a6b7c8d9
Revises: d9e3f0a1b2c4
Create Date: 2026-05-26 16:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "e4f5a6b7c8d9"
down_revision = "d9e3f0a1b2c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_trade_ledger",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("trade_index", sa.Integer(), nullable=False),
        sa.Column("strategy_name", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("signal_date", sa.Date(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("exit_date", sa.Date(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("raw_entry_price", sa.Float(), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("raw_exit_price", sa.Float(), nullable=False),
        sa.Column("exit_price", sa.Float(), nullable=False),
        sa.Column("pnl", sa.Float(), nullable=False),
        sa.Column("return_pct", sa.Float(), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=False),
        sa.Column("cost_bps", sa.Float(), nullable=False),
        sa.Column("holding_days", sa.Integer(), nullable=False),
        sa.Column("exit_reason", sa.String(length=64), nullable=False),
        sa.Column("risk_basis", sa.String(length=64), nullable=False),
        sa.Column("execution_detail_json", sa.Text(), nullable=False),
        sa.Column("liquidity_detail_json", sa.Text(), nullable=False),
        sa.Column("price_detail_json", sa.Text(), nullable=False),
        sa.Column("portfolio_detail_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "trade_index", name="uq_backtest_trade_ledger_run_index"),
    )
    for column_name in (
        "run_id",
        "strategy_name",
        "symbol",
        "signal_date",
        "entry_date",
        "exit_date",
        "exit_reason",
    ):
        op.create_index(
            op.f(f"ix_backtest_trade_ledger_{column_name}"),
            "backtest_trade_ledger",
            [column_name],
            unique=False,
        )


def downgrade() -> None:
    for column_name in (
        "exit_reason",
        "exit_date",
        "entry_date",
        "signal_date",
        "symbol",
        "strategy_name",
        "run_id",
    ):
        op.drop_index(op.f(f"ix_backtest_trade_ledger_{column_name}"), table_name="backtest_trade_ledger")
    op.drop_table("backtest_trade_ledger")
