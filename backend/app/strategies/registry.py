from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from typing import Any

from backend.app.strategies.base import BaseStrategy
from backend.app.strategies.canslim_lite import CanslimLiteStrategy
from backend.app.strategies.darvas_box import DarvasBoxStrategy
from backend.app.strategies.momentum_rank import MomentumRankStrategy
from backend.app.strategies.new_high_breakout import NewHighBreakoutStrategy
from backend.app.strategies.pullback_20ema import Pullback20EmaStrategy
from backend.app.strategies.relative_strength_leader import RelativeStrengthLeaderStrategy
from backend.app.strategies.stage_analysis_weekly import StageAnalysisWeeklyStrategy
from backend.app.strategies.trend_breakout import TrendBreakoutStrategy
from backend.app.strategies.vcp_breakout import VcpBreakoutStrategy

DEFAULT_STRATEGY_NAMES = (
    "trend_breakout",
    "vcp_breakout",
    "canslim_lite",
    "new_high_breakout",
    "pullback_20ema",
)
AVAILABLE_STRATEGY_NAMES = (
    *DEFAULT_STRATEGY_NAMES,
    "momentum_rank",
    "relative_strength_leader",
    "darvas_box",
    "stage_analysis_weekly",
)

STRATEGY_CLASSES: dict[str, type[BaseStrategy]] = {
    "trend_breakout": TrendBreakoutStrategy,
    "vcp_breakout": VcpBreakoutStrategy,
    "canslim_lite": CanslimLiteStrategy,
    "new_high_breakout": NewHighBreakoutStrategy,
    "pullback_20ema": Pullback20EmaStrategy,
    "momentum_rank": MomentumRankStrategy,
    "relative_strength_leader": RelativeStrengthLeaderStrategy,
    "darvas_box": DarvasBoxStrategy,
    "stage_analysis_weekly": StageAnalysisWeeklyStrategy,
}


@dataclass(frozen=True)
class StrategyMetadata:
    name: str
    display_name: str
    description: str
    required_fields: tuple[str, ...]
    limitations: tuple[str, ...]


STRATEGY_METADATA: dict[str, StrategyMetadata] = {
    "trend_breakout": StrategyMetadata(
        name="trend_breakout",
        display_name="Trend Breakout",
        description="Trend-aligned breakout candidate using moving-average stack, relative strength, 52-week high proximity, and volume surge.",
        required_fields=(
            "close",
            "sma50",
            "sma150",
            "sma200",
            "sma200_slope",
            "rs_percentile",
            "high_52w",
            "volume",
            "volume_ma50",
        ),
        limitations=(
            "Requires recomputed daily indicator snapshots.",
            "Common liquidity and reward/risk filters still apply after strategy conditions.",
        ),
    ),
    "vcp_breakout": StrategyMetadata(
        name="vcp_breakout",
        display_name="VCP Breakout",
        description="Volatility-contraction breakout candidate using trend stack, ATR/std contraction, dry-up, pivot breakout, volume surge, and relative strength.",
        required_fields=(
            "close",
            "sma50",
            "sma150",
            "sma200",
            "sma200_slope",
            "atr20_pct",
            "atr20_pct_ma60",
            "std20",
            "std60",
            "volume_dry_up",
            "breakout",
            "volume",
            "volume_ma50",
            "rs_percentile",
        ),
        limitations=(
            "Requires indicator fields derived from enough lookback history.",
            "Pivot distance limiting is config-gated and disabled unless explicitly enabled.",
        ),
    ),
    "canslim_lite": StrategyMetadata(
        name="canslim_lite",
        display_name="CANSLIM Lite",
        description="Lightweight CANSLIM-style screen combining as-of fundamentals, breakout status, relative strength, and market-regime alignment.",
        required_fields=(
            "quarterly_eps_growth",
            "sales_growth",
            "rs_percentile",
            "breakout",
            "market_regime",
        ),
        limitations=(
            "Uses only fundamentals with effective_date less than or equal to the trade date.",
            "Requires the configured bull market regime condition to pass.",
        ),
    ),
    "new_high_breakout": StrategyMetadata(
        name="new_high_breakout",
        display_name="New High Breakout",
        description="52-week high or near-new-high breakout candidate with trend and volume confirmation.",
        required_fields=(
            "close",
            "high_52w",
            "breakout",
            "volume",
            "volume_ma50",
            "rs_percentile",
            "sma50",
            "sma150",
            "sma200",
        ),
        limitations=(
            "Fails closed when 52-week high or volume baseline fields are missing.",
            "Common risk sizing is unchanged from the existing screener flow.",
        ),
    ),
    "pullback_20ema": StrategyMetadata(
        name="pullback_20ema",
        display_name="20 EMA Pullback",
        description="Established uptrend pullback candidate that checks low touch near EMA20, close reclaim, relative strength, volume, and ATR risk.",
        required_fields=(
            "close",
            "low",
            "ema20",
            "sma50",
            "sma150",
            "sma200",
            "sma200_slope",
            "rs_percentile",
            "volume_ratio_50",
            "atr20_pct",
        ),
        limitations=(
            "Requires EMA20 and low fields from the latest indicator migration.",
            "Designed for screening only; it does not create orders or paper fills.",
        ),
    ),
    "momentum_rank": StrategyMetadata(
        name="momentum_rank",
        display_name="Momentum Rank",
        description="Available-only momentum candidate using relative-strength percentile, RS score, trend score, sector RS, market score, and trend stack.",
        required_fields=(
            "rs_percentile",
            "relative_strength_score",
            "trend_score",
            "sector_rs_score",
            "market_score",
            "close",
            "sma50",
            "sma150",
            "sma200",
            "sma200_slope",
        ),
        limitations=(
            "Available-only; it is not part of the default screener run unless explicitly selected.",
            "Uses indicator snapshot ranks only and does not alter scoring weights.",
        ),
    ),
    "relative_strength_leader": StrategyMetadata(
        name="relative_strength_leader",
        display_name="Relative Strength Leader",
        description="Available-only leadership screen for strong market and sector relative-strength candidates near 52-week highs.",
        required_fields=(
            "rs_percentile",
            "relative_strength_score",
            "sector_rs_score",
            "close",
            "high_52w",
            "sma50",
            "sma150",
            "sma200_slope",
            "volume_ratio_50",
        ),
        limitations=(
            "Available-only; it must be explicitly selected.",
            "Fails closed when RS, high, or trend fields are unavailable.",
        ),
    ),
    "darvas_box": StrategyMetadata(
        name="darvas_box",
        display_name="Darvas Box",
        description="Available-only approximate Darvas Box breakout using prior pivot box, breakout, volume surge, relative strength, and trend context.",
        required_fields=(
            "pivot_high_20_prev",
            "pivot_low_20_prev",
            "close",
            "breakout",
            "volume",
            "volume_ma50",
            "rs_percentile",
            "sma50",
            "sma150",
        ),
        limitations=(
            "Available-only; it must be explicitly selected.",
            "Requires prior 20-day pivot fields and rejects invalid box ranges.",
        ),
    ),
    "stage_analysis_weekly": StrategyMetadata(
        name="stage_analysis_weekly",
        display_name="Stage Analysis Weekly",
        description="Available-only Stage 2 approximation using weekly close/SMA30 slope plus daily trend, relative strength, volume, and regime filter.",
        required_fields=(
            "weekly_close",
            "weekly_sma30",
            "weekly_sma30_slope",
            "close",
            "sma50",
            "sma150",
            "sma200",
            "rs_percentile",
            "volume_ratio_50",
            "market_regime",
        ),
        limitations=(
            "Available-only; it must be explicitly selected.",
            "Fails closed when weekly indicator fields are unavailable.",
        ),
    ),
}


def get_strategy_registry(strategy_config: Mapping[str, Mapping[str, Any]]) -> dict[str, BaseStrategy]:
    """Return strategy instances in the default stable order."""
    return {
        strategy_name: STRATEGY_CLASSES[strategy_name](_strategy_config(strategy_config, strategy_name))
        for strategy_name in DEFAULT_STRATEGY_NAMES
    }


def get_available_strategy_registry(strategy_config: Mapping[str, Mapping[str, Any]]) -> dict[str, BaseStrategy]:
    """Return every strategy available for explicit execution."""
    return {
        strategy_name: STRATEGY_CLASSES[strategy_name](_strategy_config(strategy_config, strategy_name))
        for strategy_name in AVAILABLE_STRATEGY_NAMES
    }


def _strategy_config(strategy_config: Mapping[str, Mapping[str, Any]], strategy_name: str) -> dict[str, Any]:
    common = strategy_config.get("common", {})
    hardening = common.get("hardening", {}) if isinstance(common, Mapping) else {}
    return {**dict(hardening), **dict(strategy_config[strategy_name])}


def list_strategy_metadata() -> list[dict[str, object]]:
    """Return frontend strategy selector metadata in the available strategy order."""
    default_names = set(DEFAULT_STRATEGY_NAMES)
    return [
        {
            "name": metadata.name,
            "display_name": metadata.display_name,
            "description": metadata.description,
            "is_default": strategy_name in default_names,
            "is_available": strategy_name in AVAILABLE_STRATEGY_NAMES,
            "required_fields": list(metadata.required_fields),
            "limitations": list(metadata.limitations),
        }
        for strategy_name in AVAILABLE_STRATEGY_NAMES
        for metadata in (STRATEGY_METADATA[strategy_name],)
    ]
