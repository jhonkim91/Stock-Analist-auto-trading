from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_config
from backend.app.core.paths import REPORT_DIR
from backend.app.models.tables import BacktestRun, IndicatorSnapshot
from backend.app.services.screener_service import ScreenerService
from backend.app.strategies.registry import get_available_strategy_registry


NOT_AVAILABLE = "not_available_in_current_mvp"
SUMMARY_METRIC_KEYS = ("trade_count", "win_rate", "total_return", "max_drawdown")
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
    def framework_summary(cls) -> dict[str, object]:
        """향후 walk-forward/PBO/DSR/attribution 확장을 위한 공통 scaffold를 반환한다."""
        return {
            "version": VALIDATION_FRAMEWORK_VERSION,
            "status": "scaffold",
            "walk_forward": cls.walk_forward_scaffold(),
            "overfitting": cls.overfitting_metrics(),
            "attribution": cls.factor_filter_attribution(),
            "trade_ledger_schema": cls.trade_ledger_schema(),
        }

    @classmethod
    def strategy_payload(cls, strategy_name: str) -> dict[str, object]:
        """전략 단위 validation payload의 안정적인 placeholder shape를 반환한다."""
        return {
            "strategy_name": strategy_name,
            "walk_forward": cls.walk_forward_scaffold(strategy_name=strategy_name),
            "overfitting": cls.overfitting_metrics(),
            "attribution": cls.factor_filter_attribution(strategy_name=strategy_name),
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
    def overfitting_metrics() -> dict[str, object]:
        return {
            "pbo": {
                "status": NOT_AVAILABLE,
                "value": NOT_AVAILABLE,
                "reason": "combinatorially_symmetric_cross_validation_not_implemented",
                "calculated": False,
            },
            "deflated_sharpe_ratio": {
                "status": NOT_AVAILABLE,
                "value": NOT_AVAILABLE,
                "reason": "multiple_testing_and_non_normal_return_adjustment_not_implemented",
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

    def strategy_summary(
        self,
        lookback_days: int = 252,
        baseline_run_id: str | None = None,
        baseline_snapshot: dict[str, object] | None = None,
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

        strategy_summaries: list[dict[str, object]] = []
        for strategy_name in strategy_names:
            backtest_summary = self._strategy_backtest_summary(
                strategy_name=strategy_name,
                start_date=window_start,
                end_date=window_end,
            )
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
                    "validation": ValidationScaffold.strategy_payload(strategy_name),
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
            "validation_framework": ValidationScaffold.framework_summary(),
            "strategies": strategy_summaries,
        }

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
