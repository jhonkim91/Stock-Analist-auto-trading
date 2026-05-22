from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

from sqlalchemy import select

from backend.app.core.config import get_config
from backend.app.models.tables import IndicatorSnapshot, ScreenResult
from backend.app.repositories.market_repository import MarketRepository
from backend.app.services.screener_service import ScreenerService
from backend.app.strategies.canslim_lite import CanslimLiteStrategy
from backend.app.strategies.trend_breakout import TrendBreakoutStrategy
from backend.app.strategies.vcp_breakout import VcpBreakoutStrategy


def _passing_indicator(**overrides):
    values = {
        "close": 100.0,
        "volume": 200000,
        "turnover_value": 2_000_000_000.0,
        "sma50": 90.0,
        "sma150": 80.0,
        "sma200": 70.0,
        "sma200_slope": 1.0,
        "volume_ma50": 100000.0,
        "atr20_pct": 0.02,
        "atr20_pct_ma60": 0.04,
        "std20": 0.01,
        "std60": 0.02,
        "high_52w": 110.0,
        "pivot_high_20_prev": 98.0,
        "volume_dry_up": True,
        "breakout": True,
        "rs_percentile": 90.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _passing_fundamentals(**overrides):
    values = {
        "effective_date": date(2026, 1, 1),
        "quarterly_eps_growth": 0.30,
        "sales_growth": 0.25,
        "roe": 0.10,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


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


def test_phase3h_default_strategy_options_preserve_base_condition_flags(seeded_db):
    config = get_config("strategies")
    indicator = _passing_indicator()
    fundamentals = _passing_fundamentals()

    trend = TrendBreakoutStrategy(config["trend_breakout"]).evaluate(indicator, fundamentals, "bull")
    vcp = VcpBreakoutStrategy(config["vcp_breakout"]).evaluate(indicator, fundamentals, "bull")
    canslim = CanslimLiteStrategy(config["canslim_lite"]).evaluate(indicator, fundamentals, "bull")

    assert "atr20_pct_max" not in trend.pass_flags
    assert "pivot_distance_limit" not in vcp.pass_flags
    assert "roe_min" not in canslim.pass_flags
    assert trend.passed is True
    assert vcp.passed is True
    assert canslim.passed is True


def test_phase3h_optional_strategy_filters_reject_fixture_conditions(seeded_db):
    config = get_config("strategies")
    fundamentals = _passing_fundamentals(roe=0.05)

    trend = TrendBreakoutStrategy(
        {**config["trend_breakout"], "atr_risk_filter_enabled": True, "max_atr20_pct": 0.03}
    ).evaluate(_passing_indicator(atr20_pct=0.06), fundamentals, "bull")
    vcp = VcpBreakoutStrategy(
        {**config["vcp_breakout"], "pivot_distance_limit_enabled": True, "max_pivot_distance_pct": 0.03}
    ).evaluate(_passing_indicator(close=110.0, pivot_high_20_prev=100.0), fundamentals, "bull")
    canslim = CanslimLiteStrategy(
        {**config["canslim_lite"], "earnings_quality_enabled": True, "min_roe": 0.15}
    ).evaluate(_passing_indicator(), fundamentals, "bull")

    assert trend.passed is False
    assert "atr20_pct_max" in trend.failed_conditions
    assert "atr20_pct_max" in trend.metadata["optional_conditions"]
    assert {"triggered_conditions", "score_breakdown", "risk_flags", "data_quality_flags", "explanation"}.issubset(
        trend.metadata
    )
    assert vcp.passed is False
    assert "pivot_distance_limit" in vcp.failed_conditions
    assert canslim.passed is False
    assert "roe_min" in canslim.failed_conditions


def test_phase3h_screener_response_includes_explanation_contract(seeded_db):
    ScreenerService(seeded_db).run()
    first = ScreenerService(seeded_db).list_results(limit=1)[0]

    for key in ("triggered_conditions", "score_breakdown", "risk_flags", "data_quality_flags", "explanation", "rationale"):
        assert key in first
    assert isinstance(first["triggered_conditions"], list)
    assert isinstance(first["score_breakdown"], dict)
    assert isinstance(first["risk_flags"], dict)
    assert isinstance(first["data_quality_flags"], dict)
    assert first["explanation"] == first["reason_summary"]
