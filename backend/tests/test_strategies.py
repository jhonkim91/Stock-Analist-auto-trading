from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

from sqlalchemy import select

from backend.app.core.config import get_config
from backend.app.models.schemas import ScreenerRunRequest
from backend.app.models.tables import IndicatorSnapshot, ScreenResult
from backend.app.repositories.market_repository import MarketRepository
from backend.app.services.backtest_service import BacktestService
from backend.app.services.screener_service import ScreenerService
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
)
from backend.app.strategies.stage_analysis_weekly import StageAnalysisWeeklyStrategy
from backend.app.strategies.trend_breakout import TrendBreakoutStrategy
from backend.app.strategies.vcp_breakout import VcpBreakoutStrategy


def _passing_indicator(**overrides):
    values = {
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


def test_phase3h_default_strategy_options_preserve_base_condition_flags(seeded_db):
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


def test_pullback_20ema_passes_after_ema_touch_and_close_reclaim():
    config = get_config("strategies")
    result = Pullback20EmaStrategy(config["pullback_20ema"]).evaluate(
        _passing_indicator(low=98.5, ema20=98.0, close=100.0),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is True
    assert result.strategy_tag == "pullback_20ema"
    assert result.failed_conditions == []
    assert result.pass_flags["low_touch_ema20"] is True
    assert result.pass_flags["close_gte_ema20"] is True
    assert result.metadata["data_quality_flags"]["ema20_available"] is True
    assert result.metadata["data_quality_flags"]["low_available"] is True
    assert {"triggered_conditions", "score_breakdown", "data_quality_flags", "explanation"}.issubset(result.metadata)


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


def test_pullback_20ema_rejects_high_atr20_pct():
    config = get_config("strategies")
    result = Pullback20EmaStrategy(config["pullback_20ema"]).evaluate(
        _passing_indicator(atr20_pct=0.081),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "atr20_pct_max" in result.failed_conditions


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
        _passing_indicator(close=99.5, high_52w=100.0, distance_from_52w_high=-0.005),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is True
    assert result.pass_flags["new_high_threshold"] is True


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
    assert result.metadata["box_top"] == 95.0
    assert result.metadata["box_bottom"] == 80.0
    assert result.metadata["box_height_pct"] == 0.1875
    assert result.metadata["score_breakdown"]["box_height_pct"] == 0.1875
    assert result.metadata["data_quality_flags"]["box_height_pct_available"] is True


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
    assert result.pass_flags["market_regime_not_bear"] is True
    assert result.metadata["data_quality_flags"]["weekly_data_available"] is True
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


def test_stage_analysis_weekly_rejects_bear_market_regime():
    config = get_config("strategies")
    result = StageAnalysisWeeklyStrategy(config["stage_analysis_weekly"]).evaluate(
        _passing_indicator(),
        _passing_fundamentals(),
        "bear",
    )

    assert result.passed is False
    assert "market_regime_not_bear" in result.failed_conditions


def test_stage_analysis_weekly_rejects_missing_weekly_data_with_quality_flag():
    config = get_config("strategies")
    result = StageAnalysisWeeklyStrategy(config["stage_analysis_weekly"]).evaluate(
        _passing_indicator(weekly_close=None, weekly_sma30=None, weekly_sma30_slope=None),
        _passing_fundamentals(),
        "neutral",
    )

    assert result.passed is False
    assert "weekly_data_available" in result.failed_conditions
    assert "weekly_close_gt_sma30" in result.failed_conditions
    assert result.metadata["data_quality_flags"]["weekly_data_available"] is False
    assert result.metadata["data_quality_flags"]["weekly_close_available"] is False
    assert result.metadata["data_quality_flags"]["weekly_sma30_available"] is False
    assert result.metadata["data_quality_flags"]["weekly_sma30_slope_available"] is False


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
    assert result.metadata["data_quality_flags"]["high_52w_available"] is True
    assert {"triggered_conditions", "score_breakdown", "data_quality_flags", "explanation"}.issubset(result.metadata)


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
