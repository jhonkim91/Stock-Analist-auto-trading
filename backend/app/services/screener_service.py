from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_config
from backend.app.models.tables import ScreenResult, SymbolMaster
from backend.app.repositories.market_repository import MarketRepository
from backend.app.repositories.screen_repository import ScreenRepository
from backend.app.services.regime_service import RegimeService
from backend.app.services.risk_service import RiskService
from backend.app.services.scoring_service import ScoringService
from backend.app.strategies.base import StrategyResult
from backend.app.strategies.registry import DEFAULT_STRATEGY_NAMES, get_available_strategy_registry


class ScreenerService:

    def __init__(self, db: Session) -> None:
        self.db = db
        self.market_repo = MarketRepository(db)
        self.screen_repo = ScreenRepository(db)
        self.risk_service = RiskService()
        self.scoring_service = ScoringService()
        self.strategy_config = get_config("strategies")
        self.strategies = get_available_strategy_registry(self.strategy_config)

    def run(self, trade_date: date | None = None, strategies: list[str] | None = None) -> dict[str, object]:
        """지정일 기준 조건검색을 실행하고 screen_results에 저장한다."""
        target_date = trade_date or self.screen_repo.latest_indicator_date()
        if target_date is None:
            raise ValueError("indicator_snapshot 데이터가 없습니다.")
        enabled = strategies or list(DEFAULT_STRATEGY_NAMES)
        indicators = self.screen_repo.indicators_for_date(target_date)
        if not indicators:
            raise ValueError(f"{target_date} 지표 스냅샷이 없습니다.")

        regime = RegimeService(self.db).detect_market_regime()["regime"]
        common = self.strategy_config["common"]
        self.screen_repo.clear_results(target_date)

        results: list[ScreenResult] = []
        for indicator in indicators:
            fundamentals = self.market_repo.fundamentals_asof(indicator.symbol, target_date)
            setattr(indicator, "earnings_event", self.market_repo.earnings_event_asof(indicator.symbol, target_date))
            for strategy_name in enabled:
                strategy = self.strategies[strategy_name]
                strategy_result = strategy.evaluate(indicator, fundamentals, str(regime))
                risk = self.risk_service.calculate(
                    indicator,
                    risk_metadata=self._as_dict(strategy_result.metadata.get("risk_metadata")),
                )
                strategy_result = self._attach_risk_plan(strategy_result, risk)
                final_result = self._apply_common_filters(strategy_result, indicator, risk.reward_risk_ratio, common)
                metadata = dict(final_result.metadata)
                total_score = self.scoring_service.score(indicator, fundamentals, risk.rr_score)
                results.append(
                    ScreenResult(
                        trade_date=target_date,
                        symbol=indicator.symbol,
                        strategy_tag=strategy_name,
                        passed=final_result.passed,
                        pass_flags=json.dumps(final_result.pass_flags, ensure_ascii=False, sort_keys=True),
                        failed_conditions=json.dumps(final_result.failed_conditions, ensure_ascii=False),
                        reason_summary=final_result.reason_summary,
                        metadata_json=self._json_dumps(metadata),
                        risk_flags_json=self._json_dumps(self._as_dict(metadata.get("risk_flags"))),
                        score_breakdown_json=self._json_dumps(self._as_dict(metadata.get("score_breakdown"))),
                        data_quality_flags_json=self._json_dumps(self._as_dict(metadata.get("data_quality_flags"))),
                        total_score=total_score,
                        entry_price=risk.entry_price,
                        stop_price=risk.stop_price,
                        target_price=risk.target_price,
                        risk_per_share=risk.risk_per_share,
                        reward_risk_ratio=risk.reward_risk_ratio,
                        position_size=risk.position_size,
                        position_notional=risk.position_notional,
                    )
                )

        self.screen_repo.save_results(results)
        return {
            "trade_date": target_date,
            "rows": len(results),
            "passed": sum(1 for row in results if row.passed),
            "strategies": enabled,
        }

    @staticmethod
    def _attach_risk_plan(result: StrategyResult, risk) -> StrategyResult:
        metadata = dict(result.metadata)
        risk_metadata = metadata.get("risk_metadata")
        risk_metadata = dict(risk_metadata) if isinstance(risk_metadata, dict) else {}
        risk_metadata.update(
            {
                "suggested_stop_price": risk.stop_price,
                "risk_per_share": risk.risk_per_share,
                "risk_basis": risk.risk_basis,
            }
        )
        metadata["risk_metadata"] = risk_metadata
        if "suggested_stop_price" in metadata or "risk_basis" in metadata:
            metadata["suggested_stop_price"] = risk.stop_price
            metadata["risk_per_share"] = risk.risk_per_share
            metadata["risk_basis"] = risk.risk_basis
        data_quality_flags = metadata.get("data_quality_flags")
        if isinstance(data_quality_flags, dict):
            metadata["data_quality_flags"] = {
                **data_quality_flags,
                "suggested_stop_price_available": risk.stop_price is not None,
                "risk_per_share_available": risk.risk_per_share is not None,
            }
        return StrategyResult(
            strategy_tag=result.strategy_tag,
            passed=result.passed,
            pass_flags=dict(result.pass_flags),
            failed_conditions=list(result.failed_conditions),
            reason_summary=result.reason_summary,
            metadata=metadata,
        )

    @staticmethod
    def _apply_common_filters(
        result: StrategyResult,
        indicator,
        reward_risk_ratio: float,
        common: dict[str, object],
    ) -> StrategyResult:
        flags = dict(result.pass_flags)
        flags["liquidity_ok"] = float(indicator.turnover_value or 0) >= float(common["min_turnover_value"])
        flags["rr_ok"] = reward_risk_ratio >= float(common["target_reward_risk"])
        failed = [key for key, value in flags.items() if not value]
        passed = all(flags.values())
        metadata = dict(result.metadata)
        return StrategyResult(
            strategy_tag=result.strategy_tag,
            passed=passed,
            pass_flags=flags,
            failed_conditions=failed,
            reason_summary=(
                f"{result.strategy_tag} 조건과 공통 리스크/유동성 조건을 모두 충족했습니다."
                if passed
                else f"{result.strategy_tag} 탈락 조건: {', '.join(failed)}"
            ),
            metadata=metadata,
        )

    def list_results(
        self,
        trade_date: date | None = None,
        strategy_name: str | None = None,
        passed: bool | None = None,
        grade: str | None = None,
        q: str | None = None,
        sort_by: str | None = None,
        sort_dir: str = "desc",
        limit: int = 100,
    ) -> list[dict[str, object]]:
        rows = self.screen_repo.list_results(trade_date)
        symbol_rows = self.db.scalars(select(SymbolMaster)).all()
        names = {symbol.symbol: symbol.name for symbol in symbol_rows}
        payload = [
            self._serialize_result(
                row,
                names.get(row.symbol, row.symbol),
                self._strategy_metadata(row),
            )
            for row in rows
        ]

        if strategy_name:
            payload = [row for row in payload if row["strategy_name"] == strategy_name]
        if passed is not None:
            payload = [row for row in payload if row["passed"] is passed]
        if grade:
            payload = [row for row in payload if row["grade"] == grade.upper()]
        if q:
            query = q.casefold()
            payload = [
                row
                for row in payload
                if query in str(row["symbol"]).casefold() or query in str(row["name"]).casefold()
            ]

        reverse = sort_dir.lower() != "asc"
        if sort_by in {"total_score", "reward_risk_ratio"}:
            payload = sorted(payload, key=lambda row: float(row.get(sort_by) or 0), reverse=reverse)

        return payload[:limit]

    def strategy_pass_rate_summary(
        self,
        lookback_days: int = 252,
        strategy_names: list[str] | None = None,
    ) -> dict[str, object]:
        """최근 screen_results 가용 거래일 기준 전략별 pass_rate를 계산한다."""
        requested_days = max(int(lookback_days), 1)
        selected_strategy_names = strategy_names or list(self.strategies)
        window_dates_desc = list(
            self.db.scalars(
                select(ScreenResult.trade_date)
                .distinct()
                .order_by(ScreenResult.trade_date.desc())
                .limit(requested_days)
            ).all()
        )
        window_dates = sorted(window_dates_desc)
        rows: list[ScreenResult] = []
        if window_dates:
            rows = list(
                self.db.scalars(
                    select(ScreenResult).where(ScreenResult.trade_date.in_(window_dates))
                ).all()
            )

        counts = {
            strategy_name: {
                "evaluated_count": 0,
                "pass_count": 0,
                "evaluated_dates": set(),
            }
            for strategy_name in selected_strategy_names
        }
        for row in rows:
            if row.strategy_tag not in counts:
                continue
            bucket = counts[row.strategy_tag]
            bucket["evaluated_count"] = int(bucket["evaluated_count"]) + 1
            bucket["pass_count"] = int(bucket["pass_count"]) + (1 if row.passed else 0)
            evaluated_dates = bucket["evaluated_dates"]
            if isinstance(evaluated_dates, set):
                evaluated_dates.add(row.trade_date)

        summaries: list[dict[str, object]] = []
        for strategy_name in selected_strategy_names:
            bucket = counts[strategy_name]
            evaluated_count = int(bucket["evaluated_count"])
            pass_count = int(bucket["pass_count"])
            evaluated_dates = bucket["evaluated_dates"]
            evaluated_trading_days = len(evaluated_dates) if isinstance(evaluated_dates, set) else 0
            summaries.append(
                {
                    "strategy_name": strategy_name,
                    "evaluated_count": evaluated_count,
                    "pass_count": pass_count,
                    "pass_rate": round(pass_count / evaluated_count, 6) if evaluated_count else None,
                    "evaluated_trading_days": evaluated_trading_days,
                    "window_trading_days": len(window_dates),
                    "window_start": window_dates[0] if window_dates else None,
                    "window_end": window_dates[-1] if window_dates else None,
                }
            )

        return {
            "requested_trading_days": requested_days,
            "available_trading_days": len(window_dates),
            "window_start": window_dates[0] if window_dates else None,
            "window_end": window_dates[-1] if window_dates else None,
            "basis": "screen_results.trade_date",
            "strategies": summaries,
        }

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 0.8:
            return "A"
        if score >= 0.65:
            return "B"
        if score >= 0.5:
            return "C"
        return "D"

    def _strategy_metadata(self, row: ScreenResult) -> dict[str, Any]:
        metadata = self._json_object(getattr(row, "metadata_json", "{}"))
        for key, column_name in (
            ("risk_flags", "risk_flags_json"),
            ("score_breakdown", "score_breakdown_json"),
            ("data_quality_flags", "data_quality_flags_json"),
        ):
            if key not in metadata:
                section = self._json_object(getattr(row, column_name, "{}"))
                if section:
                    metadata[key] = section
        return metadata

    @classmethod
    def _serialize_result(
        cls,
        row: ScreenResult,
        name: str,
        strategy_metadata: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        pass_flags = json.loads(row.pass_flags)
        failed_conditions = json.loads(row.failed_conditions)
        metadata = strategy_metadata or {}
        metadata_triggered_conditions = metadata.get("triggered_conditions")
        triggered_conditions = (
            [str(key) for key in metadata_triggered_conditions]
            if isinstance(metadata_triggered_conditions, list)
            else [key for key, value in pass_flags.items() if value]
        )
        total_conditions = max(len(pass_flags), 1)
        strategy_score_breakdown = cls._as_dict(metadata.get("score_breakdown"))
        score_details = {
            "total_score": row.total_score,
            "grade": cls._grade(row.total_score),
        }
        score_breakdown = strategy_score_breakdown or {
            **score_details,
            "condition_score": round(len(triggered_conditions) / total_conditions, 4),
            "triggered_count": len(triggered_conditions),
            "failed_count": len(failed_conditions),
            "total_conditions": len(pass_flags),
        }
        risk_metadata = cls._as_dict(metadata.get("risk_metadata"))
        risk_basis = risk_metadata.get("risk_basis")
        risk_details = {
            "entry_price": row.entry_price,
            "stop_price": row.stop_price,
            "target_price": row.target_price,
            "risk_per_share": row.risk_per_share,
            "reward_risk_ratio": row.reward_risk_ratio,
            "position_size": row.position_size,
            "position_notional": row.position_notional,
            "risk_basis": risk_basis,
        }
        execution_risk_flags = {
            "liquidity_ok": bool(pass_flags.get("liquidity_ok", False)),
            "rr_ok": bool(pass_flags.get("rr_ok", False)),
            "position_size_positive": int(row.position_size or 0) > 0,
            "risk_per_share_positive": float(row.risk_per_share or 0) > 0,
        }
        risk_flags = cls._as_dict(metadata.get("risk_flags")) or execution_risk_flags
        response_data_quality_flags = {
            "pass_flags_parseable": isinstance(pass_flags, dict),
            "failed_conditions_parseable": isinstance(failed_conditions, list),
            "entry_price_available": row.entry_price is not None,
            "stop_price_available": row.stop_price is not None,
            "target_price_available": row.target_price is not None,
        }
        data_quality_flags = cls._as_dict(metadata.get("data_quality_flags")) or response_data_quality_flags
        return {
            "trade_date": row.trade_date,
            "symbol": row.symbol,
            "name": name,
            "strategy_name": row.strategy_tag,
            "strategy_tag": row.strategy_tag,
            "passed": row.passed,
            "grade": score_details["grade"],
            "total_score": row.total_score,
            "entry_price": row.entry_price,
            "stop_price": row.stop_price,
            "target_price": row.target_price,
            "reward_risk_ratio": row.reward_risk_ratio,
            "position_size": row.position_size,
            "risk_basis": risk_basis,
            "reason_summary": row.reason_summary,
            "pass_flags_json": pass_flags,
            "failed_conditions_json": failed_conditions,
            "score_details_json": score_details,
            "risk_details_json": risk_details,
            "triggered_conditions": triggered_conditions,
            "score_breakdown": score_breakdown,
            "risk_flags": risk_flags,
            "data_quality_flags": data_quality_flags,
            "metadata": metadata,
            "risk_metadata": risk_metadata,
            "explanation": str(metadata.get("explanation") or row.reason_summary),
            "rationale": str(metadata.get("rationale") or row.reason_summary),
            "pass_flags": pass_flags,
            "failed_conditions": failed_conditions,
            "risk_per_share": row.risk_per_share,
            "position_notional": row.position_notional,
        }

    @staticmethod
    def _json_dumps(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _json_object(value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}
