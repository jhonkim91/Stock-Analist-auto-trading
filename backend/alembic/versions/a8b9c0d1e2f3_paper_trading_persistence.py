"""paper trading persistence

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-05-27 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a8b9c0d1e2f3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("paper_orders", schema=None) as batch_op:
        batch_op.add_column(sa.Column("broker_order_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("broker_order_status", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("account_alias", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("submitted_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("canceled_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("broker_status_json", sa.Text(), nullable=True))

    with op.batch_alter_table("paper_fills", schema=None) as batch_op:
        batch_op.add_column(sa.Column("broker_fill_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("broker_order_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("broker_fill_ts", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("broker_status_json", sa.Text(), nullable=True))

    with op.batch_alter_table("paper_positions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("broker_position_key", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("account_alias", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("market_value", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("unrealized_pnl", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("broker_synced_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("broker_status_json", sa.Text(), nullable=True))

    op.create_table(
        "paper_portfolio_snapshots",
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

    op.create_table(
        "broker_audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("broker_name", sa.String(length=64), nullable=False),
        sa.Column("broker_mode", sa.String(length=32), nullable=False),
        sa.Column("account_alias", sa.String(length=64), nullable=True),
        sa.Column("paper_order_id", sa.String(length=64), nullable=True),
        sa.Column("broker_order_id", sa.String(length=64), nullable=True),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason_codes_json", sa.Text(), nullable=False),
        sa.Column("sanitized_payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "notification_events",
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("channel_alias", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=True),
        sa.Column("payload_summary_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )

    op.create_table(
        "notification_delivery_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("channel_alias", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "kis_token_status_metadata",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("app_key_configured", sa.Boolean(), nullable=False),
        sa.Column("app_secret_configured", sa.Boolean(), nullable=False),
        sa.Column("token_issued", sa.Boolean(), nullable=False),
        sa.Column("token_cache_enabled", sa.Boolean(), nullable=False),
        sa.Column("token_file_persistence_enabled", sa.Boolean(), nullable=False),
        sa.Column("token_db_persistence_enabled", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("status_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("kis_token_status_metadata")
    op.drop_table("notification_delivery_logs")
    op.drop_table("notification_events")
    op.drop_table("broker_audit_events")
    op.drop_table("paper_portfolio_snapshots")

    with op.batch_alter_table("paper_positions", schema=None) as batch_op:
        batch_op.drop_column("broker_status_json")
        batch_op.drop_column("broker_synced_at")
        batch_op.drop_column("unrealized_pnl")
        batch_op.drop_column("market_value")
        batch_op.drop_column("account_alias")
        batch_op.drop_column("broker_position_key")

    with op.batch_alter_table("paper_fills", schema=None) as batch_op:
        batch_op.drop_column("broker_status_json")
        batch_op.drop_column("broker_fill_ts")
        batch_op.drop_column("broker_order_id")
        batch_op.drop_column("broker_fill_id")

    with op.batch_alter_table("paper_orders", schema=None) as batch_op:
        batch_op.drop_column("broker_status_json")
        batch_op.drop_column("canceled_at")
        batch_op.drop_column("submitted_at")
        batch_op.drop_column("account_alias")
        batch_op.drop_column("broker_order_status")
        batch_op.drop_column("broker_order_id")
