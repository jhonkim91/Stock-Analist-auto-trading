from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import select

from backend.app.models.tables import IndicatorSnapshot
from backend.app.repositories.market_repository import MarketRepository


def test_indicator_snapshot_contains_required_fields(seeded_db):
    latest_date = seeded_db.scalar(select(IndicatorSnapshot.trade_date).order_by(IndicatorSnapshot.trade_date.desc()).limit(1))
    rows = list(seeded_db.scalars(select(IndicatorSnapshot).where(IndicatorSnapshot.trade_date == latest_date)).all())

    assert len(rows) >= 15
    sample = rows[0]
    assert sample.sma20 is not None
    assert sample.ema20 is not None
    assert sample.low is not None
    assert sample.volume_ma20 is not None
    assert sample.atr14 is not None
    assert sample.turnover_value > 0
    assert sample.distance_from_52w_high is not None
    assert 0 <= sample.market_score <= 1
    assert 0 <= sample.sector_rs_score <= 1
    assert 0 <= sample.relative_strength_score <= 1


def test_indicator_snapshot_contains_exact_ema20_and_low(seeded_db):
    latest = seeded_db.scalar(
        select(IndicatorSnapshot)
        .where(IndicatorSnapshot.symbol == "KR009")
        .order_by(IndicatorSnapshot.trade_date.desc())
        .limit(1)
    )
    assert latest is not None

    daily = MarketRepository(seeded_db).daily_df(end_date=latest.trade_date)
    symbol_daily = daily[daily["symbol"] == latest.symbol].sort_values("trade_date")
    expected_ema20 = (
        symbol_daily["close"]
        .astype(float)
        .ewm(span=20, adjust=False, min_periods=20)
        .mean()
        .iloc[-1]
    )
    expected_low = float(symbol_daily.iloc[-1]["low"])

    assert latest.ema20 == pytest.approx(float(expected_ema20))
    assert latest.low == pytest.approx(expected_low)


def test_indicator_snapshot_contains_asof_weekly_fields(seeded_db):
    latest = seeded_db.scalar(
        select(IndicatorSnapshot)
        .where(IndicatorSnapshot.symbol == "KR009")
        .order_by(IndicatorSnapshot.trade_date.desc())
        .limit(1)
    )
    assert latest is not None

    daily = MarketRepository(seeded_db).daily_df(end_date=latest.trade_date)
    symbol_daily = daily[daily["symbol"] == latest.symbol].sort_values("trade_date")
    weekly = (
        symbol_daily.set_index(pd.to_datetime(symbol_daily["trade_date"]))
        .resample("W-FRI")
        .agg({"close": "last"})
        .dropna()
    )
    weekly["weekly_sma30"] = weekly["close"].rolling(30, min_periods=30).mean()
    weekly["weekly_sma30_slope"] = weekly["weekly_sma30"] - weekly["weekly_sma30"].shift(4)
    weekly_latest = weekly.iloc[-1]

    assert latest.weekly_close == pytest.approx(float(weekly_latest["close"]))
    assert latest.weekly_sma30 == pytest.approx(float(weekly_latest["weekly_sma30"]))
    assert latest.weekly_sma30_slope == pytest.approx(float(weekly_latest["weekly_sma30_slope"]))
