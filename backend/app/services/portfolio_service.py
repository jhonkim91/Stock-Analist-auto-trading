from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_config
from backend.app.models.tables import Position, ScreenResult


class PortfolioService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def risk_summary(self) -> dict[str, object]:
        positions = list(self.db.scalars(select(Position)).all())
        latest_date = self.db.scalar(select(ScreenResult.trade_date).order_by(ScreenResult.trade_date.desc()).limit(1))
        proposed = []
        if latest_date:
            proposed = list(
                self.db.scalars(select(ScreenResult).where(ScreenResult.trade_date == latest_date, ScreenResult.passed)).all()
            )
        risk_config = get_config("risk")
        account_equity = float(risk_config["portfolio"]["equity"])
        risk_per_trade = account_equity * float(risk_config["portfolio"]["risk_fraction"])
        total_position_notional = sum(position.avg_price * position.qty for position in positions)
        proposed_notional = sum(float(row.position_notional or 0) for row in proposed)
        available_risk_budget = max(risk_per_trade * max(1, len(proposed)) - proposed_notional * 0.01, 0)
        warnings = ["mock/synthetic 상태입니다.", "실제 positions 또는 broker 체결은 Phase 2 범위가 아닙니다."]
        return {
            "account_equity": account_equity,
            "risk_per_trade": risk_per_trade,
            "max_daily_loss": account_equity * 0.03,
            "open_positions_count": len(positions),
            "total_position_notional": total_position_notional,
            "available_risk_budget": round(available_risk_budget, 2),
            "warnings": warnings,
            "latest_signal_date": latest_date,
            "proposed_positions": len(proposed),
            "proposed_notional": proposed_notional,
            "broker_mode": "mock_preview_only",
            "open_positions": len(positions),
            "gross_exposure": total_position_notional,
        }
