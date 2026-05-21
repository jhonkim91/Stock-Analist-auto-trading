from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd

from backend.app.services.backtest_service import BacktestService


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
    service = BacktestService(seeded_db)
    risk = SimpleNamespace(stop_price=95.0, position_size=10)
    price_by_symbol = {
        "TEST": pd.DataFrame(
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
    }

    trade = service._simulate_trade("TEST", date(2026, 1, 1), risk, price_by_symbol)

    assert trade is not None
    assert trade["raw_entry_price"] == 100.0
    assert trade["entry_price"] > trade["raw_entry_price"]
    assert trade["exit_reason"] == "stop"
    assert trade["pnl"] < 0
    assert trade["estimated_cost"] > 0
    assert trade["cost_bps"] > 0


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
