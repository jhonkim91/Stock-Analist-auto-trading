from __future__ import annotations

import json
from datetime import date

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
from backend.app.strategies.canslim_lite import CanslimLiteStrategy
from backend.app.strategies.trend_breakout import TrendBreakoutStrategy
from backend.app.strategies.vcp_breakout import VcpBreakoutStrategy


class ScreenerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.market_repo = MarketRepository(db)
        self.screen_repo = ScreenRepository(db)
        self.risk_service = RiskService()
        self.scoring_service = ScoringService()
        self.strategy_config = get_config("strategies")
        self.strategies = {
            "trend_breakout": TrendBreakoutStrategy(self.strategy_config["trend_breakout"]),
            "vcp_breakout": VcpBreakoutStrategy(self.strategy_config["vcp_breakout"]),
            "canslim_lite": CanslimLiteStrategy(self.strategy_config["canslim_lite"]),
        }

    def run(self, trade_date: date | None = None, strategies: list[str] | None = None) -> dict[str, object]:
        """지정일 기준 조건검색을 실행하고 screen_results에 저장한다."""
        target_date = trade_date or self.screen_repo.latest_indicator_date()
        if target_date is None:
            raise ValueError("indicator_snapshot 데이터가 없습니다.")
        enabled = strategies or list(self.strategies)
        indicators = self.screen_repo.indicators_for_date(target_date)
        if not indicators:
            raise ValueError(f"{target_date} 지표 스냅샷이 없습니다.")

        regime = RegimeService(self.db).detect_market_regime()["regime"]
        common = self.strategy_config["common"]
        self.screen_repo.clear_results(target_date)

        results: list[ScreenResult] = []
        for indicator in indicators:
            fundamentals = self.market_repo.fundamentals_asof(indicator.symbol, target_date)
            risk = self.risk_service.calculate(indicator)
            for strategy_name in enabled:
                strategy = self.strategies[strategy_name]
                strategy_result = strategy.evaluate(indicator, fundamentals, str(regime))
                final_result = self._apply_common_filters(strategy_result, indicator, risk.reward_risk_ratio, common)
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
        payload = [self._serialize_result(row, names.get(row.symbol, row.symbol)) for row in rows]

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

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 0.8:
            return "A"
        if score >= 0.65:
            return "B"
        if score >= 0.5:
            return "C"
        return "D"

    @classmethod
    def _serialize_result(cls, row: ScreenResult, name: str) -> dict[str, object]:
        pass_flags = json.loads(row.pass_flags)
        failed_conditions = json.loads(row.failed_conditions)
        triggered_conditions = [key for key, value in pass_flags.items() if value]
        total_conditions = max(len(pass_flags), 1)
        score_details = {
            "total_score": row.total_score,
            "grade": cls._grade(row.total_score),
        }
        score_breakdown = {
            **score_details,
            "condition_score": round(len(triggered_conditions) / total_conditions, 4),
            "triggered_count": len(triggered_conditions),
            "failed_count": len(failed_conditions),
            "total_conditions": len(pass_flags),
        }
        risk_details = {
            "entry_price": row.entry_price,
            "stop_price": row.stop_price,
            "target_price": row.target_price,
            "risk_per_share": row.risk_per_share,
            "reward_risk_ratio": row.reward_risk_ratio,
            "position_size": row.position_size,
            "position_notional": row.position_notional,
        }
        risk_flags = {
            "liquidity_ok": bool(pass_flags.get("liquidity_ok", False)),
            "rr_ok": bool(pass_flags.get("rr_ok", False)),
            "position_size_positive": int(row.position_size or 0) > 0,
            "risk_per_share_positive": float(row.risk_per_share or 0) > 0,
        }
        data_quality_flags = {
            "pass_flags_parseable": isinstance(pass_flags, dict),
            "failed_conditions_parseable": isinstance(failed_conditions, list),
            "entry_price_available": row.entry_price is not None,
            "stop_price_available": row.stop_price is not None,
            "target_price_available": row.target_price is not None,
        }
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
            "reason_summary": row.reason_summary,
            "pass_flags_json": pass_flags,
            "failed_conditions_json": failed_conditions,
            "score_details_json": score_details,
            "risk_details_json": risk_details,
            "triggered_conditions": triggered_conditions,
            "score_breakdown": score_breakdown,
            "risk_flags": risk_flags,
            "data_quality_flags": data_quality_flags,
            "explanation": row.reason_summary,
            "rationale": row.reason_summary,
            "pass_flags": pass_flags,
            "failed_conditions": failed_conditions,
            "risk_per_share": row.risk_per_share,
            "position_notional": row.position_notional,
        }
