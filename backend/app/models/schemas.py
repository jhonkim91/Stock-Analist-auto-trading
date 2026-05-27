from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.app.strategies.registry import DEFAULT_STRATEGY_NAMES


class SeedResponse(BaseModel):
    symbols: int
    daily_rows: int
    index_rows: int
    sector_rows: int
    fundamental_rows: int


class IndicatorResponse(BaseModel):
    rows: int
    start_date: date | None = None
    end_date: date | None = None
    mode: str | None = None
    symbols: int | None = None
    deleted_rows: int | None = None


class RegimeResponse(BaseModel):
    benchmark: str
    trade_date: date
    regime: str
    index_regime: str | None = None
    market_score: float
    close_vs_200dma: float | None
    sma50_vs_200dma: float | None
    weekly_close: float | None
    weekly_sma30: float | None
    weekly_sma30_slope: float | None
    breadth_trade_date: date | None = None
    breadth_regime: str | None = None
    breadth_score: float | None = None
    breadth_score_available: bool = False
    breadth_advance_decline_ratio: float | None = None
    breadth_advance_decline_available: bool = False
    breadth_52w_high_low_ratio: float | None = None
    breadth_52w_high_low_available: bool = False
    breadth_ma50_participation: float | None = None
    breadth_ma50_participation_available: bool = False


class ScreenerRunRequest(BaseModel):
    trade_date: date | None = None
    strategies: list[str] = Field(default_factory=lambda: list(DEFAULT_STRATEGY_NAMES))


class ScreenerStrategyResponse(BaseModel):
    name: str
    display_name: str
    description: str
    is_default: bool
    is_available: bool
    required_fields: list[str]
    limitations: list[str]


class ScreenerResultResponse(BaseModel):
    trade_date: date
    symbol: str
    name: str
    strategy_name: str
    strategy_tag: str
    passed: bool
    grade: str
    total_score: float
    entry_price: float | None
    stop_price: float | None
    target_price: float | None
    reward_risk_ratio: float | None
    position_size: int
    risk_basis: str | None
    reason_summary: str
    pass_flags_json: dict[str, bool]
    failed_conditions_json: list[str]
    score_details_json: dict[str, Any]
    risk_details_json: dict[str, Any]
    triggered_conditions: list[str]
    score_breakdown: dict[str, Any]
    risk_flags: dict[str, Any]
    data_quality_flags: dict[str, Any]
    metadata: dict[str, Any]
    risk_metadata: dict[str, Any]
    explanation: str
    rationale: str
    pass_flags: dict[str, bool]
    failed_conditions: list[str]
    risk_per_share: float | None
    position_notional: float | None


class BacktestRunRequest(BaseModel):
    strategy_name: str = "trend_breakout"
    start_date: date | None = None
    end_date: date | None = None
    initial_equity: float | None = None
    top_n: int | None = Field(default=None, ge=1)
    max_positions: int | None = Field(default=None, ge=1)
    rebalance_frequency: Literal["daily", "weekly", "monthly"] | None = None
    weighting: Literal["equal_risk", "equal_weight"] | None = None
    allow_overlap_positions: bool | None = None


class BrokerPreviewRequest(BaseModel):
    symbol: str
    side: str = "buy"
    qty: int
    limit_price: float | None = None
    stop_price: float | None = None
    strategy_tag: str | None = None
    venue: str | None = None
    as_of: datetime | None = None


class PaperOrderPreviewRequest(BaseModel):
    symbol: str
    side: str = "buy"
    qty: int
    limit_price: float | None = None
    stop_price: float | None = None
    strategy_tag: str | None = None
    venue: str | None = None
    as_of: datetime | None = None


class PaperOrderSubmitRequest(PaperOrderPreviewRequest):
    confirm: bool = False
    idempotency_key: str | None = None


class PaperOrderCancelRequest(BaseModel):
    paper_order_id: str
    confirm: bool = False
    idempotency_key: str | None = None


class PaperSyncRequest(BaseModel):
    scope: Literal["orders", "fills", "positions", "portfolio", "all"] = "all"


class BrokerAdapterStatus(BaseModel):
    """broker adapter 상태를 secret 없이 표현하는 공통 schema다."""

    name: str
    mode: str
    enabled: bool = False
    paper_trading_enabled: bool = False
    live_trading_enabled: bool = False
    network_enabled: bool = False
    can_submit: bool = False
    can_cancel: bool = False
    can_sync: bool = False
    reason: str | None = None
    adapter_boundary: str | None = None
    live_fallback_enabled: bool = False


class KisTokenMetadataResponse(BaseModel):
    """KIS token lifecycle metadata를 raw value 없이 표현한다."""

    state: str
    app_key_configured: bool = False
    app_secret_configured: bool = False
    token_issued: bool = False
    refresh_token_present: bool = False
    token_cache_enabled: bool = False
    token_file_persistence_enabled: bool = False
    token_db_persistence_enabled: bool = False
    token_raw_value_persisted: bool = False
    access_token: str | None = None
    refresh_token: str | None = None
    access_token_fingerprint: str | None = None
    refresh_token_fingerprint: str | None = None
    expires_at: str | None = None
    expired: bool = False


class KisRequestSigningStatus(BaseModel):
    """KIS hashkey signing 상태를 fail-closed metadata로 표현한다."""

    hashkey_confirmed: bool = False
    hashkey_provider_configured: bool = False
    signing_enabled: bool = False
    network_call_performed: bool = False
    fail_closed: bool = True
    reason: str | None = None


class PaperBotRunRequest(BaseModel):
    auto_submit: bool | None = None


class NotificationTestRequest(BaseModel):
    channel_alias: str | None = None
    message: str = Field(default="notification test", max_length=1000)
    dry_run: bool = True


class NotificationOutboxEventRequest(BaseModel):
    event_type: str
    channel_alias: str | None = None
    subject: str | None = None
    payload_summary: dict[str, Any] = Field(default_factory=dict)


class ReportNotifyRequest(BaseModel):
    mode: Literal["summary", "summary_and_file"] = "summary"
    channel_alias: str | None = None
    dry_run: bool | None = None


class ReportAutomationRunRequest(BaseModel):
    """일간/주간 report automation run-once 요청이다."""

    report_types: list[Literal["daily", "weekly"]] = Field(default_factory=lambda: ["daily", "weekly"])
    report_date: date | None = None
    notify: bool = False
    channel_alias: str | None = None
    dry_run: bool | None = None
    confirm: bool = False


class ImportConfirmRequest(BaseModel):
    run_id: str


class ExternalPreviewDailyOhlcvRequest(BaseModel):
    source_id: str
    symbol: str
    start_date: date
    end_date: date


class GenericResponse(BaseModel):
    ok: bool
    detail: str
    data: dict[str, Any] = Field(default_factory=dict)
