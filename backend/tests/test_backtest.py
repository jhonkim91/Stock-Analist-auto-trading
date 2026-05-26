from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import select

from backend.app.core.config import get_config
from backend.app.models.tables import (
    BacktestRun,
    BacktestTradeLedger,
    CorporateAction,
    ScreenResult,
    StrategyParameterSnapshot,
    SymbolMaster,
)
from backend.app.repositories.market_repository import MarketRepository
from backend.app.services.backtest_service import BacktestService
from backend.app.services.report_service import ReportService
from backend.app.services.risk_service import RiskService
from backend.app.services.scoring_service import ScoringService
from backend.app.services.screener_service import ScreenerService
from backend.app.services.validation_service import (
    FactorFilterAttributionService,
    NOT_AVAILABLE,
    StrategyParameterSnapshotService,
    StrategyValidationService,
    ValidationScaffold,
)
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
    service.backtest_repo = SimpleNamespace(save=lambda _run, _trades=None: None)
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
    service.backtest_repo = SimpleNamespace(save=lambda _run, _trades=None: None)
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

    assert {"run_id", "strategy_name", "metrics", "trades", "trade_ledger"}.issubset(result)
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
        "walk_forward",
        "pbo",
        "probability_of_backtest_overfitting",
        "deflated_sharpe_ratio",
        "factor_filter_attribution",
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
    assert metrics["walk_forward"] == NOT_AVAILABLE
    assert metrics["pbo"] == NOT_AVAILABLE
    assert metrics["deflated_sharpe_ratio"] == NOT_AVAILABLE
    assert metrics["factor_filter_attribution"] == NOT_AVAILABLE
    assert metrics["trade_count"] >= 0
    assert result["trade_ledger"]["persisted"] is True
    assert result["trade_ledger"]["table"] == "backtest_trade_ledger"
    assert result["trade_ledger"]["rows"] == metrics["trade_count"]
    assert result["validation_framework"]["walk_forward"]["status"] == NOT_AVAILABLE
    assert result["validation_framework"]["overfitting"]["pbo"]["value"] == NOT_AVAILABLE
    assert result["validation_framework"]["trade_ledger_schema"]["scope"] == "backtest_and_report_analysis_only"


def test_backtest_persists_trade_ledger_contract(seeded_db):
    result = BacktestService(seeded_db).run("trend_breakout", start_date=date(2026, 5, 1))
    run_id = result["run_id"]
    rows = list(
        seeded_db.scalars(
            select(BacktestTradeLedger)
            .where(BacktestTradeLedger.run_id == run_id)
            .order_by(BacktestTradeLedger.trade_index)
        ).all()
    )

    assert len(rows) == result["metrics"]["trade_count"]
    assert [row.trade_index for row in rows] == list(range(1, len(rows) + 1))
    if rows:
        first = rows[0]
        assert first.strategy_name == "trend_breakout"
        assert first.status == "closed"
        assert first.qty > 0
        assert first.entry_date >= first.signal_date
        assert first.exit_date >= first.entry_date
        assert first.execution_detail_json.startswith("{")
        assert first.liquidity_detail_json.startswith("{")

    detail = BacktestService(seeded_db).get_run(run_id)
    assert detail["trade_ledger_count"] == len(rows)
    assert detail["trade_ledger"]["rows"] == len(rows)
    assert len(detail["trades"]) == len(rows)


def test_factor_filter_attribution_joins_ledger_and_screen_results(seeded_db):
    signal_date = date(2026, 5, 20)
    seeded_db.add_all(
        [
            ScreenResult(
                trade_date=signal_date,
                symbol="KR009",
                strategy_tag="trend_breakout",
                passed=True,
                pass_flags=json.dumps({"breakout": True, "rr_ok": True}, ensure_ascii=False),
                failed_conditions=json.dumps([], ensure_ascii=False),
                reason_summary="fixture pass",
                metadata_json=json.dumps(
                    {
                        "market_regime": "bull",
                        "risk_flags": {"entry_chase_warning": True},
                    },
                    ensure_ascii=False,
                ),
                risk_flags_json=json.dumps({"entry_chase_warning": True}, ensure_ascii=False),
                total_score=0.9,
                entry_price=100.0,
                stop_price=90.0,
                target_price=120.0,
                risk_per_share=10.0,
                reward_risk_ratio=2.0,
                position_size=10,
                position_notional=1000.0,
            ),
            ScreenResult(
                trade_date=signal_date,
                symbol="KR010",
                strategy_tag="trend_breakout",
                passed=False,
                pass_flags=json.dumps({"breakout": False, "rr_ok": False}, ensure_ascii=False),
                failed_conditions=json.dumps(["breakout", "rr_ok"], ensure_ascii=False),
                reason_summary="fixture fail",
                metadata_json=json.dumps({"market_regime": "bull"}, ensure_ascii=False),
                risk_flags_json=json.dumps({}, ensure_ascii=False),
                total_score=0.2,
            ),
            BacktestTradeLedger(
                run_id="bt-attribution-fixture",
                trade_index=1,
                strategy_name="trend_breakout",
                symbol="KR009",
                side="long",
                status="closed",
                signal_date=signal_date,
                entry_date=signal_date,
                exit_date=signal_date,
                qty=10,
                raw_entry_price=100.0,
                entry_price=100.0,
                raw_exit_price=110.0,
                exit_price=110.0,
                pnl=100.0,
                return_pct=0.10,
                estimated_cost=0.0,
                cost_bps=0.0,
                holding_days=1,
                exit_reason="target",
                risk_basis="fixture",
            ),
            BacktestTradeLedger(
                run_id="bt-attribution-fixture",
                trade_index=2,
                strategy_name="trend_breakout",
                symbol="KR012",
                side="long",
                status="closed",
                signal_date=signal_date,
                entry_date=signal_date,
                exit_date=signal_date,
                qty=10,
                raw_entry_price=100.0,
                entry_price=100.0,
                raw_exit_price=97.5,
                exit_price=97.5,
                pnl=-25.0,
                return_pct=-0.025,
                estimated_cost=0.0,
                cost_bps=0.0,
                holding_days=1,
                exit_reason="stop",
                risk_basis="fixture",
            ),
        ]
    )
    seeded_db.commit()

    payload = FactorFilterAttributionService(seeded_db).calculate(
        start_date=signal_date,
        end_date=signal_date,
        strategy_names=["trend_breakout"],
    )

    assert payload["status"] == "partial"
    assert payload["trade_count"] == 2
    assert payload["joined_trade_count"] == 1
    assert payload["unjoined_trade_count"] == 1
    assert payload["basis"]["not_connected_to"] == ["orders", "paper_orders", "broker_adapters", "live_trading"]

    pnl_rows = payload["realized_pnl_attribution"]["rows"]
    assert any(
        row["dimension"] == "strategy_name" and row["value"] == "trend_breakout" and row["pnl"] == 75.0
        for row in pnl_rows
    )
    assert any(row["dimension"] == "sector" and row["value"] == "Technology" for row in pnl_rows)
    assert any(row["dimension"] == "market_regime" and row["value"] == "bull" and row["pnl"] == 100.0 for row in pnl_rows)
    assert any(
        row["dimension"] == "market_regime"
        and row["value"] == NOT_AVAILABLE
        and row["unavailable_count"] == 1
        for row in pnl_rows
    )
    assert any(row["dimension"] == "pass_flag" and row["value"] == "breakout=true" for row in pnl_rows)
    assert any(row["dimension"] == "risk_flag" and row["value"] == "entry_chase_warning=true" for row in pnl_rows)

    failure_rows = payload["screen_filter_failure_counts"]["rows"]
    assert any(row["filter"] == "breakout" and row["failed_count"] == 1 for row in failure_rows)
    assert any(row["filter"] == "rr_ok" and row["failed_count"] == 1 for row in failure_rows)
    assert payload["strategies"]["trend_breakout"]["screen_filter_failure_counts"]["calculated"] is True


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
    assert summary["validation_framework"]["walk_forward"]["metric"] == NOT_AVAILABLE
    assert summary["validation_framework"]["walk_forward"]["calculated"] is False
    assert summary["validation_framework"]["walk_forward"]["reason"] == "insufficient_indicator_trading_days"
    assert summary["validation_framework"]["overfitting"]["pbo"]["value"] == NOT_AVAILABLE
    assert summary["validation_framework"]["overfitting"]["deflated_sharpe_ratio"]["value"] == NOT_AVAILABLE
    assert summary["validation_framework"]["attribution"]["value"] == NOT_AVAILABLE
    assert "orders" in summary["validation_framework"]["trade_ledger_schema"]["not_connected_to"]
    assert summary["strategies"]

    first = summary["strategies"][0]
    assert {"strategy_name", "screener", "backtest", "delta", "validation"}.issubset(first)
    assert first["delta"]["baseline"] == "unspecified"
    assert first["delta"]["total_return_delta"] is None
    assert first["backtest"]["summary_source"] == "computed_available_window"
    assert {"trade_count", "win_rate", "total_return", "max_drawdown"}.issubset(first["backtest"])
    assert first["backtest"]["pbo"] == NOT_AVAILABLE
    assert first["backtest"]["deflated_sharpe_ratio"] == NOT_AVAILABLE
    assert first["validation"]["walk_forward"]["status"] == NOT_AVAILABLE
    assert first["validation"]["walk_forward"]["calculated"] is False
    assert first["validation"]["walk_forward"]["reason"] == "insufficient_indicator_trading_days"
    assert first["validation"]["attribution"]["value"] == NOT_AVAILABLE


def test_walk_forward_runner_calculates_oos_summary_and_fail_closed_insufficient_data(seeded_db):
    service = BacktestService(seeded_db)
    dates = service._latest_indicator_dates(90)
    assert len(dates) == 90

    result = service.walk_forward(
        "trend_breakout",
        trading_dates=dates,
        train_window_trading_days=30,
        test_window_trading_days=10,
        step_trading_days=20,
        rebalance_frequency="weekly",
    )

    assert result["status"] == "calculated"
    assert result["metric"] == "out_of_sample_summary"
    assert result["calculated"] is True
    assert result["rebalance_frequency"] == "weekly"
    assert result["window_count"] >= 2
    assert result["calculated_window_count"] == result["window_count"]
    assert result["summary"]["oos_window_count"] == result["calculated_window_count"]
    assert result["summary"]["oos_trade_count"] >= 0
    assert result["summary"]["oos_total_return"] is not None
    assert result["windows"][0]["train_trading_days"] == 30
    assert result["windows"][0]["test_trading_days"] == 10
    assert result["windows"][0]["calculated"] is True
    assert {"trade_count", "win_rate", "total_return", "max_drawdown"}.issubset(
        result["windows"][0]["metrics"]
    )

    insufficient = service.walk_forward(
        "trend_breakout",
        trading_dates=dates[:20],
        train_window_trading_days=15,
        test_window_trading_days=10,
        step_trading_days=5,
    )

    assert insufficient["calculated"] is False
    assert insufficient["status"] == NOT_AVAILABLE
    assert insufficient["reason"] == "insufficient_indicator_trading_days"
    assert insufficient["summary"] is None
    assert insufficient["windows"] == []


def test_strategy_summary_calculates_pbo_and_dsr_when_walk_forward_sample_is_sufficient(seeded_db, monkeypatch):
    service = StrategyValidationService(seeded_db)
    strategy_names = list(service.strategies)[:3]
    assert len(strategy_names) == 3
    service.strategies = strategy_names
    dates = BacktestService(seeded_db)._latest_indicator_dates(60)
    return_series = {
        strategy_names[0]: [0.010, 0.020, 0.015, 0.025, 0.005],
        strategy_names[1]: [0.005, 0.015, -0.005, 0.010, 0.020],
        strategy_names[2]: [-0.010, 0.005, 0.000, 0.015, 0.010],
    }
    current_metrics = {
        "summary_source": "computed_available_window",
        "error": None,
        "trade_count": 5,
        "win_rate": 0.6,
        "total_return": 0.05,
        "max_drawdown": -0.03,
        **ValidationScaffold.metric_placeholders(),
    }

    def fake_walk_forward(
        strategy_name,
        trading_dates,
        train_window_trading_days=10,
        test_window_trading_days=5,
        step_trading_days=5,
        rebalance_frequency=None,
    ):
        windows = [
            {
                "window_index": index,
                "train_trading_days": train_window_trading_days,
                "test_trading_days": test_window_trading_days,
                "calculated": True,
                "reason": None,
                "metrics": {
                    "trade_count": index,
                    "win_rate": 0.5,
                    "total_return": value,
                    "max_drawdown": -abs(value) / 2,
                    "sharpe_ratio": value,
                    "sortino_ratio": value,
                    "calmar_ratio": value,
                    "turnover": 0.1,
                    "average_active_positions": 1,
                    "rebalance_count": 1,
                },
            }
            for index, value in enumerate(return_series[strategy_name], start=1)
        ]
        return {
            "strategy_name": strategy_name,
            "status": "calculated",
            "metric": "out_of_sample_summary",
            "calculated": True,
            "reason": None,
            "train_window_trading_days": train_window_trading_days,
            "test_window_trading_days": test_window_trading_days,
            "step_trading_days": step_trading_days,
            "rebalance_frequency": rebalance_frequency or "daily",
            "window_count": len(windows),
            "calculated_window_count": len(windows),
            "unavailable_window_count": 0,
            "summary": {
                "oos_window_count": len(windows),
                "oos_trade_count": sum(index for index in range(1, len(windows) + 1)),
                "oos_total_return": 0.05,
            },
            "windows": windows,
        }

    monkeypatch.setattr(service, "_latest_indicator_dates", lambda _lookback_days: dates)
    monkeypatch.setattr(service, "_strategy_backtest_summary", lambda **_kwargs: dict(current_metrics))
    monkeypatch.setattr(service.walk_forward_runner, "run", fake_walk_forward)

    summary = service.strategy_summary(
        lookback_days=60,
        walk_forward_train_days=10,
        walk_forward_test_days=5,
        walk_forward_step_days=5,
    )
    overfitting = summary["validation_framework"]["overfitting"]

    assert overfitting["pbo"]["calculated"] is True
    assert 0 <= overfitting["pbo"]["value"] <= 1
    assert overfitting["pbo"]["input_shape"]["candidate_count"] == 3
    assert overfitting["pbo"]["input_shape"]["split_count"] == 5
    assert overfitting["deflated_sharpe_ratio"]["calculated"] is True
    assert 0 <= overfitting["deflated_sharpe_ratio"]["value"] <= 1
    assert overfitting["deflated_sharpe_ratio"]["input_shape"]["multiple_testing"]["candidate_count"] == 3
    assert (
        overfitting["deflated_sharpe_ratio"]["input_shape"]["non_normal_adjustment"]["sample_count"]
        == 5
    )

    first = summary["strategies"][0]["validation"]["overfitting"]
    assert first["pbo"]["calculated"] is True
    assert first["pbo"]["strategy_name"] == strategy_names[0]
    assert first["deflated_sharpe_ratio"]["calculated"] is True
    assert first["deflated_sharpe_ratio"]["strategy_name"] == strategy_names[0]


def test_strategy_validation_summary_supports_baseline_run_id_and_snapshot(seeded_db, monkeypatch):
    service = StrategyValidationService(seeded_db)
    limited_dates = [date(2026, 5, 19), date(2026, 5, 20)]
    current_metrics = {
        "summary_source": "computed_available_window",
        "error": None,
        "trade_count": 10,
        "win_rate": 0.5,
        "total_return": 0.12,
        "max_drawdown": -0.08,
        **ValidationScaffold.metric_placeholders(),
    }
    monkeypatch.setattr(service, "_latest_indicator_dates", lambda _lookback_days: limited_dates)
    monkeypatch.setattr(
        service,
        "_strategy_backtest_summary",
        lambda **_kwargs: dict(current_metrics),
    )

    seeded_db.add(
        BacktestRun(
            run_id="bt-baseline-unit",
            strategy_name="trend_breakout",
            config_hash="unit",
            start_date=limited_dates[0],
            end_date=limited_dates[-1],
            metrics_json=json.dumps(
                {
                    "trade_count": 8,
                    "win_rate": 0.25,
                    "total_return": 0.02,
                    "max_drawdown": -0.10,
                }
            ),
        )
    )
    seeded_db.commit()

    run_id_summary = service.strategy_summary(lookback_days=252, baseline_run_id="bt-baseline-unit")
    trend = next(row for row in run_id_summary["strategies"] if row["strategy_name"] == "trend_breakout")
    unavailable = next(row for row in run_id_summary["strategies"] if row["strategy_name"] != "trend_breakout")

    assert run_id_summary["baseline"]["status"] == "run_id"
    assert trend["delta"]["baseline"] == "run_id"
    assert trend["delta"]["trade_count_delta"] == 2
    assert trend["delta"]["win_rate_delta"] == 0.25
    assert trend["delta"]["total_return_delta"] == 0.10
    assert trend["delta"]["max_drawdown_delta"] == 0.02
    assert unavailable["delta"]["baseline"] == "unavailable_for_strategy"

    snapshot_summary = service.strategy_summary(
        lookback_days=252,
        baseline_snapshot={
            "strategies": [
                {
                    "strategy_name": "trend_breakout",
                    "backtest": {
                        "trade_count": 7,
                        "win_rate": 0.4,
                        "total_return": 0.10,
                        "max_drawdown": -0.09,
                    },
                }
            ]
        },
    )
    snapshot_trend = next(row for row in snapshot_summary["strategies"] if row["strategy_name"] == "trend_breakout")

    assert snapshot_summary["baseline"]["status"] == "snapshot"
    assert snapshot_summary["baseline"]["snapshot_supplied"] is True
    assert snapshot_trend["delta"]["baseline"] == "snapshot"
    assert snapshot_trend["delta"]["trade_count_delta"] == 3
    assert snapshot_trend["delta"]["win_rate_delta"] == 0.1
    assert snapshot_trend["backtest"]["pbo"] == NOT_AVAILABLE
    assert snapshot_trend["backtest"]["deflated_sharpe_ratio"] == NOT_AVAILABLE


def test_strategy_parameter_snapshot_service_saves_queries_and_detects_drift(db_session):
    strategy_config = deepcopy(get_config("strategies"))
    service = StrategyParameterSnapshotService(db_session, strategy_config=strategy_config)

    unavailable = service.parameter_drift_check(as_of=date(2026, 5, 20), strategy_names=["trend_breakout"])

    assert unavailable["status"] == NOT_AVAILABLE
    assert unavailable["comparison_available"] is False
    assert unavailable["drifted_parameter_count"] == 0
    assert unavailable["changed_keys"] == []
    assert unavailable["unchanged_keys_count"] == 0
    assert unavailable["snapshot_dates"] == []
    assert unavailable["config_hash_diff"] == {
        "changed_count": 0,
        "unchanged_count": 0,
        "unavailable_count": 1,
    }
    assert unavailable["strategies"][0]["reason"] == "strategy_parameter_snapshot_not_found"

    rows = service.save_current_snapshots(
        snapshot_date=date(2026, 5, 20),
        effective_date=date(2026, 5, 20),
        strategy_names=["trend_breakout"],
    )
    persisted = db_session.scalar(select(StrategyParameterSnapshot).where(StrategyParameterSnapshot.id == rows[0].id))

    assert persisted is not None
    assert persisted.strategy_name == "trend_breakout"
    assert persisted.snapshot_date == date(2026, 5, 20)
    assert persisted.effective_date == date(2026, 5, 20)
    assert json.loads(persisted.parameter_json)["strategy"]["rs_percentile_min"] == 80
    latest = service.latest_snapshots(as_of=date(2026, 5, 21), strategy_names=["trend_breakout"])
    assert latest["trend_breakout"].id == persisted.id

    modified_config = deepcopy(strategy_config)
    modified_config["trend_breakout"]["rs_percentile_min"] = 82
    drift = StrategyParameterSnapshotService(db_session, strategy_config=modified_config).parameter_drift_check(
        as_of=date(2026, 5, 21),
        strategy_names=["trend_breakout"],
    )
    trend = drift["strategies"][0]

    assert drift["status"] == "drift_detected"
    assert drift["comparison_available"] is True
    assert drift["changed_keys"] == ["trend_breakout:strategy.rs_percentile_min"]
    assert drift["unchanged_keys_count"] > 0
    assert drift["snapshot_dates"] == [date(2026, 5, 20)]
    assert drift["config_hash_diff"]["changed_count"] == 1
    assert trend["status"] == "drift_detected"
    assert trend["drift_count"] == 1
    assert trend["changed_keys"] == ["strategy.rs_percentile_min"]
    assert trend["unchanged_keys_count"] > 0
    assert trend["config_hash_changed"] is True
    assert trend["config_hash_diff"] == "changed"
    assert trend["drifted_parameters"][0] == {
        "parameter": "strategy.rs_percentile_min",
        "change": "modified",
        "snapshot": 80,
        "current": 82,
    }


def test_weekly_report_parameter_drift_uses_latest_strategy_snapshot(seeded_db):
    snapshot_config = deepcopy(get_config("strategies"))
    snapshot_config["trend_breakout"]["rs_percentile_min"] = 70
    StrategyParameterSnapshotService(seeded_db, strategy_config=snapshot_config).save_current_snapshots(
        snapshot_date=date(2026, 5, 1),
        effective_date=date(2026, 5, 1),
        strategy_names=["trend_breakout"],
    )
    ScreenerService(seeded_db).run(strategies=["trend_breakout"])

    report = ReportService(seeded_db).generate_weekly_report()
    markdown = ReportService(seeded_db).get_markdown(str(report["report_id"]))

    assert "## Parameter Drift Check" in markdown
    assert "- parameter_history_source: strategy_parameter_snapshots" in markdown
    assert "- parameter_snapshot_status: drift_detected" in markdown
    assert "- changed_keys: trend_breakout:strategy.rs_percentile_min" in markdown
    assert "- unchanged_keys_count: " in markdown
    assert "- snapshot_dates: 2026-05-01" in markdown
    assert "- effective_dates: 2026-05-01" in markdown
    assert "- config_hash_diff: changed:1, unchanged:0, unavailable:" in markdown
    assert "| strategy | status | snapshot_date | effective_date | config_hash_diff | current_config_hash | snapshot_config_hash | changed_keys | unchanged_keys_count | change_detail |" in markdown
    assert "trend_breakout | drift_detected" in markdown
    assert "| trend_breakout | drift_detected | 2026-05-01 | 2026-05-01 | changed |" in markdown
    assert "strategy.rs_percentile_min |" in markdown
    assert "strategy.rs_percentile_min:70->80" in markdown

    detail = ReportService(seeded_db).get_report(str(report["report_id"]), include_markdown=True)
    drift_metadata = detail["metadata"]["parameter_drift"]
    assert drift_metadata["parameter_snapshot_status"] == "drift_detected"
    assert drift_metadata["changed_keys"] == "trend_breakout:strategy.rs_percentile_min"
    assert drift_metadata["snapshot_dates"] == "2026-05-01"
    trend_metadata = next(row for row in drift_metadata["strategies"] if row["strategy"] == "trend_breakout")
    assert trend_metadata["changed_keys"] == "strategy.rs_percentile_min"


def test_weekly_report_parameter_drift_marks_no_drift_detected(seeded_db):
    StrategyParameterSnapshotService(seeded_db).save_current_snapshots(
        snapshot_date=date(2026, 5, 1),
        effective_date=date(2026, 5, 1),
    )
    ScreenerService(seeded_db).run(strategies=["trend_breakout"])

    report = ReportService(seeded_db).generate_weekly_report()
    markdown = ReportService(seeded_db).get_markdown(str(report["report_id"]))

    assert "- parameter_snapshot_status: no_drift" in markdown
    assert "- changed_keys: no_drift_detected" in markdown
    assert "- no_drift_detected: true" in markdown
    assert "- config_hash_diff: changed:0, unchanged:" in markdown
    assert "no_drift_detected" in markdown

    detail = ReportService(seeded_db).get_report(str(report["report_id"]), include_markdown=True)
    drift_metadata = detail["metadata"]["parameter_drift"]
    assert drift_metadata["parameter_snapshot_status"] == "no_drift"
    assert drift_metadata["changed_keys"] == "no_drift_detected"
    assert drift_metadata["no_drift_detected"] is True


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


def test_rank_portfolio_sizing_uses_rebalance_snapshot_without_future_pnl(monkeypatch):
    service = _simulation_service()
    first_signal_date = date(2026, 1, 1)
    second_signal_date = date(2026, 1, 2)
    first_rebalance_candidates = [
        {
            "score": 2.0,
            "indicator": SimpleNamespace(symbol="AAA", close=100.0),
            "risk": SimpleNamespace(
                entry_price=100.0,
                stop_price=95.0,
                target_price=112.5,
                risk_per_share=5.0,
                position_size=100,
                position_notional=10000.0,
                risk_basis="unit_test",
            ),
            "metadata": {"execution_requires_portfolio_constructor": True},
        },
        {
            "score": 1.5,
            "indicator": SimpleNamespace(symbol="BBB", close=100.0),
            "risk": SimpleNamespace(
                entry_price=100.0,
                stop_price=95.0,
                target_price=112.5,
                risk_per_share=5.0,
                position_size=100,
                position_notional=10000.0,
                risk_basis="unit_test",
            ),
            "metadata": {"execution_requires_portfolio_constructor": True},
        },
    ]
    second_rebalance_candidates = [
        {
            "score": 1.0,
            "indicator": SimpleNamespace(symbol="CCC", close=100.0),
            "risk": SimpleNamespace(
                entry_price=100.0,
                stop_price=95.0,
                target_price=112.5,
                risk_per_share=5.0,
                position_size=100,
                position_notional=10000.0,
                risk_basis="unit_test",
            ),
            "metadata": {"execution_requires_portfolio_constructor": True},
        },
    ]

    def fake_candidates(**kwargs):
        if kwargs["signal_date"] == first_signal_date:
            return first_rebalance_candidates
        if kwargs["signal_date"] == second_signal_date:
            return second_rebalance_candidates
        return []

    monkeypatch.setattr(service, "_rank_portfolio_candidates", fake_candidates)

    def fake_simulate_trade(symbol, _signal_date, risk, _price_by_symbol, _liquidity_stats, _realism_stats):
        entry_dates = {
            "AAA": date(2026, 1, 2),
            "BBB": date(2026, 1, 2),
            "CCC": date(2026, 1, 3),
        }
        exit_dates = {
            "AAA": date(2026, 1, 5),
            "BBB": date(2026, 1, 5),
            "CCC": date(2026, 1, 6),
        }
        return {
            "symbol": symbol,
            "signal_date": _signal_date,
            "entry_date": entry_dates[symbol],
            "exit_date": exit_dates[symbol],
            "raw_entry_price": 100.0,
            "entry_price": 100.0,
            "raw_exit_price": 100.0,
            "exit_price": 100.0,
            "exit_reason": "max_holding",
            "qty": int(risk.position_size),
            "pnl": 1000.0 if symbol == "AAA" else 0.0,
            "estimated_cost": 0.0,
            "cost_bps": 0.0,
            "risk_basis": "unit_test",
            "return_pct": 0.0,
            "holding_days": 1,
            "execution_detail": {},
            "liquidity_detail": {},
            "price_detail": {},
        }

    monkeypatch.setattr(service, "_simulate_trade", fake_simulate_trade)

    trades, equity_curve, equity, exposure_days, portfolio_stats = service._run_rank_portfolio_backtest(
        strategy_name="momentum_rank",
        dates=[first_signal_date, second_signal_date],
        rows_by_date={first_signal_date: [], second_signal_date: []},
        market_regime_cache={first_signal_date: "neutral", second_signal_date: "neutral"},
        price_by_symbol={},
        equity=1000.0,
        portfolio_config={
            "max_positions": 3,
            "top_n": 2,
            "weighting": "equal_weight",
            "rebalance_frequency": "daily",
            "allow_overlap_positions": False,
        },
        liquidity_stats={"partial_fill_count": 0, "no_fill_count": 0, "total_unfilled_qty": 0},
        realism_stats={
            "adjusted_price_trade_count": 0,
            "forced_exit_count": 0,
            "delisted_exit_count": 0,
            "missing_data_exit_count": 0,
        },
    )

    assert [trade["symbol"] for trade in trades] == ["AAA", "BBB", "CCC"]
    assert [trade["qty"] for trade in trades] == [5, 5, 10]
    assert [row["date"] for row in equity_curve] == [
        first_signal_date,
        date(2026, 1, 5),
        date(2026, 1, 5),
        date(2026, 1, 6),
    ]
    assert equity == pytest.approx(2000.0)
    assert exposure_days == 3
    assert portfolio_stats["execution_requires_portfolio_constructor_signal_count"] == 3


def test_average_active_positions_sweep_counts_overlapping_ranges_more_accurately_than_endpoints():
    trades = [
        {"symbol": "AAA", "entry_date": date(2026, 1, 5), "exit_date": date(2026, 1, 10)},
        {"symbol": "BBB", "entry_date": date(2026, 1, 6), "exit_date": date(2026, 1, 9)},
    ]
    endpoint_dates = sorted({trade_date for trade in trades for trade_date in (trade["entry_date"], trade["exit_date"])})
    endpoint_average = (
        sum(BacktestService._active_position_count(trades, trade_date) for trade_date in endpoint_dates)
        / len(endpoint_dates)
    )

    assert BacktestService._average_active_positions(trades) == pytest.approx(1.6667)
    assert BacktestService._average_active_positions(trades) > endpoint_average


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


def test_market_repository_corporate_actions_asof_excludes_future_actions(db_session):
    db_session.add(SymbolMaster(symbol="CA001", name="CA One", sector="Technology"))
    db_session.add_all(
        [
            CorporateAction(symbol="CA001", action_date=date(2026, 1, 3), action_type="SPLIT", value=0.5),
            CorporateAction(symbol="CA001", action_date=date(2026, 1, 10), action_type="DIVIDEND", value=100.0),
        ]
    )
    db_session.commit()

    repo = MarketRepository(db_session)

    assert repo.corporate_actions_asof("CA001", date(2026, 1, 2)) == []
    actions = repo.corporate_actions_asof("CA001", date(2026, 1, 3))
    assert len(actions) == 1
    assert actions[0].effective_date == date(2026, 1, 3)
    assert actions[0].action_type == "SPLIT"


def test_adjusted_price_option_uses_adj_close_factor_after_corporate_action_effective_date():
    raw_service = _simulation_service(max_holding_days=1, use_adjusted_price=False)
    adjusted_service = _simulation_service(max_holding_days=1, use_adjusted_price=True)
    adjusted_service.repo = SimpleNamespace(
        get_symbol=lambda _symbol: None,
        corporate_actions_asof=lambda _symbol, trade_date: [
            SimpleNamespace(action_date=date(2026, 1, 2), action_type="SPLIT", id=1)
        ]
        if trade_date >= date(2026, 1, 2)
        else [],
    )
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
    assert adjusted_trade["price_detail"]["adjusted_price_used"] is True
    assert adjusted_trade["price_detail"]["entry_adjustment_factor"] == 0.5
    assert adjusted_trade["price_detail"]["entry_corporate_action_effective_date"] == "2026-01-02"
    assert adjusted_trade["execution_detail"]["stop_price"] == 45.0


def test_adjusted_price_option_does_not_apply_future_corporate_action():
    service = _simulation_service(max_holding_days=2, use_adjusted_price=True)
    service.repo = SimpleNamespace(
        get_symbol=lambda _symbol: None,
        corporate_actions_asof=lambda _symbol, trade_date: [
            SimpleNamespace(action_date=date(2026, 1, 3), action_type="SPLIT", id=1)
        ]
        if trade_date >= date(2026, 1, 3)
        else [],
    )
    risk = SimpleNamespace(stop_price=40.0, position_size=10)
    price_by_symbol = _price_df(
        [
            {
                "trade_date": date(2026, 1, 2),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "adj_close": 50.0,
            },
            {
                "trade_date": date(2026, 1, 3),
                "open": 100.0,
                "high": 110.0,
                "low": 99.0,
                "close": 104.0,
                "adj_close": 52.0,
            },
        ]
    )

    trade = service._simulate_trade("TEST", date(2026, 1, 1), risk, price_by_symbol)

    assert trade is not None
    assert trade["raw_entry_price"] == 100.0
    assert trade["raw_exit_price"] == 52.0
    assert trade["price_detail"]["entry_price_basis"] == "raw_ohlc"
    assert trade["price_detail"]["exit_price_basis"] == "adjusted_ohlc_from_adj_close_asof_corporate_action"
    assert trade["price_detail"]["entry_adjustment_applied"] is False
    assert trade["price_detail"]["exit_adjustment_applied"] is True
    assert trade["price_detail"]["entry_corporate_action_status"] == "no_effective_corporate_action_raw_price"
    assert trade["price_detail"]["exit_corporate_action_effective_date"] == "2026-01-03"


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
