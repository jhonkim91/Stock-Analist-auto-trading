from __future__ import annotations

from types import SimpleNamespace

import pytest
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


def test_risk_service_uses_explicit_target_for_reward_risk_score():
    indicator = SimpleNamespace(close=100.0, pivot_low_20_prev=95.0, atr20=None, atr20_pct=None)
    risk_service = RiskService()

    risk = risk_service.calculate(
        indicator,
        equity=100000.0,
        risk_metadata={
            "suggested_stop_price": 95.0,
            "suggested_target_price": 108.0,
            "risk_basis": "unit_test_stop",
        },
    )

    assert risk.target_price == 108.0
    assert risk.risk_per_share == 5.0
    assert risk.reward_risk_ratio == pytest.approx(1.6)
    assert risk.rr_score == pytest.approx(0.64)


def test_rr_ok_can_be_false_for_valid_trade_when_explicit_target_is_below_required_rr():
    indicator = SimpleNamespace(close=100.0, pivot_low_20_prev=95.0, atr20=None, atr20_pct=None)
    risk_service = RiskService()

    risk = risk_service.calculate(
        indicator,
        equity=100000.0,
        risk_metadata={
            "suggested_stop_price": 95.0,
            "suggested_target_price": 108.0,
            "risk_basis": "unit_test_stop",
        },
    )

    target_rr = float(risk_service.config["risk"]["target_reward_risk"])
    rr_ok = risk.reward_risk_ratio >= target_rr

    assert risk.entry_price > risk.stop_price
    assert risk.target_price > risk.entry_price
    assert risk.position_size > 0
    assert risk.reward_risk_ratio < target_rr
    assert risk.rr_score < 1.0
    assert rr_ok is False
