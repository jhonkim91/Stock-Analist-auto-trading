from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.models.tables import FundamentalsPti, IndicatorSnapshot


@dataclass
class StrategyResult:
    strategy_tag: str
    passed: bool
    pass_flags: dict[str, bool]
    failed_conditions: list[str] = field(default_factory=list)
    reason_summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseStrategy:
    name = "base"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def evaluate(
        self,
        indicator: IndicatorSnapshot,
        fundamentals: FundamentalsPti | None,
        market_regime: str,
    ) -> StrategyResult:
        raise NotImplementedError

    @staticmethod
    def _all_flags(flags: dict[str, bool]) -> bool:
        return all(flags.values())

    @staticmethod
    def _failed(flags: dict[str, bool]) -> list[str]:
        return [key for key, value in flags.items() if not value]

    @staticmethod
    def _summary(strategy_name: str, passed: bool, failed: list[str]) -> str:
        if passed:
            return f"{strategy_name} 조건을 모두 충족했습니다."
        return f"{strategy_name} 탈락 조건: {', '.join(failed)}"

    @staticmethod
    def _gt(left: float | None, right: float | None) -> bool:
        return left is not None and right is not None and left > right

    @staticmethod
    def _gte(left: float | None, right: float | None) -> bool:
        return left is not None and right is not None and left >= right
