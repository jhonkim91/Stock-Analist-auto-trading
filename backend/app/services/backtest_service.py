from __future__ import annotations

import json
import math
from bisect import bisect_right
from datetime import date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_config
from backend.app.models.tables import BacktestRun, IndicatorSnapshot
from backend.app.repositories.backtest_repository import BacktestRepository
from backend.app.repositories.market_repository import MarketRepository
from backend.app.services.risk_service import RiskService
from backend.app.services.scoring_service import ScoringService
from backend.app.strategies.registry import get_available_strategy_registry
from backend.app.utils.hashing import stable_hash


RANK_PORTFOLIO_STRATEGIES = {"momentum_rank", "relative_strength_leader"}
SUMMARY_METRIC_KEYS = ("trade_count", "win_rate", "total_return", "max_drawdown")


class BacktestService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = MarketRepository(db)
        self.backtest_repo = BacktestRepository(db)
        self.risk_service = RiskService()
        self.scoring_service = ScoringService()
        self.strategy_config = get_config("strategies")
        self.backtest_config = get_config("backtest")
        self.strategies = get_available_strategy_registry(self.strategy_config)

    def run(
        self,
        strategy_name: str,
        start_date: date | None = None,
        end_date: date | None = None,
        initial_equity: float | None = None,
        top_n: int | None = None,
        max_positions: int | None = None,
        rebalance_frequency: str | None = None,
        weighting: str | None = None,
        allow_overlap_positions: bool | None = None,
        save: bool = True,
    ) -> dict[str, object]:
        """종가 신호 후 다음 거래일 시가 체결 가정으로 기본 백테스트를 수행한다."""
        if strategy_name not in self.strategies:
            raise ValueError(f"지원하지 않는 전략입니다: {strategy_name}")
        equity = float(initial_equity or get_config("risk")["portfolio"]["equity"])
        initial_equity_value = equity
        indicators = self._load_indicators(start_date, end_date)
        if not indicators:
            raise ValueError("indicator_snapshot 데이터가 없습니다.")
        daily = self.repo.daily_df(start_date, end_date)
        price_by_symbol = {
            symbol: group.sort_values("trade_date").reset_index(drop=True) for symbol, group in daily.groupby("symbol")
        }
        dates = sorted({row.trade_date for row in indicators})
        rows_by_date: dict[date, list[IndicatorSnapshot]] = {}
        for row in indicators:
            rows_by_date.setdefault(row.trade_date, []).append(row)
        market_regime_cache = self._build_market_regime_cache(dates)
        execution_config = self.backtest_config["execution"]
        execution_cost_bps = self._execution_cost_bps(execution_config)
        annual_trading_days = int(self.backtest_config.get("metrics", {}).get("annual_trading_days", 252))

        liquidity_stats = {"partial_fill_count": 0, "no_fill_count": 0, "total_unfilled_qty": 0}
        realism_stats = {"adjusted_price_trade_count": 0, "forced_exit_count": 0, "delisted_exit_count": 0, "missing_data_exit_count": 0}
        total_days = max((dates[-1] - dates[0]).days, 1)
        selection_mode = self._selection_mode(strategy_name)
        portfolio_config = self._portfolio_config(
            top_n=top_n,
            max_positions=max_positions,
            rebalance_frequency=rebalance_frequency,
            weighting=weighting,
            allow_overlap_positions=allow_overlap_positions,
        )

        if strategy_name in RANK_PORTFOLIO_STRATEGIES and selection_mode == "rank_portfolio":
            trades, equity_curve, equity, exposure_days, portfolio_stats = self._run_rank_portfolio_backtest(
                strategy_name=strategy_name,
                dates=dates,
                rows_by_date=rows_by_date,
                market_regime_cache=market_regime_cache,
                price_by_symbol=price_by_symbol,
                equity=equity,
                portfolio_config=portfolio_config,
                liquidity_stats=liquidity_stats,
                realism_stats=realism_stats,
            )
        else:
            trades, equity_curve, equity, exposure_days = self._run_single_position_backtest(
                strategy_name=strategy_name,
                dates=dates,
                rows_by_date=rows_by_date,
                market_regime_cache=market_regime_cache,
                price_by_symbol=price_by_symbol,
                equity=equity,
                liquidity_stats=liquidity_stats,
                realism_stats=realism_stats,
            )
            portfolio_stats = {
                "portfolio_constructor_used": False,
                "portfolio_selection_mode": selection_mode,
                "portfolio_top_n": int(portfolio_config["top_n"]),
                "portfolio_max_positions": int(portfolio_config["max_positions"]),
                "portfolio_weighting": str(portfolio_config["weighting"]),
                "portfolio_rebalance_frequency": str(portfolio_config["rebalance_frequency"]),
                "portfolio_allow_overlap_positions": bool(portfolio_config["allow_overlap_positions"]),
            }

        metrics = self._metrics(
            trades,
            equity_curve,
            equity,
            initial_equity_value,
            exposure_days,
            total_days,
            liquidity_stats,
            realism_stats,
            execution_cost_bps=execution_cost_bps,
            annual_trading_days=annual_trading_days,
            portfolio_stats=portfolio_stats,
        )
        run_id = "unsaved"
        if save:
            run_id = f"bt-{uuid4().hex[:12]}"
            effective_backtest_config = {**self.backtest_config, "portfolio": portfolio_config}
            config_hash = stable_hash(
                {"strategy": strategy_name, "backtest": effective_backtest_config, "risk": get_config("risk")}
            )
            self.backtest_repo.save(
                BacktestRun(
                    run_id=run_id,
                    strategy_name=strategy_name,
                    config_hash=config_hash,
                    start_date=start_date,
                    end_date=end_date,
                    metrics_json=json.dumps(metrics, ensure_ascii=False, default=str),
                )
            )
        return {"run_id": run_id, "strategy_name": strategy_name, "metrics": metrics, "trades": trades[:20]}

    def list_runs(self, limit: int = 20) -> list[dict[str, object]]:
        """최근 백테스트 run 목록을 반환한다."""
        runs = list(self.db.scalars(select(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(limit)).all())
        return [self._serialize_run(run) for run in runs]

    def get_run(self, run_id: str) -> dict[str, object]:
        """단일 백테스트 run 상세를 반환한다."""
        run = self.db.get(BacktestRun, run_id)
        if run is None:
            raise ValueError("백테스트 run을 찾을 수 없습니다.")
        return self._serialize_run(run)

    def strategy_summary(
        self,
        lookback_days: int = 252,
        baseline_run_id: str | None = None,
        baseline_snapshot: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """최근 가용 거래일 기준 전략별 screener/backtest validation summary를 계산한다."""
        from backend.app.services.screener_service import ScreenerService

        requested_days = max(int(lookback_days), 1)
        strategy_names = list(self.strategies)
        indicator_dates = self._latest_indicator_dates(requested_days)
        window_start = indicator_dates[0] if indicator_dates else None
        window_end = indicator_dates[-1] if indicator_dates else None
        screener_summary = ScreenerService(self.db).strategy_pass_rate_summary(
            lookback_days=requested_days,
            strategy_names=strategy_names,
        )
        screener_by_strategy = {
            str(row["strategy_name"]): row for row in screener_summary["strategies"]  # type: ignore[index]
        }
        baseline = self._baseline_metrics_by_strategy(baseline_run_id, baseline_snapshot)

        strategy_summaries: list[dict[str, object]] = []
        for strategy_name in strategy_names:
            backtest_summary = self._strategy_backtest_summary(
                strategy_name=strategy_name,
                start_date=window_start,
                end_date=window_end,
            )
            baseline_metrics = baseline["metrics_by_strategy"].get(strategy_name)
            baseline_status = str(baseline["status"])
            if baseline_metrics is None and baseline_status in {"run_id", "snapshot"}:
                baseline_status = "unavailable_for_strategy"
            strategy_summaries.append(
                {
                    "strategy_name": strategy_name,
                    "screener": screener_by_strategy.get(
                        strategy_name,
                        {
                            "strategy_name": strategy_name,
                            "evaluated_count": 0,
                            "pass_count": 0,
                            "pass_rate": None,
                            "evaluated_trading_days": 0,
                            "window_trading_days": 0,
                            "window_start": None,
                            "window_end": None,
                        },
                    ),
                    "backtest": backtest_summary,
                    "delta": self._metric_deltas(backtest_summary, baseline_metrics, baseline_status),
                }
            )

        return {
            "lookback_days": requested_days,
            "window": {
                "requested_trading_days": requested_days,
                "available_trading_days": len(indicator_dates),
                "start_date": window_start,
                "end_date": window_end,
                "basis": "indicator_snapshot.trade_date",
            },
            "screener_window": {
                key: value
                for key, value in screener_summary.items()
                if key != "strategies"
            },
            "baseline": {
                "status": baseline["status"],
                "run_id": baseline_run_id,
                "snapshot_supplied": baseline_snapshot is not None,
            },
            "strategies": strategy_summaries,
        }

    @staticmethod
    def _serialize_run(run: BacktestRun) -> dict[str, object]:
        metrics = json.loads(run.metrics_json)
        return {
            "run_id": run.run_id,
            "strategy_name": run.strategy_name,
            "config_hash": run.config_hash,
            "start_date": run.start_date,
            "end_date": run.end_date,
            "metrics": metrics,
            "created_at": run.created_at,
        }

    def _latest_indicator_dates(self, lookback_days: int) -> list[date]:
        dates_desc = list(
            self.db.scalars(
                select(IndicatorSnapshot.trade_date)
                .distinct()
                .order_by(IndicatorSnapshot.trade_date.desc())
                .limit(max(int(lookback_days), 1))
            ).all()
        )
        return sorted(dates_desc)

    def _strategy_backtest_summary(
        self,
        strategy_name: str,
        start_date: date | None,
        end_date: date | None,
    ) -> dict[str, object]:
        if start_date is None or end_date is None:
            return {
                "summary_source": "computed_available_window",
                "error": "indicator_window_unavailable",
                **{metric: None for metric in SUMMARY_METRIC_KEYS},
            }
        try:
            result = self.run(strategy_name, start_date=start_date, end_date=end_date, save=False)
        except ValueError as exc:
            return {
                "summary_source": "computed_available_window",
                "error": str(exc),
                **{metric: None for metric in SUMMARY_METRIC_KEYS},
            }
        metrics = result["metrics"]
        return {
            "summary_source": "computed_available_window",
            "error": None,
            **{metric: metrics.get(metric) for metric in SUMMARY_METRIC_KEYS},  # type: ignore[union-attr]
        }

    def _baseline_metrics_by_strategy(
        self,
        baseline_run_id: str | None,
        baseline_snapshot: dict[str, object] | None,
    ) -> dict[str, object]:
        if baseline_run_id:
            run = self.db.get(BacktestRun, baseline_run_id)
            if run is None:
                return {"status": "missing", "metrics_by_strategy": {}}
            return {
                "status": "run_id",
                "metrics_by_strategy": {run.strategy_name: json.loads(run.metrics_json)},
            }
        if baseline_snapshot is not None:
            return {
                "status": "snapshot",
                "metrics_by_strategy": self._baseline_snapshot_metrics(baseline_snapshot),
            }
        return {"status": "unspecified", "metrics_by_strategy": {}}

    @staticmethod
    def _baseline_snapshot_metrics(snapshot: dict[str, object]) -> dict[str, dict[str, object]]:
        metrics_by_strategy: dict[str, dict[str, object]] = {}
        strategies = snapshot.get("strategies")
        if isinstance(strategies, list):
            for row in strategies:
                if not isinstance(row, dict):
                    continue
                strategy_name = row.get("strategy_name")
                metrics = row.get("backtest") or row.get("metrics")
                if isinstance(strategy_name, str) and isinstance(metrics, dict):
                    metrics_by_strategy[strategy_name] = metrics
            return metrics_by_strategy

        strategy_name = snapshot.get("strategy_name")
        if isinstance(strategy_name, str):
            metrics = snapshot.get("backtest") or snapshot.get("metrics") or snapshot
            if isinstance(metrics, dict):
                return {strategy_name: metrics}

        for key, value in snapshot.items():
            if not isinstance(value, dict):
                continue
            metrics = value.get("backtest") or value.get("metrics") or value
            if isinstance(metrics, dict):
                metrics_by_strategy[str(key)] = metrics
        return metrics_by_strategy

    @staticmethod
    def _metric_deltas(
        current_metrics: dict[str, object],
        baseline_metrics: dict[str, object] | None,
        baseline_status: str,
    ) -> dict[str, object]:
        deltas: dict[str, object] = {"baseline": baseline_status}
        for metric in SUMMARY_METRIC_KEYS:
            current_value = current_metrics.get(metric)
            baseline_value = baseline_metrics.get(metric) if baseline_metrics else None
            deltas[f"{metric}_delta"] = (
                round(float(current_value) - float(baseline_value), 6)
                if isinstance(current_value, (int, float)) and isinstance(baseline_value, (int, float))
                else None
            )
        return deltas

    def _load_indicators(self, start_date: date | None, end_date: date | None) -> list[IndicatorSnapshot]:
        stmt = select(IndicatorSnapshot)
        if start_date:
            stmt = stmt.where(IndicatorSnapshot.trade_date >= start_date)
        if end_date:
            stmt = stmt.where(IndicatorSnapshot.trade_date <= end_date)
        return list(self.db.scalars(stmt.order_by(IndicatorSnapshot.trade_date, IndicatorSnapshot.symbol)).all())

    def _run_single_position_backtest(
        self,
        strategy_name: str,
        dates: list[date],
        rows_by_date: dict[date, list[IndicatorSnapshot]],
        market_regime_cache: dict[date, str],
        price_by_symbol: dict[str, pd.DataFrame],
        equity: float,
        liquidity_stats: dict[str, int],
        realism_stats: dict[str, int],
    ) -> tuple[list[dict[str, object]], list[dict[str, object]], float, int]:
        trades: list[dict[str, object]] = []
        equity_curve = [{"date": dates[0], "equity": equity}]
        exposure_days = 0
        for signal_date in dates:
            candidates = []
            market_regime = market_regime_cache.get(signal_date, "neutral")
            for indicator in rows_by_date.get(signal_date, []):
                fundamentals = self.repo.fundamentals_asof(indicator.symbol, signal_date)
                self._attach_earnings_event(indicator, signal_date)
                strategy_result = self.strategies[strategy_name].evaluate(indicator, fundamentals, market_regime)
                risk_metadata = strategy_result.metadata.get("risk_metadata")
                risk = self.risk_service.calculate(
                    indicator,
                    equity,
                    risk_metadata=risk_metadata if isinstance(risk_metadata, dict) else None,
                )
                liquidity_ok = indicator.turnover_value >= float(self.strategy_config["common"]["min_turnover_value"])
                rr_ok = risk.reward_risk_ratio >= float(self.strategy_config["common"]["target_reward_risk"])
                if strategy_result.passed and liquidity_ok and rr_ok and risk.position_size > 0:
                    candidates.append((self.scoring_service.score(indicator, fundamentals, risk.rr_score), indicator, risk))
            if not candidates:
                continue
            _, indicator, risk = sorted(candidates, key=lambda item: item[0], reverse=True)[0]
            trade = self._simulate_trade(indicator.symbol, signal_date, risk, price_by_symbol, liquidity_stats, realism_stats)
            if trade is None:
                continue
            equity += float(trade["pnl"])
            exposure_days += int(trade["holding_days"])
            equity_curve.append({"date": trade["exit_date"], "equity": equity})
            trades.append(trade)
        return trades, equity_curve, equity, exposure_days

    def _run_rank_portfolio_backtest(
        self,
        strategy_name: str,
        dates: list[date],
        rows_by_date: dict[date, list[IndicatorSnapshot]],
        market_regime_cache: dict[date, str],
        price_by_symbol: dict[str, pd.DataFrame],
        equity: float,
        portfolio_config: dict[str, object],
        liquidity_stats: dict[str, int],
        realism_stats: dict[str, int],
    ) -> tuple[list[dict[str, object]], list[dict[str, object]], float, int, dict[str, object]]:
        trades: list[dict[str, object]] = []
        equity_curve = [{"date": dates[0], "equity": equity}]
        exposure_days = 0
        previous_weights: dict[str, float] = {}
        portfolio_turnovers: list[float] = []
        rebalance_count = 0
        constructor_required_signal_count = 0
        last_rebalance_date: date | None = None
        max_positions = int(portfolio_config["max_positions"])
        top_n = int(portfolio_config["top_n"])
        weighting = str(portfolio_config["weighting"])
        allow_overlap_positions = bool(portfolio_config["allow_overlap_positions"])

        for signal_date in dates:
            if not self._is_rebalance_date(signal_date, last_rebalance_date, str(portfolio_config["rebalance_frequency"])):
                continue
            last_rebalance_date = signal_date
            active_symbols = self._active_symbols(trades, signal_date)
            active_count = self._active_position_count(trades, signal_date)
            available_slots = max(max_positions - active_count, 0)
            if available_slots <= 0:
                continue
            candidates = self._rank_portfolio_candidates(
                strategy_name=strategy_name,
                signal_date=signal_date,
                rows=rows_by_date.get(signal_date, []),
                market_regime=market_regime_cache.get(signal_date, "neutral"),
                equity=equity,
                active_symbols=active_symbols,
                allow_overlap_positions=allow_overlap_positions,
            )
            if not candidates:
                continue
            selected = candidates[: min(top_n, available_slots)]
            if not selected:
                continue
            weights = self._candidate_weights(selected, weighting)
            selected_weights = {str(candidate["indicator"].symbol): weights[index] for index, candidate in enumerate(selected)}
            portfolio_turnovers.append(self._portfolio_turnover(previous_weights, selected_weights))
            previous_weights = selected_weights
            rebalance_count += 1
            constructor_required_signal_count += sum(
                1 for candidate in selected if bool(candidate["metadata"].get("execution_requires_portfolio_constructor"))
            )

            for rank, candidate in enumerate(selected, start=1):
                indicator = candidate["indicator"]
                target_weight = weights[rank - 1]
                risk = self._portfolio_sized_risk(
                    candidate["risk"],
                    indicator,
                    equity=equity,
                    target_weight=target_weight,
                    selected_count=len(selected),
                    weighting=weighting,
                )
                if int(risk.position_size) <= 0:
                    continue
                trade = self._simulate_trade(
                    indicator.symbol,
                    signal_date,
                    risk,
                    price_by_symbol,
                    liquidity_stats,
                    realism_stats,
                )
                if trade is None:
                    continue
                trade["portfolio_detail"] = {
                    "portfolio_constructor_used": True,
                    "selection_mode": "rank_portfolio",
                    "rebalance_date": signal_date,
                    "rank": rank,
                    "rank_score": candidate["score"],
                    "target_weight": round(target_weight, 6),
                    "top_n": top_n,
                    "max_positions": max_positions,
                    "weighting": weighting,
                    "allow_overlap_positions": allow_overlap_positions,
                }
                trade["execution_detail"]["portfolio_constructor_used"] = True
                equity += float(trade["pnl"])
                exposure_days += int(trade["holding_days"])
                equity_curve.append({"date": trade["exit_date"], "equity": equity})
                trades.append(trade)

        portfolio_stats = {
            "portfolio_constructor_used": True,
            "portfolio_selection_mode": "rank_portfolio",
            "portfolio_top_n": top_n,
            "portfolio_max_positions": max_positions,
            "portfolio_weighting": weighting,
            "portfolio_rebalance_frequency": str(portfolio_config["rebalance_frequency"]),
            "portfolio_allow_overlap_positions": allow_overlap_positions,
            "portfolio_turnover": round(sum(portfolio_turnovers) / len(portfolio_turnovers), 6)
            if portfolio_turnovers
            else 0.0,
            "average_active_positions": self._average_active_positions(trades),
            "rebalance_count": rebalance_count,
            "execution_requires_portfolio_constructor_signal_count": constructor_required_signal_count,
        }
        return trades, equity_curve, equity, exposure_days, portfolio_stats

    def _rank_portfolio_candidates(
        self,
        strategy_name: str,
        signal_date: date,
        rows: list[IndicatorSnapshot],
        market_regime: str,
        equity: float,
        active_symbols: set[str],
        allow_overlap_positions: bool,
    ) -> list[dict[str, object]]:
        candidates: list[dict[str, object]] = []
        for indicator in rows:
            if not allow_overlap_positions and str(indicator.symbol) in active_symbols:
                continue
            fundamentals = self.repo.fundamentals_asof(indicator.symbol, signal_date)
            self._attach_earnings_event(indicator, signal_date)
            strategy_result = self.strategies[strategy_name].evaluate(indicator, fundamentals, market_regime)
            risk_metadata = strategy_result.metadata.get("risk_metadata")
            risk = self.risk_service.calculate(
                indicator,
                equity,
                risk_metadata=risk_metadata if isinstance(risk_metadata, dict) else None,
            )
            liquidity_ok = indicator.turnover_value >= float(self.strategy_config["common"]["min_turnover_value"])
            rr_ok = risk.reward_risk_ratio >= float(self.strategy_config["common"]["target_reward_risk"])
            if not (strategy_result.passed and liquidity_ok and rr_ok and risk.position_size > 0):
                continue
            score = self.scoring_service.rank_score(
                strategy_name,
                indicator,
                fundamentals,
                risk.rr_score,
                strategy_result.metadata,
            )
            candidates.append(
                {
                    "score": score,
                    "indicator": indicator,
                    "risk": risk,
                    "metadata": strategy_result.metadata,
                }
            )
        return sorted(candidates, key=lambda candidate: (-float(candidate["score"]), str(candidate["indicator"].symbol)))

    def _selection_mode(self, strategy_name: str) -> str:
        if strategy_name not in RANK_PORTFOLIO_STRATEGIES:
            return "single_position"
        strategy_config = self.strategy_config.get(strategy_name, {})
        selection_mode = str(strategy_config.get("selection_mode") or "rank_portfolio")
        if selection_mode not in {"rank_portfolio", "single_position"}:
            raise ValueError(f"지원하지 않는 selection_mode입니다: {selection_mode}")
        return selection_mode

    def _attach_earnings_event(self, indicator: IndicatorSnapshot, signal_date: date) -> None:
        earnings_event_asof = getattr(self.repo, "earnings_event_asof", None)
        event = earnings_event_asof(indicator.symbol, signal_date) if callable(earnings_event_asof) else None
        setattr(indicator, "earnings_event", event)

    def _portfolio_config(
        self,
        top_n: int | None = None,
        max_positions: int | None = None,
        rebalance_frequency: str | None = None,
        weighting: str | None = None,
        allow_overlap_positions: bool | None = None,
    ) -> dict[str, object]:
        config = dict(self.backtest_config.get("portfolio", {}))
        if top_n is not None:
            config["top_n"] = top_n
        if max_positions is not None:
            config["max_positions"] = max_positions
        if rebalance_frequency is not None:
            config["rebalance_frequency"] = rebalance_frequency
        if weighting is not None:
            config["weighting"] = weighting
        if allow_overlap_positions is not None:
            config["allow_overlap_positions"] = allow_overlap_positions

        parsed_top_n = max(int(config.get("top_n", 5)), 1)
        parsed_max_positions = max(int(config.get("max_positions", parsed_top_n)), 1)
        parsed_weighting = str(config.get("weighting", "equal_risk"))
        parsed_rebalance_frequency = str(config.get("rebalance_frequency", "daily"))
        if parsed_weighting not in {"equal_risk", "equal_weight"}:
            raise ValueError(f"지원하지 않는 portfolio.weighting입니다: {parsed_weighting}")
        if parsed_rebalance_frequency not in {"daily", "weekly", "monthly"}:
            raise ValueError(f"지원하지 않는 rebalance_frequency입니다: {parsed_rebalance_frequency}")
        return {
            "top_n": min(parsed_top_n, parsed_max_positions),
            "max_positions": parsed_max_positions,
            "rebalance_frequency": parsed_rebalance_frequency,
            "weighting": parsed_weighting,
            "allow_overlap_positions": bool(config.get("allow_overlap_positions", False)),
        }

    @staticmethod
    def _is_rebalance_date(signal_date: date, last_rebalance_date: date | None, frequency: str) -> bool:
        if last_rebalance_date is None or frequency == "daily":
            return True
        if frequency == "weekly":
            return signal_date.isocalendar()[:2] != last_rebalance_date.isocalendar()[:2]
        if frequency == "monthly":
            return (signal_date.year, signal_date.month) != (last_rebalance_date.year, last_rebalance_date.month)
        return False

    @staticmethod
    def _active_symbols(trades: list[dict[str, object]], signal_date: date) -> set[str]:
        return {
            str(trade["symbol"])
            for trade in trades
            if trade["entry_date"] <= signal_date <= trade["exit_date"]
        }

    @staticmethod
    def _active_position_count(trades: list[dict[str, object]], signal_date: date) -> int:
        return sum(1 for trade in trades if trade["entry_date"] <= signal_date <= trade["exit_date"])

    @staticmethod
    def _candidate_weights(candidates: list[dict[str, object]], weighting: str) -> list[float]:
        if not candidates:
            return []
        if weighting == "equal_weight":
            return [1 / len(candidates)] * len(candidates)
        inverse_risks = [
            1 / max(float(getattr(candidate["risk"], "risk_per_share", 0.0) or 0.0), 1e-9)
            for candidate in candidates
        ]
        total = sum(inverse_risks)
        if total <= 0:
            return [1 / len(candidates)] * len(candidates)
        return [value / total for value in inverse_risks]

    @staticmethod
    def _portfolio_turnover(previous_weights: dict[str, float], next_weights: dict[str, float]) -> float:
        if not previous_weights:
            return round(sum(next_weights.values()), 6)
        symbols = set(previous_weights) | set(next_weights)
        return round(sum(abs(next_weights.get(symbol, 0.0) - previous_weights.get(symbol, 0.0)) for symbol in symbols) / 2, 6)

    @staticmethod
    def _average_active_positions(trades: list[dict[str, object]]) -> float:
        active_dates = sorted({trade_date for trade in trades for trade_date in (trade["entry_date"], trade["exit_date"])})
        if not active_dates:
            return 0.0
        active_counts = [BacktestService._active_position_count(trades, active_date) for active_date in active_dates]
        return round(sum(active_counts) / len(active_counts), 4)

    @staticmethod
    def _portfolio_sized_risk(
        risk,
        indicator: IndicatorSnapshot,
        equity: float,
        target_weight: float,
        selected_count: int,
        weighting: str,
    ):
        entry_price = float(getattr(risk, "entry_price", getattr(indicator, "close", 0.0)))
        if entry_price <= 0:
            return BacktestService._copy_risk_with_position_size(risk, 0, entry_price)
        original_qty = int(getattr(risk, "position_size", 0) or 0)
        target_notional_qty = int((equity * target_weight) // entry_price)
        position_size = min(original_qty, target_notional_qty)
        if weighting == "equal_risk":
            risk_per_share = max(float(getattr(risk, "risk_per_share", 0.0) or 0.0), 1e-9)
            risk_fraction = float(get_config("risk")["portfolio"]["risk_fraction"])
            target_risk_qty = int(((equity * risk_fraction) / max(selected_count, 1)) // risk_per_share)
            position_size = min(position_size, target_risk_qty)
        return BacktestService._copy_risk_with_position_size(risk, max(position_size, 0), entry_price)

    @staticmethod
    def _copy_risk_with_position_size(risk, position_size: int, entry_price: float):
        values = dict(getattr(risk, "__dict__", {}))
        values["position_size"] = int(position_size)
        values["position_notional"] = round(int(position_size) * float(entry_price), 2) if entry_price > 0 else 0.0
        return SimpleNamespace(**values)

    def _simulate_trade(
        self,
        symbol: str,
        signal_date: date,
        risk,
        price_by_symbol: dict[str, pd.DataFrame],
        liquidity_stats: dict[str, int] | None = None,
        realism_stats: dict[str, int] | None = None,
    ) -> dict[str, object] | None:
        prices = price_by_symbol.get(symbol)
        if prices is None or prices.empty:
            return None
        future = prices[prices["trade_date"] > signal_date].reset_index(drop=True)
        if future.empty:
            return None
        entry_bar = future.iloc[0]
        execution_config = self.backtest_config["execution"]
        commission_bps = float(execution_config["commission_bps"])
        slippage_bps = float(execution_config["slippage_bps"])
        cost_bps = commission_bps + slippage_bps
        bps = cost_bps / 10000
        same_bar_stop_first = bool(execution_config.get("same_bar_stop_first", True))
        use_adjusted_price = bool(execution_config.get("use_adjusted_price", False))
        entry_price_view = self._bar_price_view(entry_bar, use_adjusted_price)
        raw_entry_price = float(entry_price_view["open"])
        entry_price = raw_entry_price * (1 + bps)
        stop_price = float(risk.stop_price) * float(entry_price_view["adjustment_factor"])
        target_price = entry_price + (entry_price - stop_price) * float(self.strategy_config["common"]["target_reward_risk"])
        planned_qty = int(risk.position_size)
        liquidity_detail = self._liquidity_detail(entry_bar, raw_entry_price, planned_qty, execution_config)
        filled_qty = int(liquidity_detail["filled_qty"])
        unfilled_qty = int(liquidity_detail["unfilled_qty"])
        if filled_qty <= 0:
            self._record_no_fill(liquidity_stats, planned_qty)
            return None
        max_holding_days = int(execution_config["max_holding_days"])

        exit_decision: dict[str, object] | None = None
        exit_bar: pd.Series | None = None
        exit_bar_index = 0
        exit_price_view: dict[str, object] | None = None
        for index, bar in future.iloc[:max_holding_days].iterrows():
            current_price_view = self._bar_price_view(bar, use_adjusted_price)
            exit_decision = self._exit_decision(
                bar=current_price_view,
                bar_index=int(index),
                max_holding_days=max_holding_days,
                stop_price=stop_price,
                target_price=target_price,
                same_bar_stop_first=same_bar_stop_first,
            )
            if exit_decision is not None:
                exit_bar = bar
                exit_bar_index = int(index)
                exit_price_view = current_price_view
                break

        if exit_decision is None:
            forced_exit = self._forced_exit(
                symbol=symbol,
                prices=prices,
                future=future,
                max_holding_days=max_holding_days,
                execution_config=execution_config,
                use_adjusted_price=use_adjusted_price,
            )
            if forced_exit is None:
                return None
            exit_bar = forced_exit["bar"]
            exit_bar_index = int(forced_exit["bar_index"])
            exit_price_view = forced_exit["price_view"]
            exit_decision = forced_exit["exit_decision"]

        raw_exit_price = float(exit_decision["raw_exit_price"])
        exit_price = raw_exit_price * (1 - bps)
        pnl = (exit_price - entry_price) * filled_qty
        estimated_cost = ((raw_entry_price * bps) + (raw_exit_price * bps)) * filled_qty
        if unfilled_qty > 0:
            self._record_partial_fill(liquidity_stats, unfilled_qty)
        self._record_realism_stats(realism_stats, use_adjusted_price, exit_decision)
        assert exit_bar is not None
        assert exit_price_view is not None
        return {
            "symbol": symbol,
            "signal_date": signal_date,
            "entry_date": entry_bar["trade_date"],
            "raw_entry_price": round(raw_entry_price, 4),
            "entry_price": round(entry_price, 4),
            "exit_date": exit_bar["trade_date"],
            "raw_exit_price": round(raw_exit_price, 4),
            "exit_price": round(exit_price, 4),
            "exit_reason": exit_decision["exit_reason"],
            "qty": filled_qty,
            "pnl": round(pnl, 2),
            "estimated_cost": round(estimated_cost, 2),
            "cost_bps": round(cost_bps, 4),
            "risk_basis": str(getattr(risk, "risk_basis", "unavailable")),
            "return_pct": round((exit_price / entry_price) - 1, 6),
            "holding_days": exit_bar_index + 1,
            "execution_detail": {
                "entry_assumption": "next_open",
                "exit_assumption": exit_decision["exit_assumption"],
                "same_bar_stop_first": same_bar_stop_first,
                "stop_touched": exit_decision["stop_touched"],
                "target_touched": exit_decision["target_touched"],
                "same_bar_both_touched": exit_decision["same_bar_both_touched"],
                "gap_stop": exit_decision["gap_stop"],
                "gap_target": exit_decision["gap_target"],
                "stop_price": round(stop_price, 4),
                "target_price": round(target_price, 4),
                "risk_basis": str(getattr(risk, "risk_basis", "unavailable")),
                "commission_bps": commission_bps,
                "slippage_bps": slippage_bps,
                "forced_exit": bool(exit_decision.get("forced_exit", False)),
                "delisted_exit": bool(exit_decision.get("delisted_exit", False)),
                "missing_data_exit": bool(exit_decision.get("missing_data_exit", False)),
                "delisted_handling_policy": str(execution_config.get("delisted_handling_policy", "ignore")),
                "missing_data_policy": str(execution_config.get("missing_data_policy", "ignore")),
            },
            "liquidity_detail": liquidity_detail,
            "price_detail": {
                "use_adjusted_price": use_adjusted_price,
                "entry_price_basis": entry_price_view["price_basis"],
                "exit_price_basis": exit_price_view["price_basis"],
                "entry_adjustment_factor": entry_price_view["adjustment_factor"],
                "exit_adjustment_factor": exit_price_view["adjustment_factor"],
                "entry_raw_close": entry_price_view["source_close"],
                "entry_adj_close": entry_price_view["source_adj_close"],
                "exit_raw_close": exit_price_view["source_close"],
                "exit_adj_close": exit_price_view["source_adj_close"],
            },
        }

    def _forced_exit(
        self,
        symbol: str,
        prices: pd.DataFrame,
        future: pd.DataFrame,
        max_holding_days: int,
        execution_config: dict[str, object],
        use_adjusted_price: bool,
    ) -> dict[str, object] | None:
        holding_window = future.iloc[:max_holding_days]
        if holding_window.empty or len(holding_window) >= max_holding_days:
            return None
        last_bar = holding_window.iloc[-1]
        last_date = last_bar["trade_date"]
        is_delisted = self._is_delisted_at_last_bar(symbol, prices, last_bar)
        if is_delisted:
            policy = str(execution_config.get("delisted_handling_policy", "ignore"))
            if policy != "last_available_close":
                return None
            exit_reason = "delisted"
            exit_assumption = "delisted_last_available_close_exit"
        else:
            policy = str(execution_config.get("missing_data_policy", "ignore"))
            if policy != "last_available_close":
                return None
            exit_reason = "missing_data"
            exit_assumption = "missing_data_last_available_close_exit"

        price_view = self._bar_price_view(last_bar, use_adjusted_price)
        return {
            "bar": last_bar,
            "bar_index": int(holding_window.index[-1]),
            "price_view": price_view,
            "exit_decision": {
                "exit_reason": exit_reason,
                "raw_exit_price": float(price_view["close"]),
                "exit_assumption": exit_assumption,
                "stop_touched": False,
                "target_touched": False,
                "same_bar_both_touched": False,
                "gap_stop": False,
                "gap_target": False,
                "forced_exit": True,
                "delisted_exit": is_delisted,
                "missing_data_exit": not is_delisted,
                "last_available_date": last_date,
            },
        }

    def _is_delisted_at_last_bar(self, symbol: str, prices: pd.DataFrame, last_bar: pd.Series) -> bool:
        row_flag = self._truthy_flag(last_bar.get("delisted", False)) or self._truthy_flag(last_bar.get("is_delisted", False))
        if row_flag:
            return True
        delist_date = self._delist_date(symbol, prices)
        last_trade_date = self._optional_date(last_bar["trade_date"])
        return delist_date is not None and last_trade_date is not None and delist_date <= last_trade_date

    def _delist_date(self, symbol: str, prices: pd.DataFrame) -> date | None:
        if "delist_date" in prices.columns:
            delist_dates = prices["delist_date"].dropna()
            if not delist_dates.empty:
                return self._optional_date(delist_dates.iloc[-1])
        symbol_row = self.repo.get_symbol(symbol)
        return symbol_row.delist_date if symbol_row is not None else None

    @classmethod
    def _bar_price_view(cls, bar: pd.Series, use_adjusted_price: bool) -> dict[str, object]:
        close = float(bar["close"])
        adj_close = cls._optional_positive_float(bar.get("adj_close"))
        factor = adj_close / close if use_adjusted_price and close > 0 and adj_close is not None else 1.0
        return {
            "open": float(bar["open"]) * factor,
            "high": float(bar["high"]) * factor,
            "low": float(bar["low"]) * factor,
            "close": close * factor,
            "adjustment_factor": round(factor, 8),
            "price_basis": "adjusted_ohlc_from_adj_close" if use_adjusted_price and factor != 1.0 else "raw_ohlc",
            "source_close": close,
            "source_adj_close": adj_close,
        }

    @staticmethod
    def _truthy_flag(value: object) -> bool:
        if pd.isna(value):
            return False
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y"}
        return bool(value)

    @staticmethod
    def _optional_date(value: object) -> date | None:
        if value is None or pd.isna(value):
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.date()

    @classmethod
    def _liquidity_detail(
        cls,
        entry_bar: pd.Series,
        raw_entry_price: float,
        planned_qty: int,
        execution_config: dict[str, object],
    ) -> dict[str, object]:
        max_participation_rate = float(execution_config.get("max_participation_rate", 1.0))
        min_fill_ratio = float(execution_config.get("min_fill_ratio", 0.0))
        allow_partial_fill = bool(execution_config.get("allow_partial_fill", True))
        requested_notional = planned_qty * raw_entry_price
        turnover_value = cls._positive_float(entry_bar.get("turnover_value", 0))
        volume = cls._positive_float(entry_bar.get("volume", 0))

        if turnover_value > 0:
            liquidity_notional = turnover_value
            liquidity_basis = "turnover_value"
        elif volume > 0:
            liquidity_notional = volume * raw_entry_price
            liquidity_basis = "volume_x_entry_price"
        else:
            liquidity_notional = 0.0
            liquidity_basis = "missing_liquidity"

        cap_notional = liquidity_notional * max_participation_rate
        fill_ratio = min(1.0, cap_notional / requested_notional) if requested_notional > 0 else 0.0
        filled_qty = planned_qty if fill_ratio >= 1.0 else int(planned_qty * fill_ratio)
        if not allow_partial_fill and fill_ratio < 1.0:
            filled_qty = 0
        if planned_qty <= 0 or filled_qty <= 0 or (filled_qty / planned_qty) < min_fill_ratio:
            filled_qty = 0
        unfilled_qty = max(planned_qty - filled_qty, 0)

        return {
            "planned_qty": planned_qty,
            "filled_qty": filled_qty,
            "unfilled_qty": unfilled_qty,
            "requested_notional": round(requested_notional, 2),
            "liquidity_notional": round(liquidity_notional, 2),
            "cap_notional": round(cap_notional, 2),
            "fill_ratio": round(fill_ratio, 6),
            "max_participation_rate": max_participation_rate,
            "min_fill_ratio": min_fill_ratio,
            "allow_partial_fill": allow_partial_fill,
            "liquidity_basis": liquidity_basis,
            "position_size_cap_applied": filled_qty < planned_qty,
        }

    @staticmethod
    def _positive_float(value: object) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.0
        if pd.isna(numeric) or numeric <= 0:
            return 0.0
        return numeric

    @staticmethod
    def _optional_positive_float(value: object) -> float | None:
        numeric = BacktestService._positive_float(value)
        return numeric if numeric > 0 else None

    @staticmethod
    def _record_no_fill(liquidity_stats: dict[str, int] | None, planned_qty: int) -> None:
        if liquidity_stats is None:
            return
        liquidity_stats["no_fill_count"] = int(liquidity_stats.get("no_fill_count", 0)) + 1
        liquidity_stats["total_unfilled_qty"] = int(liquidity_stats.get("total_unfilled_qty", 0)) + max(planned_qty, 0)

    @staticmethod
    def _record_partial_fill(liquidity_stats: dict[str, int] | None, unfilled_qty: int) -> None:
        if liquidity_stats is None:
            return
        liquidity_stats["partial_fill_count"] = int(liquidity_stats.get("partial_fill_count", 0)) + 1
        liquidity_stats["total_unfilled_qty"] = int(liquidity_stats.get("total_unfilled_qty", 0)) + max(unfilled_qty, 0)

    @staticmethod
    def _record_realism_stats(
        realism_stats: dict[str, int] | None,
        use_adjusted_price: bool,
        exit_decision: dict[str, object],
    ) -> None:
        if realism_stats is None:
            return
        if use_adjusted_price:
            realism_stats["adjusted_price_trade_count"] = int(realism_stats.get("adjusted_price_trade_count", 0)) + 1
        if bool(exit_decision.get("forced_exit", False)):
            realism_stats["forced_exit_count"] = int(realism_stats.get("forced_exit_count", 0)) + 1
        if bool(exit_decision.get("delisted_exit", False)):
            realism_stats["delisted_exit_count"] = int(realism_stats.get("delisted_exit_count", 0)) + 1
        if bool(exit_decision.get("missing_data_exit", False)):
            realism_stats["missing_data_exit_count"] = int(realism_stats.get("missing_data_exit_count", 0)) + 1

    @staticmethod
    def _exit_decision(
        bar: dict[str, object],
        bar_index: int,
        max_holding_days: int,
        stop_price: float,
        target_price: float,
        same_bar_stop_first: bool,
    ) -> dict[str, object] | None:
        open_price = float(bar["open"])
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])
        stop_touched = low <= stop_price
        target_touched = high >= target_price
        gap_stop = open_price <= stop_price
        gap_target = open_price >= target_price
        same_bar_both_touched = stop_touched and target_touched

        if bar_index == 0 and gap_stop:
            return {
                "exit_reason": "stop",
                "raw_exit_price": open_price,
                "exit_assumption": "entry_gap_below_stop_open_exit",
                "stop_touched": True,
                "target_touched": target_touched,
                "same_bar_both_touched": same_bar_both_touched,
                "gap_stop": True,
                "gap_target": gap_target,
            }

        if same_bar_both_touched:
            if same_bar_stop_first:
                return {
                    "exit_reason": "stop",
                    "raw_exit_price": min(open_price, stop_price),
                    "exit_assumption": "same_bar_stop_first_stop_exit",
                    "stop_touched": True,
                    "target_touched": True,
                    "same_bar_both_touched": True,
                    "gap_stop": gap_stop,
                    "gap_target": gap_target,
                }
            return {
                "exit_reason": "target",
                "raw_exit_price": max(open_price, target_price),
                "exit_assumption": "same_bar_target_first_target_exit",
                "stop_touched": True,
                "target_touched": True,
                "same_bar_both_touched": True,
                "gap_stop": gap_stop,
                "gap_target": gap_target,
            }

        if stop_touched:
            return {
                "exit_reason": "stop",
                "raw_exit_price": min(open_price, stop_price),
                "exit_assumption": "gap_down_stop_open_exit" if gap_stop else "intraday_stop_exit",
                "stop_touched": True,
                "target_touched": False,
                "same_bar_both_touched": False,
                "gap_stop": gap_stop,
                "gap_target": gap_target,
            }

        if target_touched:
            return {
                "exit_reason": "target",
                "raw_exit_price": max(open_price, target_price),
                "exit_assumption": "gap_up_target_open_exit" if gap_target else "intraday_target_exit",
                "stop_touched": False,
                "target_touched": True,
                "same_bar_both_touched": False,
                "gap_stop": gap_stop,
                "gap_target": gap_target,
            }

        if bar_index == max_holding_days - 1:
            return {
                "exit_reason": "max_holding",
                "raw_exit_price": close,
                "exit_assumption": "max_holding_close_exit",
                "stop_touched": False,
                "target_touched": False,
                "same_bar_both_touched": False,
                "gap_stop": False,
                "gap_target": False,
            }

        return None

    @staticmethod
    def _execution_cost_bps(execution_config: dict[str, object]) -> float:
        return float(execution_config["commission_bps"]) + float(execution_config["slippage_bps"])

    def _build_market_regime_cache(self, signal_dates: list[date]) -> dict[date, str]:
        index_df = self.repo.index_df()
        return self._market_regime_cache_from_index(index_df, signal_dates)

    @classmethod
    def _market_regime_cache_from_index(cls, index_df: pd.DataFrame, signal_dates: list[date]) -> dict[date, str]:
        unique_signal_dates = sorted(set(signal_dates))
        if not unique_signal_dates:
            return {}
        if index_df.empty:
            return {signal_date: "neutral" for signal_date in unique_signal_dates}

        regimes_by_index_date = cls._market_regimes_by_index_date(index_df)
        index_dates = sorted(regimes_by_index_date)
        if not index_dates:
            return {signal_date: "neutral" for signal_date in unique_signal_dates}

        cache: dict[date, str] = {}
        for signal_date in unique_signal_dates:
            position = bisect_right(index_dates, signal_date)
            cache[signal_date] = regimes_by_index_date[index_dates[position - 1]] if position else "neutral"
        return cache

    @classmethod
    def _market_regimes_by_index_date(cls, index_df: pd.DataFrame) -> dict[date, str]:
        df = index_df.sort_values("trade_date").reset_index(drop=True).copy()
        if df.empty:
            return {}
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        df["sma50"] = df["close"].rolling(50, min_periods=50).mean()
        df["sma200"] = df["close"].rolling(200, min_periods=200).mean()
        weekly_stats_by_date = cls._weekly_regime_stats_by_date(df)

        regimes: dict[date, str] = {}
        for index, row in df.iterrows():
            trade_date = row["trade_date"]
            if index + 1 < 200:
                regimes[trade_date] = "neutral"
                continue

            weekly_latest = weekly_stats_by_date[trade_date]
            weekly_sma30 = weekly_latest["weekly_sma30"]
            weekly_sma30_slope = weekly_latest["weekly_sma30_slope"]
            bull = (
                float(row["close"]) > float(row["sma200"])
                and float(row["sma50"]) > float(row["sma200"])
                and pd.notna(weekly_sma30)
                and pd.notna(weekly_sma30_slope)
                and float(weekly_latest["close"]) > float(weekly_sma30)
                and float(weekly_sma30_slope) > 0
            )
            bear = float(row["close"]) < float(row["sma200"]) and float(row["sma50"]) < float(row["sma200"])
            regimes[trade_date] = "bull" if bull else ("bear" if bear else "neutral")
        return regimes

    @staticmethod
    def _weekly_regime_stats_by_date(index_df: pd.DataFrame) -> dict[date, dict[str, float | None]]:
        stats_by_date: dict[date, dict[str, float | None]] = {}
        completed_week_closes: list[float] = []
        current_week_label: date | None = None
        current_week_close: float | None = None

        for _, row in index_df.iterrows():
            trade_date = row["trade_date"]
            week_label = pd.Timestamp(trade_date).to_period("W-FRI").end_time.date()
            if current_week_label is None:
                current_week_label = week_label
            elif week_label != current_week_label:
                if current_week_close is not None:
                    completed_week_closes.append(current_week_close)
                current_week_label = week_label

            current_week_close = float(row["close"])
            weekly_closes = [*completed_week_closes, current_week_close]
            weekly_sma30 = sum(weekly_closes[-30:]) / 30 if len(weekly_closes) >= 30 else None
            weekly_sma30_slope = None
            if len(weekly_closes) >= 34 and weekly_sma30 is not None:
                weekly_sma30_slope = weekly_sma30 - (sum(weekly_closes[-34:-4]) / 30)

            stats_by_date[trade_date] = {
                "close": current_week_close,
                "weekly_sma30": weekly_sma30,
                "weekly_sma30_slope": weekly_sma30_slope,
            }
        return stats_by_date

    def _market_regime_on(self, signal_date: date) -> str:
        return self._market_regime_cache_from_index(self.repo.index_df(), [signal_date]).get(signal_date, "neutral")

    @staticmethod
    def _metrics(
        trades: list[dict[str, object]],
        equity_curve: list[dict[str, object]],
        final_equity: float,
        initial_equity: float,
        exposure_days: int,
        total_days: int,
        liquidity_stats: dict[str, int] | None = None,
        realism_stats: dict[str, int] | None = None,
        execution_cost_bps: float = 0.0,
        annual_trading_days: int = 252,
        portfolio_stats: dict[str, object] | None = None,
    ) -> dict[str, object]:
        pnls = [float(trade["pnl"]) for trade in trades]
        wins = [pnl for pnl in pnls if pnl > 0]
        losses = [pnl for pnl in pnls if pnl < 0]
        total_return = final_equity / initial_equity - 1
        years = max(total_days / 365.25, 1 / 365.25)
        cagr = (final_equity / initial_equity) ** (1 / years) - 1 if final_equity > 0 else -1
        equity_values = [float(row["equity"]) for row in equity_curve]
        peaks = pd.Series(equity_values).cummax()
        drawdowns = pd.Series(equity_values) / peaks - 1
        max_drawdown = float(drawdowns.min()) if len(drawdowns) else 0.0
        equity_returns = pd.Series(equity_values, dtype="float64").pct_change().dropna()
        annualized_volatility = 0.0
        sharpe_ratio: float | None = None
        sortino_ratio: float | None = None
        if len(equity_returns) >= 2:
            return_std = float(equity_returns.std(ddof=0))
            annualized_volatility = return_std * math.sqrt(annual_trading_days)
            if return_std > 0:
                sharpe_ratio = float(equity_returns.mean()) / return_std * math.sqrt(annual_trading_days)
            downside_returns = equity_returns[equity_returns < 0]
            if len(downside_returns) >= 2:
                downside_std = float(downside_returns.std(ddof=0))
                if downside_std > 0:
                    sortino_ratio = float(equity_returns.mean()) / downside_std * math.sqrt(annual_trading_days)
        calmar_ratio = float(cagr) / abs(max_drawdown) if max_drawdown < 0 else None
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        total_estimated_cost = sum(float(trade.get("estimated_cost", 0)) for trade in trades)
        traded_notional = sum(
            int(trade.get("qty", 0) or 0)
            * (
                BacktestService._positive_float(trade.get("raw_entry_price", trade.get("entry_price", 0)))
                + BacktestService._positive_float(trade.get("raw_exit_price", trade.get("exit_price", 0)))
            )
            for trade in trades
        )
        turnover = traded_notional / initial_equity if initial_equity > 0 else 0.0
        portfolio_stats = portfolio_stats or {}
        return {
            "trade_count": len(trades),
            "trades": len(trades),
            "win_rate": round(len(wins) / len(trades), 4) if trades else 0.0,
            "total_return": round(total_return, 6),
            "cagr": round(float(cagr), 6),
            "max_drawdown": round(max_drawdown, 6),
            "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else (None if gross_profit == 0 else 999.0),
            "expectancy": round(sum(pnls) / len(pnls), 4) if pnls else 0.0,
            "avg_win": round(sum(wins) / len(wins), 4) if wins else 0.0,
            "avg_loss": round(sum(losses) / len(losses), 4) if losses else 0.0,
            "average_holding_days": round(sum(int(trade["holding_days"]) for trade in trades) / len(trades), 4) if trades else 0.0,
            "exposure": round(exposure_days / total_days, 6),
            "total_estimated_cost": round(total_estimated_cost, 2),
            "cost_bps": round(float(execution_cost_bps), 4),
            "annualized_volatility": round(float(annualized_volatility), 6),
            "sharpe_ratio": round(sharpe_ratio, 6) if sharpe_ratio is not None else None,
            "sortino_ratio": round(sortino_ratio, 6) if sortino_ratio is not None else None,
            "calmar_ratio": round(calmar_ratio, 6) if calmar_ratio is not None else None,
            "turnover": round(turnover, 6),
            "portfolio_turnover": round(float(portfolio_stats.get("portfolio_turnover", 0.0) or 0.0), 6),
            "average_active_positions": round(float(portfolio_stats.get("average_active_positions", 0.0) or 0.0), 4),
            "rebalance_count": int(portfolio_stats.get("rebalance_count", 0) or 0),
            "portfolio_constructor_used": bool(portfolio_stats.get("portfolio_constructor_used", False)),
            "portfolio_selection_mode": str(portfolio_stats.get("portfolio_selection_mode", "single_position")),
            "portfolio_top_n": int(portfolio_stats.get("portfolio_top_n", 0) or 0),
            "portfolio_max_positions": int(portfolio_stats.get("portfolio_max_positions", 0) or 0),
            "portfolio_weighting": str(portfolio_stats.get("portfolio_weighting", "not_applicable")),
            "portfolio_rebalance_frequency": str(portfolio_stats.get("portfolio_rebalance_frequency", "not_applicable")),
            "portfolio_allow_overlap_positions": bool(
                portfolio_stats.get("portfolio_allow_overlap_positions", False)
            ),
            "execution_requires_portfolio_constructor_signal_count": int(
                portfolio_stats.get("execution_requires_portfolio_constructor_signal_count", 0) or 0
            ),
            "regime_segment_return": "not_available_in_current_mvp",
            "partial_fill_count": int((liquidity_stats or {}).get("partial_fill_count", 0)),
            "no_fill_count": int((liquidity_stats or {}).get("no_fill_count", 0)),
            "total_unfilled_qty": int((liquidity_stats or {}).get("total_unfilled_qty", 0)),
            "adjusted_price_trade_count": int((realism_stats or {}).get("adjusted_price_trade_count", 0)),
            "forced_exit_count": int((realism_stats or {}).get("forced_exit_count", 0)),
            "delisted_exit_count": int((realism_stats or {}).get("delisted_exit_count", 0)),
            "missing_data_exit_count": int((realism_stats or {}).get("missing_data_exit_count", 0)),
        }
