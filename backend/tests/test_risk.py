from __future__ import annotations

from sqlalchemy import select

from backend.app.models.tables import IndicatorSnapshot
from backend.app.services.risk_service import RiskService


def test_risk_service_calculates_position_size_and_rr(seeded_db):
    indicator = seeded_db.scalar(
        select(IndicatorSnapshot)
        .where(IndicatorSnapshot.symbol == "KR009")
        .order_by(IndicatorSnapshot.trade_date.desc())
        .limit(1)
    )
    risk = RiskService().calculate(indicator)

    assert risk.entry_price > risk.stop_price
    assert risk.target_price > risk.entry_price
    assert risk.risk_per_share > 0
    assert risk.reward_risk_ratio >= 2.5
    assert risk.position_size > 0
    assert risk.position_notional > 0
