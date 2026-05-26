from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from backend.app.core.database import Base
from backend.app.models import tables  # noqa: F401

ALEMBIC_HEAD = "a8b9c0d1e2f3"


def _alembic_config(database_url: str) -> Config:
    repo_root = Path(__file__).resolve().parents[2]
    config = Config(str(repo_root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_alembic_initial_migration_upgrade_and_downgrade(tmp_path: Path, monkeypatch) -> None:
    """초기 Alembic migration이 빈 SQLite DB에 적용되고 rollback 가능한지 확인한다."""
    database_path = tmp_path / "alembic_smoke.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    config = _alembic_config(database_url)
    command.upgrade(config, "head")

    engine = create_engine(database_url, future=True)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    assert {
        "alembic_version",
        "symbol_master",
        "daily_ohlcv",
        "import_runs",
        "orders",
        "paper_orders",
        "backtest_runs",
        "backtest_trade_ledger",
        "strategy_parameter_snapshots",
        "earnings_events",
        "paper_portfolio_snapshots",
        "broker_audit_events",
        "notification_events",
        "notification_delivery_logs",
        "kis_token_status_metadata",
    }.issubset(table_names)
    paper_order_columns = {column["name"] for column in inspector.get_columns("paper_orders")}
    assert {
        "broker_order_id",
        "broker_order_status",
        "account_alias",
        "submitted_at",
        "canceled_at",
        "broker_status_json",
    }.issubset(paper_order_columns)
    paper_fill_columns = {column["name"] for column in inspector.get_columns("paper_fills")}
    assert {"broker_fill_id", "broker_order_id", "broker_fill_ts", "broker_status_json"}.issubset(paper_fill_columns)
    paper_position_columns = {column["name"] for column in inspector.get_columns("paper_positions")}
    assert {
        "broker_position_key",
        "account_alias",
        "market_value",
        "unrealized_pnl",
        "broker_synced_at",
        "broker_status_json",
    }.issubset(paper_position_columns)
    strategy_parameter_snapshot_columns = {
        column["name"] for column in inspector.get_columns("strategy_parameter_snapshots")
    }
    assert {
        "strategy_name",
        "config_hash",
        "snapshot_date",
        "effective_date",
        "parameter_json",
        "created_at",
    }.issubset(strategy_parameter_snapshot_columns)
    trade_ledger_columns = {column["name"] for column in inspector.get_columns("backtest_trade_ledger")}
    assert {
        "run_id",
        "trade_index",
        "strategy_name",
        "symbol",
        "signal_date",
        "entry_date",
        "exit_date",
        "qty",
        "entry_price",
        "exit_price",
        "pnl",
        "return_pct",
        "exit_reason",
        "execution_detail_json",
    }.issubset(trade_ledger_columns)
    indicator_columns = {column["name"] for column in inspector.get_columns("indicator_snapshot")}
    assert {
        "weekly_close",
        "weekly_sma30",
        "weekly_sma30_slope",
        "low",
        "ema20",
        "contraction_count",
        "contraction_count_available",
        "pullback_depth_last",
        "pullback_depth_last_available",
        "pullback_depth_prev",
        "pullback_depth_prev_available",
        "box_age_days",
        "box_age_days_available",
        "box_redefinition_count",
        "box_redefinition_count_available",
        "weekly_breakout",
        "weekly_breakout_available",
        "weekly_volume_ratio",
        "weekly_volume_ratio_available",
        "weekly_rs_score",
        "weekly_rs_score_available",
        "breadth_advance_decline_ratio",
        "breadth_advance_decline_available",
        "breadth_52w_high_low_ratio",
        "breadth_52w_high_low_available",
        "breadth_ma50_participation",
        "breadth_ma50_participation_available",
        "breadth_score",
        "breadth_score_available",
    }.issubset(indicator_columns)
    screen_result_columns = {column["name"] for column in inspector.get_columns("screen_results")}
    assert {
        "metadata_json",
        "risk_flags_json",
        "score_breakdown_json",
        "data_quality_flags_json",
    }.issubset(screen_result_columns)
    with engine.connect() as connection:
        assert connection.scalar(text("select version_num from alembic_version")) == ALEMBIC_HEAD

    command.downgrade(config, "base")

    downgraded_tables = set(inspect(engine).get_table_names())
    assert "symbol_master" not in downgraded_tables
    assert "paper_orders" not in downgraded_tables
    engine.dispose()


def test_existing_create_all_sqlite_schema_can_be_stamped_as_head(tmp_path: Path, monkeypatch) -> None:
    """기존 create_all 기반 SQLite DB를 초기 Alembic baseline으로 stamp할 수 있는지 확인한다."""
    database_path = tmp_path / "existing_create_all.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(bind=engine)

    config = _alembic_config(database_url)
    command.stamp(config, "head")
    command.check(config)

    with engine.connect() as connection:
        assert connection.scalar(text("select version_num from alembic_version")) == ALEMBIC_HEAD
    engine.dispose()
