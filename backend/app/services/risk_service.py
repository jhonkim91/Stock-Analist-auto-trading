from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.app.core.config import get_config
from backend.app.models.tables import IndicatorSnapshot, ScreenResult


@dataclass
class RiskPlan:
    entry_price: float
    stop_price: float
    target_price: float
    risk_per_share: float
    reward_risk_ratio: float
    position_size: int
    position_notional: float
    rr_score: float
    risk_basis: str


class RiskService:
    def __init__(self) -> None:
        self.config = get_config("risk")

    def calculate(
        self,
        indicator: IndicatorSnapshot,
        equity: float | None = None,
        risk_metadata: dict[str, Any] | None = None,
    ) -> RiskPlan:
        """손절가, 목표가, 손익비, 포지션 크기를 계산한다."""
        portfolio = self.config["portfolio"]
        risk_config = self.config["risk"]
        equity_value = float(equity or portfolio["equity"])
        entry_price = float(indicator.close)
        stop_price, risk_basis = self._select_stop_price(indicator, entry_price, risk_config, risk_metadata)
        risk_per_share = max(entry_price - stop_price, 1e-9)
        target_rr = max(float(risk_config["target_reward_risk"]), 1e-9)
        target_price = self._select_target_price(indicator, entry_price, risk_per_share, target_rr, risk_metadata)
        position_risk_budget = equity_value * float(portfolio["risk_fraction"])
        risk_qty = int(position_risk_budget // risk_per_share)
        max_notional_qty = int((equity_value * float(portfolio["max_position_fraction"])) // entry_price)
        qty = max(min(risk_qty, max_notional_qty), 0)
        position_notional = qty * entry_price
        reward_risk_ratio = max((target_price - entry_price) / risk_per_share, 0.0)
        rr_score = min(reward_risk_ratio / target_rr, 1.0)
        return RiskPlan(
            entry_price=round(entry_price, 4),
            stop_price=round(stop_price, 4),
            target_price=round(target_price, 4),
            risk_per_share=round(risk_per_share, 4),
            reward_risk_ratio=round(reward_risk_ratio, 4),
            position_size=qty,
            position_notional=round(position_notional, 2),
            rr_score=round(rr_score, 4),
            risk_basis=risk_basis,
        )

    def bot_candidate_gate(self, screen_result: ScreenResult) -> dict[str, Any]:
        """저장된 screen result를 bot preview decision에 사용할 수 있는지 fail-closed로 평가한다."""
        reasons: list[str] = []
        if not bool(screen_result.passed):
            reasons.append("SCREEN_RESULT_NOT_PASSED")
        if int(screen_result.position_size or 0) <= 0:
            reasons.append("POSITION_SIZE_UNAVAILABLE")
        if self._as_float(screen_result.entry_price) is None:
            reasons.append("ENTRY_PRICE_UNAVAILABLE")
        if self._as_float(screen_result.stop_price) is None:
            reasons.append("STOP_PRICE_UNAVAILABLE")
        if self._as_float(screen_result.target_price) is None:
            reasons.append("TARGET_PRICE_UNAVAILABLE")
        if self._as_float(screen_result.reward_risk_ratio) is None:
            reasons.append("REWARD_RISK_RATIO_UNAVAILABLE")
        max_notional = float(self.config["portfolio"]["equity"]) * float(self.config["portfolio"]["max_position_fraction"])
        if float(screen_result.position_notional or 0.0) > max_notional:
            reasons.append("POSITION_NOTIONAL_LIMIT_EXCEEDED")
        return {
            "passed": not reasons,
            "reason_codes": reasons,
            "position_size": int(screen_result.position_size or 0),
            "position_notional": float(screen_result.position_notional or 0.0),
            "reward_risk_ratio": self._as_float(screen_result.reward_risk_ratio),
        }

    def _select_stop_price(
        self,
        indicator: IndicatorSnapshot,
        entry_price: float,
        risk_config: dict[str, Any],
        risk_metadata: dict[str, Any] | None,
    ) -> tuple[float, str]:
        strategy_stop = self._as_float((risk_metadata or {}).get("suggested_stop_price"))
        strategy_basis = str((risk_metadata or {}).get("risk_basis") or "strategy_suggested_stop_price")
        pivot_stop = self._as_float(getattr(indicator, "pivot_low_20_prev", None))
        atr_stop = self._atr_stop(indicator, entry_price, risk_config)
        hard_stop = entry_price * (1 - float(risk_config["hard_stop_pct"]))

        for stop_price, risk_basis in (
            (strategy_stop, strategy_basis),
            (pivot_stop, "pivot_low_20_prev"),
            (atr_stop, "atr_stop"),
            (hard_stop, "hard_stop"),
        ):
            if stop_price is not None and 0 < stop_price < entry_price:
                return float(stop_price), risk_basis

        return max(entry_price * 0.01, 1e-9), "hard_stop"

    def _select_target_price(
        self,
        indicator: IndicatorSnapshot,
        entry_price: float,
        risk_per_share: float,
        target_rr: float,
        risk_metadata: dict[str, Any] | None,
    ) -> float:
        explicit_target = self._metadata_target_price(risk_metadata)
        if explicit_target is not None:
            return explicit_target

        indicator_target = self._indicator_target_price(indicator, entry_price)
        if indicator_target is not None:
            return indicator_target

        return entry_price + risk_per_share * target_rr

    @classmethod
    def _metadata_target_price(cls, risk_metadata: dict[str, Any] | None) -> float | None:
        metadata = risk_metadata or {}
        for key in ("suggested_target_price", "target_price", "profit_target_price", "take_profit_price"):
            target_price = cls._as_float(metadata.get(key))
            if target_price is not None and target_price > 0:
                return target_price
        return None

    @classmethod
    def _indicator_target_price(cls, indicator: IndicatorSnapshot, entry_price: float) -> float | None:
        target_price = cls._as_float(getattr(indicator, "target_price", None))
        if target_price is not None and target_price > entry_price:
            return target_price
        return None

    def _atr_stop(self, indicator: IndicatorSnapshot, entry_price: float, risk_config: dict[str, Any]) -> float:
        atr = (
            self._as_float(getattr(indicator, "atr20", None))
            or self._as_float(getattr(indicator, "atr14", None))
            or self._atr_from_pct(indicator, entry_price)
            or entry_price * 0.03
        )
        return entry_price - atr * float(risk_config["atr_stop_multiple"])

    @staticmethod
    def _atr_from_pct(indicator: IndicatorSnapshot, entry_price: float) -> float | None:
        atr20_pct = RiskService._as_float(getattr(indicator, "atr20_pct", None))
        if atr20_pct is None or atr20_pct <= 0:
            return None
        return entry_price * atr20_pct

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
