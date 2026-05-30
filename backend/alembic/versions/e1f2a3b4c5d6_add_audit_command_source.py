"""add command_source to audit events

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
create_date: 2026-05-30

paper_audit_events / broker_audit_events에 command_source(요청 출처) 컬럼을 추가한다.
기존 SQLite 파일을 보존하는 additive migration이며, 이미 컬럼이 있으면 건너뛴다.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "e1f2a3b4c5d6"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


_AUDIT_TABLES = ("paper_audit_events", "broker_audit_events")


def _existing_columns(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    for table_name in _AUDIT_TABLES:
        if table_name not in existing_tables:
            continue
        if "command_source" in _existing_columns(bind, table_name):
            continue
        op.add_column(table_name, sa.Column("command_source", sa.String(length=32), nullable=True))


def downgrade() -> None:
    # 컬럼 삭제는 SQLite 호환을 위해 생략한다(append-only 정책, d1e2f3a4b5c6와 동일).
    pass
