from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import NormalDist, median
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_config
from backend.app.core.paths import REPORT_DIR
from backend.app.models.tables import (
    BacktestRun,
    BacktestTradeLedger,
    IndicatorSnapshot,
    ScreenResult,
    StrategyParameterSnapshot,
    SymbolMaster,
)
from backend.app.services.screener_service import ScreenerService
from backend.app.strategies.registry import get_available_strategy_registry
from backend.app.utils.hashing import stable_hash


NOT_AVAILABLE = "not_available_in_current_mvp"
SUMMARY_METRIC_KEYS = ("trade_count", "win_rate", "total_return", "max_drawdown")
WALK_FORWARD_METRIC_KEYS = (
    "trade_count",
    "win_rate",
    "total_return",
    "max_drawdown",
    "sharpe_ratio",
    "sortino_ratio",
    "calmar_ratio",
    "turnover",
    "average_active_positions",
    "rebalance_count",
)
DEFAULT_WALK_FORWARD_TRAIN_DAYS = 126
DEFAULT_WALK_FORWARD_TEST_DAYS = 21
DEFAULT_WALK_FORWARD_STEP_DAYS = 63
VALID_REBALANCE_FREQUENCIES = {"daily", "weekly", "monthly"}
PBO_MIN_STRATEGIES = 2
PBO_MIN_WINDOWS = 2
DSR_MIN_RETURN_SAMPLES = 4
DSR_MIN_CANDIDATES = 2
VALIDATION_FRAMEWORK_VERSION = "validation_scaffold_v0.1"


class ValidationScaffold:
    @staticmethod
    def metric_placeholders() -> dict[str, str]:
        """아직 계산하지 않는 상위 검증 metric을 명시 문자열로 반환한다."""
        return {
            "walk_forward": NOT_AVAILABLE,
            "pbo": NOT_AVAILABLE,
            "probability_of_backtest_overfitting": NOT_AVAILABLE,
            "deflated_sharpe_ratio": NOT_AVAILABLE,
            "factor_filter_attribution": NOT_AVAILABLE,
        }

    @classmethod
    def framework_summary(
        cls,
        walk_forward: dict[str, object] | None = None,
        overfitting: dict[str, object] | None = None,
        attribution: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """향후 walk-forward/PBO/DSR/attribution 확장을 위한 공통 scaffold를 반환한다."""
        return {
            "version": VALIDATION_FRAMEWORK_VERSION,
            "status": "scaffold",
            "walk_forward": walk_forward or cls.walk_forward_scaffold(),
            "overfitting": overfitting or cls.overfitting_metrics(),
            "attribution": attribution or cls.factor_filter_attribution(),
            "trade_ledger_schema": cls.trade_ledger_schema(),
        }

    @classmethod
    def strategy_payload(
        cls,
        strategy_name: str,
        walk_forward: dict[str, object] | None = None,
        overfitting: dict[str, object] | None = None,
        attribution: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """전략 단위 validation payload의 안정적인 placeholder shape를 반환한다."""
        return {
            "strategy_name": strategy_name,
            "walk_forward": walk_forward or cls.walk_forward_scaffold(strategy_name=strategy_name),
            "overfitting": overfitting or cls.overfitting_metrics(strategy_name=strategy_name),
            "attribution": attribution or cls.factor_filter_attribution(strategy_name=strategy_name),
        }

    @staticmethod
    def walk_forward_scaffold(strategy_name: str | None = None) -> dict[str, object]:
        return {
            "status": NOT_AVAILABLE,
            "metric": NOT_AVAILABLE,
            "strategy_name": strategy_name,
            "reason": "walk_forward_window_engine_not_implemented",
            "planned_inputs": [
                "strategy_name",
                "train_window_trading_days",
                "test_window_trading_days",
                "step_trading_days",
                "baseline_snapshot",
            ],
            "calculated": False,
        }

    @staticmethod
    def overfitting_metrics(strategy_name: str | None = None) -> dict[str, object]:
        return {
            "pbo": {
                "status": NOT_AVAILABLE,
                "value": NOT_AVAILABLE,
                "strategy_name": strategy_name,
                "reason": "insufficient_calculated_walk_forward_results",
                "method": "walk_forward_leave_one_window_cscv_lite",
                "input_shape": {
                    "candidate_source": "strategy_validation.walk_forward.windows",
                    "candidate_count": 0,
                    "window_count": 0,
                    "min_candidate_count": PBO_MIN_STRATEGIES,
                    "min_window_count": PBO_MIN_WINDOWS,
                    "performance_metric": "total_return",
                },
                "calculated": False,
            },
            "deflated_sharpe_ratio": {
                "status": NOT_AVAILABLE,
                "value": NOT_AVAILABLE,
                "strategy_name": strategy_name,
                "reason": "insufficient_oos_return_samples",
                "method": "bailey_lopez_de_prado_deflated_sharpe_lite",
                "input_shape": {
                    "multiple_testing": {
                        "candidate_source": "available_strategy_registry",
                        "candidate_count": 0,
                        "min_candidate_count": DSR_MIN_CANDIDATES,
                        "adjustment": "expected_max_sharpe_across_candidates",
                    },
                    "non_normal_adjustment": {
                        "return_series_source": "walk_forward_window_total_return",
                        "sample_count": 0,
                        "min_sample_count": DSR_MIN_RETURN_SAMPLES,
                        "skewness": None,
                        "kurtosis": None,
                    },
                },
                "calculated": False,
            },
        }

    @staticmethod
    def factor_filter_attribution(strategy_name: str | None = None) -> dict[str, object]:
        return {
            "status": NOT_AVAILABLE,
            "value": NOT_AVAILABLE,
            "strategy_name": strategy_name,
            "reason": "trade_outcome_to_factor_filter_join_not_implemented",
            "planned_dimensions": [
                "market_regime",
                "sector",
                "strategy_name",
                "pass_flags",
                "failed_conditions",
                "risk_flags",
            ],
            "calculated": False,
        }

    @staticmethod
    def trade_ledger_schema() -> dict[str, object]:
        return {
            "status": "available_minimal_backtest_ledger",
            "table": "backtest_trade_ledger",
            "scope": "backtest_and_report_analysis_only",
            "not_connected_to": [
                "orders",
                "paper_orders",
                "broker_adapters",
                "kis_order_routes",
                "live_trading",
            ],
            "minimum_fields": [
                {"name": "run_id", "type": "string", "required": True},
                {"name": "trade_index", "type": "integer", "required": True},
                {"name": "strategy_name", "type": "string", "required": True},
                {"name": "symbol", "type": "string", "required": True},
                {"name": "side", "type": "string", "required": True},
                {"name": "status", "type": "string", "required": True},
                {"name": "signal_date", "type": "date", "required": True},
                {"name": "entry_date", "type": "date", "required": True},
                {"name": "exit_date", "type": "date", "required": True},
                {"name": "qty", "type": "integer", "required": True},
                {"name": "entry_price", "type": "float", "required": True},
                {"name": "exit_price", "type": "float", "required": True},
                {"name": "pnl", "type": "float", "required": True},
                {"name": "return_pct", "type": "float", "required": True},
                {"name": "exit_reason", "type": "string", "required": True},
            ],
        }


class FactorFilterAttributionService:
    """저장형 trade ledger와 screen_results를 실제 join 가능한 범위에서 연결한다."""

    JOIN_KEYS = (
        "backtest_trade_ledger.signal_date = screen_results.trade_date",
        "backtest_trade_ledger.symbol = screen_results.symbol",
        "backtest_trade_ledger.strategy_name = screen_results.strategy_tag",
    )
    PNL_DIMENSIONS = ("strategy_name", "sector", "market_regime")

    def __init__(self, db: Session) -> None:
        self.db = db

    def calculate(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        strategy_names: list[str] | None = None,
        trades: list[BacktestTradeLedger] | None = None,
        screen_results: list[ScreenResult] | None = None,
    ) -> dict[str, object]:
        """실현 PnL attribution과 screen filter failure count를 분리해 계산한다."""
        selected_trades = (
            list(trades)
            if trades is not None
            else self._trade_ledger_for_window(start_date, end_date, strategy_names)
        )
        selected_screens = (
            list(screen_results)
            if screen_results is not None
            else self._screen_results_for_window(start_date, end_date, strategy_names)
        )
        join_screens = self._join_screen_results(selected_screens, selected_trades)
        sectors = self._symbol_sectors(
            {trade.symbol for trade in selected_trades} | {screen.symbol for screen in selected_screens}
        )
        screen_index = self._screen_index(join_screens)
        joined_rows = [
            self._joined_trade_row(trade, screen_index.get(self._trade_key(trade)), sectors)
            for trade in selected_trades
        ]
        joined_trade_count = sum(1 for row in joined_rows if row["join_status"] == "joined")
        unjoined_trade_count = len(joined_rows) - joined_trade_count
        resolved_strategy_names = self._resolve_strategy_names(strategy_names, joined_rows, selected_screens)
        pnl_rows = self._pnl_attribution_rows(joined_rows)
        failure_rows = self._screen_filter_failure_rows(selected_screens)
        status, reason = self._status(
            trade_count=len(selected_trades),
            screen_count=len(selected_screens),
            unjoined_trade_count=unjoined_trade_count,
        )
        calculated = status != NOT_AVAILABLE
        return {
            "status": status,
            "value": "calculated" if calculated else NOT_AVAILABLE,
            "calculated": calculated,
            "reason": reason,
            "basis": {
                "join_keys": list(self.JOIN_KEYS),
                "ledger_window_basis": "backtest_trade_ledger.exit_date",
                "screen_window_basis": "screen_results.trade_date",
                "ledger_source": "backtest_trade_ledger",
                "screen_source": "screen_results",
                "sector_source": "symbol_master.sector",
                "market_regime_source": "screen_results.metadata_json.market_regime",
                "unavailable_value": NOT_AVAILABLE,
                "scope": "backtest_and_report_analysis_only",
                "not_connected_to": ["orders", "paper_orders", "broker_adapters", "live_trading"],
            },
            "trade_count": len(selected_trades),
            "screen_result_count": len(selected_screens),
            "joined_trade_count": joined_trade_count,
            "unjoined_trade_count": unjoined_trade_count,
            "market_regime_unavailable_count": sum(
                1 for row in joined_rows if row["market_regime"] == NOT_AVAILABLE
            ),
            "sector_unavailable_count": sum(1 for row in joined_rows if row["sector"] == NOT_AVAILABLE),
            "realized_pnl_attribution": {
                "status": "calculated" if selected_trades else NOT_AVAILABLE,
                "value": "calculated" if selected_trades else NOT_AVAILABLE,
                "calculated": bool(selected_trades),
                "rows": pnl_rows,
            },
            "screen_filter_failure_counts": {
                "status": "calculated" if selected_screens else NOT_AVAILABLE,
                "value": "calculated" if selected_screens else NOT_AVAILABLE,
                "calculated": bool(selected_screens),
                "rows": failure_rows,
            },
            "strategies": self._strategy_payloads(resolved_strategy_names, joined_rows, selected_screens),
        }

    def _trade_ledger_for_window(
        self,
        start_date: date | None,
        end_date: date | None,
        strategy_names: list[str] | None,
    ) -> list[BacktestTradeLedger]:
        stmt = select(BacktestTradeLedger)
        if start_date is not None:
            stmt = stmt.where(BacktestTradeLedger.exit_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(BacktestTradeLedger.exit_date <= end_date)
        if strategy_names:
            stmt = stmt.where(BacktestTradeLedger.strategy_name.in_(strategy_names))
        return list(
            self.db.scalars(
                stmt.order_by(
                    BacktestTradeLedger.exit_date,
                    BacktestTradeLedger.run_id,
                    BacktestTradeLedger.trade_index,
                )
            ).all()
        )

    def _screen_results_for_window(
        self,
        start_date: date | None,
        end_date: date | None,
        strategy_names: list[str] | None,
    ) -> list[ScreenResult]:
        stmt = select(ScreenResult)
        if start_date is not None:
            stmt = stmt.where(ScreenResult.trade_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(ScreenResult.trade_date <= end_date)
        if strategy_names:
            stmt = stmt.where(ScreenResult.strategy_tag.in_(strategy_names))
        return list(
            self.db.scalars(
                stmt.order_by(
                    ScreenResult.trade_date,
                    ScreenResult.strategy_tag,
                    ScreenResult.symbol,
                    ScreenResult.id,
                )
            ).all()
        )

    def _join_screen_results(
        self,
        screen_results: list[ScreenResult],
        trades: list[BacktestTradeLedger],
    ) -> list[ScreenResult]:
        indexed = self._screen_index(screen_results)
        missing = [trade for trade in trades if self._trade_key(trade) not in indexed]
        if not missing:
            return screen_results
        dates = {trade.signal_date for trade in missing}
        symbols = {trade.symbol for trade in missing}
        strategies = {trade.strategy_name for trade in missing}
        if not dates or not symbols or not strategies:
            return screen_results
        additional = list(
            self.db.scalars(
                select(ScreenResult)
                .where(ScreenResult.trade_date.in_(dates))
                .where(ScreenResult.symbol.in_(symbols))
                .where(ScreenResult.strategy_tag.in_(strategies))
                .order_by(ScreenResult.trade_date, ScreenResult.strategy_tag, ScreenResult.symbol, ScreenResult.id)
            ).all()
        )
        combined = list(screen_results)
        combined_index = dict(indexed)
        for row in additional:
            key = self._screen_key(row)
            if key in combined_index:
                continue
            combined_index[key] = row
            combined.append(row)
        return combined

    def _symbol_sectors(self, symbols: set[str]) -> dict[str, str]:
        if not symbols:
            return {}
        rows = self.db.scalars(select(SymbolMaster).where(SymbolMaster.symbol.in_(symbols))).all()
        return {row.symbol: row.sector for row in rows if row.sector}

    @classmethod
    def _joined_trade_row(
        cls,
        trade: BacktestTradeLedger,
        screen: ScreenResult | None,
        sectors: dict[str, str],
    ) -> dict[str, object]:
        metadata = cls._json_object(getattr(screen, "metadata_json", None)) if screen is not None else {}
        risk_flags = cls._json_object(getattr(screen, "risk_flags_json", None)) if screen is not None else {}
        if not risk_flags:
            risk_flags = cls._as_dict(metadata.get("risk_flags"))
        return {
            "strategy_name": trade.strategy_name,
            "symbol": trade.symbol,
            "signal_date": trade.signal_date,
            "exit_date": trade.exit_date,
            "pnl": float(trade.pnl or 0),
            "return_pct": float(trade.return_pct or 0),
            "is_win": float(trade.pnl or 0) > 0,
            "join_status": "joined" if screen is not None else NOT_AVAILABLE,
            "sector": sectors.get(trade.symbol) or NOT_AVAILABLE,
            "market_regime": cls._market_regime_from_metadata(metadata),
            "pass_flags": cls._json_object(getattr(screen, "pass_flags", None)) if screen is not None else None,
            "failed_conditions": cls._json_list(getattr(screen, "failed_conditions", None)) if screen is not None else None,
            "risk_flags": risk_flags if screen is not None else None,
        }

    @classmethod
    def _pnl_attribution_rows(cls, joined_rows: list[dict[str, object]]) -> list[dict[str, object]]:
        if not joined_rows:
            return [
                cls._unavailable_pnl_row(
                    "strategy_name",
                    NOT_AVAILABLE,
                    "trade_ledger_unavailable",
                )
            ]

        rows: list[dict[str, object]] = []
        for dimension in cls.PNL_DIMENSIONS:
            rows.extend(cls._group_pnl_rows(joined_rows, dimension))
        rows.extend(cls._flag_pnl_rows(joined_rows, "pass_flag", "pass_flags"))
        rows.extend(cls._failed_condition_pnl_rows(joined_rows))
        rows.extend(cls._flag_pnl_rows(joined_rows, "risk_flag", "risk_flags"))
        return cls._sort_pnl_rows(rows)

    @classmethod
    def _group_pnl_rows(cls, joined_rows: list[dict[str, object]], dimension: str) -> list[dict[str, object]]:
        grouped: dict[str, list[dict[str, object]]] = {}
        for row in joined_rows:
            value = str(row.get(dimension) or NOT_AVAILABLE)
            grouped.setdefault(value, []).append(row)
        return [cls._pnl_row(dimension, value, rows) for value, rows in grouped.items()]

    @classmethod
    def _flag_pnl_rows(
        cls,
        joined_rows: list[dict[str, object]],
        dimension: str,
        field_name: str,
    ) -> list[dict[str, object]]:
        grouped: dict[str, list[dict[str, object]]] = {}
        unavailable_count = 0
        for row in joined_rows:
            flags = row.get(field_name)
            if not isinstance(flags, dict) or not flags:
                unavailable_count += 1
                continue
            for flag, value in flags.items():
                grouped.setdefault(f"{flag}={str(bool(value)).lower()}", []).append(row)
        rows = [cls._pnl_row(dimension, value, grouped_rows) for value, grouped_rows in grouped.items()]
        if unavailable_count:
            rows.append(
                cls._unavailable_pnl_row(
                    dimension,
                    NOT_AVAILABLE,
                    f"{field_name}_join_unavailable",
                    unavailable_count=unavailable_count,
                )
            )
        return rows

    @classmethod
    def _failed_condition_pnl_rows(cls, joined_rows: list[dict[str, object]]) -> list[dict[str, object]]:
        grouped: dict[str, list[dict[str, object]]] = {}
        unavailable_count = 0
        no_failed_count = 0
        for row in joined_rows:
            failed = row.get("failed_conditions")
            if not isinstance(failed, list):
                unavailable_count += 1
                continue
            if not failed:
                no_failed_count += 1
            for condition in failed:
                grouped.setdefault(str(condition), []).append(row)
        rows = [cls._pnl_row("failed_condition", value, grouped_rows) for value, grouped_rows in grouped.items()]
        if no_failed_count:
            rows.append(
                cls._pnl_row(
                    "failed_condition",
                    "no_failed_conditions",
                    [row for row in joined_rows if row.get("failed_conditions") == []],
                )
            )
        if unavailable_count:
            rows.append(
                cls._unavailable_pnl_row(
                    "failed_condition",
                    NOT_AVAILABLE,
                    "failed_conditions_join_unavailable",
                    unavailable_count=unavailable_count,
                )
            )
        return rows

    @classmethod
    def _pnl_row(cls, dimension: str, value: str, rows: list[dict[str, object]]) -> dict[str, object]:
        pnl = sum(float(row.get("pnl") or 0) for row in rows)
        trade_count = len(rows)
        joined_count = sum(1 for row in rows if row.get("join_status") == "joined")
        status = NOT_AVAILABLE if value == NOT_AVAILABLE else "calculated"
        return {
            "attribution_type": "realized_pnl",
            "dimension": dimension,
            "value": value,
            "trade_count": trade_count,
            "pnl": round(pnl, 2),
            "win_rate": cls._ratio(sum(1 for row in rows if bool(row.get("is_win"))), trade_count),
            "avg_return": cls._round_or_unavailable(
                sum(float(row.get("return_pct") or 0) for row in rows) / trade_count if trade_count else None
            ),
            "joined_trade_count": joined_count,
            "unavailable_count": trade_count if status == NOT_AVAILABLE else 0,
            "status": status,
            "reason": "dimension_value_unavailable" if status == NOT_AVAILABLE else None,
        }

    @staticmethod
    def _unavailable_pnl_row(
        dimension: str,
        value: str,
        reason: str,
        unavailable_count: int = 0,
    ) -> dict[str, object]:
        return {
            "attribution_type": "realized_pnl",
            "dimension": dimension,
            "value": value,
            "trade_count": 0,
            "pnl": NOT_AVAILABLE,
            "win_rate": NOT_AVAILABLE,
            "avg_return": NOT_AVAILABLE,
            "joined_trade_count": 0,
            "unavailable_count": unavailable_count,
            "status": NOT_AVAILABLE,
            "reason": reason,
        }

    @classmethod
    def _screen_filter_failure_rows(cls, screen_results: list[ScreenResult]) -> list[dict[str, object]]:
        if not screen_results:
            return [
                {
                    "attribution_type": "screen_filter_failure",
                    "strategy_name": NOT_AVAILABLE,
                    "filter": NOT_AVAILABLE,
                    "failed_count": 0,
                    "screened_count": 0,
                    "status": NOT_AVAILABLE,
                    "reason": "screen_results_unavailable",
                }
            ]

        screened_counts: dict[str, int] = {}
        failure_counts: dict[tuple[str, str], int] = {}
        for row in screen_results:
            screened_counts[row.strategy_tag] = screened_counts.get(row.strategy_tag, 0) + 1
            for condition in cls._json_list(row.failed_conditions):
                key = (row.strategy_tag, condition)
                failure_counts[key] = failure_counts.get(key, 0) + 1

        if not failure_counts:
            return [
                {
                    "attribution_type": "screen_filter_failure",
                    "strategy_name": "all",
                    "filter": "no_failed_conditions",
                    "failed_count": 0,
                    "screened_count": len(screen_results),
                    "status": "calculated",
                    "reason": None,
                }
            ]

        return [
            {
                "attribution_type": "screen_filter_failure",
                "strategy_name": strategy_name,
                "filter": condition,
                "failed_count": count,
                "screened_count": screened_counts.get(strategy_name, 0),
                "status": "calculated",
                "reason": None,
            }
            for (strategy_name, condition), count in sorted(
                failure_counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1])
            )
        ]

    @classmethod
    def _strategy_payloads(
        cls,
        strategy_names: list[str],
        joined_rows: list[dict[str, object]],
        screen_results: list[ScreenResult],
    ) -> dict[str, dict[str, object]]:
        payloads: dict[str, dict[str, object]] = {}
        for strategy_name in strategy_names:
            strategy_trades = [row for row in joined_rows if row.get("strategy_name") == strategy_name]
            strategy_screens = [row for row in screen_results if row.strategy_tag == strategy_name]
            trade_count = len(strategy_trades)
            screen_count = len(strategy_screens)
            unjoined_count = sum(1 for row in strategy_trades if row.get("join_status") != "joined")
            status, reason = cls._status(
                trade_count=trade_count,
                screen_count=screen_count,
                unjoined_trade_count=unjoined_count,
            )
            calculated = status != NOT_AVAILABLE
            payloads[strategy_name] = {
                "status": status,
                "value": "calculated" if calculated else NOT_AVAILABLE,
                "strategy_name": strategy_name,
                "calculated": calculated,
                "reason": reason,
                "trade_count": trade_count,
                "screen_result_count": screen_count,
                "joined_trade_count": trade_count - unjoined_count,
                "unjoined_trade_count": unjoined_count,
                "realized_pnl_attribution": {
                    "status": "calculated" if trade_count else NOT_AVAILABLE,
                    "value": "calculated" if trade_count else NOT_AVAILABLE,
                    "calculated": bool(trade_count),
                    "rows": cls._pnl_attribution_rows(strategy_trades),
                },
                "screen_filter_failure_counts": {
                    "status": "calculated" if screen_count else NOT_AVAILABLE,
                    "value": "calculated" if screen_count else NOT_AVAILABLE,
                    "calculated": bool(screen_count),
                    "rows": cls._screen_filter_failure_rows(strategy_screens),
                },
            }
        return payloads

    @staticmethod
    def _status(trade_count: int, screen_count: int, unjoined_trade_count: int) -> tuple[str, str | None]:
        if trade_count <= 0 and screen_count <= 0:
            return NOT_AVAILABLE, "trade_ledger_and_screen_results_unavailable"
        if trade_count <= 0:
            return "partial", "trade_ledger_unavailable"
        if screen_count <= 0:
            return "partial", "screen_results_unavailable"
        if unjoined_trade_count > 0:
            return "partial", "one_or_more_trade_rows_unjoined"
        return "calculated", None

    @classmethod
    def _resolve_strategy_names(
        cls,
        strategy_names: list[str] | None,
        joined_rows: list[dict[str, object]],
        screen_results: list[ScreenResult],
    ) -> list[str]:
        if strategy_names:
            return list(strategy_names)
        names = {str(row["strategy_name"]) for row in joined_rows}
        names.update(row.strategy_tag for row in screen_results)
        return sorted(names)

    @staticmethod
    def _trade_key(trade: BacktestTradeLedger) -> tuple[date, str, str]:
        return (trade.signal_date, trade.symbol, trade.strategy_name)

    @staticmethod
    def _screen_key(screen: ScreenResult) -> tuple[date, str, str]:
        return (screen.trade_date, screen.symbol, screen.strategy_tag)

    @classmethod
    def _screen_index(cls, screen_results: list[ScreenResult]) -> dict[tuple[date, str, str], ScreenResult]:
        index: dict[tuple[date, str, str], ScreenResult] = {}
        for row in sorted(screen_results, key=lambda item: int(item.id or 0)):
            index.setdefault(cls._screen_key(row), row)
        return index

    @staticmethod
    def _market_regime_from_metadata(metadata: dict[str, object]) -> str:
        for key in ("market_regime", "regime"):
            value = metadata.get(key)
            if isinstance(value, str) and value:
                return value
        context = metadata.get("strategy_context")
        if isinstance(context, dict):
            value = context.get("market_regime")
            if isinstance(value, str) and value:
                return value
        return NOT_AVAILABLE

    @staticmethod
    def _json_object(value: object) -> dict[str, object]:
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            parsed = json.loads(str(value))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _json_list(value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        if not value:
            return []
        try:
            parsed = json.loads(str(value))
        except json.JSONDecodeError:
            return []
        return [str(item) for item in parsed] if isinstance(parsed, list) else []

    @staticmethod
    def _as_dict(value: object) -> dict[str, object]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _ratio(numerator: int, denominator: int) -> float | str:
        if denominator <= 0:
            return NOT_AVAILABLE
        return round(numerator / denominator, 6)

    @staticmethod
    def _round_or_unavailable(value: float | None) -> float | str:
        if value is None:
            return NOT_AVAILABLE
        return round(float(value), 6)

    @staticmethod
    def _sort_pnl_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
        dimension_order = {
            "strategy_name": 0,
            "sector": 1,
            "market_regime": 2,
            "pass_flag": 3,
            "failed_condition": 4,
            "risk_flag": 5,
        }
        return sorted(
            rows,
            key=lambda row: (
                dimension_order.get(str(row.get("dimension")), 99),
                1 if row.get("status") == NOT_AVAILABLE else 0,
                str(row.get("value")),
            ),
        )


class ValidationBaselineComparator:
    def __init__(self, db: Session) -> None:
        self.db = db

    def resolve(
        self,
        baseline_run_id: str | None,
        baseline_snapshot: dict[str, object] | None,
    ) -> dict[str, object]:
        """run id 또는 snapshot 입력을 strategy별 baseline metric map으로 변환한다."""
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
                "metrics_by_strategy": self.snapshot_metrics(baseline_snapshot),
            }
        return {"status": "unspecified", "metrics_by_strategy": {}}

    @staticmethod
    def snapshot_metrics(snapshot: dict[str, object]) -> dict[str, dict[str, object]]:
        """여러 snapshot shape를 strategy별 metric map으로 정규화한다."""
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
    def metric_deltas(
        current_metrics: dict[str, object],
        baseline_metrics: dict[str, object] | None,
        baseline_status: str,
    ) -> dict[str, object]:
        """공통 summary metric delta를 재사용 가능한 방식으로 계산한다."""
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


class WalkForwardRunner:
    def __init__(self, db: Session, backtest_service: Any) -> None:
        self.db = db
        self.backtest_service = backtest_service
        self.backtest_config = getattr(backtest_service, "backtest_config", get_config("backtest"))

    def run(
        self,
        strategy_name: str,
        trading_dates: list[date],
        train_window_trading_days: int = DEFAULT_WALK_FORWARD_TRAIN_DAYS,
        test_window_trading_days: int = DEFAULT_WALK_FORWARD_TEST_DAYS,
        step_trading_days: int = DEFAULT_WALK_FORWARD_STEP_DAYS,
        rebalance_frequency: str | None = None,
    ) -> dict[str, object]:
        """고정 전략 설정으로 OOS test window만 실행하는 최소 walk-forward 요약을 계산한다."""
        train_days = self._positive_int(train_window_trading_days, "train_window_trading_days")
        test_days = self._positive_int(test_window_trading_days, "test_window_trading_days")
        step_days = self._positive_int(step_trading_days, "step_trading_days")
        resolved_rebalance = self._resolve_rebalance_frequency(rebalance_frequency)
        dates = sorted(set(trading_dates))
        minimum_required = train_days + test_days
        base_payload = self._base_payload(
            strategy_name=strategy_name,
            train_days=train_days,
            test_days=test_days,
            step_days=step_days,
            rebalance_frequency=resolved_rebalance,
            available_trading_days=len(dates),
            minimum_required_trading_days=minimum_required,
        )
        if len(dates) < minimum_required:
            return {
                **base_payload,
                "status": NOT_AVAILABLE,
                "metric": NOT_AVAILABLE,
                "calculated": False,
                "reason": "insufficient_indicator_trading_days",
                "window_count": 0,
                "calculated_window_count": 0,
                "unavailable_window_count": 0,
                "summary": None,
                "windows": [],
            }

        windows: list[dict[str, object]] = []
        start_index = 0
        window_index = 1
        while start_index + minimum_required <= len(dates):
            train_start_index = start_index
            train_end_index = start_index + train_days - 1
            test_start_index = start_index + train_days
            test_end_index = test_start_index + test_days - 1
            train_start = dates[train_start_index]
            train_end = dates[train_end_index]
            test_start = dates[test_start_index]
            test_end = dates[test_end_index]
            window = {
                "window_index": window_index,
                "train_start_date": train_start,
                "train_end_date": train_end,
                "test_start_date": test_start,
                "test_end_date": test_end,
                "train_trading_days": train_days,
                "test_trading_days": test_days,
                "calculated": False,
                "reason": None,
                "metrics": None,
            }
            try:
                result = self.backtest_service.run(
                    strategy_name,
                    start_date=test_start,
                    end_date=test_end,
                    rebalance_frequency=resolved_rebalance,
                    save=False,
                )
            except ValueError as exc:
                window["reason"] = str(exc)
            else:
                metrics = result.get("metrics") if isinstance(result, dict) else None
                if isinstance(metrics, dict):
                    window["calculated"] = True
                    window["metrics"] = self._metric_subset(metrics)
                else:
                    window["reason"] = "backtest_metrics_unavailable"
            windows.append(window)
            start_index += step_days
            window_index += 1

        calculated_windows = [window for window in windows if window["calculated"] is True]
        if not calculated_windows:
            return {
                **base_payload,
                "status": NOT_AVAILABLE,
                "metric": NOT_AVAILABLE,
                "calculated": False,
                "reason": "walk_forward_windows_unavailable",
                "window_count": len(windows),
                "calculated_window_count": 0,
                "unavailable_window_count": len(windows),
                "summary": None,
                "windows": windows,
            }

        unavailable_window_count = len(windows) - len(calculated_windows)
        return {
            **base_payload,
            "status": "partial" if unavailable_window_count else "calculated",
            "metric": "out_of_sample_summary",
            "calculated": True,
            "reason": "one_or_more_walk_forward_windows_unavailable" if unavailable_window_count else None,
            "window_count": len(windows),
            "calculated_window_count": len(calculated_windows),
            "unavailable_window_count": unavailable_window_count,
            "first_test_start_date": calculated_windows[0]["test_start_date"],
            "last_test_end_date": calculated_windows[-1]["test_end_date"],
            "summary": self._out_of_sample_summary(calculated_windows),
            "windows": windows,
        }

    def _base_payload(
        self,
        *,
        strategy_name: str,
        train_days: int,
        test_days: int,
        step_days: int,
        rebalance_frequency: str,
        available_trading_days: int,
        minimum_required_trading_days: int,
    ) -> dict[str, object]:
        return {
            "strategy_name": strategy_name,
            "train_window_trading_days": train_days,
            "test_window_trading_days": test_days,
            "step_trading_days": step_days,
            "rebalance_frequency": rebalance_frequency,
            "available_trading_days": available_trading_days,
            "minimum_required_trading_days": minimum_required_trading_days,
            "basis": "indicator_snapshot.trade_date",
            "execution_scope": "out_of_sample_test_windows_only",
        }

    @staticmethod
    def _positive_int(value: int, field_name: str) -> int:
        parsed = int(value)
        if parsed < 1:
            raise ValueError(f"{field_name} must be >= 1")
        return parsed

    def _resolve_rebalance_frequency(self, rebalance_frequency: str | None) -> str:
        portfolio_config = self.backtest_config.get("portfolio", {}) if isinstance(self.backtest_config, dict) else {}
        resolved = str(rebalance_frequency or portfolio_config.get("rebalance_frequency", "daily"))
        if resolved not in VALID_REBALANCE_FREQUENCIES:
            raise ValueError(f"지원하지 않는 rebalance_frequency입니다: {resolved}")
        return resolved

    @staticmethod
    def _metric_subset(metrics: dict[str, object]) -> dict[str, object]:
        return {key: metrics.get(key) for key in WALK_FORWARD_METRIC_KEYS}

    @classmethod
    def _out_of_sample_summary(cls, calculated_windows: list[dict[str, object]]) -> dict[str, object]:
        metric_rows = [
            window["metrics"]
            for window in calculated_windows
            if isinstance(window.get("metrics"), dict)
        ]
        total_returns = cls._numeric_values(metric_rows, "total_return")
        max_drawdowns = cls._numeric_values(metric_rows, "max_drawdown")
        trade_count = int(sum(cls._numeric_values(metric_rows, "trade_count")))
        weighted_win_rate = cls._weighted_average(metric_rows, "win_rate", "trade_count")
        return {
            "oos_window_count": len(metric_rows),
            "oos_trade_count": trade_count,
            "oos_weighted_win_rate": cls._round_or_none(weighted_win_rate),
            "oos_total_return": cls._round_or_none(cls._compound_returns(total_returns)),
            "oos_average_window_return": cls._round_or_none(cls._average(total_returns)),
            "oos_median_window_return": cls._round_or_none(median(total_returns) if total_returns else None),
            "oos_positive_window_rate": cls._round_or_none(
                sum(1 for value in total_returns if value > 0) / len(total_returns) if total_returns else None
            ),
            "oos_max_drawdown": cls._round_or_none(min(max_drawdowns) if max_drawdowns else None),
            "oos_average_sharpe_ratio": cls._round_or_none(cls._average(cls._numeric_values(metric_rows, "sharpe_ratio"))),
            "oos_average_turnover": cls._round_or_none(cls._average(cls._numeric_values(metric_rows, "turnover"))),
        }

    @staticmethod
    def _numeric_values(metric_rows: list[object], metric: str) -> list[float]:
        values: list[float] = []
        for row in metric_rows:
            if not isinstance(row, dict):
                continue
            value = row.get(metric)
            if isinstance(value, (int, float)):
                values.append(float(value))
        return values

    @staticmethod
    def _average(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    @staticmethod
    def _weighted_average(metric_rows: list[object], metric: str, weight_metric: str) -> float | None:
        numerator = 0.0
        denominator = 0.0
        for row in metric_rows:
            if not isinstance(row, dict):
                continue
            value = row.get(metric)
            weight = row.get(weight_metric)
            if isinstance(value, (int, float)) and isinstance(weight, (int, float)) and float(weight) > 0:
                numerator += float(value) * float(weight)
                denominator += float(weight)
        return numerator / denominator if denominator else None

    @staticmethod
    def _compound_returns(returns: list[float]) -> float | None:
        if not returns:
            return None
        compounded = 1.0
        for value in returns:
            compounded *= 1.0 + value
        return compounded - 1.0

    @staticmethod
    def _round_or_none(value: float | None, digits: int = 6) -> float | None:
        return round(float(value), digits) if value is not None else None


class OverfittingValidationCalculator:
    def calculate(
        self,
        walk_forward_by_strategy: dict[str, dict[str, object]],
    ) -> dict[str, object]:
        """walk-forward window 결과에서 PBO/DSR을 계산 가능한 범위로 산출한다."""
        pbo_framework, pbo_by_strategy = self._calculate_pbo(walk_forward_by_strategy)
        dsr_framework, dsr_by_strategy = self._calculate_deflated_sharpe_ratio(walk_forward_by_strategy)
        strategy_payloads = {
            strategy_name: {
                "pbo": pbo_by_strategy.get(
                    strategy_name,
                    self._pbo_unavailable("insufficient_strategy_candidate_history", strategy_name=strategy_name),
                ),
                "deflated_sharpe_ratio": dsr_by_strategy.get(
                    strategy_name,
                    self._dsr_unavailable("insufficient_oos_return_samples", strategy_name=strategy_name),
                ),
            }
            for strategy_name in walk_forward_by_strategy
        }
        return {
            "framework": {
                "pbo": pbo_framework,
                "deflated_sharpe_ratio": dsr_framework,
            },
            "strategies": strategy_payloads,
        }

    def _calculate_pbo(
        self,
        walk_forward_by_strategy: dict[str, dict[str, object]],
    ) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
        matrix, candidate_names, common_windows = self._pbo_matrix(walk_forward_by_strategy)
        input_shape = {
            "candidate_source": "strategy_validation.walk_forward.windows",
            "candidate_count": len(candidate_names),
            "strategy_count": len(walk_forward_by_strategy),
            "window_count": len(common_windows),
            "min_candidate_count": PBO_MIN_STRATEGIES,
            "min_window_count": PBO_MIN_WINDOWS,
            "split_method": "leave_one_window_out",
            "performance_metric": "total_return",
        }
        if len(candidate_names) < PBO_MIN_STRATEGIES:
            reason = "insufficient_strategy_candidates"
            return (
                self._pbo_unavailable(reason, input_shape=input_shape),
                {
                    strategy_name: self._pbo_unavailable(
                        reason,
                        strategy_name=strategy_name,
                        input_shape=input_shape,
                    )
                    for strategy_name in walk_forward_by_strategy
                },
            )
        if len(common_windows) < PBO_MIN_WINDOWS:
            reason = "insufficient_comparable_walk_forward_windows"
            return (
                self._pbo_unavailable(reason, input_shape=input_shape),
                {
                    strategy_name: self._pbo_unavailable(
                        reason,
                        strategy_name=strategy_name,
                        input_shape=input_shape,
                    )
                    for strategy_name in walk_forward_by_strategy
                },
            )

        splits: list[dict[str, object]] = []
        strategy_splits: dict[str, list[dict[str, object]]] = {name: [] for name in candidate_names}
        selected_counts: dict[str, int] = {name: 0 for name in candidate_names}
        for holdout_window in common_windows:
            in_sample_values = {
                strategy_name: self._average(
                    [value for window_index, value in matrix[strategy_name].items() if window_index != holdout_window]
                )
                for strategy_name in candidate_names
            }
            out_of_sample_values = {
                strategy_name: matrix[strategy_name][holdout_window] for strategy_name in candidate_names
            }
            in_sample_percentiles = self._rank_percentiles(in_sample_values)
            out_of_sample_percentiles = self._rank_percentiles(out_of_sample_values)
            selected_strategy = max(sorted(candidate_names), key=lambda name: in_sample_values[name])
            selected_counts[selected_strategy] += 1
            selected_percentile = out_of_sample_percentiles[selected_strategy]
            selected_logit = self._logit(selected_percentile)
            selected_overfit = selected_logit <= 0
            splits.append(
                {
                    "holdout_window_index": holdout_window,
                    "selected_strategy_name": selected_strategy,
                    "in_sample_metric": self._round(in_sample_values[selected_strategy]),
                    "out_of_sample_metric": self._round(out_of_sample_values[selected_strategy]),
                    "out_of_sample_rank": self._rank(out_of_sample_values, selected_strategy),
                    "out_of_sample_rank_percentile": self._round(selected_percentile),
                    "logit_rank": self._round(selected_logit),
                    "overfit": selected_overfit,
                }
            )
            for strategy_name in candidate_names:
                in_sample_rank_percentile = in_sample_percentiles[strategy_name]
                out_of_sample_rank_percentile = out_of_sample_percentiles[strategy_name]
                strategy_splits[strategy_name].append(
                    {
                        "holdout_window_index": holdout_window,
                        "in_sample_rank_percentile": self._round(in_sample_rank_percentile),
                        "out_of_sample_rank_percentile": self._round(out_of_sample_rank_percentile),
                        "rank_decay": self._round(in_sample_rank_percentile - out_of_sample_rank_percentile),
                        "overfit": in_sample_rank_percentile >= 0.5 and out_of_sample_rank_percentile <= 0.5,
                    }
                )

        pbo_value = sum(1 for split in splits if split["overfit"]) / len(splits)
        framework_payload = {
            "status": "calculated",
            "value": self._round(pbo_value),
            "probability_of_backtest_overfitting": self._round(pbo_value),
            "reason": None,
            "method": "walk_forward_leave_one_window_cscv_lite",
            "calculated": True,
            "input_shape": {
                **input_shape,
                "split_count": len(splits),
            },
            "selected_strategy_counts": selected_counts,
            "splits": splits,
        }
        strategy_payloads: dict[str, dict[str, object]] = {}
        for strategy_name in walk_forward_by_strategy:
            rows = strategy_splits.get(strategy_name, [])
            if not rows:
                strategy_payloads[strategy_name] = self._pbo_unavailable(
                    "insufficient_strategy_candidate_history",
                    strategy_name=strategy_name,
                    input_shape=input_shape,
                )
                continue
            strategy_value = sum(1 for row in rows if row["overfit"]) / len(rows)
            strategy_payloads[strategy_name] = {
                "status": "calculated",
                "value": self._round(strategy_value),
                "strategy_name": strategy_name,
                "reason": None,
                "method": "walk_forward_leave_one_window_rank_decay_lite",
                "calculated": True,
                "input_shape": {
                    **input_shape,
                    "split_count": len(rows),
                },
                "strategy_rank_decay_probability": self._round(strategy_value),
                "splits": rows,
            }
        return framework_payload, strategy_payloads

    def _calculate_deflated_sharpe_ratio(
        self,
        walk_forward_by_strategy: dict[str, dict[str, object]],
    ) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
        strategy_inputs: dict[str, dict[str, object]] = {}
        strategy_payloads: dict[str, dict[str, object]] = {}
        for strategy_name, walk_forward in walk_forward_by_strategy.items():
            returns, test_window_days = self._window_total_returns(walk_forward)
            input_shape = self._dsr_input_shape(
                candidate_count=0,
                sample_count=len(returns),
                skewness=None,
                kurtosis=None,
            )
            if walk_forward.get("calculated") is not True:
                strategy_payloads[strategy_name] = self._dsr_unavailable(
                    "insufficient_calculated_walk_forward_results",
                    strategy_name=strategy_name,
                    input_shape=input_shape,
                )
                continue
            if len(returns) < DSR_MIN_RETURN_SAMPLES:
                strategy_payloads[strategy_name] = self._dsr_unavailable(
                    "insufficient_oos_return_samples",
                    strategy_name=strategy_name,
                    input_shape=input_shape,
                )
                continue
            sample_std = self._sample_standard_deviation(returns)
            if sample_std is None or sample_std <= 0:
                strategy_payloads[strategy_name] = self._dsr_unavailable(
                    "zero_oos_return_variance",
                    strategy_name=strategy_name,
                    input_shape=input_shape,
                )
                continue
            sample_mean = self._average(returns)
            observed_sharpe = sample_mean / sample_std
            skewness = self._skewness(returns)
            kurtosis = self._kurtosis(returns)
            strategy_inputs[strategy_name] = {
                "returns": returns,
                "sample_count": len(returns),
                "sample_mean": sample_mean,
                "sample_standard_deviation": sample_std,
                "observed_sharpe_ratio": observed_sharpe,
                "skewness": skewness,
                "kurtosis": kurtosis,
                "test_window_trading_days": test_window_days,
            }

        candidate_count = len(strategy_inputs)
        if candidate_count < DSR_MIN_CANDIDATES:
            reason = "insufficient_multiple_testing_candidates"
            framework_input_shape = self._dsr_input_shape(candidate_count=candidate_count, sample_count=0)
            framework_payload = self._dsr_unavailable(reason, input_shape=framework_input_shape)
            for strategy_name in strategy_inputs:
                strategy_payloads[strategy_name] = self._dsr_unavailable(
                    reason,
                    strategy_name=strategy_name,
                    input_shape=self._dsr_input_shape(
                        candidate_count=candidate_count,
                        sample_count=int(strategy_inputs[strategy_name]["sample_count"]),
                        skewness=self._round(strategy_inputs[strategy_name]["skewness"]),
                        kurtosis=self._round(strategy_inputs[strategy_name]["kurtosis"]),
                    ),
                )
            return framework_payload, strategy_payloads

        candidate_sharpes = [float(row["observed_sharpe_ratio"]) for row in strategy_inputs.values()]
        candidate_sharpe_std = self._sample_standard_deviation(candidate_sharpes) or 0.0
        expected_max_sharpe = self._expected_max_sharpe(candidate_count, candidate_sharpe_std)
        calculated_payloads: dict[str, dict[str, object]] = {}
        for strategy_name, row in strategy_inputs.items():
            observed_sharpe = float(row["observed_sharpe_ratio"])
            skewness = float(row["skewness"])
            kurtosis = float(row["kurtosis"])
            sample_count = int(row["sample_count"])
            denominator = 1 - skewness * observed_sharpe + ((kurtosis - 1) / 4) * observed_sharpe**2
            input_shape = self._dsr_input_shape(
                candidate_count=candidate_count,
                sample_count=sample_count,
                skewness=self._round(skewness),
                kurtosis=self._round(kurtosis),
            )
            if denominator <= 0 or not math.isfinite(denominator):
                strategy_payloads[strategy_name] = self._dsr_unavailable(
                    "non_normal_adjustment_denominator_non_positive",
                    strategy_name=strategy_name,
                    input_shape=input_shape,
                )
                continue
            statistic = (observed_sharpe - expected_max_sharpe) * math.sqrt(sample_count - 1) / math.sqrt(denominator)
            dsr_value = NormalDist().cdf(statistic)
            payload = {
                "status": "calculated",
                "value": self._round(dsr_value),
                "deflated_sharpe_ratio": self._round(dsr_value),
                "strategy_name": strategy_name,
                "reason": None,
                "method": "bailey_lopez_de_prado_deflated_sharpe_lite",
                "calculated": True,
                "observed_sharpe_ratio": self._round(observed_sharpe),
                "expected_max_sharpe_ratio": self._round(expected_max_sharpe),
                "candidate_sharpe_standard_deviation": self._round(candidate_sharpe_std),
                "test_window_trading_days": row["test_window_trading_days"],
                "input_shape": input_shape,
            }
            calculated_payloads[strategy_name] = payload
            strategy_payloads[strategy_name] = payload

        if not calculated_payloads:
            reason = self._common_reason(strategy_payloads.values())
            return self._dsr_unavailable(reason, input_shape=self._dsr_input_shape(candidate_count=candidate_count)), strategy_payloads

        selected_strategy_name = max(
            sorted(calculated_payloads),
            key=lambda name: float(calculated_payloads[name]["observed_sharpe_ratio"]),
        )
        selected_payload = calculated_payloads[selected_strategy_name]
        framework_payload = {
            **selected_payload,
            "strategy_name": None,
            "selected_strategy_name": selected_strategy_name,
            "calculated_strategy_count": len(calculated_payloads),
            "unavailable_strategy_count": len(walk_forward_by_strategy) - len(calculated_payloads),
            "strategy_values": [
                {
                    "strategy_name": strategy_name,
                    "calculated": payload.get("calculated"),
                    "value": payload.get("value"),
                    "reason": payload.get("reason"),
                    "observed_sharpe_ratio": payload.get("observed_sharpe_ratio"),
                }
                for strategy_name, payload in strategy_payloads.items()
            ],
        }
        return framework_payload, strategy_payloads

    @classmethod
    def _pbo_matrix(
        cls,
        walk_forward_by_strategy: dict[str, dict[str, object]],
    ) -> tuple[dict[str, dict[int, float]], list[str], list[int]]:
        matrix: dict[str, dict[int, float]] = {}
        for strategy_name, walk_forward in walk_forward_by_strategy.items():
            if walk_forward.get("calculated") is not True:
                continue
            values_by_window: dict[int, float] = {}
            for window in walk_forward.get("windows", []):
                if not isinstance(window, dict) or window.get("calculated") is not True:
                    continue
                metrics = window.get("metrics")
                if not isinstance(metrics, dict):
                    continue
                value = cls._numeric(metrics.get("total_return"))
                window_index = cls._positive_window_index(window.get("window_index"))
                if value is not None and window_index is not None:
                    values_by_window[window_index] = value
            if values_by_window:
                matrix[strategy_name] = values_by_window
        candidate_names = sorted(matrix)
        if not candidate_names:
            return matrix, candidate_names, []
        common_windows = sorted(set.intersection(*(set(matrix[name]) for name in candidate_names)))
        return matrix, candidate_names, common_windows

    @classmethod
    def _window_total_returns(cls, walk_forward: dict[str, object]) -> tuple[list[float], int | None]:
        returns: list[float] = []
        test_window_days = walk_forward.get("test_window_trading_days")
        parsed_test_days = int(test_window_days) if isinstance(test_window_days, int) and test_window_days > 0 else None
        for window in walk_forward.get("windows", []):
            if not isinstance(window, dict) or window.get("calculated") is not True:
                continue
            metrics = window.get("metrics")
            if not isinstance(metrics, dict):
                continue
            value = cls._numeric(metrics.get("total_return"))
            if value is not None:
                returns.append(value)
            if parsed_test_days is None:
                candidate_days = window.get("test_trading_days")
                if isinstance(candidate_days, int) and candidate_days > 0:
                    parsed_test_days = candidate_days
        return returns, parsed_test_days

    @staticmethod
    def _pbo_unavailable(
        reason: str,
        *,
        strategy_name: str | None = None,
        input_shape: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload = ValidationScaffold.overfitting_metrics(strategy_name=strategy_name)["pbo"]
        if input_shape is not None:
            payload["input_shape"] = {
                **payload["input_shape"],  # type: ignore[index]
                **input_shape,
            }
        payload["reason"] = reason
        return payload

    @staticmethod
    def _dsr_unavailable(
        reason: str,
        *,
        strategy_name: str | None = None,
        input_shape: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload = ValidationScaffold.overfitting_metrics(strategy_name=strategy_name)["deflated_sharpe_ratio"]
        if input_shape is not None:
            payload["input_shape"] = input_shape
        payload["reason"] = reason
        return payload

    @staticmethod
    def _dsr_input_shape(
        *,
        candidate_count: int,
        sample_count: int = 0,
        skewness: float | None = None,
        kurtosis: float | None = None,
    ) -> dict[str, object]:
        return {
            "multiple_testing": {
                "candidate_source": "available_strategy_registry",
                "candidate_count": candidate_count,
                "min_candidate_count": DSR_MIN_CANDIDATES,
                "adjustment": "expected_max_sharpe_across_candidates",
            },
            "non_normal_adjustment": {
                "return_series_source": "walk_forward_window_total_return",
                "sample_count": sample_count,
                "min_sample_count": DSR_MIN_RETURN_SAMPLES,
                "skewness": skewness,
                "kurtosis": kurtosis,
            },
        }

    @staticmethod
    def _expected_max_sharpe(candidate_count: int, candidate_sharpe_std: float) -> float:
        if candidate_count <= 1 or candidate_sharpe_std <= 0:
            return 0.0
        normal = NormalDist()
        euler_gamma = 0.5772156649015329
        first_quantile = normal.inv_cdf(1 - 1 / candidate_count)
        second_quantile = normal.inv_cdf(1 - 1 / (candidate_count * math.e))
        return candidate_sharpe_std * ((1 - euler_gamma) * first_quantile + euler_gamma * second_quantile)

    @staticmethod
    def _rank(values: dict[str, float], strategy_name: str) -> int:
        selected_value = values[strategy_name]
        return 1 + sum(1 for value in values.values() if value > selected_value)

    @classmethod
    def _rank_percentiles(cls, values: dict[str, float]) -> dict[str, float]:
        candidate_count = len(values)
        if candidate_count <= 1:
            return {strategy_name: 1.0 for strategy_name in values}
        return {
            strategy_name: (candidate_count - cls._rank(values, strategy_name)) / (candidate_count - 1)
            for strategy_name in values
        }

    @staticmethod
    def _logit(value: float) -> float:
        bounded = min(max(value, 1e-6), 1 - 1e-6)
        return math.log(bounded / (1 - bounded))

    @staticmethod
    def _numeric(value: object) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None

    @staticmethod
    def _positive_window_index(value: object) -> int | None:
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value if value > 0 else None

    @classmethod
    def _average(cls, values: list[float]) -> float:
        return sum(values) / len(values)

    @classmethod
    def _sample_standard_deviation(cls, values: list[float]) -> float | None:
        if len(values) < 2:
            return None
        average = cls._average(values)
        variance = sum((value - average) ** 2 for value in values) / (len(values) - 1)
        return math.sqrt(variance)

    @classmethod
    def _population_standard_deviation(cls, values: list[float]) -> float | None:
        if not values:
            return None
        average = cls._average(values)
        variance = sum((value - average) ** 2 for value in values) / len(values)
        return math.sqrt(variance)

    @classmethod
    def _skewness(cls, values: list[float]) -> float:
        average = cls._average(values)
        std = cls._population_standard_deviation(values)
        if std is None or std <= 0:
            return 0.0
        return sum(((value - average) / std) ** 3 for value in values) / len(values)

    @classmethod
    def _kurtosis(cls, values: list[float]) -> float:
        average = cls._average(values)
        std = cls._population_standard_deviation(values)
        if std is None or std <= 0:
            return 3.0
        return sum(((value - average) / std) ** 4 for value in values) / len(values)

    @staticmethod
    def _round(value: object, digits: int = 6) -> float | None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None
        parsed = float(value)
        return round(parsed, digits) if math.isfinite(parsed) else None

    @staticmethod
    def _common_reason(payloads: object) -> str:
        reasons = {
            str(payload.get("reason"))
            for payload in payloads
            if isinstance(payload, dict) and payload.get("reason")
        }
        if len(reasons) == 1:
            return next(iter(reasons))
        return "overfitting_metric_unavailable"


class StrategyParameterSnapshotService:
    def __init__(self, db: Session, strategy_config: dict[str, Any] | None = None) -> None:
        self.db = db
        self.strategy_config = strategy_config or get_config("strategies")

    def save_current_snapshots(
        self,
        snapshot_date: date | None = None,
        effective_date: date | None = None,
        strategy_names: list[str] | None = None,
    ) -> list[StrategyParameterSnapshot]:
        """현재 strategy config를 strategy별 parameter snapshot row로 저장한다."""
        target_snapshot_date = snapshot_date or date.today()
        target_effective_date = effective_date or target_snapshot_date
        payloads = self.current_parameter_payloads(strategy_names=strategy_names)
        rows: list[StrategyParameterSnapshot] = []
        for strategy_name, parameter_payload in payloads.items():
            config_hash = self.parameter_config_hash(strategy_name, parameter_payload)
            parameter_json = self._json_dumps(parameter_payload)
            existing = self.db.scalar(
                select(StrategyParameterSnapshot)
                .where(StrategyParameterSnapshot.strategy_name == strategy_name)
                .where(StrategyParameterSnapshot.snapshot_date == target_snapshot_date)
                .where(StrategyParameterSnapshot.effective_date == target_effective_date)
                .where(StrategyParameterSnapshot.config_hash == config_hash)
                .limit(1)
            )
            if existing is None:
                existing = StrategyParameterSnapshot(
                    strategy_name=strategy_name,
                    config_hash=config_hash,
                    snapshot_date=target_snapshot_date,
                    effective_date=target_effective_date,
                    parameter_json=parameter_json,
                )
                self.db.add(existing)
            else:
                existing.parameter_json = parameter_json
            rows.append(existing)
        self.db.commit()
        for row in rows:
            self.db.refresh(row)
        return rows

    def latest_snapshots(
        self,
        as_of: date | None = None,
        strategy_names: list[str] | None = None,
    ) -> dict[str, StrategyParameterSnapshot]:
        """기준일 이전의 최신 strategy parameter snapshot을 strategy별로 반환한다."""
        selected_strategy_names = self._resolve_strategy_names(strategy_names)
        snapshots: dict[str, StrategyParameterSnapshot] = {}
        for strategy_name in selected_strategy_names:
            stmt = select(StrategyParameterSnapshot).where(StrategyParameterSnapshot.strategy_name == strategy_name)
            if as_of is not None:
                stmt = stmt.where(StrategyParameterSnapshot.snapshot_date <= as_of).where(
                    StrategyParameterSnapshot.effective_date <= as_of
                )
            snapshot = self.db.scalar(
                stmt.order_by(
                    StrategyParameterSnapshot.effective_date.desc(),
                    StrategyParameterSnapshot.snapshot_date.desc(),
                    StrategyParameterSnapshot.created_at.desc(),
                    StrategyParameterSnapshot.id.desc(),
                ).limit(1)
            )
            if snapshot is not None:
                snapshots[strategy_name] = snapshot
        return snapshots

    def parameter_drift_check(
        self,
        as_of: date | None = None,
        strategy_names: list[str] | None = None,
    ) -> dict[str, object]:
        """현재 config와 최신 snapshot을 비교해 strategy parameter drift payload를 반환한다."""
        target_date = as_of or date.today()
        current_payloads = self.current_parameter_payloads(strategy_names=strategy_names)
        snapshots = self.latest_snapshots(as_of=target_date, strategy_names=list(current_payloads))
        strategy_rows: list[dict[str, object]] = []
        changed_keys: list[str] = []
        snapshot_dates: set[date] = set()
        effective_dates: set[date] = set()
        drifted_parameter_count = 0
        drifted_strategy_count = 0
        unchanged_keys_count = 0
        missing_snapshot_count = 0
        config_hash_changed_count = 0
        config_hash_unchanged_count = 0

        for strategy_name, current_payload in current_payloads.items():
            current_hash = self.parameter_config_hash(strategy_name, current_payload)
            snapshot = snapshots.get(strategy_name)
            if snapshot is None:
                missing_snapshot_count += 1
                strategy_rows.append(
                    {
                        "strategy_name": strategy_name,
                        "status": NOT_AVAILABLE,
                        "reason": "strategy_parameter_snapshot_not_found",
                        "current_config_hash": current_hash,
                        "snapshot_config_hash": None,
                        "snapshot_date": None,
                        "effective_date": None,
                        "drift_count": 0,
                        "drifted_parameters": [],
                        "changed_keys": [],
                        "unchanged_keys_count": 0,
                        "config_hash_changed": None,
                        "config_hash_diff": NOT_AVAILABLE,
                    }
                )
                continue

            snapshot_payload = self._loads_snapshot_payload(snapshot.parameter_json)
            diffs = self._parameter_diffs(snapshot_payload, current_payload)
            row_changed_keys = [str(diff["parameter"]) for diff in diffs if isinstance(diff, dict) and diff.get("parameter")]
            row_unchanged_keys_count = self._unchanged_keys_count(snapshot_payload, current_payload)
            drift_count = len(diffs)
            config_hash_changed = current_hash != snapshot.config_hash
            drifted_parameter_count += drift_count
            unchanged_keys_count += row_unchanged_keys_count
            changed_keys.extend(f"{strategy_name}:{key}" for key in row_changed_keys)
            snapshot_dates.add(snapshot.snapshot_date)
            effective_dates.add(snapshot.effective_date)
            if config_hash_changed:
                config_hash_changed_count += 1
            else:
                config_hash_unchanged_count += 1
            if drift_count:
                drifted_strategy_count += 1
            strategy_rows.append(
                {
                    "strategy_name": strategy_name,
                    "status": "drift_detected" if drift_count else "no_drift",
                    "reason": None,
                    "current_config_hash": current_hash,
                    "snapshot_config_hash": snapshot.config_hash,
                    "snapshot_date": snapshot.snapshot_date,
                    "effective_date": snapshot.effective_date,
                    "drift_count": drift_count,
                    "drifted_parameters": diffs,
                    "changed_keys": row_changed_keys,
                    "unchanged_keys_count": row_unchanged_keys_count,
                    "config_hash_changed": config_hash_changed,
                    "config_hash_diff": "changed" if config_hash_changed else "unchanged",
                }
            )

        compared_strategy_count = len(current_payloads) - missing_snapshot_count
        if compared_strategy_count <= 0:
            status = NOT_AVAILABLE
            reason = "strategy_parameter_snapshot_not_found"
            comparison_available = False
            history_source = NOT_AVAILABLE
        elif drifted_strategy_count:
            status = "drift_detected"
            reason = None
            comparison_available = True
            history_source = "strategy_parameter_snapshots"
        elif missing_snapshot_count:
            status = "partial_snapshot_history"
            reason = "one_or_more_strategy_snapshots_missing"
            comparison_available = True
            history_source = "strategy_parameter_snapshots"
        else:
            status = "no_drift"
            reason = None
            comparison_available = True
            history_source = "strategy_parameter_snapshots"

        return {
            "status": status,
            "reason": reason,
            "comparison_available": comparison_available,
            "as_of": target_date,
            "history_source": history_source,
            "strategy_count": len(current_payloads),
            "compared_strategy_count": compared_strategy_count,
            "missing_snapshot_count": missing_snapshot_count,
            "drifted_strategy_count": drifted_strategy_count,
            "drifted_parameter_count": drifted_parameter_count,
            "changed_keys": changed_keys,
            "unchanged_keys_count": unchanged_keys_count,
            "snapshot_dates": sorted(snapshot_dates),
            "effective_dates": sorted(effective_dates),
            "current_config_hash": stable_hash({"strategies": current_payloads}),
            "config_hash_diff": {
                "changed_count": config_hash_changed_count,
                "unchanged_count": config_hash_unchanged_count,
                "unavailable_count": missing_snapshot_count,
            },
            "strategies": strategy_rows,
        }

    def current_parameter_payloads(self, strategy_names: list[str] | None = None) -> dict[str, dict[str, object]]:
        """현재 config에서 비교 가능한 strategy별 parameter payload를 만든다."""
        return {
            strategy_name: {
                "common": self.strategy_config.get("common", {}),
                "strategy": self.strategy_config.get(strategy_name, {}),
            }
            for strategy_name in self._resolve_strategy_names(strategy_names)
        }

    @staticmethod
    def parameter_config_hash(strategy_name: str, parameter_payload: dict[str, object]) -> str:
        """strategy 이름과 parameter payload를 안정적인 config hash로 변환한다."""
        return stable_hash({"strategy_name": strategy_name, "parameters": parameter_payload})

    def _resolve_strategy_names(self, strategy_names: list[str] | None) -> list[str]:
        available_strategy_names = list(get_available_strategy_registry(self.strategy_config))
        selected = strategy_names or available_strategy_names
        unknown = [name for name in selected if name not in available_strategy_names]
        if unknown:
            raise ValueError(f"지원하지 않는 전략입니다: {', '.join(sorted(unknown))}")
        return list(selected)

    @staticmethod
    def _json_dumps(payload: dict[str, object]) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)

    @staticmethod
    def _loads_snapshot_payload(parameter_json: str) -> dict[str, object]:
        try:
            loaded = json.loads(parameter_json)
        except json.JSONDecodeError:
            return {"_invalid_parameter_json": parameter_json}
        return loaded if isinstance(loaded, dict) else {"_invalid_parameter_json": loaded}

    @classmethod
    def _parameter_diffs(
        cls,
        snapshot_payload: object,
        current_payload: object,
        prefix: str = "",
    ) -> list[dict[str, object]]:
        diffs: list[dict[str, object]] = []
        if isinstance(snapshot_payload, dict) and isinstance(current_payload, dict):
            keys = sorted(set(snapshot_payload) | set(current_payload))
            for key in keys:
                path = f"{prefix}.{key}" if prefix else str(key)
                if key not in snapshot_payload:
                    diffs.append(
                        {
                            "parameter": path,
                            "change": "added",
                            "snapshot": None,
                            "current": current_payload[key],
                        }
                    )
                elif key not in current_payload:
                    diffs.append(
                        {
                            "parameter": path,
                            "change": "removed",
                            "snapshot": snapshot_payload[key],
                            "current": None,
                        }
                    )
                else:
                    diffs.extend(cls._parameter_diffs(snapshot_payload[key], current_payload[key], path))
            return diffs
        if snapshot_payload != current_payload:
            return [
                {
                    "parameter": prefix,
                    "change": "modified",
                    "snapshot": snapshot_payload,
                    "current": current_payload,
                }
            ]
        return diffs

    @classmethod
    def _unchanged_keys_count(cls, snapshot_payload: object, current_payload: object) -> int:
        snapshot_values = cls._parameter_path_values(snapshot_payload)
        current_values = cls._parameter_path_values(current_payload)
        return sum(
            1
            for key in set(snapshot_values) & set(current_values)
            if snapshot_values[key] == current_values[key]
        )

    @classmethod
    def _parameter_path_values(cls, payload: object, prefix: str = "") -> dict[str, object]:
        if isinstance(payload, dict):
            if not payload and prefix:
                return {prefix: {}}
            values: dict[str, object] = {}
            for key, value in payload.items():
                path = f"{prefix}.{key}" if prefix else str(key)
                values.update(cls._parameter_path_values(value, path))
            return values
        return {prefix or "value": payload}


class StrategyValidationService:
    def __init__(self, db: Session, backtest_service: Any | None = None) -> None:
        self.db = db
        if backtest_service is None:
            from backend.app.services.backtest_service import BacktestService

            backtest_service = BacktestService(db)
        self.backtest_service = backtest_service
        self.strategy_config = getattr(backtest_service, "strategy_config", get_config("strategies"))
        self.strategies = getattr(
            backtest_service,
            "strategies",
            get_available_strategy_registry(self.strategy_config),
        )
        self.baseline_comparator = ValidationBaselineComparator(db)
        self.walk_forward_runner = WalkForwardRunner(db, backtest_service)

    def strategy_summary(
        self,
        lookback_days: int = 252,
        baseline_run_id: str | None = None,
        baseline_snapshot: dict[str, object] | None = None,
        walk_forward_train_days: int = DEFAULT_WALK_FORWARD_TRAIN_DAYS,
        walk_forward_test_days: int = DEFAULT_WALK_FORWARD_TEST_DAYS,
        walk_forward_step_days: int = DEFAULT_WALK_FORWARD_STEP_DAYS,
        walk_forward_rebalance_frequency: str | None = None,
    ) -> dict[str, object]:
        """전략별 validation summary를 계산하고 저장과 무관한 payload만 반환한다."""
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
        baseline = self.baseline_comparator.resolve(baseline_run_id, baseline_snapshot)

        backtest_by_strategy: dict[str, dict[str, object]] = {}
        walk_forward_by_strategy: dict[str, dict[str, object]] = {}
        for strategy_name in strategy_names:
            backtest_by_strategy[strategy_name] = self._strategy_backtest_summary(
                strategy_name=strategy_name,
                start_date=window_start,
                end_date=window_end,
            )
            walk_forward_summary = self.walk_forward_runner.run(
                strategy_name=strategy_name,
                trading_dates=indicator_dates,
                train_window_trading_days=walk_forward_train_days,
                test_window_trading_days=walk_forward_test_days,
                step_trading_days=walk_forward_step_days,
                rebalance_frequency=walk_forward_rebalance_frequency,
            )
            walk_forward_by_strategy[strategy_name] = walk_forward_summary

        overfitting_result = OverfittingValidationCalculator().calculate(walk_forward_by_strategy)
        overfitting_by_strategy = overfitting_result["strategies"]
        attribution_summary = (
            FactorFilterAttributionService(self.db).calculate(
                start_date=window_start,
                end_date=window_end,
                strategy_names=strategy_names,
            )
            if window_start is not None and window_end is not None
            else FactorFilterAttributionService(self.db).calculate(
                strategy_names=strategy_names,
                trades=[],
                screen_results=[],
            )
        )

        strategy_summaries: list[dict[str, object]] = []
        for strategy_name in strategy_names:
            backtest_summary = backtest_by_strategy[strategy_name]
            walk_forward_summary = walk_forward_by_strategy[strategy_name]
            baseline_metrics = baseline["metrics_by_strategy"].get(strategy_name)  # type: ignore[index]
            baseline_status = str(baseline["status"])
            if baseline_metrics is None and baseline_status in {"run_id", "snapshot"}:
                baseline_status = "unavailable_for_strategy"
            strategy_summaries.append(
                {
                    "strategy_name": strategy_name,
                    "screener": screener_by_strategy.get(strategy_name, self._empty_screener_row(strategy_name)),
                    "backtest": backtest_summary,
                    "delta": self.baseline_comparator.metric_deltas(
                        backtest_summary,
                        baseline_metrics if isinstance(baseline_metrics, dict) else None,
                        baseline_status,
                    ),
                    "validation": ValidationScaffold.strategy_payload(
                        strategy_name,
                        walk_forward=walk_forward_summary,
                        overfitting=overfitting_by_strategy.get(strategy_name)
                        if isinstance(overfitting_by_strategy, dict)
                        else None,
                        attribution=self._strategy_attribution_payload(attribution_summary, strategy_name),
                    ),
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
                "comparison_metric_keys": list(SUMMARY_METRIC_KEYS),
            },
            "validation_framework": ValidationScaffold.framework_summary(
                walk_forward=self._walk_forward_framework_summary(
                    walk_forward_by_strategy=walk_forward_by_strategy,
                    train_window_trading_days=walk_forward_train_days,
                    test_window_trading_days=walk_forward_test_days,
                    step_trading_days=walk_forward_step_days,
                    rebalance_frequency=walk_forward_rebalance_frequency,
                ),
                overfitting=overfitting_result["framework"]
                if isinstance(overfitting_result.get("framework"), dict)
                else None,
                attribution=attribution_summary,
            ),
            "strategies": strategy_summaries,
        }

    @staticmethod
    def _strategy_attribution_payload(
        attribution_summary: dict[str, object],
        strategy_name: str,
    ) -> dict[str, object]:
        strategies = attribution_summary.get("strategies")
        if isinstance(strategies, dict):
            payload = strategies.get(strategy_name)
            if isinstance(payload, dict):
                return payload
        return ValidationScaffold.factor_filter_attribution(strategy_name=strategy_name)

    def _walk_forward_framework_summary(
        self,
        *,
        walk_forward_by_strategy: dict[str, dict[str, object]],
        train_window_trading_days: int,
        test_window_trading_days: int,
        step_trading_days: int,
        rebalance_frequency: str | None,
    ) -> dict[str, object]:
        calculated_rows = [
            row for row in walk_forward_by_strategy.values() if row.get("calculated") is True
        ]
        unavailable_rows = [
            row for row in walk_forward_by_strategy.values() if row.get("calculated") is not True
        ]
        if calculated_rows:
            status = "partial" if unavailable_rows else "calculated"
            reason = "one_or_more_strategy_walk_forward_unavailable" if unavailable_rows else None
            calculated = True
            metric = "out_of_sample_summary"
        else:
            status = NOT_AVAILABLE
            reason = self._common_unavailable_reason(unavailable_rows)
            calculated = False
            metric = NOT_AVAILABLE
        resolved_rebalance = (
            calculated_rows[0].get("rebalance_frequency")
            if calculated_rows
            else unavailable_rows[0].get("rebalance_frequency")
            if unavailable_rows
            else rebalance_frequency
        )
        return {
            "status": status,
            "metric": metric,
            "calculated": calculated,
            "reason": reason,
            "train_window_trading_days": int(train_window_trading_days),
            "test_window_trading_days": int(test_window_trading_days),
            "step_trading_days": int(step_trading_days),
            "rebalance_frequency": resolved_rebalance,
            "strategy_count": len(walk_forward_by_strategy),
            "calculated_strategy_count": len(calculated_rows),
            "unavailable_strategy_count": len(unavailable_rows),
            "strategy_summaries": [
                {
                    "strategy_name": strategy_name,
                    "calculated": row.get("calculated"),
                    "status": row.get("status"),
                    "reason": row.get("reason"),
                    "summary": row.get("summary"),
                }
                for strategy_name, row in walk_forward_by_strategy.items()
            ],
        }

    @staticmethod
    def _common_unavailable_reason(rows: list[dict[str, object]]) -> str:
        reasons = {str(row.get("reason")) for row in rows if row.get("reason")}
        if len(reasons) == 1:
            return next(iter(reasons))
        return "walk_forward_unavailable"

    def _latest_indicator_dates(self, lookback_days: int) -> list[date]:
        provider = getattr(self.backtest_service, "_latest_indicator_dates", None)
        if callable(provider):
            return provider(lookback_days)
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
                **ValidationScaffold.metric_placeholders(),
            }
        try:
            result = self.backtest_service.run(strategy_name, start_date=start_date, end_date=end_date, save=False)
        except ValueError as exc:
            return {
                "summary_source": "computed_available_window",
                "error": str(exc),
                **{metric: None for metric in SUMMARY_METRIC_KEYS},
                **ValidationScaffold.metric_placeholders(),
            }
        metrics = result["metrics"]
        return {
            "summary_source": "computed_available_window",
            "error": None,
            **{metric: metrics.get(metric) for metric in SUMMARY_METRIC_KEYS},  # type: ignore[union-attr]
            **ValidationScaffold.metric_placeholders(),
        }

    @staticmethod
    def _empty_screener_row(strategy_name: str) -> dict[str, object]:
        return {
            "strategy_name": strategy_name,
            "evaluated_count": 0,
            "pass_count": 0,
            "pass_rate": None,
            "evaluated_trading_days": 0,
            "window_trading_days": 0,
            "window_start": None,
            "window_end": None,
        }


class ValidationReportService:
    def write_strategy_validation_summary(
        self,
        summary: dict[str, object],
        lookback_days: int = 252,
    ) -> dict[str, object]:
        """strategy validation summary를 공통 JSON report 포맷으로 저장한다."""
        path = REPORT_DIR / f"strategy_validation_{int(lookback_days)}d.json"
        return self.write_json_report(
            summary,
            path=path,
            report_kind="strategy_validation_summary",
            required_fields=[
                "checkpoint",
                "command",
                "result",
                "summary_endpoint",
                "report_path",
                "baseline_status",
                "safety_contract",
                "walk_forward",
                "overfitting",
                "unavailable_metrics",
            ],
        )

    def write_json_report(
        self,
        payload: dict[str, object],
        *,
        path: Path,
        report_kind: str,
        required_fields: list[str],
    ) -> dict[str, object]:
        """향후 walk-forward 결과도 재사용할 수 있는 JSON report 저장 포맷이다."""
        report_payload = {
            **payload,
            "generated_at": datetime.now(UTC).isoformat(),
            "report": {
                "format": "json",
                "kind": report_kind,
                "path": str(path),
                "filename": path.name,
            },
            "validation_documentation_format": {
                "docs_file": "docs/VALIDATION.md",
                "required_fields": required_fields,
            },
        }
        content = json.dumps(report_payload, ensure_ascii=False, indent=2, default=str)
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(content + "\n", encoding="utf-8")
        report_payload["report"] = {
            **report_payload["report"],  # type: ignore[arg-type]
            "bytes": len(content.encode("utf-8")),
        }
        return report_payload
