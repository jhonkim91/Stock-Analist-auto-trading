from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from backend.app.core.config import get_config
from backend.app.models.schemas import ScreenerRunRequest
from backend.app.models.tables import EarningsEvent, IndicatorSnapshot, ScreenResult
from backend.app.repositories.market_repository import MarketRepository
from backend.app.services.backtest_service import BacktestService
from backend.app.services.screener_service import ScreenerService
from backend.app.strategies.base import StrategyResult
from backend.app.strategies.canslim_lite import CanslimLiteStrategy
from backend.app.strategies.darvas_box import DarvasBoxStrategy
from backend.app.strategies.momentum_rank import MomentumRankStrategy
from backend.app.strategies.new_high_breakout import NewHighBreakoutStrategy
from backend.app.strategies.pullback_20ema import Pullback20EmaStrategy
from backend.app.strategies.relative_strength_leader import RelativeStrengthLeaderStrategy
from backend.app.strategies.registry import (
    AVAILABLE_STRATEGY_NAMES,
    DEFAULT_STRATEGY_NAMES,
    get_available_strategy_registry,
    get_strategy_registry,
    list_strategy_metadata,
)
from backend.app.strategies.stage_analysis_weekly import StageAnalysisWeeklyStrategy
from backend.app.strategies.trend_breakout import TrendBreakoutStrategy
from backend.app.strategies.vcp_breakout import VcpBreakoutStrategy


def _earnings_event(symbol: str = "KRTEST", days_to_earnings: int = -20):
    earnings_date = date(2026, 5, 20) + timedelta(days=days_to_earnings)
    return SimpleNamespace(
        symbol=symbol,
        earnings_date=earnings_date,
        release_ts=datetime(earnings_date.year, earnings_date.month, earnings_date.day, 15, 30),
        session="after_close",
    )


def _passing_indicator(**overrides):
    values = {
        "trade_date": date(2026, 5, 20),
        "symbol": "KRTEST",
        "close": 100.0,
        "low": 98.5,
        "volume": 200000,
        "turnover_value": 2_000_000_000.0,
        "ema20": 98.0,
        "sma50": 90.0,
        "sma150": 80.0,
        "sma200": 70.0,
        "sma200_slope": 1.0,
        "weekly_close": 100.0,
        "weekly_sma30": 90.0,
        "weekly_sma30_slope": 2.0,
        "contraction_count": 3,
        "contraction_count_available": True,
        "pullback_depth_last": 0.04,
        "pullback_depth_last_available": True,
        "pullback_depth_prev": 0.08,
        "pullback_depth_prev_available": True,
        "box_age_days": 12,
        "box_age_days_available": True,
        "box_redefinition_count": 1,
        "box_redefinition_count_available": True,
        "weekly_breakout": True,
        "weekly_breakout_available": True,
        "weekly_volume_ratio": 1.25,
        "weekly_volume_ratio_available": True,
        "weekly_rs_score": 0.90,
        "weekly_rs_score_available": True,
        "volume_ma20": 250000.0,
        "volume_ma50": 100000.0,
        "volume_ratio_50": 1.1,
        "atr20_pct": 0.02,
        "atr20_pct_ma60": 0.04,
        "std20": 0.01,
        "std60": 0.02,
        "high_52w": 100.0,
        "distance_from_52w_high": 0.0,
        "pivot_high_20_prev": 98.0,
        "pivot_low_20_prev": 82.0,
        "volume_dry_up": True,
        "breakout": True,
        "rs_percentile": 90.0,
        "relative_strength_score": 0.90,
        "trend_score": 0.80,
        "sector_rs_score": 0.70,
        "market_score": 0.50,
        "pullback_count": 1,
        "pullback_count_available": True,
        "earnings_event": _earnings_event(),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _passing_fundamentals(**overrides):
    values = {
        "effective_date": date(2026, 1, 1),
        "quarterly_eps_growth": 0.30,
        "sales_growth": 0.25,
        "roe": 0.10,
        "gross_profitability": 0.25,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _strategy_config(strategy_name: str, **overrides):
    config = get_config("strategies")
    values = {
        **dict(config.get("common", {}).get("hardening", {})),
        **dict(config[strategy_name]),
    }
    values.update(overrides)
    return values


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


def test_screener_canslim_uses_repo_earnings_event_asof_metadata(seeded_db):
    indicator = seeded_db.scalar(
        select(IndicatorSnapshot)
        .where(IndicatorSnapshot.symbol == "KR009")
        .order_by(IndicatorSnapshot.trade_date.desc())
        .limit(1)
    )
    assert indicator is not None
    event_date = indicator.trade_date + timedelta(days=2)
    seeded_db.add(
        EarningsEvent(
            symbol="KR009",
            earnings_date=event_date,
            release_ts=datetime(event_date.year, event_date.month, event_date.day, 8, 0),
            session="before_open",
        )
    )
    seeded_db.commit()

    ScreenerService(seeded_db).run(trade_date=indicator.trade_date, strategies=["canslim_lite"])

    row = seeded_db.scalar(
        select(ScreenResult)
        .where(ScreenResult.symbol == "KR009", ScreenResult.strategy_tag == "canslim_lite")
        .limit(1)
    )
    assert row is not None
    flags = json.loads(row.pass_flags)
    metadata = json.loads(row.metadata_json)
    assert flags["earnings_blackout_clear"] is False
    assert metadata["earnings_blackout_status"] == "earnings_blackout_fail_closed"
    assert metadata["earnings_event"]["days_to_earnings"] == 2
    assert metadata["data_quality_flags"]["earnings_event_available"] is True
    assert metadata["pti_validation_status"] == "pti_validation_not_available_in_current_mvp"


def test_screener_stores_required_pass_fail_evidence(seeded_db):
    result = ScreenerService(seeded_db).run()

    assert result["strategies"] == list(DEFAULT_STRATEGY_NAMES)
    assert "new_high_breakout" in result["strategies"]
    assert result["rows"] >= 45
    rows = list(seeded_db.scalars(select(ScreenResult)).all())
    assert rows
    assert {row.strategy_tag for row in rows} == set(DEFAULT_STRATEGY_NAMES)
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


def test_common_filters_preserve_strategy_metadata():
    metadata = {
        "triggered_conditions": ["close_gt_sma50"],
        "score_breakdown": {"condition_score": 1.0, "triggered_count": 1, "failed_count": 0, "total_conditions": 1},
        "risk_flags": {"entry_chase_warning": True},
        "data_quality_flags": {"high_52w_available": True},
        "risk_metadata": {"risk_basis": "atr_stop"},
        "explanation": "strategy-time explanation",
        "rationale": "strategy-time rationale",
    }
    result = StrategyResult(
        strategy_tag="metadata_probe",
        passed=True,
        pass_flags={"close_gt_sma50": True},
        failed_conditions=[],
        reason_summary="strategy passed",
        metadata=metadata,
    )

    filtered = ScreenerService._apply_common_filters(
        result,
        _passing_indicator(turnover_value=0.0),
        reward_risk_ratio=0.1,
        common=get_config("strategies")["common"],
    )

    assert filtered.passed is False
    assert {"liquidity_ok", "rr_ok"}.issubset(filtered.failed_conditions)
    assert filtered.metadata == metadata
    assert filtered.metadata["risk_flags"]["entry_chase_warning"] is True
    assert filtered.metadata["data_quality_flags"]["high_52w_available"] is True


def test_phase3h_default_strategy_options_preserve_base_condition_flags():
    config = get_config("strategies")
    indicator = _passing_indicator()
    fundamentals = _passing_fundamentals()

    trend = TrendBreakoutStrategy(config["trend_breakout"]).evaluate(indicator, fundamentals, "bull")
    vcp = VcpBreakoutStrategy(config["vcp_breakout"]).evaluate(indicator, fundamentals, "bull")
    canslim = CanslimLiteStrategy(config["canslim_lite"]).evaluate(indicator, fundamentals, "bull")
    new_high = NewHighBreakoutStrategy(config["new_high_breakout"]).evaluate(indicator, fundamentals, "bull")
    pullback = Pullback20EmaStrategy(config["pullback_20ema"]).evaluate(indicator, fundamentals, "bull")

    assert "atr20_pct_max" not in trend.pass_flags
    assert "pivot_distance_limit" not in vcp.pass_flags
    assert "roe_min" not in canslim.pass_flags
    assert trend.passed is True
    assert vcp.passed is True
    assert canslim.passed is True
    assert new_high.passed is True
    assert pullback.passed is True


def test_canslim_rejects_broken_technical_trend_when_enabled():
    result = CanslimLiteStrategy(
        _strategy_config("canslim_lite", technical_trend_filter_enabled=True)
    ).evaluate(
        _passing_indicator(sma50=75.0),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is False
    assert result.pass_flags["sma50_gt_sma150"] is False
    assert "sma50_gt_sma150" in result.failed_conditions
    assert result.metadata["data_quality_flags"]["technical_trend_available"] is True


def test_canslim_rejects_missing_volume_surge_when_confirmation_enabled():
    result = CanslimLiteStrategy(
        _strategy_config("canslim_lite", volume_confirmation_enabled=True, volume_surge_multiple=1.5)
    ).evaluate(
        _passing_indicator(volume=149999, volume_ma50=100000.0),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is False
    assert result.pass_flags["volume_surge"] is False
    assert "volume_surge" in result.failed_conditions
    assert result.metadata["data_quality_flags"]["volume_ma50_available"] is True


def test_canslim_allows_missing_sector_rs_when_filter_disabled():
    result = CanslimLiteStrategy(
        _strategy_config("canslim_lite", sector_rs_filter_enabled=False)
    ).evaluate(
        _passing_indicator(sector_rs_score=None),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is True
    assert "sector_rs_score_min" not in result.pass_flags
    assert result.metadata["data_quality_flags"]["sector_rs_score_available"] is False


def test_canslim_rejects_missing_fundamentals_with_explicit_failure():
    result = CanslimLiteStrategy(_strategy_config("canslim_lite")).evaluate(
        _passing_indicator(),
        None,
        "bull",
    )

    assert result.passed is False
    assert "fundamentals_available_asof" in result.failed_conditions
    assert result.metadata["fundamentals_available_asof"] is False
    assert result.metadata["data_quality_flags"]["fundamentals_available"] is False
    assert result.metadata["data_quality_flags"]["fundamentals_effective_date_available"] is False


def test_canslim_marks_missing_roe_when_earnings_quality_enabled():
    result = CanslimLiteStrategy(
        _strategy_config("canslim_lite", earnings_quality_enabled=True, min_roe=0.15)
    ).evaluate(
        _passing_indicator(),
        _passing_fundamentals(roe=None),
        "bull",
    )

    assert result.passed is False
    assert result.pass_flags["roe_min"] is False
    assert "roe_min" in result.failed_conditions
    assert result.metadata["data_quality_flags"]["roe_available"] is False


def test_canslim_metadata_includes_pti_mvp_status_without_lookahead_claim():
    result = CanslimLiteStrategy(_strategy_config("canslim_lite")).evaluate(
        _passing_indicator(),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is True
    assert result.metadata["fundamentals_available_asof"] is True
    assert result.metadata["fundamentals_effective_date_available"] is True
    assert result.metadata["pti_validation_status"] == "pti_validation_not_available_in_current_mvp"
    assert result.metadata["data_quality_flags"]["pti_validation_not_available_in_current_mvp"] is True
    assert result.metadata["earnings_blackout_status"] == "clear"
    assert result.metadata["earnings_event"]["days_to_earnings"] == -20
    assert result.metadata["data_quality_flags"]["earnings_event_available"] is True
    assert "no_lookahead_claim" not in result.metadata


@pytest.mark.parametrize(
    ("days_to_earnings", "expected_pass", "expected_status"),
    [
        (-6, True, "clear"),
        (-2, False, "earnings_blackout_fail_closed"),
        (2, False, "earnings_blackout_fail_closed"),
        (6, True, "clear"),
    ],
)
def test_canslim_earnings_blackout_before_after_window(days_to_earnings, expected_pass, expected_status):
    result = CanslimLiteStrategy(_strategy_config("canslim_lite", earnings_blackout_days=5)).evaluate(
        _passing_indicator(earnings_event=_earnings_event(days_to_earnings=days_to_earnings)),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is expected_pass
    assert result.pass_flags["earnings_blackout_clear"] is expected_pass
    assert result.metadata["earnings_blackout_status"] == expected_status
    assert result.metadata["earnings_event"]["days_to_earnings"] == days_to_earnings


def test_canslim_missing_earnings_event_fails_closed_with_metadata():
    result = CanslimLiteStrategy(_strategy_config("canslim_lite")).evaluate(
        _passing_indicator(earnings_event=None),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is False
    assert "earnings_blackout_clear" in result.failed_conditions
    assert result.metadata["earnings_blackout_status"] == "earnings_event_missing_fail_closed"
    assert result.metadata["data_quality_flags"]["earnings_event_available"] is False


def test_canslim_institutional_proxy_is_optional_and_config_gated():
    result = CanslimLiteStrategy(
        _strategy_config("canslim_lite", require_institutional_proxy=True)
    ).evaluate(
        _passing_indicator(volume_ratio_50=0.90),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is False
    assert result.pass_flags["institutional_proxy"] is False
    assert "institutional_proxy" in result.failed_conditions
    assert result.metadata["institutional_proxy"] is False
    assert result.metadata["data_quality_flags"]["institutional_proxy_available"] is True


def test_trend_breakout_rejects_false_breakout():
    result = TrendBreakoutStrategy(_strategy_config("trend_breakout")).evaluate(
        _passing_indicator(breakout=False),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is False
    assert result.pass_flags["breakout"] is False
    assert "breakout" in result.failed_conditions
    assert result.metadata["data_quality_flags"]["breakout_available"] is True


def test_trend_breakout_rejects_bear_market_regime():
    result = TrendBreakoutStrategy(_strategy_config("trend_breakout")).evaluate(
        _passing_indicator(),
        _passing_fundamentals(),
        "bear",
    )

    assert result.passed is False
    assert result.pass_flags["market_regime_not_bear"] is False
    assert "market_regime_not_bear" in result.failed_conditions
    assert result.metadata["data_quality_flags"]["market_regime_available"] is True


def test_trend_breakout_allows_neutral_market_by_default():
    result = TrendBreakoutStrategy(_strategy_config("trend_breakout")).evaluate(
        _passing_indicator(),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is True
    assert result.pass_flags["market_regime_not_bear"] is True


def test_trend_breakout_allows_missing_sector_rs_when_filter_disabled():
    result = TrendBreakoutStrategy(_strategy_config("trend_breakout")).evaluate(
        _passing_indicator(sector_rs_score=None),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is True
    assert "sector_rs_score_min" not in result.pass_flags
    assert result.metadata["data_quality_flags"]["sector_rs_score_available"] is False


def test_trend_breakout_rejects_low_sector_rs_when_filter_enabled():
    result = TrendBreakoutStrategy(
        _strategy_config("trend_breakout", sector_rs_filter_enabled=True, sector_rs_score_min=0.60)
    ).evaluate(
        _passing_indicator(sector_rs_score=0.59),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is False
    assert result.pass_flags["sector_rs_score_min"] is False
    assert "sector_rs_score_min" in result.failed_conditions
    assert "sector_rs_score_min" in result.metadata["optional_conditions"]
    assert result.metadata["data_quality_flags"]["sector_rs_score_available"] is True


def test_trend_breakout_keeps_existing_contract_fields_with_new_quality_flags():
    result = TrendBreakoutStrategy(_strategy_config("trend_breakout")).evaluate(
        _passing_indicator(),
        _passing_fundamentals(),
        "bull",
    )

    assert {
        "close_gt_sma50",
        "sma50_gt_sma150",
        "sma150_gt_sma200",
        "sma200_slope_positive",
        "rs_percentile_min",
        "near_52w_high",
        "volume_surge",
        "breakout",
        "market_regime_not_bear",
    }.issubset(result.pass_flags)
    assert {
        "triggered_conditions",
        "score_breakdown",
        "risk_flags",
        "data_quality_flags",
        "explanation",
        "rationale",
    }.issubset(result.metadata)
    assert {
        "breakout_available",
        "high_52w_available",
        "sector_rs_score_available",
        "market_regime_available",
        "atr20_pct_available",
    }.issubset(result.metadata["data_quality_flags"])


def test_trend_breakout_entry_chase_warning_is_metadata_only():
    result = TrendBreakoutStrategy(_strategy_config("trend_breakout")).evaluate(
        _passing_indicator(distance_from_52w_high=0.0),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is True
    assert "entry_chase_warning" not in result.pass_flags
    assert result.metadata["risk_flags"]["entry_chase_warning"] is True
    assert result.metadata["risk_flags"]["distance_from_52w_high_too_low"] is True
    assert result.metadata["risk_flags"]["close_extended_above_52w_high"] is False


def test_trend_breakout_entry_chase_warning_detects_extended_close_above_high():
    result = TrendBreakoutStrategy(_strategy_config("trend_breakout")).evaluate(
        _passing_indicator(close=104.0, high_52w=100.0, distance_from_52w_high=-0.04),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is True
    assert "entry_chase_warning" not in result.pass_flags
    assert result.metadata["risk_flags"]["entry_chase_warning"] is True
    assert result.metadata["risk_flags"]["distance_from_52w_high_too_low"] is False
    assert result.metadata["risk_flags"]["close_extended_above_52w_high"] is True


def test_vcp_breakout_rejects_bear_market_regime():
    result = VcpBreakoutStrategy(_strategy_config("vcp_breakout")).evaluate(
        _passing_indicator(),
        _passing_fundamentals(),
        "bear",
    )

    assert result.passed is False
    assert result.pass_flags["market_regime_not_bear"] is False
    assert "market_regime_not_bear" in result.failed_conditions
    assert result.metadata["data_quality_flags"]["market_regime_available"] is True


def test_vcp_breakout_allows_neutral_market_by_default():
    result = VcpBreakoutStrategy(_strategy_config("vcp_breakout")).evaluate(
        _passing_indicator(),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is True
    assert result.pass_flags["market_regime_not_bear"] is True


def test_vcp_breakout_allows_missing_sector_rs_when_filter_disabled():
    result = VcpBreakoutStrategy(_strategy_config("vcp_breakout")).evaluate(
        _passing_indicator(sector_rs_score=None),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is True
    assert "sector_rs_score_min" not in result.pass_flags
    assert result.metadata["data_quality_flags"]["sector_rs_score_available"] is False


def test_vcp_breakout_rejects_low_sector_rs_when_filter_enabled():
    result = VcpBreakoutStrategy(
        _strategy_config("vcp_breakout", sector_rs_filter_enabled=True, sector_rs_score_min=0.60)
    ).evaluate(
        _passing_indicator(sector_rs_score=0.59),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is False
    assert result.pass_flags["sector_rs_score_min"] is False
    assert "sector_rs_score_min" in result.failed_conditions
    assert "sector_rs_score_min" in result.metadata["optional_conditions"]


def test_vcp_breakout_rejects_extended_pivot_distance_when_enabled():
    result = VcpBreakoutStrategy(
        _strategy_config("vcp_breakout", pivot_distance_limit_enabled=True, max_pivot_distance_pct=0.03)
    ).evaluate(
        _passing_indicator(close=110.0, pivot_high_20_prev=100.0),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is False
    assert result.pass_flags["pivot_distance_limit"] is False
    assert "pivot_distance_limit" in result.failed_conditions
    assert result.metadata["pivot_distance_pct"] == pytest.approx(0.10)
    assert result.metadata["data_quality_flags"]["pivot_high_20_prev_available"] is True


def test_vcp_breakout_marks_missing_pivot_high_when_distance_limit_enabled():
    result = VcpBreakoutStrategy(
        _strategy_config("vcp_breakout", pivot_distance_limit_enabled=True, max_pivot_distance_pct=0.03)
    ).evaluate(
        _passing_indicator(pivot_high_20_prev=None),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is False
    assert result.pass_flags["pivot_distance_limit"] is False
    assert result.metadata["pivot_distance_pct"] is None
    assert result.metadata["data_quality_flags"]["pivot_high_20_prev_available"] is False
    assert result.metadata["data_quality_flags"]["pivot_distance_pct_available"] is False


def test_vcp_breakout_rejects_high_atr20_pct_when_filter_enabled():
    result = VcpBreakoutStrategy(
        _strategy_config("vcp_breakout", atr_risk_filter_enabled=True, max_atr20_pct=0.08)
    ).evaluate(
        _passing_indicator(atr20_pct=0.081, atr20_pct_ma60=0.10),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is False
    assert result.pass_flags["atr20_pct_max"] is False
    assert "atr20_pct_max" in result.failed_conditions
    assert "atr20_pct_max" in result.metadata["optional_conditions"]


def test_vcp_breakout_metadata_includes_quality_fields():
    result = VcpBreakoutStrategy(_strategy_config("vcp_breakout")).evaluate(
        _passing_indicator(),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is True
    assert result.metadata["pivot_distance_pct"] == pytest.approx((100.0 - 98.0) / 98.0, abs=1e-6)
    assert result.metadata["contraction_confirmed"] is True
    assert result.pass_flags["contraction_count_min"] is True
    assert result.pass_flags["pullback_depth_decreasing"] is True
    assert result.metadata["contraction_count"] == 3
    assert result.metadata["pullback_depth_last"] == pytest.approx(0.04)
    assert result.metadata["pullback_depth_prev"] == pytest.approx(0.08)
    assert result.metadata["data_quality_flags"]["contraction_count_available"] is True
    assert result.metadata["data_quality_flags"]["pullback_depth_last_available"] is True
    assert result.metadata["volume_dry_up_confirmed"] is True
    assert result.metadata["breakout_volume_confirmed"] is True


def test_vcp_breakout_rejects_insufficient_contraction_count():
    result = VcpBreakoutStrategy(_strategy_config("vcp_breakout", min_contraction_count=2)).evaluate(
        _passing_indicator(contraction_count=1),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is False
    assert result.pass_flags["contraction_count_min"] is False
    assert "contraction_count_min" in result.failed_conditions
    assert result.metadata["contraction_confirmed"] is False


def test_vcp_breakout_rejects_non_decreasing_pullback_depth():
    result = VcpBreakoutStrategy(
        _strategy_config("vcp_breakout", require_decreasing_pullback_depth=True)
    ).evaluate(
        _passing_indicator(pullback_depth_last=0.09, pullback_depth_prev=0.08),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is False
    assert result.pass_flags["pullback_depth_decreasing"] is False
    assert "pullback_depth_decreasing" in result.failed_conditions


def test_vcp_breakout_rejects_missing_pullback_depth_availability():
    result = VcpBreakoutStrategy(_strategy_config("vcp_breakout")).evaluate(
        _passing_indicator(
            pullback_depth_last=0.0,
            pullback_depth_prev=0.0,
            pullback_depth_last_available=False,
            pullback_depth_prev_available=False,
        ),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is False
    assert result.pass_flags["pullback_depth_available"] is False
    assert result.metadata["data_quality_flags"]["pullback_depth_last_available"] is False


def test_strategy_registry_preserves_default_order_types_and_contract():
    config = get_config("strategies")
    registry = get_strategy_registry(config)
    available_registry = get_available_strategy_registry(config)
    indicator = _passing_indicator()
    fundamentals = _passing_fundamentals()

    assert list(registry) == list(DEFAULT_STRATEGY_NAMES)
    assert list(available_registry) == list(AVAILABLE_STRATEGY_NAMES)
    assert ScreenerRunRequest().strategies == list(DEFAULT_STRATEGY_NAMES)
    assert "momentum_rank" not in registry
    assert isinstance(registry["trend_breakout"], TrendBreakoutStrategy)
    assert isinstance(registry["vcp_breakout"], VcpBreakoutStrategy)
    assert isinstance(registry["canslim_lite"], CanslimLiteStrategy)
    assert isinstance(registry["new_high_breakout"], NewHighBreakoutStrategy)
    assert isinstance(registry["pullback_20ema"], Pullback20EmaStrategy)
    assert isinstance(available_registry["new_high_breakout"], NewHighBreakoutStrategy)
    assert isinstance(available_registry["pullback_20ema"], Pullback20EmaStrategy)
    assert isinstance(available_registry["momentum_rank"], MomentumRankStrategy)
    assert isinstance(available_registry["relative_strength_leader"], RelativeStrengthLeaderStrategy)
    assert isinstance(available_registry["darvas_box"], DarvasBoxStrategy)
    assert isinstance(available_registry["stage_analysis_weekly"], StageAnalysisWeeklyStrategy)
    assert "relative_strength_leader" not in registry
    assert "darvas_box" not in registry
    assert "stage_analysis_weekly" not in registry

    results = {
        strategy_name: strategy.evaluate(indicator, fundamentals, "bull")
        for strategy_name, strategy in registry.items()
    }
    assert all(result.passed for result in results.values())
    assert "atr20_pct_max" not in results["trend_breakout"].pass_flags
    assert "pivot_distance_limit" not in results["vcp_breakout"].pass_flags
    assert "roe_min" not in results["canslim_lite"].pass_flags


def test_strategy_metadata_endpoint_exposes_default_and_available_contract(client):
    metadata = list_strategy_metadata()

    assert [row["name"] for row in metadata] == list(AVAILABLE_STRATEGY_NAMES)
    assert [row["name"] for row in metadata if row["is_default"]] == list(DEFAULT_STRATEGY_NAMES)
    assert all(row["is_available"] is True for row in metadata)
    assert all(row["display_name"] for row in metadata)
    assert all(row["description"] for row in metadata)
    assert all(row["required_fields"] for row in metadata)
    assert all(row["limitations"] for row in metadata)

    response = client.get("/api/screener/strategies")
    assert response.status_code == 200
    payload = response.json()
    assert [row["name"] for row in payload] == list(AVAILABLE_STRATEGY_NAMES)
    assert [row["name"] for row in payload if row["is_default"]] == list(DEFAULT_STRATEGY_NAMES)
    assert {"name", "display_name", "description", "is_default", "is_available", "required_fields", "limitations"}.issubset(
        payload[0]
    )
    available_only = [row["name"] for row in payload if not row["is_default"] and row["is_available"]]
    assert available_only == ["momentum_rank", "relative_strength_leader", "darvas_box", "stage_analysis_weekly"]


def test_pullback_20ema_passes_after_ema_touch_and_close_reclaim():
    config = get_config("strategies")
    result = Pullback20EmaStrategy(config["pullback_20ema"]).evaluate(
        _passing_indicator(low=98.5, ema20=98.0, close=100.0, pivot_low_20_prev=96.0),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is True
    assert result.strategy_tag == "pullback_20ema"
    assert result.failed_conditions == []
    assert result.pass_flags["low_touch_ema20"] is True
    assert result.pass_flags["close_gte_ema20"] is True
    assert result.pass_flags["market_regime_not_bear"] is True
    assert "sector_rs_score_min" not in result.pass_flags
    assert "near_high_52w" not in result.pass_flags
    assert "roe_min" not in result.pass_flags
    assert result.metadata["data_quality_flags"]["ema20_available"] is True
    assert result.metadata["data_quality_flags"]["low_available"] is True
    assert result.metadata["low_to_ema20_pct"] == pytest.approx(0.005102)
    assert result.metadata["close_to_ema20_pct"] == pytest.approx(0.020408)
    assert result.metadata["volume_ratio_50"] == pytest.approx(1.1)
    assert result.metadata["atr20_pct"] == pytest.approx(0.02)
    assert result.metadata["pullback_quality"] == "valid"
    assert result.metadata["risk_metadata"]["suggested_stop_price"] == 96.0
    assert result.metadata["risk_metadata"]["risk_per_share"] == 4.0
    assert result.metadata["risk_metadata"]["risk_basis"] == "swing_low"
    assert {"triggered_conditions", "score_breakdown", "data_quality_flags", "explanation"}.issubset(result.metadata)


def test_pullback_20ema_uses_ema_failure_stop_when_swing_low_missing():
    config = get_config("strategies")
    result = Pullback20EmaStrategy(config["pullback_20ema"]).evaluate(
        _passing_indicator(pivot_low_20_prev=None, ema20=98.0, close=100.0),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is True
    assert result.metadata["risk_metadata"]["suggested_stop_price"] == 98.0
    assert result.metadata["risk_metadata"]["risk_per_share"] == 2.0
    assert result.metadata["risk_metadata"]["risk_basis"] == "ema20_failure"


def test_pullback_20ema_rejects_bear_market_regime():
    config = get_config("strategies")
    result = Pullback20EmaStrategy(config["pullback_20ema"]).evaluate(
        _passing_indicator(),
        _passing_fundamentals(),
        "bear",
    )

    assert result.passed is False
    assert result.pass_flags["market_regime_not_bear"] is False
    assert "market_regime_not_bear" in result.failed_conditions
    assert result.metadata["data_quality_flags"]["market_regime_available"] is True


def test_pullback_20ema_rejects_low_sector_rs_when_filter_enabled():
    config = get_config("strategies")
    result = Pullback20EmaStrategy(
        {**config["pullback_20ema"], "sector_rs_filter_enabled": True, "sector_rs_score_min": 0.60}
    ).evaluate(
        _passing_indicator(sector_rs_score=0.59),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert result.pass_flags["sector_rs_score_min"] is False
    assert "sector_rs_score_min" in result.failed_conditions
    assert "sector_rs_score_min" in result.metadata["optional_conditions"]
    assert result.metadata["data_quality_flags"]["sector_rs_score_available"] is True


def test_pullback_20ema_rejects_missing_high_52w_when_near_high_filter_enabled():
    config = get_config("strategies")
    result = Pullback20EmaStrategy(
        {**config["pullback_20ema"], "near_high_52w_filter_enabled": True, "near_high_52w_threshold": 0.85}
    ).evaluate(
        _passing_indicator(high_52w=None),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert result.pass_flags["near_high_52w"] is False
    assert "near_high_52w" in result.failed_conditions
    assert "near_high_52w" in result.metadata["optional_conditions"]
    assert result.metadata["data_quality_flags"]["high_52w_available"] is False
    assert result.metadata["data_quality_flags"]["near_high_52w_available"] is False


def test_pullback_20ema_allows_missing_fundamentals_when_quality_filter_disabled():
    config = get_config("strategies")
    result = Pullback20EmaStrategy(config["pullback_20ema"]).evaluate(
        _passing_indicator(),
        None,
        "neutral",
    )

    assert result.passed is True
    assert "roe_min" not in result.pass_flags
    assert result.metadata["data_quality_flags"]["fundamentals_available"] is False
    assert result.metadata["data_quality_flags"]["roe_available"] is False


def test_pullback_20ema_rejects_missing_ema20_with_quality_flag():
    config = get_config("strategies")
    result = Pullback20EmaStrategy(config["pullback_20ema"]).evaluate(
        _passing_indicator(ema20=None),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "ema20_available" in result.failed_conditions
    assert "low_touch_ema20" in result.failed_conditions
    assert "close_gte_ema20" in result.failed_conditions
    assert result.metadata["data_quality_flags"]["ema20_available"] is False
    assert result.metadata["low_to_ema20_pct"] is None
    assert result.metadata["close_to_ema20_pct"] is None
    assert result.metadata["pullback_quality"] == "too_deep_or_missing"


def test_pullback_20ema_rejects_broken_trend_alignment():
    config = get_config("strategies")
    result = Pullback20EmaStrategy(config["pullback_20ema"]).evaluate(
        _passing_indicator(sma150=95.0, sma200=96.0),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "sma150_gt_sma200" in result.failed_conditions


def test_pullback_20ema_rejects_excessive_pullback_volume():
    config = get_config("strategies")
    result = Pullback20EmaStrategy(config["pullback_20ema"]).evaluate(
        _passing_indicator(volume_ratio_50=1.21),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "volume_ratio_50_max" in result.failed_conditions
    assert result.metadata["pullback_quality"] == "volume_too_high"


@pytest.mark.parametrize(("pullback_count", "expected_pass"), [(1, True), (2, True), (3, False)])
def test_pullback_20ema_accepts_first_second_and_rejects_third_pullback(pullback_count, expected_pass):
    config = get_config("strategies")
    result = Pullback20EmaStrategy(config["pullback_20ema"]).evaluate(
        _passing_indicator(pullback_count=pullback_count),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is expected_pass
    assert result.pass_flags["pullback_count_within_limit"] is expected_pass
    assert result.metadata["pullback_count"] == pullback_count
    if not expected_pass:
        assert "pullback_count_within_limit" in result.failed_conditions
        assert result.metadata["pullback_quality"] == "too_late_pullback"


def test_pullback_20ema_rejects_missing_volume_dry_up_vs_ma20():
    config = get_config("strategies")
    result = Pullback20EmaStrategy(config["pullback_20ema"]).evaluate(
        _passing_indicator(volume=251000, volume_ma20=250000.0),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert result.pass_flags["volume_dry_up_vs_ma20"] is False
    assert "volume_dry_up_vs_ma20" in result.failed_conditions
    assert result.metadata["pullback_quality"] == "volume_not_dry_vs_ma20"


def test_pullback_20ema_rejects_high_atr20_pct():
    config = get_config("strategies")
    result = Pullback20EmaStrategy(config["pullback_20ema"]).evaluate(
        _passing_indicator(atr20_pct=0.081),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "atr20_pct_max" in result.failed_conditions
    assert result.metadata["pullback_quality"] == "atr_too_high"


def test_new_high_breakout_passes_with_near_high_breakout_fixture():
    config = get_config("strategies")
    result = NewHighBreakoutStrategy(config["new_high_breakout"]).evaluate(
        _passing_indicator(),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is True
    assert result.strategy_tag == "new_high_breakout"
    assert result.failed_conditions == []
    assert result.pass_flags["new_high_threshold"] is True
    assert result.pass_flags["breakout"] is True
    assert result.pass_flags["volume_surge"] is True
    assert result.metadata["data_quality_flags"]["high_52w_available"] is True
    assert result.metadata["data_quality_flags"]["distance_from_52w_high_available"] is True
    assert result.metadata["data_quality_flags"]["volume_ratio_50_available"] is True
    assert {"triggered_conditions", "score_breakdown", "data_quality_flags", "explanation"}.issubset(result.metadata)


def test_new_high_breakout_allows_configured_near_high_threshold_boundary():
    config = get_config("strategies")
    result = NewHighBreakoutStrategy(config["new_high_breakout"]).evaluate(
        _passing_indicator(close=100.0, high_52w=100.0, distance_from_52w_high=0.0),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is True
    assert result.pass_flags["new_high_threshold"] is True
    assert result.pass_flags["breakout_buffer"] is True


def test_new_high_breakout_breakout_buffer_boundary_value():
    config = _strategy_config("new_high_breakout", breakout_buffer_pct=0.01)
    passing = NewHighBreakoutStrategy(config).evaluate(
        _passing_indicator(close=101.0, high_52w=100.0, distance_from_52w_high=0.01),
        _passing_fundamentals(),
        "neutral",
    )
    failing = NewHighBreakoutStrategy(config).evaluate(
        _passing_indicator(close=100.99, high_52w=100.0, distance_from_52w_high=0.0099),
        _passing_fundamentals(),
        "neutral",
    )

    assert passing.passed is True
    assert passing.pass_flags["breakout_buffer"] is True
    assert passing.metadata["breakout_buffer_price"] == pytest.approx(101.0)
    assert failing.passed is False
    assert failing.pass_flags["breakout_buffer"] is False
    assert "breakout_buffer" in failing.failed_conditions


def test_new_high_breakout_rejects_missing_high_52w_with_quality_flag():
    config = get_config("strategies")
    result = NewHighBreakoutStrategy(config["new_high_breakout"]).evaluate(
        _passing_indicator(high_52w=None, distance_from_52w_high=None),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "high_52w_available" in result.failed_conditions
    assert "new_high_threshold" in result.failed_conditions
    assert result.metadata["data_quality_flags"]["high_52w_available"] is False
    assert result.metadata["data_quality_flags"]["distance_from_52w_high_available"] is False


def test_new_high_breakout_rejects_low_volume_surge():
    config = get_config("strategies")
    result = NewHighBreakoutStrategy(config["new_high_breakout"]).evaluate(
        _passing_indicator(volume=149999, volume_ma50=100000.0),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "volume_surge" in result.failed_conditions


def test_new_high_breakout_rejects_false_breakout():
    config = get_config("strategies")
    result = NewHighBreakoutStrategy(config["new_high_breakout"]).evaluate(
        _passing_indicator(breakout=False),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "breakout" in result.failed_conditions


def test_darvas_box_passes_with_box_breakout_fixture():
    config = get_config("strategies")
    result = DarvasBoxStrategy(config["darvas_box"]).evaluate(
        _passing_indicator(close=100.0, pivot_high_20_prev=95.0, pivot_low_20_prev=80.0),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is True
    assert result.strategy_tag == "darvas_box"
    assert result.failed_conditions == []
    assert result.pass_flags["valid_box_range"] is True
    assert result.pass_flags["box_height_pct_max"] is True
    assert result.pass_flags["close_gt_box_top"] is True
    assert result.pass_flags["box_bottom_lt_close"] is True
    assert result.pass_flags["risk_per_share_positive"] is True
    assert result.pass_flags["market_regime_not_bear"] is True
    assert result.pass_flags["sma150_gt_sma200"] is True
    assert result.pass_flags["sma200_slope_positive"] is True
    assert "sector_rs_score_min" not in result.pass_flags
    assert "atr20_pct_max" not in result.pass_flags
    assert result.metadata["box_top"] == 95.0
    assert result.metadata["box_bottom"] == 80.0
    assert result.metadata["box_height_pct"] == 0.1875
    assert result.metadata["box_age_days"] == 12
    assert result.metadata["box_redefinition_count"] == 1
    assert result.metadata["rising_box_sequence"] is True
    assert result.metadata["suggested_stop_price"] == 80.0
    assert result.metadata["risk_per_share"] == 20.0
    assert result.metadata["risk_basis"] == "darvas_box_bottom"
    assert result.metadata["risk_metadata"]["suggested_stop_price"] == 80.0
    assert result.metadata["risk_metadata"]["risk_per_share"] == 20.0
    assert result.metadata["risk_metadata"]["risk_basis"] == "darvas_box_bottom"
    assert result.metadata["score_breakdown"]["box_height_pct"] == 0.1875
    assert result.metadata["score_breakdown"]["box_top"] == 95.0
    assert result.metadata["score_breakdown"]["box_bottom"] == 80.0
    assert result.metadata["score_breakdown"]["box_age_days"] == 12
    assert result.metadata["score_breakdown"]["box_redefinition_count"] == 1
    assert result.metadata["data_quality_flags"]["box_height_pct_available"] is True
    assert result.metadata["data_quality_flags"]["box_age_days_available"] is True
    assert result.metadata["data_quality_flags"]["box_redefinition_count_available"] is True


def test_darvas_box_rejects_young_box_age():
    config = get_config("strategies")
    result = DarvasBoxStrategy({**config["darvas_box"], "min_box_age_days": 10}).evaluate(
        _passing_indicator(close=100.0, pivot_high_20_prev=95.0, pivot_low_20_prev=80.0, box_age_days=4),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert result.pass_flags["box_age_days_min"] is False
    assert "box_age_days_min" in result.failed_conditions


def test_darvas_box_rejects_missing_rising_box_sequence():
    config = get_config("strategies")
    result = DarvasBoxStrategy({**config["darvas_box"], "require_rising_box": True}).evaluate(
        _passing_indicator(
            close=100.0,
            pivot_high_20_prev=95.0,
            pivot_low_20_prev=80.0,
            box_redefinition_count=0,
        ),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert result.pass_flags["rising_box_sequence"] is False
    assert "rising_box_sequence" in result.failed_conditions
    assert result.metadata["rising_box_sequence"] is False


def test_darvas_box_rejects_missing_box_age_availability():
    config = get_config("strategies")
    result = DarvasBoxStrategy(config["darvas_box"]).evaluate(
        _passing_indicator(
            close=100.0,
            pivot_high_20_prev=95.0,
            pivot_low_20_prev=80.0,
            box_age_days=0,
            box_age_days_available=False,
        ),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert result.pass_flags["box_age_days_available"] is False
    assert result.metadata["data_quality_flags"]["box_age_days_available"] is False


def test_darvas_box_rejects_bear_market_regime():
    config = get_config("strategies")
    result = DarvasBoxStrategy(config["darvas_box"]).evaluate(
        _passing_indicator(close=100.0, pivot_high_20_prev=95.0, pivot_low_20_prev=80.0),
        _passing_fundamentals(),
        "bear",
    )

    assert result.passed is False
    assert result.pass_flags["market_regime_not_bear"] is False
    assert "market_regime_not_bear" in result.failed_conditions
    assert result.metadata["data_quality_flags"]["market_regime_available"] is True


def test_darvas_box_rejects_broken_long_trend_when_enabled():
    config = get_config("strategies")
    result = DarvasBoxStrategy(config["darvas_box"]).evaluate(
        _passing_indicator(close=100.0, pivot_high_20_prev=95.0, pivot_low_20_prev=80.0, sma150=70.0, sma200=80.0),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert result.pass_flags["sma150_gt_sma200"] is False
    assert "sma150_gt_sma200" in result.failed_conditions
    assert result.metadata["data_quality_flags"]["sma150_available"] is True
    assert result.metadata["data_quality_flags"]["sma200_available"] is True


def test_darvas_box_rejects_invalid_box_bottom_risk():
    config = get_config("strategies")
    result = DarvasBoxStrategy(config["darvas_box"]).evaluate(
        _passing_indicator(close=100.0, pivot_high_20_prev=95.0, pivot_low_20_prev=100.0),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert result.pass_flags["box_bottom_lt_close"] is False
    assert result.pass_flags["risk_per_share_positive"] is False
    assert "box_bottom_lt_close" in result.failed_conditions
    assert "risk_per_share_positive" in result.failed_conditions
    assert result.metadata["suggested_stop_price"] is None
    assert result.metadata["risk_per_share"] is None
    assert result.metadata["risk_basis"] == "unavailable"
    assert (
        result.metadata["risk_metadata"]["fallback_policy"]
        == "fail_closed_missing_or_invalid_box_bottom_fallback_to_common_risk"
    )


def test_darvas_box_rejects_tall_box_height():
    config = get_config("strategies")
    result = DarvasBoxStrategy(config["darvas_box"]).evaluate(
        _passing_indicator(close=131.0, pivot_high_20_prev=130.0, pivot_low_20_prev=100.0),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "box_height_pct_max" in result.failed_conditions
    assert result.metadata["box_height_pct"] == 0.3


def test_darvas_box_rejects_missing_pivots_with_quality_flags():
    config = get_config("strategies")
    result = DarvasBoxStrategy(config["darvas_box"]).evaluate(
        _passing_indicator(pivot_high_20_prev=None, pivot_low_20_prev=None),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "pivot_high_20_prev_available" in result.failed_conditions
    assert "pivot_low_20_prev_available" in result.failed_conditions
    assert "valid_box_range" in result.failed_conditions
    assert result.metadata["data_quality_flags"]["pivot_high_20_prev_available"] is False
    assert result.metadata["data_quality_flags"]["pivot_low_20_prev_available"] is False
    assert result.metadata["data_quality_flags"]["box_height_pct_available"] is False
    assert result.metadata["score_breakdown"]["box_height_pct"] is None


def test_darvas_box_rejects_low_volume_surge():
    config = get_config("strategies")
    result = DarvasBoxStrategy(config["darvas_box"]).evaluate(
        _passing_indicator(close=100.0, pivot_high_20_prev=95.0, pivot_low_20_prev=80.0, volume=149999),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "volume_surge" in result.failed_conditions


def test_darvas_box_rejects_low_sector_rs_when_filter_enabled():
    config = get_config("strategies")
    result = DarvasBoxStrategy(
        {**config["darvas_box"], "sector_rs_filter_enabled": True, "sector_rs_score_min": 0.60}
    ).evaluate(
        _passing_indicator(close=100.0, pivot_high_20_prev=95.0, pivot_low_20_prev=80.0, sector_rs_score=0.59),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert result.pass_flags["sector_rs_score_min"] is False
    assert "sector_rs_score_min" in result.failed_conditions
    assert "sector_rs_score_min" in result.metadata["optional_conditions"]
    assert result.metadata["data_quality_flags"]["sector_rs_score_available"] is True


def test_darvas_box_rejects_high_atr20_pct_when_filter_enabled():
    config = get_config("strategies")
    result = DarvasBoxStrategy(
        {**config["darvas_box"], "atr_risk_filter_enabled": True, "max_atr20_pct": 0.08}
    ).evaluate(
        _passing_indicator(close=100.0, pivot_high_20_prev=95.0, pivot_low_20_prev=80.0, atr20_pct=0.081),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert result.pass_flags["atr20_pct_max"] is False
    assert "atr20_pct_max" in result.failed_conditions
    assert "atr20_pct_max" in result.metadata["optional_conditions"]
    assert result.metadata["data_quality_flags"]["atr20_pct_available"] is True


def test_stage_analysis_weekly_passes_with_stage2_fixture():
    config = get_config("strategies")
    result = StageAnalysisWeeklyStrategy(config["stage_analysis_weekly"]).evaluate(
        _passing_indicator(),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is True
    assert result.strategy_tag == "stage_analysis_weekly"
    assert result.failed_conditions == []
    assert result.pass_flags["weekly_close_gt_sma30"] is True
    assert result.pass_flags["weekly_sma30_slope_positive"] is True
    assert result.pass_flags["weekly_breakout"] is True
    assert result.pass_flags["weekly_volume_ratio_min"] is True
    assert result.pass_flags["weekly_rs_score_min"] is True
    assert result.pass_flags["market_regime_not_bear"] is True
    assert "sector_rs_score_min" not in result.pass_flags
    assert "market_score_min" not in result.pass_flags
    assert "roe_min" not in result.pass_flags
    assert result.metadata["suggested_stop_basis"] == "weekly_sma30"
    assert result.metadata["weekly_close_to_sma30_pct"] == pytest.approx(0.111111)
    assert result.metadata["weekly_sma30_slope"] == pytest.approx(2.0)
    assert result.metadata["weekly_data_available"] is True
    assert result.metadata["weekly_breakout"] is True
    assert result.metadata["weekly_volume_ratio"] == pytest.approx(1.25)
    assert result.metadata["weekly_rs_score"] == pytest.approx(0.90)
    assert result.metadata["risk_metadata"]["suggested_stop_price"] == 90.0
    assert result.metadata["risk_metadata"]["risk_per_share"] == 10.0
    assert result.metadata["risk_metadata"]["risk_basis"] == "weekly_sma30"
    assert result.metadata["risk_metadata"]["suggested_stop_basis"] == "weekly_sma30"
    assert result.metadata["risk_metadata"]["weekly_close_to_sma30_pct"] == pytest.approx(0.111111)
    assert result.metadata["data_quality_flags"]["weekly_data_available"] is True
    assert result.metadata["data_quality_flags"]["weekly_breakout_available"] is True
    assert result.metadata["data_quality_flags"]["weekly_volume_ratio_available"] is True
    assert result.metadata["data_quality_flags"]["weekly_rs_score_available"] is True
    assert result.metadata["data_quality_flags"]["sector_rs_score_available"] is True
    assert result.metadata["data_quality_flags"]["market_score_available"] is True
    assert result.metadata["data_quality_flags"]["fundamentals_available"] is True
    assert result.metadata["data_quality_flags"]["roe_available"] is True
    assert {"triggered_conditions", "score_breakdown", "data_quality_flags", "explanation"}.issubset(result.metadata)


def test_stage_analysis_weekly_rejects_flat_or_falling_sma30():
    config = get_config("strategies")
    result = StageAnalysisWeeklyStrategy(config["stage_analysis_weekly"]).evaluate(
        _passing_indicator(weekly_sma30_slope=0.0),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "weekly_sma30_slope_positive" in result.failed_conditions


def test_stage_analysis_weekly_rejects_close_below_weekly_sma30():
    config = get_config("strategies")
    result = StageAnalysisWeeklyStrategy(config["stage_analysis_weekly"]).evaluate(
        _passing_indicator(weekly_close=89.0, weekly_sma30=90.0),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "weekly_close_gt_sma30" in result.failed_conditions


def test_stage_analysis_weekly_rejects_missing_weekly_breakout_availability():
    config = get_config("strategies")
    result = StageAnalysisWeeklyStrategy(config["stage_analysis_weekly"]).evaluate(
        _passing_indicator(weekly_breakout=False, weekly_breakout_available=False),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert result.pass_flags["weekly_breakout_available"] is False
    assert result.pass_flags["weekly_breakout"] is False
    assert "weekly_breakout_available" in result.failed_conditions
    assert result.metadata["weekly_breakout"] is None
    assert result.metadata["data_quality_flags"]["weekly_breakout_available"] is False


def test_stage_analysis_weekly_rejects_low_weekly_rs_score():
    config = get_config("strategies")
    result = StageAnalysisWeeklyStrategy(config["stage_analysis_weekly"]).evaluate(
        _passing_indicator(weekly_rs_score=0.69),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert result.pass_flags["weekly_rs_score_min"] is False
    assert "weekly_rs_score_min" in result.failed_conditions


def test_stage_analysis_weekly_rejects_bear_market_regime():
    config = get_config("strategies")
    result = StageAnalysisWeeklyStrategy(config["stage_analysis_weekly"]).evaluate(
        _passing_indicator(),
        _passing_fundamentals(),
        "bear",
    )

    assert result.passed is False
    assert "market_regime_not_bear" in result.failed_conditions


@pytest.mark.parametrize(
    ("missing_field", "expected_condition"),
    [
        ("weekly_close", "weekly_close_available"),
        ("weekly_sma30", "weekly_sma30_available"),
        ("weekly_sma30_slope", "weekly_sma30_slope_available"),
    ],
)
def test_stage_analysis_weekly_rejects_any_missing_weekly_field(missing_field, expected_condition):
    config = get_config("strategies")
    result = StageAnalysisWeeklyStrategy(config["stage_analysis_weekly"]).evaluate(
        _passing_indicator(**{missing_field: None}),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "weekly_data_available" in result.failed_conditions
    assert expected_condition in result.failed_conditions
    assert result.metadata["data_quality_flags"]["weekly_data_available"] is False
    assert result.metadata["data_quality_flags"][expected_condition] is False


def test_stage_analysis_weekly_rejects_missing_weekly_data_with_quality_flag():
    config = get_config("strategies")
    result = StageAnalysisWeeklyStrategy(config["stage_analysis_weekly"]).evaluate(
        _passing_indicator(weekly_close=None, weekly_sma30=None, weekly_sma30_slope=None),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "weekly_close_available" in result.failed_conditions
    assert "weekly_sma30_available" in result.failed_conditions
    assert "weekly_sma30_slope_available" in result.failed_conditions
    assert "weekly_data_available" in result.failed_conditions
    assert "weekly_close_gt_sma30" in result.failed_conditions
    assert "weekly_sma30_slope_positive" in result.failed_conditions
    assert result.metadata["weekly_close_to_sma30_pct"] is None
    assert result.metadata["weekly_sma30_slope"] is None
    assert result.metadata["risk_metadata"]["risk_basis"] == "unavailable"
    assert result.metadata["risk_metadata"]["fallback_policy"] == "fail_closed_missing_weekly_data_fallback_to_common_risk"
    assert result.metadata["data_quality_flags"]["weekly_data_available"] is False
    assert result.metadata["data_quality_flags"]["weekly_close_available"] is False
    assert result.metadata["data_quality_flags"]["weekly_sma30_available"] is False
    assert result.metadata["data_quality_flags"]["weekly_sma30_slope_available"] is False


def test_stage_analysis_weekly_rejects_low_sector_rs_when_filter_enabled():
    config = get_config("strategies")
    result = StageAnalysisWeeklyStrategy(
        {**config["stage_analysis_weekly"], "sector_rs_filter_enabled": True, "sector_rs_score_min": 0.60}
    ).evaluate(
        _passing_indicator(sector_rs_score=0.59),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert result.pass_flags["sector_rs_score_min"] is False
    assert "sector_rs_score_min" in result.failed_conditions
    assert "sector_rs_score_min" in result.metadata["optional_conditions"]
    assert result.metadata["data_quality_flags"]["sector_rs_score_available"] is True


def test_stage_analysis_weekly_rejects_low_market_score_when_filter_enabled():
    config = get_config("strategies")
    result = StageAnalysisWeeklyStrategy(
        {**config["stage_analysis_weekly"], "market_score_filter_enabled": True, "market_score_min": 0.50}
    ).evaluate(
        _passing_indicator(market_score=0.49),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert result.pass_flags["market_score_min"] is False
    assert "market_score_min" in result.failed_conditions
    assert "market_score_min" in result.metadata["optional_conditions"]
    assert result.metadata["data_quality_flags"]["market_score_available"] is True


def test_stage_analysis_weekly_allows_missing_fundamentals_when_quality_filter_disabled():
    config = get_config("strategies")
    result = StageAnalysisWeeklyStrategy(config["stage_analysis_weekly"]).evaluate(
        _passing_indicator(),
        None,
        "neutral",
    )

    assert result.passed is True
    assert "roe_min" not in result.pass_flags
    assert result.metadata["data_quality_flags"]["fundamentals_available"] is False
    assert result.metadata["data_quality_flags"]["roe_available"] is False


def test_stage_analysis_weekly_rejects_low_roe_when_quality_filter_enabled():
    config = get_config("strategies")
    result = StageAnalysisWeeklyStrategy(
        {**config["stage_analysis_weekly"], "fundamentals_quality_enabled": True, "min_roe": 0.15}
    ).evaluate(
        _passing_indicator(),
        _passing_fundamentals(roe=0.14),
        "neutral",
    )

    assert result.passed is False
    assert result.pass_flags["roe_min"] is False
    assert "roe_min" in result.failed_conditions
    assert "roe_min" in result.metadata["optional_conditions"]
    assert result.metadata["data_quality_flags"]["fundamentals_available"] is True
    assert result.metadata["data_quality_flags"]["roe_available"] is True


def test_momentum_rank_passes_with_strong_relative_strength_fixture():
    config = get_config("strategies")
    result = MomentumRankStrategy(config["momentum_rank"]).evaluate(
        _passing_indicator(),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is True
    assert result.strategy_tag == "momentum_rank"
    assert result.failed_conditions == []
    assert result.pass_flags["relative_strength_score_min"] is True
    assert result.metadata["data_quality_flags"]["sector_rs_score_available"] is True
    assert result.metadata["momentum_quality_score"] == pytest.approx(0.725)
    assert result.metadata["score_breakdown"]["momentum_quality_score"] == pytest.approx(0.725)
    assert result.metadata["relative_strength_score"] == pytest.approx(0.90)
    assert result.metadata["trend_score"] == pytest.approx(0.80)
    assert result.metadata["sector_rs_score"] == pytest.approx(0.70)
    assert result.metadata["market_score"] == pytest.approx(0.50)
    assert result.metadata["atr20_pct"] == pytest.approx(0.02)
    assert result.metadata["signal_type"] == "ranking_candidate"
    assert result.metadata["execution_requires_portfolio_constructor"] is True
    assert result.metadata["rebalance_rule_not_available_in_current_mvp"] is True
    assert result.metadata["risk_flags"]["execution_requires_portfolio_constructor"] is True
    assert result.metadata["risk_flags"]["rebalance_rule_not_available_in_current_mvp"] is True
    assert result.metadata["risk_flags"]["atr20_pct_too_high"] is False
    assert result.metadata["risk_flags"]["volume_ratio_50_too_low"] is False
    assert result.metadata["data_quality_flags"]["atr20_pct_available"] is True
    assert result.metadata["data_quality_flags"]["volume_ratio_50_available"] is True
    assert result.metadata["data_quality_flags"]["close_available"] is True
    assert result.metadata["data_quality_flags"]["sma50_available"] is True
    assert result.metadata["data_quality_flags"]["sma150_available"] is True
    assert result.metadata["data_quality_flags"]["sma200_available"] is True


def test_rank_strategies_default_to_rank_portfolio_selection_mode():
    config = get_config("strategies")

    assert config["momentum_rank"]["selection_mode"] == "rank_portfolio"
    assert config["relative_strength_leader"]["selection_mode"] == "rank_portfolio"


def test_momentum_rank_keeps_atr_and_volume_filters_optional_by_default():
    config = get_config("strategies")
    result = MomentumRankStrategy(config["momentum_rank"]).evaluate(
        _passing_indicator(atr20_pct=0.20, volume_ratio_50=0.20),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is True
    assert "atr20_pct_max" not in result.pass_flags
    assert "volume_ratio_50_min" not in result.pass_flags
    assert result.metadata["risk_flags"]["atr20_pct_too_high"] is True
    assert result.metadata["risk_flags"]["volume_ratio_50_too_low"] is True


def test_momentum_rank_rejects_high_atr20_pct_when_filter_enabled():
    config = get_config("strategies")
    result = MomentumRankStrategy(
        {**config["momentum_rank"], "atr_risk_filter_enabled": True, "max_atr20_pct": 0.08}
    ).evaluate(
        _passing_indicator(atr20_pct=0.081),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert result.pass_flags["atr20_pct_max"] is False
    assert "atr20_pct_max" in result.failed_conditions
    assert "atr20_pct_max" in result.metadata["optional_conditions"]
    assert result.metadata["risk_flags"]["atr20_pct_too_high"] is True
    assert result.metadata["data_quality_flags"]["atr20_pct_available"] is True


def test_momentum_rank_rejects_low_volume_ratio_50_when_confirmation_enabled():
    config = get_config("strategies")
    result = MomentumRankStrategy(
        {**config["momentum_rank"], "volume_confirmation_enabled": True, "min_volume_ratio_50": 0.8}
    ).evaluate(
        _passing_indicator(volume_ratio_50=0.79),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert result.pass_flags["volume_ratio_50_min"] is False
    assert "volume_ratio_50_min" in result.failed_conditions
    assert "volume_ratio_50_min" in result.metadata["optional_conditions"]
    assert result.metadata["risk_flags"]["volume_ratio_50_too_low"] is True
    assert result.metadata["data_quality_flags"]["volume_ratio_50_available"] is True


def test_momentum_rank_rejects_low_rs_percentile():
    config = get_config("strategies")
    result = MomentumRankStrategy(config["momentum_rank"]).evaluate(
        _passing_indicator(rs_percentile=84.0),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "rs_percentile_min" in result.failed_conditions


def test_momentum_rank_rejects_low_sector_rs_score():
    config = get_config("strategies")
    result = MomentumRankStrategy(config["momentum_rank"]).evaluate(
        _passing_indicator(sector_rs_score=0.59),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "sector_rs_score_min" in result.failed_conditions


def test_momentum_rank_rejects_low_trend_score():
    config = get_config("strategies")
    result = MomentumRankStrategy(config["momentum_rank"]).evaluate(
        _passing_indicator(trend_score=0.74),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "trend_score_min" in result.failed_conditions


def test_relative_strength_leader_passes_with_strong_leadership_fixture():
    config = get_config("strategies")
    result = RelativeStrengthLeaderStrategy(config["relative_strength_leader"]).evaluate(
        _passing_indicator(),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is True
    assert result.strategy_tag == "relative_strength_leader"
    assert result.failed_conditions == []
    assert result.pass_flags["near_high_52w"] is True
    assert result.pass_flags["market_regime_not_bear"] is True
    assert "market_score_min" not in result.pass_flags
    assert "atr20_pct_max" not in result.pass_flags
    assert "roe_min" not in result.pass_flags
    assert result.metadata["leadership_score"] == pytest.approx(0.875)
    assert result.metadata["score_breakdown"]["leadership_score"] == pytest.approx(0.875)
    assert result.metadata["rs_percentile"] == pytest.approx(90.0)
    assert result.metadata["relative_strength_score"] == pytest.approx(0.90)
    assert result.metadata["sector_rs_score"] == pytest.approx(0.70)
    assert result.metadata["near_high_52w"] is True
    assert result.metadata["signal_type"] == "ranking_candidate"
    assert result.metadata["execution_requires_portfolio_constructor"] is True
    assert "risk_flags" in result.metadata
    assert result.metadata["risk_flags"]["bear_market"] is False
    assert result.metadata["risk_flags"]["atr20_pct_too_high"] is False
    assert result.metadata["risk_flags"]["execution_requires_portfolio_constructor"] is True
    assert result.metadata["data_quality_flags"]["high_52w_available"] is True
    assert result.metadata["data_quality_flags"]["market_score_available"] is True
    assert result.metadata["data_quality_flags"]["atr20_pct_available"] is True
    assert result.metadata["data_quality_flags"]["fundamentals_available"] is True
    assert result.metadata["data_quality_flags"]["roe_available"] is True
    assert {"triggered_conditions", "score_breakdown", "data_quality_flags", "explanation"}.issubset(result.metadata)


def test_relative_strength_leader_rejects_bear_market_regime():
    config = get_config("strategies")
    result = RelativeStrengthLeaderStrategy(config["relative_strength_leader"]).evaluate(
        _passing_indicator(),
        _passing_fundamentals(),
        "bear",
    )

    assert result.passed is False
    assert result.pass_flags["market_regime_not_bear"] is False
    assert "market_regime_not_bear" in result.failed_conditions
    assert result.metadata["risk_flags"]["bear_market"] is True
    assert result.metadata["data_quality_flags"]["market_regime_available"] is True


def test_relative_strength_leader_rejects_low_market_score_when_filter_enabled():
    config = get_config("strategies")
    result = RelativeStrengthLeaderStrategy(
        {**config["relative_strength_leader"], "market_score_filter_enabled": True, "market_score_min": 0.50}
    ).evaluate(
        _passing_indicator(market_score=0.49),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert result.pass_flags["market_score_min"] is False
    assert "market_score_min" in result.failed_conditions
    assert "market_score_min" in result.metadata["optional_conditions"]
    assert result.metadata["risk_flags"]["market_score_below_min"] is True
    assert result.metadata["data_quality_flags"]["market_score_available"] is True


def test_relative_strength_leader_rejects_high_atr20_pct_when_filter_enabled():
    config = get_config("strategies")
    result = RelativeStrengthLeaderStrategy(
        {**config["relative_strength_leader"], "atr_risk_filter_enabled": True, "max_atr20_pct": 0.08}
    ).evaluate(
        _passing_indicator(atr20_pct=0.081),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert result.pass_flags["atr20_pct_max"] is False
    assert "atr20_pct_max" in result.failed_conditions
    assert "atr20_pct_max" in result.metadata["optional_conditions"]
    assert result.metadata["risk_flags"]["atr20_pct_too_high"] is True
    assert result.metadata["data_quality_flags"]["atr20_pct_available"] is True


def test_relative_strength_leader_allows_missing_fundamentals_when_quality_filter_disabled():
    config = get_config("strategies")
    result = RelativeStrengthLeaderStrategy(config["relative_strength_leader"]).evaluate(
        _passing_indicator(),
        None,
        "neutral",
    )

    assert result.passed is True
    assert "roe_min" not in result.pass_flags
    assert result.metadata["risk_flags"]["fundamentals_missing"] is True
    assert result.metadata["data_quality_flags"]["fundamentals_available"] is False
    assert result.metadata["data_quality_flags"]["roe_available"] is False


def test_relative_strength_leader_rejects_low_roe_when_quality_filter_enabled():
    config = get_config("strategies")
    result = RelativeStrengthLeaderStrategy(
        {**config["relative_strength_leader"], "fundamentals_quality_enabled": True, "min_roe": 0.15}
    ).evaluate(
        _passing_indicator(),
        _passing_fundamentals(roe=0.14),
        "neutral",
    )

    assert result.passed is False
    assert result.pass_flags["roe_min"] is False
    assert "roe_min" in result.failed_conditions
    assert "roe_min" in result.metadata["optional_conditions"]
    assert result.metadata["risk_flags"]["roe_below_min"] is True
    assert result.metadata["data_quality_flags"]["fundamentals_available"] is True
    assert result.metadata["data_quality_flags"]["roe_available"] is True


def test_relative_strength_leader_rejects_low_rs_percentile():
    config = get_config("strategies")
    result = RelativeStrengthLeaderStrategy(config["relative_strength_leader"]).evaluate(
        _passing_indicator(rs_percentile=89.0),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "rs_percentile_min" in result.failed_conditions


def test_relative_strength_leader_rejects_low_sector_rs_score():
    config = get_config("strategies")
    result = RelativeStrengthLeaderStrategy(config["relative_strength_leader"]).evaluate(
        _passing_indicator(sector_rs_score=0.69),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "sector_rs_score_min" in result.failed_conditions


def test_relative_strength_leader_rejects_missing_high_52w_with_quality_flag():
    config = get_config("strategies")
    result = RelativeStrengthLeaderStrategy(config["relative_strength_leader"]).evaluate(
        _passing_indicator(high_52w=None),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "near_high_52w" in result.failed_conditions
    assert result.metadata["data_quality_flags"]["high_52w_available"] is False


def test_relative_strength_leader_rejects_low_volume_ratio_50():
    config = get_config("strategies")
    result = RelativeStrengthLeaderStrategy(config["relative_strength_leader"]).evaluate(
        _passing_indicator(volume_ratio_50=0.99),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "volume_ratio_50_min" in result.failed_conditions


def test_screener_can_run_relative_strength_leader_when_explicitly_selected(seeded_db):
    result = ScreenerService(seeded_db).run(strategies=["relative_strength_leader"])

    rows = list(seeded_db.scalars(select(ScreenResult)).all())
    listed = ScreenerService(seeded_db).list_results(strategy_name="relative_strength_leader", limit=1)
    assert result["rows"] > 0
    assert result["strategies"] == ["relative_strength_leader"]
    assert {row.strategy_tag for row in rows} == {"relative_strength_leader"}
    assert listed
    first = listed[0]
    assert first["strategy_name"] == "relative_strength_leader"
    assert {"triggered_conditions", "score_breakdown", "data_quality_flags", "explanation", "rationale"}.issubset(first)
    assert "high_52w_available" in first["data_quality_flags"]
    assert "volume_ratio_50_available" in first["data_quality_flags"]


def test_backtest_can_run_relative_strength_leader_when_explicitly_selected(seeded_db):
    result = BacktestService(seeded_db).run("relative_strength_leader")

    assert result["run_id"]
    assert result["strategy_name"] == "relative_strength_leader"
    assert "metrics" in result
    assert "trade_count" in result["metrics"]
    assert result["metrics"]["portfolio_constructor_used"] is True
    assert result["metrics"]["portfolio_selection_mode"] == "rank_portfolio"


def test_screener_can_run_new_high_breakout_when_explicitly_selected(seeded_db):
    result = ScreenerService(seeded_db).run(strategies=["new_high_breakout"])

    rows = list(seeded_db.scalars(select(ScreenResult)).all())
    listed = ScreenerService(seeded_db).list_results(strategy_name="new_high_breakout", limit=1)
    assert result["rows"] > 0
    assert result["strategies"] == ["new_high_breakout"]
    assert {row.strategy_tag for row in rows} == {"new_high_breakout"}
    assert listed
    first = listed[0]
    assert first["strategy_name"] == "new_high_breakout"
    assert {"triggered_conditions", "score_breakdown", "data_quality_flags", "explanation", "rationale"}.issubset(first)
    assert "high_52w_available" in first["data_quality_flags"]
    assert "distance_from_52w_high_available" in first["data_quality_flags"]
    assert "volume_ratio_50_available" in first["data_quality_flags"]


def test_backtest_can_run_new_high_breakout_when_explicitly_selected(seeded_db):
    result = BacktestService(seeded_db).run("new_high_breakout")

    assert result["run_id"]
    assert result["strategy_name"] == "new_high_breakout"
    assert "metrics" in result
    assert "trade_count" in result["metrics"]


def test_screener_can_run_pullback_20ema_when_explicitly_selected(seeded_db):
    result = ScreenerService(seeded_db).run(strategies=["pullback_20ema"])

    rows = list(seeded_db.scalars(select(ScreenResult)).all())
    listed = ScreenerService(seeded_db).list_results(strategy_name="pullback_20ema", limit=100)
    assert result["rows"] > 0
    assert result["strategies"] == ["pullback_20ema"]
    assert {row.strategy_tag for row in rows} == {"pullback_20ema"}
    assert listed
    first = listed[0]
    assert first["strategy_name"] == "pullback_20ema"
    assert {"triggered_conditions", "score_breakdown", "data_quality_flags", "explanation", "rationale"}.issubset(first)
    assert "ema20_available" in first["data_quality_flags"]
    assert "low_available" in first["data_quality_flags"]


def test_backtest_can_run_pullback_20ema_when_explicitly_selected(seeded_db):
    result = BacktestService(seeded_db).run("pullback_20ema")

    assert result["run_id"]
    assert result["strategy_name"] == "pullback_20ema"
    assert "metrics" in result
    assert "trade_count" in result["metrics"]


def test_screener_can_run_darvas_box_when_explicitly_selected(seeded_db):
    result = ScreenerService(seeded_db).run(strategies=["darvas_box"])

    rows = list(seeded_db.scalars(select(ScreenResult)).all())
    listed = ScreenerService(seeded_db).list_results(strategy_name="darvas_box", limit=100)
    assert result["rows"] > 0
    assert result["strategies"] == ["darvas_box"]
    assert {row.strategy_tag for row in rows} == {"darvas_box"}
    assert listed
    first = listed[0]
    assert first["strategy_name"] == "darvas_box"
    assert {"triggered_conditions", "score_breakdown", "data_quality_flags", "explanation", "rationale"}.issubset(first)
    assert "pivot_high_20_prev_available" in first["data_quality_flags"]
    assert "pivot_low_20_prev_available" in first["data_quality_flags"]
    assert "box_height_pct_available" in first["data_quality_flags"]
    assert "box_top" in first["score_breakdown"]
    assert "box_bottom" in first["score_breakdown"]
    assert "box_height_pct" in first["score_breakdown"]


def test_backtest_can_run_darvas_box_when_explicitly_selected(seeded_db):
    result = BacktestService(seeded_db).run("darvas_box")

    assert result["run_id"]
    assert result["strategy_name"] == "darvas_box"
    assert "metrics" in result
    assert "trade_count" in result["metrics"]


def test_screener_can_run_stage_analysis_weekly_when_explicitly_selected(seeded_db):
    result = ScreenerService(seeded_db).run(strategies=["stage_analysis_weekly"])

    rows = list(seeded_db.scalars(select(ScreenResult)).all())
    listed = ScreenerService(seeded_db).list_results(strategy_name="stage_analysis_weekly", limit=100)
    assert result["rows"] > 0
    assert result["strategies"] == ["stage_analysis_weekly"]
    assert {row.strategy_tag for row in rows} == {"stage_analysis_weekly"}
    assert listed
    first = listed[0]
    assert first["strategy_name"] == "stage_analysis_weekly"
    assert {"triggered_conditions", "score_breakdown", "data_quality_flags", "explanation", "rationale"}.issubset(first)
    assert "weekly_data_available" in first["data_quality_flags"]
    assert "weekly_close_available" in first["data_quality_flags"]
    assert "weekly_sma30_available" in first["data_quality_flags"]
    assert "weekly_sma30_slope_available" in first["data_quality_flags"]


@pytest.mark.parametrize(
    "strategy_name",
    ["new_high_breakout", "pullback_20ema", "darvas_box", "stage_analysis_weekly"],
)
def test_screener_risk_metadata_matches_risk_details_json(seeded_db, strategy_name):
    ScreenerService(seeded_db).run(strategies=[strategy_name])

    rows = ScreenerService(seeded_db).list_results(strategy_name=strategy_name, limit=10)

    assert rows
    for row in rows:
        risk_metadata = row["risk_metadata"]
        risk_details = row["risk_details_json"]
        assert row["risk_basis"] == risk_details["risk_basis"] == risk_metadata["risk_basis"]
        assert row["stop_price"] == pytest.approx(risk_metadata["suggested_stop_price"])
        assert risk_details["stop_price"] == pytest.approx(risk_metadata["suggested_stop_price"])
        assert risk_details["risk_per_share"] == pytest.approx(risk_metadata["risk_per_share"])


def test_backtest_can_run_stage_analysis_weekly_when_explicitly_selected(seeded_db):
    result = BacktestService(seeded_db).run("stage_analysis_weekly")

    assert result["run_id"]
    assert result["strategy_name"] == "stage_analysis_weekly"
    assert "metrics" in result
    assert "trade_count" in result["metrics"]


def test_screener_can_run_momentum_rank_when_explicitly_selected(seeded_db):
    result = ScreenerService(seeded_db).run(strategies=["momentum_rank"])

    rows = list(seeded_db.scalars(select(ScreenResult)).all())
    assert result["rows"] > 0
    assert result["strategies"] == ["momentum_rank"]
    assert {row.strategy_tag for row in rows} == {"momentum_rank"}


def test_backtest_can_run_momentum_rank_when_explicitly_selected(seeded_db):
    result = BacktestService(seeded_db).run("momentum_rank")

    assert result["run_id"]
    assert result["strategy_name"] == "momentum_rank"
    assert "metrics" in result
    assert "trade_count" in result["metrics"]
    assert result["metrics"]["portfolio_constructor_used"] is True
    assert result["metrics"]["portfolio_selection_mode"] == "rank_portfolio"


def test_phase3h_optional_strategy_filters_reject_fixture_conditions():
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


@pytest.mark.parametrize(
    (
        "strategy_cls",
        "strategy_name",
        "enabled_config",
        "condition_name",
        "quality_flag",
        "market_regime",
        "indicator_overrides",
        "fundamental_overrides",
    ),
    [
        (
            TrendBreakoutStrategy,
            "trend_breakout",
            {"sector_rs_filter_enabled": True, "sector_rs_score_min": 0.60},
            "sector_rs_score_min",
            "sector_rs_score_available",
            "bull",
            {},
            {},
        ),
        (
            VcpBreakoutStrategy,
            "vcp_breakout",
            {"sector_rs_score_min_enabled": True, "sector_rs_score_min": 0.60},
            "sector_rs_score_min",
            "sector_rs_score_available",
            "bull",
            {},
            {},
        ),
        (
            CanslimLiteStrategy,
            "canslim_lite",
            {"optional_fundamental_quality_enabled": True, "min_roe": 0.15, "min_gross_profitability": 0.20},
            "optional_fundamental_quality",
            "fundamental_quality_available",
            "bull",
            {},
            {"roe": 0.20, "gross_profitability": 0.25},
        ),
        (
            NewHighBreakoutStrategy,
            "new_high_breakout",
            {"market_score_min_enabled": True, "market_score_min": 0.50},
            "market_score_min",
            "market_score_available",
            "bull",
            {},
            {},
        ),
        (
            Pullback20EmaStrategy,
            "pullback_20ema",
            {"volume_ratio_50_min_enabled": True, "volume_ratio_50_min": 1.0},
            "volume_ratio_50_min",
            "volume_ratio_50_available",
            "bull",
            {},
            {},
        ),
        (
            MomentumRankStrategy,
            "momentum_rank",
            {"market_regime_not_bear_enabled": True},
            "market_regime_not_bear",
            "market_regime_available",
            "bull",
            {},
            {},
        ),
        (
            RelativeStrengthLeaderStrategy,
            "relative_strength_leader",
            {"market_score_min_enabled": True, "market_score_min": 0.50},
            "market_score_min",
            "market_score_available",
            "bull",
            {},
            {},
        ),
        (
            DarvasBoxStrategy,
            "darvas_box",
            {"atr20_pct_max_enabled": True, "atr20_pct_max": 0.08},
            "atr20_pct_max",
            "atr20_pct_available",
            "bull",
            {"close": 100.0, "pivot_high_20_prev": 95.0, "pivot_low_20_prev": 80.0},
            {},
        ),
        (
            StageAnalysisWeeklyStrategy,
            "stage_analysis_weekly",
            {"sector_rs_score_min_enabled": True, "sector_rs_score_min": 0.60},
            "sector_rs_score_min",
            "sector_rs_score_available",
            "bull",
            {},
            {},
        ),
    ],
)
def test_phase_c_hardening_optional_conditions_pass_with_quality_flags(
    strategy_cls,
    strategy_name,
    enabled_config,
    condition_name,
    quality_flag,
    market_regime,
    indicator_overrides,
    fundamental_overrides,
):
    result = strategy_cls(_strategy_config(strategy_name, **enabled_config)).evaluate(
        _passing_indicator(**indicator_overrides),
        _passing_fundamentals(**fundamental_overrides),
        market_regime,
    )

    assert result.passed is True
    assert result.pass_flags[condition_name] is True
    assert condition_name in result.metadata["optional_conditions"]
    assert result.metadata["data_quality_flags"][quality_flag] is True
    assert result.metadata["risk_metadata"]["suggested_stop_price"] is not None
    assert {"suggested_stop_price", "risk_per_share", "risk_basis", "entry_chase_warning"}.issubset(
        result.metadata["risk_metadata"]
    )


@pytest.mark.parametrize(
    (
        "strategy_cls",
        "strategy_name",
        "enabled_config",
        "condition_name",
        "quality_flag",
        "market_regime",
        "indicator_overrides",
        "fundamental_overrides",
    ),
    [
        (
            TrendBreakoutStrategy,
            "trend_breakout",
            {"sector_rs_filter_enabled": True, "sector_rs_score_min": 0.60},
            "sector_rs_score_min",
            "sector_rs_score_available",
            "bull",
            {"sector_rs_score": 0.59},
            {},
        ),
        (
            VcpBreakoutStrategy,
            "vcp_breakout",
            {"sector_rs_score_min_enabled": True, "sector_rs_score_min": 0.60},
            "sector_rs_score_min",
            "sector_rs_score_available",
            "bull",
            {"sector_rs_score": 0.59},
            {},
        ),
        (
            CanslimLiteStrategy,
            "canslim_lite",
            {"optional_fundamental_quality_enabled": True, "min_roe": 0.15, "min_gross_profitability": 0.20},
            "optional_fundamental_quality",
            "fundamental_quality_available",
            "bull",
            {},
            {"roe": 0.20, "gross_profitability": 0.19},
        ),
        (
            NewHighBreakoutStrategy,
            "new_high_breakout",
            {"market_score_min_enabled": True, "market_score_min": 0.50},
            "market_score_min",
            "market_score_available",
            "bull",
            {"market_score": 0.49},
            {},
        ),
        (
            Pullback20EmaStrategy,
            "pullback_20ema",
            {"volume_ratio_50_min_enabled": True, "volume_ratio_50_min": 1.0},
            "volume_ratio_50_min",
            "volume_ratio_50_available",
            "bull",
            {"volume_ratio_50": 0.99},
            {},
        ),
        (
            MomentumRankStrategy,
            "momentum_rank",
            {"market_regime_not_bear_enabled": True},
            "market_regime_not_bear",
            "market_regime_available",
            "bear",
            {},
            {},
        ),
        (
            RelativeStrengthLeaderStrategy,
            "relative_strength_leader",
            {"market_score_min_enabled": True, "market_score_min": 0.50},
            "market_score_min",
            "market_score_available",
            "bull",
            {"market_score": 0.49},
            {},
        ),
        (
            DarvasBoxStrategy,
            "darvas_box",
            {"atr20_pct_max_enabled": True, "atr20_pct_max": 0.08},
            "atr20_pct_max",
            "atr20_pct_available",
            "bull",
            {"close": 100.0, "pivot_high_20_prev": 95.0, "pivot_low_20_prev": 80.0, "atr20_pct": 0.081},
            {},
        ),
        (
            StageAnalysisWeeklyStrategy,
            "stage_analysis_weekly",
            {"sector_rs_score_min_enabled": True, "sector_rs_score_min": 0.60},
            "sector_rs_score_min",
            "sector_rs_score_available",
            "bull",
            {"sector_rs_score": 0.59},
            {},
        ),
    ],
)
def test_phase_c_hardening_optional_conditions_fail_closed_with_quality_flags(
    strategy_cls,
    strategy_name,
    enabled_config,
    condition_name,
    quality_flag,
    market_regime,
    indicator_overrides,
    fundamental_overrides,
):
    result = strategy_cls(_strategy_config(strategy_name, **enabled_config)).evaluate(
        _passing_indicator(**indicator_overrides),
        _passing_fundamentals(**fundamental_overrides),
        market_regime,
    )

    assert result.passed is False
    assert result.pass_flags[condition_name] is False
    assert condition_name in result.failed_conditions
    assert condition_name in result.metadata["optional_conditions"]
    assert result.metadata["data_quality_flags"][quality_flag] is True


def test_phase_c_hardening_risk_metadata_is_additive_not_a_pass_flag():
    result = TrendBreakoutStrategy(_strategy_config("trend_breakout")).evaluate(
        _passing_indicator(),
        _passing_fundamentals(),
        "bull",
    )

    assert result.passed is True
    assert "risk_metadata" not in result.pass_flags
    assert result.metadata["risk_metadata"] == {
        "suggested_stop_price": 82.0,
        "risk_per_share": 18.0,
        "risk_basis": "pivot_low_20_prev",
        "entry_chase_warning": False,
        "entry_chase_reference": 100.0,
    }
    assert result.metadata["data_quality_flags"]["suggested_stop_price_available"] is True
    assert result.metadata["data_quality_flags"]["risk_per_share_available"] is True


def test_canslim_optional_earnings_quality_is_config_gated():
    result = CanslimLiteStrategy(
        _strategy_config("canslim_lite", optional_earnings_quality_enabled=True)
    ).evaluate(
        _passing_indicator(),
        _passing_fundamentals(sales_growth=0.19, roe=0.20),
        "bull",
    )

    assert result.passed is False
    assert result.pass_flags["optional_earnings_quality"] is False
    assert "optional_earnings_quality" in result.failed_conditions
    assert result.metadata["data_quality_flags"]["earnings_quality_available"] is True


def test_phase3h_screener_response_includes_explanation_contract(seeded_db):
    ScreenerService(seeded_db).run()
    first = ScreenerService(seeded_db).list_results(limit=1)[0]

    for key in (
        "triggered_conditions",
        "score_breakdown",
        "risk_flags",
        "data_quality_flags",
        "metadata",
        "risk_metadata",
        "explanation",
        "rationale",
    ):
        assert key in first
    assert isinstance(first["triggered_conditions"], list)
    assert isinstance(first["score_breakdown"], dict)
    assert isinstance(first["risk_flags"], dict)
    assert isinstance(first["data_quality_flags"], dict)
    assert first["explanation"] == first["metadata"]["explanation"]


def test_screener_list_results_uses_stored_metadata_without_reevaluation(seeded_db, monkeypatch):
    ScreenerService(seeded_db).run(strategies=["new_high_breakout"])
    service = ScreenerService(seeded_db)

    def fail_if_reevaluated(*_args, **_kwargs):
        raise AssertionError("list_results must not re-evaluate strategy metadata")

    monkeypatch.setattr(service.strategies["new_high_breakout"], "evaluate", fail_if_reevaluated)
    first = service.list_results(strategy_name="new_high_breakout", limit=1)[0]

    assert first["strategy_name"] == "new_high_breakout"
    assert "distance_from_52w_high_available" in first["data_quality_flags"]
    assert "chase_warning" in first["metadata"]
    assert "chase_warning" in first["risk_flags"]
