from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

ALEMBIC_HEAD = "d1e2f3a4b5c6"
FORBIDDEN_RAW_SECRET_COLUMNS = {
    "access" + "_token",
    "refresh" + "_token",
    "app" + "_key",
    "app" + "_secret",
    "account" + "_number",
    "account" + "_no",
    "ca" + "no",
    "telegram" + "_token",
    "chat" + "_id",
    "webhook" + "_url",
    "discord" + "_webhook" + "_url",
}


def _alembic_config(database_url: str) -> Config:
    repo_root = Path(__file__).resolve().parents[2]
    config = Config(str(repo_root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_phase3_paper_persistence_migration_is_additive(tmp_path: Path, monkeypatch) -> None:
    """Phase 3 paper persistence migration은 기존 paper tables를 보존하고 새 table만 추가한다."""
    database_path = tmp_path / "phase3_paper_persistence.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    config = _alembic_config(database_url)
    command.upgrade(config, "head")

    engine = create_engine(database_url, future=True)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    assert {
        "paper_orders",
        "paper_fills",
        "paper_positions",
        "paper_audit_events",
        "paper_portfolio_snapshots",
        "paper_account_snapshots",
        "broker_audit_events",
        "notification_events",
        "notification_delivery_logs",
        "kis_token_status_metadata",
        "paper_bot_runs",
        "paper_bot_decisions",
    }.issubset(table_names)

    paper_orders = {column["name"]: column for column in inspector.get_columns("paper_orders")}
    assert {
        "paper_order_id",
        "symbol",
        "side",
        "qty",
        "broker_order_id",
        "broker_order_status",
        "account_alias",
        "submitted_at",
        "canceled_at",
        "broker_status_json",
    }.issubset(paper_orders)
    assert paper_orders["broker_order_id"]["nullable"] is True
    assert paper_orders["account_alias"]["nullable"] is True

    paper_fills = {column["name"]: column for column in inspector.get_columns("paper_fills")}
    assert {"broker_fill_id", "broker_order_id", "broker_fill_ts", "broker_status_json"}.issubset(paper_fills)
    assert paper_fills["broker_fill_id"]["nullable"] is True

    paper_positions = {column["name"]: column for column in inspector.get_columns("paper_positions")}
    assert {
        "broker_position_key",
        "account_alias",
        "market_value",
        "unrealized_pnl",
        "broker_synced_at",
        "broker_status_json",
    }.issubset(paper_positions)
    assert paper_positions["broker_position_key"]["nullable"] is True

    synthetic_positions = {column["name"] for column in inspector.get_columns("positions")}
    assert "broker_position_key" not in synthetic_positions
    assert "account_alias" not in synthetic_positions

    paper_account_snapshots = {column["name"] for column in inspector.get_columns("paper_account_snapshots")}
    assert {
        "snapshot_id",
        "snapshot_ts",
        "cash_balance",
        "buying_power",
        "market_value",
        "total_equity",
        "metadata_json",
    }.issubset(paper_account_snapshots)

    paper_bot_runs = {column["name"] for column in inspector.get_columns("paper_bot_runs")}
    assert {
        "trade_date",
        "dry_run",
        "preview_count",
        "skipped_count",
        "rejected_count",
        "request_json",
        "result_json",
    }.issubset(paper_bot_runs)

    with engine.connect() as connection:
        assert connection.scalar(text("select version_num from alembic_version")) == ALEMBIC_HEAD
    engine.dispose()


def test_phase3_persistence_tables_do_not_add_raw_secret_columns(tmp_path: Path, monkeypatch) -> None:
    """paper persistence schema에는 raw token/account/webhook/chat_id column을 만들지 않는다."""
    database_path = tmp_path / "phase3_secret_column_scan.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    config = _alembic_config(database_url)
    command.upgrade(config, "head")

    engine = create_engine(database_url, future=True)
    inspector = inspect(engine)
    checked_tables = {
        "paper_orders",
        "paper_fills",
        "paper_positions",
        "paper_portfolio_snapshots",
        "paper_account_snapshots",
        "broker_audit_events",
        "notification_events",
        "notification_delivery_logs",
        "kis_token_status_metadata",
        "paper_bot_runs",
        "paper_bot_decisions",
    }
    for table_name in checked_tables:
        column_names = {column["name"] for column in inspector.get_columns(table_name)}
        assert FORBIDDEN_RAW_SECRET_COLUMNS.isdisjoint(column_names)
    engine.dispose()
