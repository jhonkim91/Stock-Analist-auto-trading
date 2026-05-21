from __future__ import annotations

from sqlalchemy import select

from backend.app.models.tables import IndicatorSnapshot


def test_indicator_snapshot_contains_required_fields(seeded_db):
    latest_date = seeded_db.scalar(select(IndicatorSnapshot.trade_date).order_by(IndicatorSnapshot.trade_date.desc()).limit(1))
    rows = list(seeded_db.scalars(select(IndicatorSnapshot).where(IndicatorSnapshot.trade_date == latest_date)).all())

    assert len(rows) >= 15
    sample = rows[0]
    assert sample.sma20 is not None
    assert sample.volume_ma20 is not None
    assert sample.atr14 is not None
    assert sample.turnover_value > 0
    assert sample.distance_from_52w_high is not None
    assert 0 <= sample.market_score <= 1
    assert 0 <= sample.sector_rs_score <= 1
    assert 0 <= sample.relative_strength_score <= 1
