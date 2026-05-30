"""extend paper bot run contract

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-05-28 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "d1e2f3a4b5c6"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("paper_bot_runs"):
        return
    existing_columns = {column["name"] for column in inspector.get_columns("paper_bot_runs")}
    with op.batch_alter_table("paper_bot_runs", schema=None) as batch_op:
        if "trade_date" not in existing_columns:
            batch_op.add_column(sa.Column("trade_date", sa.Date(), nullable=True))
        if "dry_run" not in existing_columns:
            batch_op.add_column(sa.Column("dry_run", sa.Boolean(), nullable=True))
        if "preview_count" not in existing_columns:
            batch_op.add_column(sa.Column("preview_count", sa.Integer(), nullable=True))
        if "skipped_count" not in existing_columns:
            batch_op.add_column(sa.Column("skipped_count", sa.Integer(), nullable=True))
        if "rejected_count" not in existing_columns:
            batch_op.add_column(sa.Column("rejected_count", sa.Integer(), nullable=True))
        if "request_json" not in existing_columns:
            batch_op.add_column(sa.Column("request_json", sa.Text(), nullable=True))
        if "result_json" not in existing_columns:
            batch_op.add_column(sa.Column("result_json", sa.Text(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("paper_bot_runs"):
        return
    existing_columns = {column["name"] for column in inspector.get_columns("paper_bot_runs")}
    with op.batch_alter_table("paper_bot_runs", schema=None) as batch_op:
        for column_name in (
            "result_json",
            "request_json",
            "rejected_count",
            "skipped_count",
            "preview_count",
            "dry_run",
            "trade_date",
        ):
            if column_name in existing_columns:
                batch_op.drop_column(column_name)
