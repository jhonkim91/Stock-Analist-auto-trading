from __future__ import annotations

from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from backend.app.core.config import get_config
from backend.app.services.backtest_service import BacktestService
from backend.app.services.risk_service import RiskService
from backend.app.services.scoring_service import ScoringService
from backend.app.strategies.registry import get_available_strategy_registry


def _service_with_execution(seeded_db, **execution_overrides) -> BacktestService:
    service = BacktestService(seeded_db)
    service.backtest_config = {
        **service.backtest_config,
        "execution": {**service.backtest_config["execution"], **execution_overrides},
    }
    return service


def _simulation_service(**execution_overrides) -> BacktestService:
    service = BacktestService.__new__(BacktestService)
    service.backtest_config = {
        **get_config("backtest"),
        "execution": {**get_config("backtest")["execution"], **execution_overrides},
    }
    service.strategy_config = get_config("strategies")
    service.repo = SimpleNamespace(get_symbol=lambda _symbol: None)
    return service


def _strategy_indicator(**overrides) -> SimpleNamespace:
    values = {
        "trade_date": date(2026, 1, 1),
        "symbol": "TEST",
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
        "weekly_breakout": True,
        "weekly_breakout_available": True,
        "weekly_volume_ratio": 1.2,
        "weekly_volume_ratio_available": True,
        "weekly_rs_score": 0.80,
        "weekly_rs_score_available": True,
        "volume_ma20": 300000.0,
        "volume_ma50": 100000.0,
        "volume_ratio_50": 1.1,
        "atr20_pct": 0.02,
        "atr20_pct_ma60": 0.04,
        "std20": 0.01,
        "std60": 0.02,
        "high_52w": 100.0,
        "distance_from_52w_high": 0.0,
        "pivot_high_20_prev": 98.0,
        "pivot_low_20_prev": 94.0,
        "pullback_count": 1,
        "pullback_count_available": True,
        "contraction_count": 1,
        "contraction_count_available": True,
        "box_age_days": 10,
        "box_age_days_available": True,
        "box_redefinition_count": 1,
        "box_redefinition_count_available": True,
        "volume_dry_up": True,
        "breakout": True,
        "rs_percentile": 90.0,
        "relative_strength_score": 0.90,
        "trend_score": 0.80,
        "volume_score": 0.75,
        "pattern_score": 0.80,
        "sector_rs_score": 0.70,
        "market_score": 0.50,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _strategy_trade_service(indicator: SimpleNamespace) -> BacktestService:
    service = BacktestService.__new__(BacktestService)
    strategy_config = get_config("strategies")
    service.db = SimpleNamespace()
    service.repo = SimpleNamespace(
        daily_df=lambda _start_date=None, _end_date=None: pd.DataFrame(
            [
                {
                    "trade_date": date(2026, 1, 2),
                    "symbol": indicator.symbol,
                    "open": 100.0,
                    "high": 105.0,
                    "low": 99.0,
                    "close": 101.0,
                    "volume": 1000000,
                    "turnover_value": 1_000_000_000.0,
                }
            ]
        ),
        fundamentals_asof=lambda _symbol, _trade_date: SimpleNamespace(
            effective_date=date(2025, 12, 31),
            quarterly_eps_growth=0.30,
            sales_growth=0.25,
            roe=0.20,
            gross_profitability=0.25,
        ),
        index_df=lambda: pd.DataFrame(),
        get_symbol=lambda _symbol: None,
    )
    service.backtest_repo = SimpleNamespace(save=lambda _run: None)
    service.risk_service = RiskService()
    service.scoring_service = ScoringService()
    service.strategy_config = strategy_config
    service.backtest_config = {
        **get_config("backtest"),
        "execution": {**get_config("backtest")["execution"], "max_holding_days": 1},
    }
    service.strategies = get_available_strategy_registry(strategy_config)
    service._load_indicators = lambda _start_date=None, _end_date=None: [indicator]
    return service


def _rank_portfolio_service(
    indicators: list[SimpleNamespace],
    *,
    strategy_name: str = "momentum_rank",
    selection_mode: str = "rank_portfolio",
    top_n: int = 2,
    max_positions: int = 3,
    weighting: str = "equal_weight",
) -> BacktestService:
    strategy_config = deepcopy(get_config("strategies"))
    strategy_config[strategy_name] = {**strategy_config[strategy_name], "selection_mode": selection_mode}
    daily_rows = [
        {
            "trade_date": date(2026, 1, 2),
            "symbol": indicator.symbol,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 101.0,
            "volume": 1000000,
            "turnover_value": 1_000_000_000.0,
        }
        for indicator in indicators
    ]
    service = BacktestService.__new__(BacktestService)
    service.db = SimpleNamespace()
    service.repo = SimpleNamespace(
        daily_df=lambda _start_date=None, _end_date=None: pd.DataFrame(daily_rows),
        fundamentals_asof=lambda _symbol, _trade_date: SimpleNamespace(
            effective_date=date(2025, 12, 31),
            quarterly_eps_growth=0.30,
            sales_growth=0.25,
            roe=0.20,
            gross_profitability=0.25,
        ),
        index_df=lambda: pd.DataFrame(),
        get_symbol=lambda _symbol: None,
    )
    service.backtest_repo = SimpleNamespace(save=lambda _run: None)
    service.risk_service = RiskService()
    service.scoring_service = ScoringService()
    service.strategy_config = strategy_config
    service.backtest_config = {
        **deepcopy(get_config("backtest")),
        "execution": {**get_config("backtest")["execution"], "max_holding_days": 1},
        "portfolio": {
            **get_config("backtest")["portfolio"],
            "top_n": top_n,
            "max_positions": max_positions,
            "rebalance_frequency": "daily",
            "weighting": weighting,
            "allow_overlap_positions": False,
        },
    }
    service.strategies = get_available_strategy_registry(strategy_config)
    service._load_indicators = lambda _start_date=None, _end_date=None: indicators
    return service


def _price_df(rows: list[dict[str, object]]) -> dict[str, pd.DataFrame]:
    enriched_rows = []
    for row in rows:
        enriched_rows.append({"volume": 1000000, "turnover_value": 1000000000.0, **row})
    return {"TEST": pd.DataFrame(enriched_rows)}


def _legacy_market_regime_from_index(index_df: pd.DataFrame, signal_date: date) -> str:
    df = index_df[index_df["trade_date"] <= signal_date].sort_values("trade_date").copy()
    if len(df) < 200:
        return "neutral"
    df["sma50"] = df["close"].rolling(50, min_periods=50).mean()
    df["sma200"] = df["close"].rolling(200, min_periods=200).mean()
    weekly = df.set_index(pd.to_datetime(df["trade_date"])).resample("W-FRI").agg({"close": "last"}).dropna()
    weekly["weekly_sma30"] = weekly["close"].rolling(30, min_periods=30).mean()
    weekly["weekly_sma30_slope"] = weekly["weekly_sma30"] - weekly["weekly_sma30"].shift(4)
    latest = df.iloc[-1]
    weekly_latest = weekly.iloc[-1]
    bull = (
        latest["close"] > latest["sma200"]
        and latest["sma50"] > latest["sma200"]
        and pd.notna(weekly_latest["weekly_sma30"])
        and pd.notna(weekly_latest["weekly_sma30_slope"])
        and weekly_latest["close"] > weekly_latest["weekly_sma30"]
        and weekly_latest["weekly_sma30_slope"] > 0
    )
    bear = latest["close"] < latest["sma200"] and latest["sma50"] < latest["sma200"]
    return "bull" if bull else ("bear" if bear else "neutral")


def test_backtest_runs_and_reports_required_metrics(seeded_db):
    result = BacktestService(seeded_db).run("trend_breakout", start_date=date(2026, 5, 1))
    metrics = result["metrics"]

    assert {"run_id", "strategy_name", "metrics", "trades"}.issubset(result)
    for key in (
        "trade_count",
        "trades",
        "total_return",
        "cagr",
        "win_rate",
        "profit_factor",
        "max_drawdown",
        "expectancy",
        "average_holding_days",
        "avg_win",
        "avg_loss",
        "exposure",
        "total_estimated_cost",
        "cost_bps",
        "partial_fill_count",
        "no_fill_count",
        "total_unfilled_qty",
        "adjusted_price_trade_count",
        "forced_exit_count",
        "delisted_exit_count",
        "missing_data_exit_count",
        "portfolio_turnover",
        "average_active_positions",
        "rebalance_count",
        "portfolio_constructor_used",
    ):
        assert key in metrics
    for key in (
        "annualized_volatility",
        "sharpe_ratio",
        "sortino_ratio",
        "calmar_ratio",
        "turnover",
        "regime_segment_return",
    ):
        assert key in metrics
    assert metrics["regime_segment_return"] == "not_available_in_current_mvp"
    assert metrics["trade_count"] >= 0


def test_strategy_summary_uses_available_window_and_unspecified_baseline(seeded_db, monkeypatch):
    service = BacktestService(seeded_db)
    limited_dates = service._latest_indicator_dates(2)
    assert limited_dates
    monkeypatch.setattr(service, "_latest_indicator_dates", lambda _lookback_days: limited_dates)

    summary = service.strategy_summary(lookback_days=252)

    assert summary["lookback_days"] == 252
    assert summary["window"]["available_trading_days"] == len(limited_dates)
    assert summary["window"]["available_trading_days"] < summary["window"]["requested_trading_days"]
    assert summary["baseline"]["status"] == "unspecified"
    assert summary["strategies"]

    first = summary["strategies"][0]
    assert {"strategy_name", "screener", "backtest", "delta"}.issubset(first)
    assert first["delta"]["baseline"] == "unspecified"
    assert first["delta"]["total_return_delta"] is None
    assert first["backtest"]["summary_source"] == "computed_available_window"
    assert {"trade_count", "win_rate", "total_return", "max_drawdown"}.issubset(first["backtest"])


def test_backtest_metrics_cost_bps_uses_execution_config_override(seeded_db):
    service = _service_with_execution(seeded_db, commission_bps=3.25, slippage_bps=4.75)

    result = service.run("trend_breakout", start_date=date(2026, 5, 1))

    assert result["metrics"]["cost_bps"] == 8.0
    for trade in result["trades"]:
        assert trade["cost_bps"] == 8.0


def test_rank_portfolio_top_n_holds_multiple_symbols_at_once():
    indicators = [
        _strategy_indicator(
            symbol="AAA",
            rs_percentile=99.0,
            relative_strength_score=0.98,
            trend_score=0.92,
            sector_rs_score=0.88,
            market_score=0.80,
        ),
        _strategy_indicator(
            symbol="BBB",
            rs_percentile=97.0,
            relative_strength_score=0.95,
            trend_score=0.89,
            sector_rs_score=0.84,
            market_score=0.74,
        ),
        _strategy_indicator(
            symbol="CCC",
            rs_percentile=86.0,
            relative_strength_score=0.86,
            trend_score=0.76,
            sector_rs_score=0.62,
            market_score=0.55,
        ),
    ]
    service = _rank_portfolio_service(indicators, top_n=2, max_positions=3, weighting="equal_weight")

    result = service.run("momentum_rank", start_date=date(2026, 1, 1), end_date=date(2026, 1, 2))

    trades = result["trades"]
    metrics = result["metrics"]
    assert len(trades) == 2
    assert {trade["symbol"] for trade in trades} == {"AAA", "BBB"}
    assert {trade["entry_date"] for trade in trades} == {date(2026, 1, 2)}
    assert all(trade["portfolio_detail"]["portfolio_constructor_used"] is True for trade in trades)
    assert metrics["portfolio_constructor_used"] is True
    assert metrics["portfolio_selection_mode"] == "rank_portfolio"
    assert metrics["portfolio_top_n"] == 2
    assert metrics["portfolio_max_positions"] == 3
    assert metrics["portfolio_weighting"] == "equal_weight"
    assert metrics["rebalance_count"] == 1
    assert metrics["average_active_positions"] == pytest.approx(2.0)
    assert metrics["execution_requires_portfolio_constructor_signal_count"] == 2


def test_rank_strategy_single_position_selection_mode_keeps_legacy_fallback():
    indicators = [
        _strategy_indicator(
            symbol="AAA",
            rs_percentile=99.0,
            relative_strength_score=0.98,
            trend_score=0.92,
            sector_rs_score=0.88,
            market_score=0.80,
        ),
        _strategy_indicator(
            symbol="BBB",
            rs_percentile=97.0,
            relative_strength_score=0.95,
            trend_score=0.89,
            sector_rs_score=0.84,
            market_score=0.74,
        ),
    ]
    service = _rank_portfolio_service(indicators, selection_mode="single_position", top_n=2, max_positions=2)

    result = service.run("momentum_rank", start_date=date(2026, 1, 1), end_date=date(2026, 1, 2))

    assert len(result["trades"]) == 1
    assert result["trades"][0]["symbol"] == "AAA"
    assert result["metrics"]["portfolio_constructor_used"] is False
    assert result["metrics"]["portfolio_selection_mode"] == "single_position"
    assert result["metrics"]["rebalance_count"] == 0


@pytest.mark.parametrize(
    ("strategy_name", "indicator_overrides", "expected_basis", "expected_stop"),
    [
        ("new_high_breakout", {}, "pivot_low_20_prev", 94.0),
        ("pullback_20ema", {"pivot_low_20_prev": 96.0}, "swing_low", 96.0),
        ("darvas_box", {"pivot_high_20_prev": 95.0, "pivot_low_20_prev": 80.0}, "darvas_box_bottom", 80.0),
        ("stage_analysis_weekly", {"weekly_sma30": 90.0}, "weekly_sma30", 90.0),
    ],
)
def test_backtest_trade_payload_reflects_strategy_risk_basis(
    strategy_name,
    indicator_overrides,
    expected_basis,
    expected_stop,
):
    service = _strategy_trade_service(_strategy_indicator(**indicator_overrides))

    result = service.run(strategy_name, start_date=date(2026, 1, 1), end_date=date(2026, 1, 2))

    assert result["trades"]
    trade = result["trades"][0]
    assert trade["risk_basis"] == expected_basis
    assert trade["execution_detail"]["risk_basis"] == expected_basis
    assert trade["execution_detail"]["stop_price"] == pytest.approx(expected_stop)


def test_regime_cache_loads_index_once_and_matches_legacy_asof(seeded_db, monkeypatch):
    service = BacktestService(seeded_db)
    index_df = service.repo.index_df()
    signal_dates = sorted({row.trade_date for row in service._load_indicators(None, None)})
    sampled_dates = sorted({signal_dates[0], signal_dates[min(199, len(signal_dates) - 1)], signal_dates[-1]})
    legacy_by_date = {
        signal_date: _legacy_market_regime_from_index(index_df, signal_date) for signal_date in sampled_dates
    }
    index_df_call_count = 0
    original_index_df = service.repo.index_df

    def counted_index_df(*args, **kwargs):
        nonlocal index_df_call_count
        index_df_call_count += 1
        return original_index_df(*args, **kwargs)

    monkeypatch.setattr(service.repo, "index_df", counted_index_df)
    cached_by_date = service._build_market_regime_cache(signal_dates)

    assert index_df_call_count == 1
    for signal_date in sampled_dates:
        assert cached_by_date[signal_date] == legacy_by_date[signal_date]


def test_next_open_entry_and_same_bar_stop_target_prefers_stop():
    service = _simulation_service(same_bar_stop_first=True)
    risk = SimpleNamespace(stop_price=95.0, position_size=10)
    price_by_symbol = _price_df(
        [
            {
                "trade_date": date(2026, 1, 2),
                "open": 100.0,
                "high": 200.0,
                "low": 90.0,
                "close": 120.0,
            }
        ]
    )

    trade = service._simulate_trade("TEST", date(2026, 1, 1), risk, price_by_symbol)

    assert trade is not None
    assert trade["raw_entry_price"] == 100.0
    assert trade["entry_price"] > trade["raw_entry_price"]
    assert trade["exit_reason"] == "stop"
    assert trade["pnl"] < 0
    assert trade["estimated_cost"] > 0
    assert trade["cost_bps"] > 0
    assert trade["execution_detail"]["entry_assumption"] == "next_open"
    assert trade["execution_detail"]["exit_assumption"] == "same_bar_stop_first_stop_exit"
    assert trade["execution_detail"]["same_bar_stop_first"] is True
    assert trade["execution_detail"]["same_bar_both_touched"] is True


def test_entry_gap_down_below_stop_exits_at_next_open():
    service = _simulation_service(same_bar_stop_first=False)
    risk = SimpleNamespace(stop_price=95.0, position_size=10)
    price_by_symbol = _price_df(
        [
            {
                "trade_date": date(2026, 1, 2),
                "open": 90.0,
                "high": 120.0,
                "low": 89.0,
                "close": 94.0,
            }
        ]
    )

    trade = service._simulate_trade("TEST", date(2026, 1, 1), risk, price_by_symbol)

    assert trade is not None
    assert trade["exit_reason"] == "stop"
    assert trade["raw_exit_price"] == 90.0
    assert trade["holding_days"] == 1
    assert trade["execution_detail"]["exit_assumption"] == "entry_gap_below_stop_open_exit"
    assert trade["execution_detail"]["gap_stop"] is True


def test_holding_day_gap_down_stop_exits_at_open():
    service = _simulation_service()
    risk = SimpleNamespace(stop_price=95.0, position_size=10)
    price_by_symbol = _price_df(
        [
            {
                "trade_date": date(2026, 1, 2),
                "open": 100.0,
                "high": 105.0,
                "low": 98.0,
                "close": 101.0,
            },
            {
                "trade_date": date(2026, 1, 3),
                "open": 90.0,
                "high": 100.0,
                "low": 89.0,
                "close": 92.0,
            },
        ]
    )

    trade = service._simulate_trade("TEST", date(2026, 1, 1), risk, price_by_symbol)

    assert trade is not None
    assert trade["exit_reason"] == "stop"
    assert trade["raw_exit_price"] == 90.0
    assert trade["holding_days"] == 2
    assert trade["execution_detail"]["exit_assumption"] == "gap_down_stop_open_exit"
    assert trade["execution_detail"]["gap_stop"] is True


def test_gap_up_above_target_exits_at_open_without_intraday_high_capture():
    service = _simulation_service()
    risk = SimpleNamespace(stop_price=95.0, position_size=10)
    price_by_symbol = _price_df(
        [
            {
                "trade_date": date(2026, 1, 2),
                "open": 100.0,
                "high": 105.0,
                "low": 98.0,
                "close": 101.0,
            },
            {
                "trade_date": date(2026, 1, 3),
                "open": 120.0,
                "high": 130.0,
                "low": 118.0,
                "close": 125.0,
            },
        ]
    )

    trade = service._simulate_trade("TEST", date(2026, 1, 1), risk, price_by_symbol)

    assert trade is not None
    assert trade["exit_reason"] == "target"
    assert trade["raw_exit_price"] == 120.0
    assert trade["raw_exit_price"] < 130.0
    assert trade["execution_detail"]["exit_assumption"] == "gap_up_target_open_exit"
    assert trade["execution_detail"]["gap_target"] is True


def test_same_bar_stop_target_prefers_target_when_configured():
    service = _simulation_service(same_bar_stop_first=False)
    risk = SimpleNamespace(stop_price=95.0, position_size=10)
    price_by_symbol = _price_df(
        [
            {
                "trade_date": date(2026, 1, 2),
                "open": 100.0,
                "high": 200.0,
                "low": 90.0,
                "close": 120.0,
            }
        ]
    )

    trade = service._simulate_trade("TEST", date(2026, 1, 1), risk, price_by_symbol)

    assert trade is not None
    assert trade["exit_reason"] == "target"
    assert trade["raw_exit_price"] == trade["execution_detail"]["target_price"]
    assert trade["execution_detail"]["exit_assumption"] == "same_bar_target_first_target_exit"
    assert trade["execution_detail"]["same_bar_stop_first"] is False
    assert trade["execution_detail"]["same_bar_both_touched"] is True


def test_max_holding_exit_still_uses_close():
    service = _simulation_service(max_holding_days=2)
    risk = SimpleNamespace(stop_price=95.0, position_size=10)
    price_by_symbol = _price_df(
        [
            {
                "trade_date": date(2026, 1, 2),
                "open": 100.0,
                "high": 105.0,
                "low": 98.0,
                "close": 101.0,
            },
            {
                "trade_date": date(2026, 1, 3),
                "open": 102.0,
                "high": 108.0,
                "low": 99.0,
                "close": 104.0,
            },
        ]
    )

    trade = service._simulate_trade("TEST", date(2026, 1, 1), risk, price_by_symbol)

    assert trade is not None
    assert trade["exit_reason"] == "max_holding"
    assert trade["raw_exit_price"] == 104.0
    assert trade["holding_days"] == 2
    assert trade["execution_detail"]["exit_assumption"] == "max_holding_close_exit"


def test_adjusted_price_option_uses_adj_close_factor_without_changing_default():
    raw_service = _simulation_service(max_holding_days=1, use_adjusted_price=False)
    adjusted_service = _simulation_service(max_holding_days=1, use_adjusted_price=True)
    risk = SimpleNamespace(stop_price=90.0, position_size=10)
    price_by_symbol = _price_df(
        [
            {
                "trade_date": date(2026, 1, 2),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 102.0,
                "adj_close": 51.0,
            }
        ]
    )

    raw_trade = raw_service._simulate_trade("TEST", date(2026, 1, 1), risk, price_by_symbol)
    adjusted_trade = adjusted_service._simulate_trade("TEST", date(2026, 1, 1), risk, price_by_symbol)

    assert raw_trade is not None
    assert adjusted_trade is not None
    assert raw_trade["raw_entry_price"] == 100.0
    assert raw_trade["raw_exit_price"] == 102.0
    assert raw_trade["price_detail"]["use_adjusted_price"] is False
    assert adjusted_trade["raw_entry_price"] == 50.0
    assert adjusted_trade["raw_exit_price"] == 51.0
    assert adjusted_trade["price_detail"]["use_adjusted_price"] is True
    assert adjusted_trade["price_detail"]["entry_adjustment_factor"] == 0.5
    assert adjusted_trade["execution_detail"]["stop_price"] == 45.0


def test_delisted_policy_forces_last_available_close_exit():
    service = _simulation_service(max_holding_days=5, delisted_handling_policy="last_available_close")
    risk = SimpleNamespace(stop_price=50.0, position_size=10)
    realism_stats = {"adjusted_price_trade_count": 0, "forced_exit_count": 0, "delisted_exit_count": 0, "missing_data_exit_count": 0}
    price_by_symbol = _price_df(
        [
            {
                "trade_date": date(2026, 1, 2),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
            },
            {
                "trade_date": date(2026, 1, 3),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 80.0,
                "delist_date": "2026-01-03",
            },
        ]
    )

    trade = service._simulate_trade("TEST", date(2026, 1, 1), risk, price_by_symbol, realism_stats=realism_stats)

    assert trade is not None
    assert trade["exit_reason"] == "delisted"
    assert trade["raw_exit_price"] == 80.0
    assert trade["holding_days"] == 2
    assert trade["execution_detail"]["forced_exit"] is True
    assert trade["execution_detail"]["delisted_exit"] is True
    assert trade["execution_detail"]["exit_assumption"] == "delisted_last_available_close_exit"
    assert realism_stats["forced_exit_count"] == 1
    assert realism_stats["delisted_exit_count"] == 1


def test_missing_data_policy_can_force_last_available_close_exit():
    service = _simulation_service(max_holding_days=5, missing_data_policy="last_available_close")
    risk = SimpleNamespace(stop_price=50.0, position_size=10)
    realism_stats = {"adjusted_price_trade_count": 0, "forced_exit_count": 0, "delisted_exit_count": 0, "missing_data_exit_count": 0}
    price_by_symbol = _price_df(
        [
            {
                "trade_date": date(2026, 1, 2),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
            },
            {
                "trade_date": date(2026, 1, 3),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 98.0,
            },
        ]
    )

    trade = service._simulate_trade("TEST", date(2026, 1, 1), risk, price_by_symbol, realism_stats=realism_stats)

    assert trade is not None
    assert trade["exit_reason"] == "missing_data"
    assert trade["raw_exit_price"] == 98.0
    assert trade["execution_detail"]["forced_exit"] is True
    assert trade["execution_detail"]["missing_data_exit"] is True
    assert realism_stats["forced_exit_count"] == 1
    assert realism_stats["missing_data_exit_count"] == 1


def test_backtest_metrics_include_fee_and_slippage_costs():
    metrics = BacktestService._metrics(
        trades=[
            {"pnl": 1000.0, "holding_days": 2, "estimated_cost": 30.0},
            {"pnl": -500.0, "holding_days": 1, "estimated_cost": 20.0},
        ],
        equity_curve=[
            {"date": date(2026, 1, 1), "equity": 100000.0},
            {"date": date(2026, 1, 2), "equity": 101000.0},
            {"date": date(2026, 1, 3), "equity": 100500.0},
        ],
        final_equity=100500.0,
        initial_equity=100000.0,
        exposure_days=3,
        total_days=10,
        execution_cost_bps=7.0,
    )

    assert metrics["trade_count"] == 2
    assert metrics["total_estimated_cost"] == 50.0
    assert metrics["cost_bps"] == 7.0
    assert metrics["win_rate"] == 0.5
    assert metrics["profit_factor"] == 2.0
    assert metrics["max_drawdown"] < 0
    assert "annualized_volatility" in metrics
    assert "sharpe_ratio" in metrics
    assert "sortino_ratio" in metrics
    assert "calmar_ratio" in metrics
    assert "turnover" in metrics
    assert metrics["regime_segment_return"] == "not_available_in_current_mvp"


def test_liquidity_keeps_full_quantity_when_turnover_is_sufficient():
    service = _simulation_service(max_holding_days=1, max_participation_rate=0.05, min_fill_ratio=0.25)
    risk = SimpleNamespace(stop_price=90.0, position_size=10)
    price_by_symbol = _price_df(
        [
            {
                "trade_date": date(2026, 1, 2),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 102.0,
                "turnover_value": 1000000.0,
            }
        ]
    )

    trade = service._simulate_trade("TEST", date(2026, 1, 1), risk, price_by_symbol)

    assert trade is not None
    assert trade["qty"] == 10
    assert trade["liquidity_detail"]["planned_qty"] == 10
    assert trade["liquidity_detail"]["filled_qty"] == 10
    assert trade["liquidity_detail"]["unfilled_qty"] == 0
    assert trade["liquidity_detail"]["liquidity_basis"] == "turnover_value"
    assert trade["liquidity_detail"]["position_size_cap_applied"] is False


def test_turnover_cap_creates_partial_fill_and_uses_filled_qty_for_costs():
    service = _simulation_service(
        max_holding_days=1, max_participation_rate=0.05, min_fill_ratio=0.25, allow_partial_fill=True
    )
    risk = SimpleNamespace(stop_price=90.0, position_size=1000)
    stats = {"partial_fill_count": 0, "no_fill_count": 0, "total_unfilled_qty": 0}
    price_by_symbol = _price_df(
        [
            {
                "trade_date": date(2026, 1, 2),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 102.0,
                "turnover_value": 1000000.0,
            }
        ]
    )

    trade = service._simulate_trade("TEST", date(2026, 1, 1), risk, price_by_symbol, stats)

    assert trade is not None
    assert trade["qty"] == 500
    assert trade["liquidity_detail"]["planned_qty"] == 1000
    assert trade["liquidity_detail"]["filled_qty"] == 500
    assert trade["liquidity_detail"]["unfilled_qty"] == 500
    assert trade["liquidity_detail"]["requested_notional"] == 100000.0
    assert trade["liquidity_detail"]["cap_notional"] == 50000.0
    assert trade["liquidity_detail"]["fill_ratio"] == 0.5
    assert trade["liquidity_detail"]["position_size_cap_applied"] is True
    assert trade["estimated_cost"] == pytest.approx(70.7)
    assert trade["pnl"] == pytest.approx(929.3)
    assert stats == {"partial_fill_count": 1, "no_fill_count": 0, "total_unfilled_qty": 500}


def test_fill_ratio_below_min_fill_skips_trade_and_counts_no_fill():
    service = _simulation_service(
        max_holding_days=1, max_participation_rate=0.05, min_fill_ratio=0.25, allow_partial_fill=True
    )
    risk = SimpleNamespace(stop_price=90.0, position_size=1000)
    stats = {"partial_fill_count": 0, "no_fill_count": 0, "total_unfilled_qty": 0}
    price_by_symbol = _price_df(
        [
            {
                "trade_date": date(2026, 1, 2),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 102.0,
                "turnover_value": 100000.0,
            }
        ]
    )

    trade = service._simulate_trade("TEST", date(2026, 1, 1), risk, price_by_symbol, stats)

    assert trade is None
    assert stats == {"partial_fill_count": 0, "no_fill_count": 1, "total_unfilled_qty": 1000}


def test_disallow_partial_fill_skips_when_liquidity_cap_is_below_request():
    service = _simulation_service(
        max_holding_days=1, max_participation_rate=0.05, min_fill_ratio=0.25, allow_partial_fill=False
    )
    risk = SimpleNamespace(stop_price=90.0, position_size=1000)
    stats = {"partial_fill_count": 0, "no_fill_count": 0, "total_unfilled_qty": 0}
    price_by_symbol = _price_df(
        [
            {
                "trade_date": date(2026, 1, 2),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 102.0,
                "turnover_value": 1000000.0,
            }
        ]
    )

    trade = service._simulate_trade("TEST", date(2026, 1, 1), risk, price_by_symbol, stats)

    assert trade is None
    assert stats == {"partial_fill_count": 0, "no_fill_count": 1, "total_unfilled_qty": 1000}


def test_zero_turnover_falls_back_to_volume_times_entry_price():
    service = _simulation_service(max_holding_days=1, max_participation_rate=0.05, min_fill_ratio=0.25)
    risk = SimpleNamespace(stop_price=90.0, position_size=10)
    price_by_symbol = _price_df(
        [
            {
                "trade_date": date(2026, 1, 2),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 102.0,
                "volume": 10000,
                "turnover_value": 0.0,
            }
        ]
    )

    trade = service._simulate_trade("TEST", date(2026, 1, 1), risk, price_by_symbol)

    assert trade is not None
    assert trade["qty"] == 10
    assert trade["liquidity_detail"]["liquidity_basis"] == "volume_x_entry_price"
    assert trade["liquidity_detail"]["liquidity_notional"] == 1000000.0


def test_zero_turnover_and_zero_volume_skips_trade():
    service = _simulation_service(max_holding_days=1, max_participation_rate=0.05, min_fill_ratio=0.25)
    risk = SimpleNamespace(stop_price=90.0, position_size=10)
    stats = {"partial_fill_count": 0, "no_fill_count": 0, "total_unfilled_qty": 0}
    price_by_symbol = _price_df(
        [
            {
                "trade_date": date(2026, 1, 2),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 102.0,
                "volume": 0,
                "turnover_value": 0.0,
            }
        ]
    )

    trade = service._simulate_trade("TEST", date(2026, 1, 1), risk, price_by_symbol, stats)

    assert trade is None
    assert stats == {"partial_fill_count": 0, "no_fill_count": 1, "total_unfilled_qty": 10}


def test_backtest_metrics_include_optional_liquidity_counts():
    metrics = BacktestService._metrics(
        trades=[],
        equity_curve=[{"date": date(2026, 1, 1), "equity": 100000.0}],
        final_equity=100000.0,
        initial_equity=100000.0,
        exposure_days=0,
        total_days=10,
        liquidity_stats={"partial_fill_count": 2, "no_fill_count": 3, "total_unfilled_qty": 40},
        realism_stats={
            "adjusted_price_trade_count": 1,
            "forced_exit_count": 2,
            "delisted_exit_count": 1,
            "missing_data_exit_count": 1,
        },
    )

    assert metrics["partial_fill_count"] == 2
    assert metrics["no_fill_count"] == 3
    assert metrics["total_unfilled_qty"] == 40
    assert metrics["adjusted_price_trade_count"] == 1
    assert metrics["forced_exit_count"] == 2
    assert metrics["delisted_exit_count"] == 1
    assert metrics["missing_data_exit_count"] == 1
