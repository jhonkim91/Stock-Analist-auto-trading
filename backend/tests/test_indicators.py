from __future__ import annotations

from datetime import timedelta

import pandas as pd
import pytest
from sqlalchemy import select

from backend.app.models.tables import IndicatorSnapshot
from backend.app.repositories.market_repository import MarketRepository
from backend.app.services.indicator_service import IndicatorService
from backend.app.services.market_data_service import MarketDataService


def _snapshot_payloads(db, *, symbol: str, start_date, end_date) -> list[dict[str, object]]:
    rows = list(
        db.scalars(
            select(IndicatorSnapshot)
            .where(
                IndicatorSnapshot.symbol == symbol,
                IndicatorSnapshot.trade_date >= start_date,
                IndicatorSnapshot.trade_date <= end_date,
            )
            .order_by(IndicatorSnapshot.trade_date)
        ).all()
    )
    return [
        {
            column.name: getattr(row, column.name)
            for column in IndicatorSnapshot.__table__.columns
            if column.name != "id"
        }
        for row in rows
    ]


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
    assert sample.contraction_count_available is True
    assert sample.box_age_days_available is True
    assert sample.box_redefinition_count_available is True
    assert sample.weekly_breakout_available is True
    assert sample.weekly_volume_ratio_available is True
    assert sample.weekly_rs_score_available is True
    assert 0 <= sample.market_score <= 1
    assert 0 <= sample.sector_rs_score <= 1
    assert 0 <= sample.relative_strength_score <= 1
    assert sample.breadth_score_available is True
    assert sample.breadth_advance_decline_available is True
    assert sample.breadth_52w_high_low_available is True
    assert sample.breadth_ma50_participation_available is True
    assert 0 <= sample.breadth_score <= 1


def test_indicator_incremental_recompute_matches_full_recompute_for_changed_range(db_session):
    MarketDataService(db_session).seed_sample_data()
    IndicatorService(db_session).recompute()

    latest_date = db_session.scalar(
        select(IndicatorSnapshot.trade_date).order_by(IndicatorSnapshot.trade_date.desc()).limit(1)
    )
    start_date = latest_date - timedelta(days=30)
    baseline = _snapshot_payloads(db_session, symbol="KR009", start_date=start_date, end_date=latest_date)
    assert baseline

    rows = list(
        db_session.scalars(
            select(IndicatorSnapshot).where(
                IndicatorSnapshot.symbol == "KR009",
                IndicatorSnapshot.trade_date >= start_date,
                IndicatorSnapshot.trade_date <= latest_date,
            )
        ).all()
    )
    for row in rows:
        row.sma20 = -1.0
        row.breadth_score = -1.0
    db_session.commit()

    result = IndicatorService(db_session).recompute(symbol="KR009", start_date=start_date, end_date=latest_date)
    incremental = _snapshot_payloads(db_session, symbol="KR009", start_date=start_date, end_date=latest_date)

    assert result["mode"] == "incremental"
    assert result["rows"] == len(baseline)
    assert incremental == baseline


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


def test_weekly_derived_field_availability_flags_fail_closed_on_short_history():
    dates = pd.bdate_range(end="2026-05-20", periods=40)
    df = pd.DataFrame(
        {
            "trade_date": [dt.date() for dt in dates],
            "symbol": "SHORT",
            "open": [100.0 + index for index in range(len(dates))],
            "high": [101.0 + index for index in range(len(dates))],
            "low": [99.0 + index for index in range(len(dates))],
            "close": [100.0 + index for index in range(len(dates))],
            "volume": [100000 for _ in dates],
            "turnover_value": [10_000_000.0 for _ in dates],
            "venue": "KRX",
        }
    )
    features = IndicatorService._compute_symbol_indicators(df)
    features = IndicatorService._attach_weekly_relative_strength(features)
    latest = features.iloc[-1]

    assert pd.isna(latest["weekly_sma30"])
    assert pd.isna(latest["weekly_sma30_slope"])
    assert bool(latest["weekly_breakout_available"]) is False
    assert bool(latest["weekly_volume_ratio_available"]) is False
    assert bool(latest["weekly_rs_score_available"]) is False


def test_indicator_snapshot_contains_asof_pattern_engine_fields(seeded_db):
    latest = seeded_db.scalar(
        select(IndicatorSnapshot)
        .where(IndicatorSnapshot.symbol == "KR007")
        .order_by(IndicatorSnapshot.trade_date.desc())
        .limit(1)
    )
    assert latest is not None

    daily = MarketRepository(seeded_db).daily_df(end_date=latest.trade_date)
    symbol_daily = daily[daily["symbol"] == latest.symbol].sort_values("trade_date").reset_index(drop=True)
    position = len(symbol_daily) - 1
    lookback_start = max(0, position - IndicatorService.VCP_PATTERN_LOOKBACK_DAYS + 1)
    depths = IndicatorService._recent_pullback_depths(
        symbol_daily.loc[lookback_start:position, "high"].astype(float).to_numpy(),
        symbol_daily.loc[lookback_start:position, "low"].astype(float).to_numpy(),
    )
    expected_last = depths[-1] if depths else None
    expected_prev = depths[-2] if len(depths) >= 2 else None

    assert latest.contraction_count_available is True
    assert latest.contraction_count == len(depths)
    assert latest.pullback_depth_last_available == (expected_last is not None)
    assert latest.pullback_depth_prev_available == (expected_prev is not None)
    if expected_last is not None:
        assert latest.pullback_depth_last == pytest.approx(expected_last)
    if expected_prev is not None:
        assert latest.pullback_depth_prev == pytest.approx(expected_prev)

    previous_window = symbol_daily.iloc[position - IndicatorService.DARVAS_BOX_WINDOW_DAYS:position]
    box_top = float(previous_window["high"].max())
    box_bottom = float(previous_window["low"].min())
    top_date = previous_window[previous_window["high"] == box_top]["trade_date"].iloc[-1]
    bottom_date = previous_window[previous_window["low"] == box_bottom]["trade_date"].iloc[-1]
    expected_age = (pd.Timestamp(latest.trade_date) - pd.Timestamp(max(top_date, bottom_date))).days

    expected_redefinitions = 0
    previous_top = None
    start = max(
        IndicatorService.DARVAS_BOX_WINDOW_DAYS,
        position - IndicatorService.DARVAS_BOX_SEQUENCE_LOOKBACK_DAYS + 1,
    )
    for cursor in range(start, position + 1):
        current_top = float(
            symbol_daily.iloc[cursor - IndicatorService.DARVAS_BOX_WINDOW_DAYS:cursor]["high"].max()
        )
        if previous_top is not None and current_top > previous_top:
            expected_redefinitions += 1
        previous_top = current_top

    assert latest.box_age_days_available is True
    assert latest.box_age_days == expected_age
    assert latest.box_redefinition_count_available is True
    assert latest.box_redefinition_count == expected_redefinitions


def test_indicator_snapshot_contains_weekly_breakout_volume_and_rs_fields(seeded_db):
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
        .agg({"high": "max", "close": "last", "volume": "sum"})
        .dropna()
    )
    weekly["breakout_level"] = weekly["high"].shift(1).rolling(13, min_periods=13).max()
    weekly["weekly_breakout"] = weekly["close"] > weekly["breakout_level"]
    weekly["weekly_volume_avg30"] = weekly["volume"].shift(1).rolling(30, min_periods=30).mean()
    weekly["weekly_volume_ratio"] = weekly["volume"] / weekly["weekly_volume_avg30"]
    weekly_latest = weekly.iloc[-1]

    weekly_returns = []
    for symbol, group in daily.groupby("symbol"):
        symbol_weekly = (
            group.sort_values("trade_date")
            .set_index(pd.to_datetime(group.sort_values("trade_date")["trade_date"]))
            .resample("W-FRI")
            .agg({"close": "last"})
            .dropna()
        )
        weekly_return = symbol_weekly["close"].iloc[-1] / symbol_weekly["close"].iloc[-14] - 1
        weekly_returns.append({"symbol": symbol, "weekly_return_13": weekly_return})
    weekly_returns_df = pd.DataFrame(weekly_returns)
    weekly_returns_df["weekly_rs_score"] = weekly_returns_df["weekly_return_13"].rank(pct=True)
    expected_weekly_rs_score = float(
        weekly_returns_df.loc[weekly_returns_df["symbol"] == latest.symbol, "weekly_rs_score"].iloc[0]
    )

    assert latest.weekly_breakout_available is True
    assert latest.weekly_breakout is bool(weekly_latest["weekly_breakout"])
    assert latest.weekly_volume_ratio_available is True
    assert latest.weekly_volume_ratio == pytest.approx(float(weekly_latest["weekly_volume_ratio"]))
    assert latest.weekly_rs_score_available is True
    assert latest.weekly_rs_score == pytest.approx(expected_weekly_rs_score)
