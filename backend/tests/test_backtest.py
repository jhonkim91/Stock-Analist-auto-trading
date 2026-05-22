from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from backend.app.services.backtest_service import BacktestService


def _service_with_execution(seeded_db, **execution_overrides) -> BacktestService:
    service = BacktestService(seeded_db)
    service.backtest_config = {
        **service.backtest_config,
        "execution": {**service.backtest_config["execution"], **execution_overrides},
    }
    return service


def _price_df(rows: list[dict[str, object]]) -> dict[str, pd.DataFrame]:
    enriched_rows = []
    for row in rows:
        enriched_rows.append({"volume": 1000000, "turnover_value": 1000000000.0, **row})
    return {"TEST": pd.DataFrame(enriched_rows)}


def test_backtest_runs_and_reports_required_metrics(seeded_db):
    result = BacktestService(seeded_db).run("trend_breakout")
    metrics = result["metrics"]

    for key in (
        "trade_count",
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
    ):
        assert key in metrics
    assert metrics["trade_count"] >= 0


def test_next_open_entry_and_same_bar_stop_target_prefers_stop(seeded_db):
    service = _service_with_execution(seeded_db, same_bar_stop_first=True)
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


def test_entry_gap_down_below_stop_exits_at_next_open(seeded_db):
    service = _service_with_execution(seeded_db, same_bar_stop_first=False)
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


def test_holding_day_gap_down_stop_exits_at_open(seeded_db):
    service = _service_with_execution(seeded_db)
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


def test_gap_up_above_target_exits_at_open_without_intraday_high_capture(seeded_db):
    service = _service_with_execution(seeded_db)
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


def test_same_bar_stop_target_prefers_target_when_configured(seeded_db):
    service = _service_with_execution(seeded_db, same_bar_stop_first=False)
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


def test_max_holding_exit_still_uses_close(seeded_db):
    service = _service_with_execution(seeded_db, max_holding_days=2)
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


def test_backtest_metrics_include_fee_and_slippage_costs(seeded_db):
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
    )

    assert metrics["trade_count"] == 2
    assert metrics["total_estimated_cost"] == 50.0
    assert metrics["win_rate"] == 0.5
    assert metrics["profit_factor"] == 2.0
    assert metrics["max_drawdown"] < 0


def test_liquidity_keeps_full_quantity_when_turnover_is_sufficient(seeded_db):
    service = _service_with_execution(seeded_db, max_holding_days=1, max_participation_rate=0.05, min_fill_ratio=0.25)
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


def test_turnover_cap_creates_partial_fill_and_uses_filled_qty_for_costs(seeded_db):
    service = _service_with_execution(
        seeded_db, max_holding_days=1, max_participation_rate=0.05, min_fill_ratio=0.25, allow_partial_fill=True
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


def test_fill_ratio_below_min_fill_skips_trade_and_counts_no_fill(seeded_db):
    service = _service_with_execution(
        seeded_db, max_holding_days=1, max_participation_rate=0.05, min_fill_ratio=0.25, allow_partial_fill=True
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


def test_disallow_partial_fill_skips_when_liquidity_cap_is_below_request(seeded_db):
    service = _service_with_execution(
        seeded_db, max_holding_days=1, max_participation_rate=0.05, min_fill_ratio=0.25, allow_partial_fill=False
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


def test_zero_turnover_falls_back_to_volume_times_entry_price(seeded_db):
    service = _service_with_execution(seeded_db, max_holding_days=1, max_participation_rate=0.05, min_fill_ratio=0.25)
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


def test_zero_turnover_and_zero_volume_skips_trade(seeded_db):
    service = _service_with_execution(seeded_db, max_holding_days=1, max_participation_rate=0.05, min_fill_ratio=0.25)
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


def test_backtest_metrics_include_optional_liquidity_counts(seeded_db):
    metrics = BacktestService._metrics(
        trades=[],
        equity_curve=[{"date": date(2026, 1, 1), "equity": 100000.0}],
        final_equity=100000.0,
        initial_equity=100000.0,
        exposure_days=0,
        total_days=10,
        liquidity_stats={"partial_fill_count": 2, "no_fill_count": 3, "total_unfilled_qty": 40},
    )

    assert metrics["partial_fill_count"] == 2
    assert metrics["no_fill_count"] == 3
    assert metrics["total_unfilled_qty"] == 40
