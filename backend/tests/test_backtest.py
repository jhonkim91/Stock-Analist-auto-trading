from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from backend.app.core.config import get_config
from backend.app.services.backtest_service import BacktestService


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


def test_backtest_metrics_cost_bps_uses_execution_config_override(seeded_db):
    service = _service_with_execution(seeded_db, commission_bps=3.25, slippage_bps=4.75)

    result = service.run("trend_breakout", start_date=date(2026, 5, 1))

    assert result["metrics"]["cost_bps"] == 8.0
    for trade in result["trades"]:
        assert trade["cost_bps"] == 8.0


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
