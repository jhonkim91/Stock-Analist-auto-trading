from __future__ import annotations

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


def get_strategy_registry(strategy_config: Mapping[str, Mapping[str, Any]]) -> dict[str, BaseStrategy]:
    """Return strategy instances in the default stable order."""
    return {
        strategy_name: STRATEGY_CLASSES[strategy_name](dict(strategy_config[strategy_name]))
        for strategy_name in DEFAULT_STRATEGY_NAMES
    }


def get_available_strategy_registry(strategy_config: Mapping[str, Mapping[str, Any]]) -> dict[str, BaseStrategy]:
    """Return every strategy available for explicit execution."""
    return {
        strategy_name: STRATEGY_CLASSES[strategy_name](dict(strategy_config[strategy_name]))
        for strategy_name in AVAILABLE_STRATEGY_NAMES
    }
