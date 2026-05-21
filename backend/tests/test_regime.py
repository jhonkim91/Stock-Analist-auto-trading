from __future__ import annotations

from backend.app.services.regime_service import RegimeService


def test_market_regime_uses_daily_resampled_weekly_conditions(seeded_db):
    regime = RegimeService(seeded_db).detect_market_regime()

    assert regime["benchmark"] == "KOSPI_SAMPLE"
    assert regime["regime"] == "bull"
    assert regime["weekly_close"] is not None
    assert regime["weekly_sma30"] is not None
    assert regime["weekly_sma30_slope"] is not None
