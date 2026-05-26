from __future__ import annotations

import pandas as pd

from backend.app.models.tables import IndexOhlcv
from backend.app.services.regime_service import RegimeService


def test_market_regime_uses_daily_resampled_weekly_conditions(seeded_db):
    regime = RegimeService(seeded_db).detect_market_regime()

    assert regime["benchmark"] == "KOSPI_SAMPLE"
    assert regime["regime"] == "bull"
    assert regime["index_regime"] == "bull"
    assert regime["weekly_close"] is not None
    assert regime["weekly_sma30"] is not None
    assert regime["weekly_sma30_slope"] is not None
    assert regime["breadth_score_available"] is True
    assert regime["breadth_regime"] in {"strong", "neutral", "weak"}
    assert regime["breadth_advance_decline_available"] is True
    assert regime["breadth_52w_high_low_available"] is True
    assert regime["breadth_ma50_participation_available"] is True


def test_market_regime_marks_breadth_not_available_without_universe_data(db_session):
    dates = pd.bdate_range(end="2026-05-20", periods=260)
    db_session.add_all(
        [
            IndexOhlcv(
                trade_date=dt.date(),
                symbol="KOSPI_SAMPLE",
                open=2500.0 + index,
                high=2510.0 + index,
                low=2490.0 + index,
                close=2500.0 + index,
                volume=500000000,
            )
            for index, dt in enumerate(dates)
        ]
    )
    db_session.commit()

    regime = RegimeService(db_session).detect_market_regime()

    assert regime["breadth_regime"] == "not_available"
    assert regime["breadth_score_available"] is False
    assert regime["breadth_score"] is None
