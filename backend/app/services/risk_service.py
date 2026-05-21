from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.config import get_config
from backend.app.models.tables import IndicatorSnapshot


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


class RiskService:
    def __init__(self) -> None:
        self.config = get_config("risk")

    def calculate(self, indicator: IndicatorSnapshot, equity: float | None = None) -> RiskPlan:
        """손절가, 목표가, 손익비, 포지션 크기를 계산한다."""
        portfolio = self.config["portfolio"]
        risk_config = self.config["risk"]
        equity_value = float(equity or portfolio["equity"])
        entry_price = float(indicator.close)
        atr_stop = entry_price - float(indicator.atr20 or indicator.atr14 or entry_price * 0.03) * float(
            risk_config["atr_stop_multiple"]
        )
        hard_stop = entry_price * (1 - float(risk_config["hard_stop_pct"]))
        pivot_stop = float(indicator.pivot_low_20_prev or 0)
        stop_price = max(price for price in (atr_stop, hard_stop, pivot_stop) if price > 0)
        if stop_price >= entry_price:
            stop_price = min(atr_stop, hard_stop)
        risk_per_share = max(entry_price - stop_price, 1e-9)
        target_rr = float(risk_config["target_reward_risk"])
        target_price = entry_price + risk_per_share * target_rr
        position_risk_budget = equity_value * float(portfolio["risk_fraction"])
        risk_qty = int(position_risk_budget // risk_per_share)
        max_notional_qty = int((equity_value * float(portfolio["max_position_fraction"])) // entry_price)
        qty = max(min(risk_qty, max_notional_qty), 0)
        position_notional = qty * entry_price
        reward_risk_ratio = (target_price - entry_price) / risk_per_share
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
        )
