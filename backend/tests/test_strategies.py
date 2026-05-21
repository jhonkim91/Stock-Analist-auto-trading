from __future__ import annotations

import json
from datetime import date

from sqlalchemy import select

from backend.app.models.tables import IndicatorSnapshot, ScreenResult
from backend.app.repositories.market_repository import MarketRepository
from backend.app.services.screener_service import ScreenerService


def test_canslim_uses_only_effective_date_not_future_fundamentals(seeded_db):
    indicator = seeded_db.scalar(
        select(IndicatorSnapshot)
        .where(IndicatorSnapshot.symbol == "KR009")
        .order_by(IndicatorSnapshot.trade_date.desc())
        .limit(1)
    )
    fundamentals = MarketRepository(seeded_db).fundamentals_asof("KR009", indicator.trade_date)

    assert fundamentals is not None
    assert fundamentals.effective_date <= indicator.trade_date
    assert fundamentals.effective_date == date(2026, 4, 15)
    assert fundamentals.quarterly_eps_growth < 0.60


def test_screener_stores_required_pass_fail_evidence(seeded_db):
    result = ScreenerService(seeded_db).run()

    assert result["rows"] >= 45
    rows = list(seeded_db.scalars(select(ScreenResult)).all())
    assert rows
    assert any(row.passed for row in rows)
    for row in rows:
        flags = json.loads(row.pass_flags)
        failed = json.loads(row.failed_conditions)
        assert isinstance(row.passed, bool)
        assert isinstance(flags, dict)
        assert isinstance(failed, list)
        assert row.reason_summary

    low_liquidity = seeded_db.scalar(
        select(ScreenResult).where(ScreenResult.symbol == "KR011").order_by(ScreenResult.total_score.desc()).limit(1)
    )
    assert low_liquidity is not None
    assert "liquidity_ok" in json.loads(low_liquidity.failed_conditions)
