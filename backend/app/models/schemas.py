from __future__ import annotations

from datetime import date
from typing import Any

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


class RegimeResponse(BaseModel):
    benchmark: str
    trade_date: date
    regime: str
    market_score: float
    close_vs_200dma: float | None
    sma50_vs_200dma: float | None
    weekly_close: float | None
    weekly_sma30: float | None
    weekly_sma30_slope: float | None


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


class BacktestRunRequest(BaseModel):
    strategy_name: str = "trend_breakout"
    start_date: date | None = None
    end_date: date | None = None
    initial_equity: float | None = None


class BrokerPreviewRequest(BaseModel):
    symbol: str
    side: str = "buy"
    qty: int
    limit_price: float | None = None
    stop_price: float | None = None
    strategy_tag: str | None = None


class PaperOrderPreviewRequest(BaseModel):
    symbol: str
    side: str = "buy"
    qty: int
    limit_price: float | None = None
    stop_price: float | None = None
    strategy_tag: str | None = None


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
