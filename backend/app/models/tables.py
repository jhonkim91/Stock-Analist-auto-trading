from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


def utc_now() -> datetime:
    """UTC aware timestamp를 생성한다."""
    return datetime.now(UTC)


class SymbolMaster(Base):
    __tablename__ = "symbol_master"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    asset_type: Mapped[str] = mapped_column(String(32), default="stock")
    currency: Mapped[str] = mapped_column(String(8), default="KRW")
    market: Mapped[str] = mapped_column(String(16), default="KR")
    exchange: Mapped[str] = mapped_column(String(32), default="KRX")
    sector: Mapped[str] = mapped_column(String(64))
    industry: Mapped[str] = mapped_column(String(64), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    list_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delist_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class DailyOhlcv(Base):
    __tablename__ = "daily_ohlcv"
    __table_args__ = (UniqueConstraint("trade_date", "symbol", "venue", name="uq_daily_symbol_date_venue"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    adj_close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer)
    turnover_value: Mapped[float] = mapped_column(Float)
    venue: Mapped[str] = mapped_column(String(32), default="KRX")


class DataSource(Base):
    __tablename__ = "data_sources"

    source_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_type: Mapped[str] = mapped_column(String(32), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    market: Mapped[str] = mapped_column(String(32), default="KRX")
    venue: Mapped[str] = mapped_column(String(32), default="KRX")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Seoul")
    zero_volume_policy: Mapped[str] = mapped_column(String(64), default="warn")
    unknown_symbol_policy: Mapped[str] = mapped_column(String(64), default="warn_and_create_on_confirm")
    max_rows: Mapped[int] = mapped_column(Integer, default=10000)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class ImportRun(Base):
    __tablename__ = "import_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    provider_type: Mapped[str] = mapped_column(String(32), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    file_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    can_confirm: Mapped[bool] = mapped_column(Boolean, default=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    info_count: Mapped[int] = mapped_column(Integer, default=0)
    inserted_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    staged_rows_json: Mapped[str] = mapped_column(Text, default="[]")
    preview_rows_json: Mapped[str] = mapped_column(Text, default="[]")
    source_config_snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    provider_metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DataQualityCheck(Base):
    __tablename__ = "data_quality_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    trade_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    field: Mapped[str | None] = mapped_column(String(64), nullable=True)
    check_code: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class ExternalSymbolMapping(Base):
    __tablename__ = "external_symbol_mapping"
    __table_args__ = (UniqueConstraint("source_id", "external_symbol", name="uq_external_symbol_source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    external_symbol: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    market: Mapped[str] = mapped_column(String(32), default="KRX")
    venue: Mapped[str] = mapped_column(String(32), default="KRX")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class CorporateAction(Base):
    __tablename__ = "corporate_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    action_date: Mapped[date] = mapped_column(Date, index=True)
    action_type: Mapped[str] = mapped_column(String(32), index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class TradingCalendar(Base):
    __tablename__ = "trading_calendar"
    __table_args__ = (UniqueConstraint("market", "calendar_date", name="uq_trading_calendar_market_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(String(32), index=True)
    calendar_date: Mapped[date] = mapped_column(Date, index=True)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class IndexOhlcv(Base):
    __tablename__ = "index_ohlcv"
    __table_args__ = (UniqueConstraint("trade_date", "symbol", name="uq_index_symbol_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer)


class SectorOhlcv(Base):
    __tablename__ = "sector_ohlcv"
    __table_args__ = (UniqueConstraint("trade_date", "sector", name="uq_sector_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    sector: Mapped[str] = mapped_column(String(64), index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer)


class FundamentalsPti(Base):
    __tablename__ = "fundamentals_pti"
    __table_args__ = (UniqueConstraint("symbol", "asof_date", "effective_date", name="uq_fund_symbol_asof_effective"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asof_date: Mapped[date] = mapped_column(Date, index=True)
    effective_date: Mapped[date] = mapped_column(Date, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    revenue: Mapped[float] = mapped_column(Float)
    eps: Mapped[float] = mapped_column(Float)
    op_margin: Mapped[float] = mapped_column(Float, default=0.0)
    roe: Mapped[float] = mapped_column(Float, default=0.0)
    gross_profitability: Mapped[float] = mapped_column(Float, default=0.0)
    quarterly_eps_growth: Mapped[float] = mapped_column(Float, default=0.0)
    sales_growth: Mapped[float] = mapped_column(Float, default=0.0)


class EarningsEvent(Base):
    __tablename__ = "earnings_events"
    __table_args__ = (UniqueConstraint("symbol", "earnings_date", "session", name="uq_earnings_symbol_date_session"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    earnings_date: Mapped[date] = mapped_column(Date, index=True)
    release_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    session: Mapped[str] = mapped_column(String(32), default="unknown")


class IndicatorSnapshot(Base):
    __tablename__ = "indicator_snapshot"
    __table_args__ = (UniqueConstraint("trade_date", "symbol", name="uq_indicator_symbol_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    close: Mapped[float] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume: Mapped[int] = mapped_column(Integer)
    turnover_value: Mapped[float] = mapped_column(Float)
    sma20: Mapped[float | None] = mapped_column(Float, nullable=True)
    ema20: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma50: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma150: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma200: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma200_slope: Mapped[float | None] = mapped_column(Float, nullable=True)
    weekly_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    weekly_sma30: Mapped[float | None] = mapped_column(Float, nullable=True)
    weekly_sma30_slope: Mapped[float | None] = mapped_column(Float, nullable=True)
    contraction_count: Mapped[int] = mapped_column(Integer, default=0)
    contraction_count_available: Mapped[bool] = mapped_column(Boolean, default=False)
    pullback_depth_last: Mapped[float | None] = mapped_column(Float, nullable=True)
    pullback_depth_last_available: Mapped[bool] = mapped_column(Boolean, default=False)
    pullback_depth_prev: Mapped[float | None] = mapped_column(Float, nullable=True)
    pullback_depth_prev_available: Mapped[bool] = mapped_column(Boolean, default=False)
    box_age_days: Mapped[int] = mapped_column(Integer, default=0)
    box_age_days_available: Mapped[bool] = mapped_column(Boolean, default=False)
    box_redefinition_count: Mapped[int] = mapped_column(Integer, default=0)
    box_redefinition_count_available: Mapped[bool] = mapped_column(Boolean, default=False)
    weekly_breakout: Mapped[bool] = mapped_column(Boolean, default=False)
    weekly_breakout_available: Mapped[bool] = mapped_column(Boolean, default=False)
    weekly_volume_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    weekly_volume_ratio_available: Mapped[bool] = mapped_column(Boolean, default=False)
    weekly_rs_score: Mapped[float] = mapped_column(Float, default=0.0)
    weekly_rs_score_available: Mapped[bool] = mapped_column(Boolean, default=False)
    volume_ma20: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_ma50: Mapped[float | None] = mapped_column(Float, nullable=True)
    atr14: Mapped[float | None] = mapped_column(Float, nullable=True)
    atr20: Mapped[float | None] = mapped_column(Float, nullable=True)
    atr20_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    atr20_pct_ma60: Mapped[float | None] = mapped_column(Float, nullable=True)
    std20: Mapped[float | None] = mapped_column(Float, nullable=True)
    std60: Mapped[float | None] = mapped_column(Float, nullable=True)
    high_52w: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_from_52w_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_ratio_50: Mapped[float | None] = mapped_column(Float, nullable=True)
    pivot_high_20_prev: Mapped[float | None] = mapped_column(Float, nullable=True)
    pivot_low_20_prev: Mapped[float | None] = mapped_column(Float, nullable=True)
    breakout: Mapped[bool] = mapped_column(Boolean, default=False)
    volume_dry_up: Mapped[bool] = mapped_column(Boolean, default=False)
    rs_percentile: Mapped[float | None] = mapped_column(Float, nullable=True)
    trend_score: Mapped[float] = mapped_column(Float, default=0.0)
    volume_score: Mapped[float] = mapped_column(Float, default=0.0)
    pattern_score: Mapped[float] = mapped_column(Float, default=0.0)
    fund_score: Mapped[float] = mapped_column(Float, default=0.0)
    market_score: Mapped[float] = mapped_column(Float, default=0.0)
    sector_rs_score: Mapped[float] = mapped_column(Float, default=0.0)
    relative_strength_score: Mapped[float] = mapped_column(Float, default=0.0)
    rr_score: Mapped[float] = mapped_column(Float, default=0.0)


class ScreenResult(Base):
    __tablename__ = "screen_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    strategy_tag: Mapped[str] = mapped_column(String(64), index=True)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    pass_flags: Mapped[str] = mapped_column(Text)
    failed_conditions: Mapped[str] = mapped_column(Text)
    reason_summary: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    risk_flags_json: Mapped[str] = mapped_column(Text, default="{}")
    score_breakdown_json: Mapped[str] = mapped_column(Text, default="{}")
    data_quality_flags_json: Mapped[str] = mapped_column(Text, default="{}")
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_per_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    reward_risk_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_size: Mapped[int] = mapped_column(Integer, default=0)
    position_notional: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Report(Base):
    __tablename__ = "reports"

    report_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    report_type: Mapped[str] = mapped_column(String(32))
    version: Mapped[str] = mapped_column(String(32))
    path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    strategy_name: Mapped[str] = mapped_column(String(64), index=True)
    config_hash: Mapped[str] = mapped_column(String(64))
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    metrics_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    entry_ts: Mapped[datetime] = mapped_column(DateTime)
    avg_price: Mapped[float] = mapped_column(Float)
    qty: Mapped[int] = mapped_column(Integer)
    stop_price: Mapped[float] = mapped_column(Float)
    strategy_tag: Mapped[str] = mapped_column(String(64))


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_ts: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))
    qty: Mapped[int] = mapped_column(Integer)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="preview_only")
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)


class PaperOrder(Base):
    __tablename__ = "paper_orders"

    paper_order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_ts: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_ts: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))
    qty: Mapped[int] = mapped_column(Integer)
    filled_qty: Mapped[int] = mapped_column(Integer, default=0)
    remaining_qty: Mapped[int] = mapped_column(Integer, default=0)
    order_type: Mapped[str] = mapped_column(String(16), default="limit")
    limit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="preview_only")
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    request_hash: Mapped[str] = mapped_column(String(64), default="")
    strategy_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason_codes_json: Mapped[str] = mapped_column(Text, default="[]")
    risk_gate_json: Mapped[str] = mapped_column(Text, default="{}")
    live_order_created: Mapped[bool] = mapped_column(Boolean, default=False)
    broker_order_created: Mapped[bool] = mapped_column(Boolean, default=False)
    network_call_performed: Mapped[bool] = mapped_column(Boolean, default=False)


class PaperFill(Base):
    __tablename__ = "paper_fills"

    paper_fill_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    paper_order_id: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))
    qty: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)
    fill_ts: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    fill_source: Mapped[str] = mapped_column(String(32), default="local_simulator")
    simulator_version: Mapped[str] = mapped_column(String(32), default="phase_3e1_skeleton")
    commission: Mapped[float] = mapped_column(Float, default=0.0)
    slippage_bps: Mapped[float] = mapped_column(Float, default=0.0)
    live_order_created: Mapped[bool] = mapped_column(Boolean, default=False)
    broker_order_created: Mapped[bool] = mapped_column(Boolean, default=False)
    network_call_performed: Mapped[bool] = mapped_column(Boolean, default=False)


class PaperPosition(Base):
    __tablename__ = "paper_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    strategy_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    qty: Mapped[int] = mapped_column(Integer, default=0)
    avg_price: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    last_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class PaperAuditEvent(Base):
    __tablename__ = "paper_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    paper_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision: Mapped[str] = mapped_column(String(16), default="deny")
    reason_codes_json: Mapped[str] = mapped_column(Text, default="[]")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
