from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.config import get_config
from backend.app.core.paths import CONFIG_DIR
from backend.app.models.tables import (
    PaperAccountSnapshot,
    PaperBotDecision,
    PaperBotRun,
    PaperOrder,
    PaperPosition,
    ScreenResult,
    SymbolMaster,
)
from backend.app.services.market_session_service import MarketSessionService
from backend.app.services.paper_bot_service import PaperBotConfigService
from backend.app.services.paper_order_service import OPEN_ORDER_STATUSES, PaperOrderService
from backend.app.services.paper_trading_service import PaperConfigService
from backend.app.workers.realtime_market_worker import realtime_market_worker

BOT_ALLOWED_ACTIONS = {"submitted", "skipped", "rejected"}


class PaperBotExecutor:
    """KIS paper 전용 bot preview/run과 주문 전 risk gate를 실행한다."""

    def __init__(
        self,
        db: Session,
        *,
        config_dir: Path = CONFIG_DIR,
        market_session_service: MarketSessionService | None = None,
    ) -> None:
        self.db = db
        self.config_dir = config_dir
        self.bot_config_service = PaperBotConfigService(config_dir)
        self.paper_config_service = PaperConfigService(config_dir)
        self.market_session_service = market_session_service or MarketSessionService()
        self.risk_config = get_config("risk")

    def preview(
        self,
        *,
        trade_date: date | None,
        strategies: list[str],
        watchlist_symbols: list[str] | None = None,
        max_candidates: int,
    ) -> dict[str, Any]:
        """주문 생성 없이 bot 후보와 risk gate 결과만 저장 및 반환한다."""
        return self._execute(
            mode="preview",
            trade_date=trade_date,
            strategies=strategies,
            watchlist_symbols=watchlist_symbols or [],
            max_candidates=max_candidates,
            dry_run=True,
        )

    def run(
        self,
        *,
        trade_date: date | None,
        strategies: list[str],
        watchlist_symbols: list[str] | None = None,
        max_candidates: int,
        dry_run: bool,
    ) -> dict[str, Any]:
        """dry_run이면 preview만, false이면 모든 paper gate 통과 시 local/KIS paper submit을 시도한다."""
        return self._execute(
            mode="run",
            trade_date=trade_date,
            strategies=strategies,
            watchlist_symbols=watchlist_symbols or [],
            max_candidates=max_candidates,
            dry_run=dry_run,
        )

    def get_run(self, *, run_id: str) -> dict[str, Any]:
        """저장된 bot run과 decision rows를 반환한다."""
        run = self.db.get(PaperBotRun, run_id)
        if run is None:
            return {
                "ok": False,
                "status": "not_found",
                "run_id": run_id,
                "reason": "PAPER_BOT_RUN_NOT_FOUND",
                "reason_codes": ["PAPER_BOT_RUN_NOT_FOUND"],
                "live_order_created": False,
                "network_call_performed": False,
            }
        decisions = list(
            self.db.scalars(
                select(PaperBotDecision)
                .where(PaperBotDecision.run_id == run_id)
                .order_by(PaperBotDecision.id.asc())
            ).all()
        )
        return {
            "ok": True,
            "status": run.status,
            "run_id": run.run_id,
            "mode": run.mode,
            "trade_date": run.trade_date.isoformat() if run.trade_date else None,
            "dry_run": bool(run.dry_run),
            "decision_count": int(run.decision_count or 0),
            "preview_count": int(run.preview_count or 0),
            "skipped_count": int(run.skipped_count or 0),
            "rejected_count": int(run.rejected_count or 0),
            "submitted_count": int(run.submitted_count or 0),
            "reason_codes": self._json_list(run.reason_codes_json),
            "request": self._json_object(run.request_json),
            "result": self._json_object(run.result_json),
            "decisions": [self._decision_payload(row) for row in decisions],
            "paper_order_submitted": int(run.submitted_count or 0) > 0,
            "live_order_created": False,
            "network_call_performed": False,
        }

    def _execute(
        self,
        *,
        mode: str,
        trade_date: date | None,
        strategies: list[str],
        watchlist_symbols: list[str],
        max_candidates: int,
        dry_run: bool,
    ) -> dict[str, Any]:
        normalized_strategies = [item.strip() for item in strategies if item and item.strip()]
        normalized_watchlist = self._normalize_symbols(watchlist_symbols)
        target_date = self._resolve_trade_date(trade_date)
        request_payload = {
            "trade_date": target_date.isoformat() if target_date else None,
            "strategies": normalized_strategies,
            "watchlist_symbols": normalized_watchlist,
            "max_candidates": max(1, int(max_candidates)),
            "dry_run": bool(dry_run),
        }
        bot_config, bot_config_reasons = self.bot_config_service.load()
        paper_config, paper_config_reasons = self.paper_config_service.load()
        session = self.market_session_service.session_at()
        run_reasons = self._run_level_reasons(
            bot_config=bot_config,
            bot_config_reasons=bot_config_reasons,
            paper_config=paper_config,
            paper_config_reasons=paper_config_reasons,
            session=session,
        )
        run = PaperBotRun(
            run_id=f"paper-bot-{uuid4().hex[:16]}",
            mode=mode,
            status="created",
            trade_date=target_date,
            dry_run=bool(dry_run),
            auto_submit_requested=not bool(dry_run),
            auto_submit_allowed=not bool(dry_run) and not run_reasons,
            decision_count=0,
            preview_count=0,
            skipped_count=0,
            rejected_count=0,
            submitted_count=0,
            reason_codes_json=json.dumps(run_reasons, ensure_ascii=False),
            request_json=json.dumps(request_payload, ensure_ascii=False, sort_keys=True, default=str),
            result_json="{}",
        )
        self.db.add(run)
        self.db.commit()

        decisions: list[dict[str, Any]] = []
        if bool(bot_config.get("enabled")) and target_date is not None:
            decisions = self._build_and_store_decisions(
                run=run,
                target_date=target_date,
                strategies=normalized_strategies,
                watchlist_symbols=normalized_watchlist,
                max_candidates=max(1, int(max_candidates)),
                dry_run=dry_run,
                run_reasons=run_reasons,
                bot_config=bot_config,
                paper_config=paper_config,
                session=session,
            )

        summary = self._decision_summary(decisions)
        status = self._run_status(bot_enabled=bool(bot_config.get("enabled")), summary=summary, run_reasons=run_reasons)
        result_summary = {
            **summary,
            "candidate_count": len(decisions),
            "candidate_source": "watchlist_screen_results" if normalized_watchlist else "screen_results",
            "watchlist_symbols": normalized_watchlist,
            "target_trade_date": target_date.isoformat() if target_date else None,
            "dry_run": bool(dry_run),
            "reason_codes": run_reasons,
        }
        run.status = status
        run.decision_count = len(decisions)
        run.preview_count = int(summary["preview_count"])
        run.skipped_count = int(summary["skipped_count"])
        run.rejected_count = int(summary["rejected_count"])
        run.submitted_count = int(summary["submitted_count"])
        run.auto_submit_allowed = not bool(dry_run) and not run_reasons
        run.result_json = json.dumps(result_summary, ensure_ascii=False, sort_keys=True, default=str)
        self.db.add(run)
        self.db.commit()

        return {
            "ok": True,
            "status": run.status,
            "run_id": run.run_id,
            "mode": mode,
            "trade_date": target_date,
            "dry_run": bool(dry_run),
            "auto_submit_requested": not bool(dry_run),
            "auto_submit_allowed": bool(run.auto_submit_allowed),
            "paper_order_submitted": int(run.submitted_count or 0) > 0,
            "decision_count": int(run.decision_count or 0),
            "preview_count": int(run.preview_count or 0),
            "skipped_count": int(run.skipped_count or 0),
            "rejected_count": int(run.rejected_count or 0),
            "submitted_count": int(run.submitted_count or 0),
            "decisions": decisions,
            "candidate_source": "watchlist_screen_results" if normalized_watchlist else "screen_results",
            "watchlist_symbols": normalized_watchlist,
            "reason_codes": run_reasons,
            "session": self._session_payload(session),
            "paper_order_created": int(run.submitted_count or 0) > 0,
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": False,
            "counts": self._counts(),
        }

    def _build_and_store_decisions(
        self,
        *,
        run: PaperBotRun,
        target_date: date,
        strategies: list[str],
        watchlist_symbols: list[str],
        max_candidates: int,
        dry_run: bool,
        run_reasons: list[str],
        bot_config: dict[str, Any],
        paper_config: dict[str, Any],
        session: dict[str, Any],
    ) -> list[dict[str, Any]]:
        candidates = self._screen_candidates(
            target_date=target_date,
            strategies=strategies,
            watchlist_symbols=watchlist_symbols,
            max_candidates=max_candidates,
        )
        decisions: list[dict[str, Any]] = []
        planned_submissions = 0
        planned_symbols: set[str] = set()
        for candidate in candidates:
            eligibility_reasons = self._candidate_eligibility_reasons(candidate)
            sizing = self._sizing(candidate, paper_config=paper_config)
            gate_reasons = self._risk_gate_reasons(
                candidate=candidate,
                sizing=sizing,
                run_reasons=run_reasons,
                bot_config=bot_config,
                paper_config=paper_config,
                session=session,
                planned_symbols=planned_symbols,
                planned_submissions=planned_submissions,
            )
            reason_codes = _merge_reason_codes(eligibility_reasons + gate_reasons)
            action = self._action_for_decision(
                dry_run=dry_run,
                eligibility_reasons=eligibility_reasons,
                gate_reasons=gate_reasons,
                reason_codes=reason_codes,
            )
            paper_order_id = None
            if action == "submitted":
                submit_result = PaperOrderService(self.db, config_dir=self.config_dir).submit_order(
                    symbol=candidate.symbol,
                    side="buy",
                    qty=int(sizing["qty"]),
                    confirm=True,
                    idempotency_key=f"{run.run_id}:{candidate.symbol}:{candidate.strategy_tag}",
                    limit_price=candidate.entry_price,
                    stop_price=candidate.stop_price,
                    strategy_tag=candidate.strategy_tag,
                    command_source="paper_bot",
                )
                if submit_result.get("ok") and isinstance(submit_result.get("order"), dict):
                    paper_order_id = str(submit_result["order"]["paper_order_id"])
                    planned_submissions += 1
                    planned_symbols.add(candidate.symbol)
                else:
                    action = "rejected"
                    reason_codes = _merge_reason_codes(reason_codes + list(submit_result.get("reason_codes") or []))

            if action == "submitted":
                planned_symbols.add(candidate.symbol)
            elif action == "skipped" and "PAPER_BOT_DRY_RUN" not in reason_codes:
                reason_codes = _merge_reason_codes(reason_codes + ["PAPER_BOT_SKIPPED"])
            decision = PaperBotDecision(
                run_id=run.run_id,
                symbol=candidate.symbol,
                strategy_tag=candidate.strategy_tag,
                action=action,
                total_score=candidate.total_score,
                qty=int(sizing["qty"]),
                limit_price=candidate.entry_price,
                stop_price=candidate.stop_price,
                target_price=candidate.target_price,
                risk_passed=action in {"submitted", "skipped"} and not gate_reasons and not eligibility_reasons,
                reason_codes_json=json.dumps(reason_codes, ensure_ascii=False),
                paper_order_id=paper_order_id,
            )
            self.db.add(decision)
            payload = self._decision_payload(decision, reason_codes=reason_codes, sizing=sizing)
            decisions.append(payload)
            if planned_submissions >= int(bot_config.get("max_auto_submit_orders") or 0) and not dry_run:
                planned_symbols.add(candidate.symbol)
        self.db.commit()
        return decisions

    def _screen_candidates(
        self,
        *,
        target_date: date,
        strategies: list[str],
        watchlist_symbols: list[str],
        max_candidates: int,
    ) -> list[ScreenResult]:
        statement = (
            select(ScreenResult)
            .where(ScreenResult.trade_date == target_date, ScreenResult.passed.is_(True))
            .order_by(ScreenResult.total_score.desc(), ScreenResult.symbol.asc())
            .limit(max_candidates)
        )
        if strategies:
            statement = statement.where(ScreenResult.strategy_tag.in_(strategies))
        if watchlist_symbols:
            statement = statement.where(ScreenResult.symbol.in_(watchlist_symbols))
        return list(self.db.scalars(statement).all())

    def _candidate_eligibility_reasons(self, candidate: ScreenResult) -> list[str]:
        reasons: list[str] = []
        metadata = self._json_object(candidate.metadata_json)
        risk_metadata = metadata.get("risk_metadata")
        if not isinstance(risk_metadata, dict) or not risk_metadata:
            reasons.append("RISK_METADATA_INVALID")
        if self._positive_float(candidate.risk_per_share) is None:
            reasons.append("RISK_PER_SHARE_REQUIRED")
        if self._positive_float(candidate.stop_price) is None:
            reasons.append("STOP_PRICE_REQUIRED")
        if self._positive_float(candidate.entry_price) is None:
            reasons.append("ENTRY_PRICE_REQUIRED")
        data_quality = self._data_quality_flags(candidate, metadata)
        if not data_quality:
            reasons.append("DATA_QUALITY_FLAGS_MISSING")
        elif any(value is False for value in data_quality.values()):
            reasons.append("DATA_QUALITY_FLAGS_FAILED")
        return reasons

    def _sizing(self, candidate: ScreenResult, *, paper_config: dict[str, Any]) -> dict[str, Any]:
        portfolio = self.risk_config["portfolio"]
        equity = float(portfolio["equity"])
        cash_available = self._cash_available(default=equity)
        entry_price = float(candidate.entry_price or 0.0)
        stop_price = float(candidate.stop_price or 0.0)
        risk_per_share = float(candidate.risk_per_share or max(entry_price - stop_price, 0.0))
        risk_budget = equity * float(portfolio["risk_fraction"])
        max_order_notional = min(
            float(paper_config.get("max_order_notional") or 0.0) or equity,
            equity * float(portfolio["max_position_fraction"]),
        )
        risk_qty = int(risk_budget // risk_per_share) if risk_per_share > 0 else 0
        notional_qty = int(max_order_notional // entry_price) if entry_price > 0 else 0
        cash_qty = int(cash_available // entry_price) if entry_price > 0 else 0
        screen_qty = int(candidate.position_size or 0)
        qty_candidates = [value for value in (risk_qty, notional_qty, cash_qty, screen_qty) if value > 0]
        qty = min(qty_candidates) if qty_candidates else 0
        notional = qty * entry_price
        return {
            "qty": qty,
            "entry_price": entry_price,
            "stop_price": stop_price,
            "risk_per_share": risk_per_share,
            "risk_budget": round(risk_budget, 4),
            "max_order_notional": round(max_order_notional, 4),
            "cash_available": round(cash_available, 4),
            "current_exposure": round(self._current_exposure(), 4),
            "order_notional": round(notional, 4),
        }

    def _risk_gate_reasons(
        self,
        *,
        candidate: ScreenResult,
        sizing: dict[str, Any],
        run_reasons: list[str],
        bot_config: dict[str, Any],
        paper_config: dict[str, Any],
        session: dict[str, Any],
        planned_symbols: set[str],
        planned_submissions: int,
    ) -> list[str]:
        reasons = list(run_reasons)
        qty = int(sizing["qty"])
        order_notional = float(sizing["order_notional"])
        if qty <= 0:
            reasons.append("PAPER_BOT_SIZING_QTY_ZERO")
        if candidate.symbol in planned_symbols:
            reasons.append("PAPER_BOT_DUPLICATE_PLANNED_SYMBOL")
        if self._has_open_order(candidate.symbol):
            reasons.append("PAPER_DUPLICATE_OPEN_ORDER")
        if not bool(session.get("current_session_allows_preview")):
            reasons.append("MARKET_SESSION_CLOSED")
        reasons.extend(self._realtime_quote_reasons(candidate.symbol, paper_config=paper_config))
        reasons.extend(self._loss_limit_reasons())
        reasons.extend(self._concentration_reasons(candidate, order_notional=order_notional))
        if order_notional > float(bot_config.get("max_order_notional") or 0.0):
            reasons.append("PAPER_BOT_ORDER_NOTIONAL_LIMIT_EXCEEDED")
        if order_notional > float(sizing["cash_available"]):
            reasons.append("PAPER_BOT_CASH_LIMIT_EXCEEDED")
        if int(sizing["qty"]) > int(bot_config.get("max_order_qty") or 0):
            reasons.append("PAPER_BOT_ORDER_QTY_LIMIT_EXCEEDED")
        if planned_submissions >= int(bot_config.get("max_auto_submit_orders") or 0) and int(bot_config.get("max_auto_submit_orders") or 0) >= 0:
            reasons.append("PAPER_BOT_MAX_SUBMITS_PER_RUN_REACHED")
        return _merge_reason_codes(reasons)

    def _run_level_reasons(
        self,
        *,
        bot_config: dict[str, Any],
        bot_config_reasons: list[str],
        paper_config: dict[str, Any],
        paper_config_reasons: list[str],
        session: dict[str, Any],
    ) -> list[str]:
        reasons = list(bot_config_reasons) + list(paper_config_reasons)
        if not bool(bot_config.get("enabled")):
            reasons.append("PAPER_BOT_DISABLED")
        if bool(bot_config.get("kill_switch_enabled")):
            reasons.append("PAPER_BOT_KILL_SWITCH_ACTIVE")
        if bool(paper_config.get("kill_switch_enabled")):
            reasons.append("KILL_SWITCH_ACTIVE")
        if not bool(session.get("current_session_allows_preview")):
            reasons.append("MARKET_SESSION_CLOSED")
        return _merge_reason_codes(reasons)

    @staticmethod
    def _action_for_decision(
        *,
        dry_run: bool,
        eligibility_reasons: list[str],
        gate_reasons: list[str],
        reason_codes: list[str],
    ) -> str:
        if eligibility_reasons:
            return "skipped"
        if gate_reasons:
            return "rejected"
        if dry_run:
            reason_codes.append("PAPER_BOT_DRY_RUN")
            return "skipped"
        return "submitted"

    @staticmethod
    def _run_status(*, bot_enabled: bool, summary: dict[str, int], run_reasons: list[str]) -> str:
        if not bot_enabled:
            return "disabled"
        if summary["submitted_count"] > 0:
            return "submitted"
        if summary["rejected_count"] > 0:
            return "rejected"
        if summary["skipped_count"] > 0:
            return "skipped"
        if run_reasons:
            return "blocked"
        return "completed"

    def _resolve_trade_date(self, requested: date | None) -> date | None:
        if requested is not None:
            return requested
        return self.db.scalar(select(ScreenResult.trade_date).order_by(ScreenResult.trade_date.desc()).limit(1))

    @staticmethod
    def _normalize_symbols(symbols: list[str] | None) -> list[str]:
        normalized: list[str] = []
        for symbol in symbols or []:
            value = str(symbol or "").strip().upper()
            if value and value not in normalized:
                normalized.append(value)
        return normalized

    def _cash_available(self, *, default: float) -> float:
        snapshot = self.db.scalar(
            select(PaperAccountSnapshot).order_by(
                PaperAccountSnapshot.snapshot_ts.desc(),
                PaperAccountSnapshot.created_at.desc(),
            )
        )
        if snapshot is None:
            return default
        for value in (snapshot.buying_power, snapshot.cash_balance, snapshot.total_equity):
            if value is not None and float(value) > 0:
                return float(value)
        return default

    def _current_exposure(self) -> float:
        position_value = sum(
            self._position_market_value(row)
            for row in self.db.scalars(select(PaperPosition).where(PaperPosition.qty > 0)).all()
        )
        open_order_notional = sum(
            float(order.limit_price or 0.0) * int(order.remaining_qty or order.qty or 0)
            for order in self.db.scalars(select(PaperOrder).where(PaperOrder.status.in_(OPEN_ORDER_STATUSES))).all()
        )
        return position_value + open_order_notional

    def _loss_limit_reasons(self) -> list[str]:
        portfolio = self.risk_config["portfolio"]
        max_daily_loss = float(portfolio["equity"]) * float(portfolio["max_daily_loss_fraction"])
        realized = float(
            self.db.scalar(select(func.coalesce(func.sum(PaperPosition.realized_pnl), 0.0))) or 0.0
        )
        return ["PAPER_BOT_DAILY_LOSS_LIMIT_EXCEEDED"] if realized <= -max_daily_loss else []

    def _concentration_reasons(self, candidate: ScreenResult, *, order_notional: float) -> list[str]:
        portfolio = self.risk_config["portfolio"]
        equity = float(portfolio["equity"])
        reasons: list[str] = []
        current_positions = list(self.db.scalars(select(PaperPosition).where(PaperPosition.qty > 0)).all())
        held_symbols = {row.symbol for row in current_positions}
        open_symbols = set(self.db.scalars(select(PaperOrder.symbol).where(PaperOrder.status.in_(OPEN_ORDER_STATUSES))).all())
        if candidate.symbol not in held_symbols and candidate.symbol not in open_symbols:
            if len(held_symbols | open_symbols) >= int(portfolio["max_open_positions"]):
                reasons.append("PAPER_BOT_MAX_POSITIONS_EXCEEDED")

        symbol_exposure = sum(self._position_market_value(row) for row in current_positions if row.symbol == candidate.symbol)
        if symbol_exposure + order_notional > equity * float(portfolio["max_symbol_exposure_fraction"]):
            reasons.append("PAPER_BOT_SYMBOL_CONCENTRATION_EXCEEDED")

        strategy_exposure = sum(
            self._position_market_value(row)
            for row in current_positions
            if row.strategy_tag == candidate.strategy_tag
        )
        if strategy_exposure + order_notional > equity * float(portfolio["max_strategy_exposure_fraction"]):
            reasons.append("PAPER_BOT_STRATEGY_CONCENTRATION_EXCEEDED")

        sector = self._sector(candidate.symbol)
        if sector:
            sector_symbols = set(self.db.scalars(select(SymbolMaster.symbol).where(SymbolMaster.sector == sector)).all())
            sector_exposure = sum(
                self._position_market_value(row)
                for row in current_positions
                if row.symbol in sector_symbols
            )
            if sector_exposure + order_notional > equity * float(portfolio["max_sector_exposure_fraction"]):
                reasons.append("PAPER_BOT_SECTOR_CONCENTRATION_EXCEEDED")
        return reasons

    def _realtime_quote_reasons(self, symbol: str, *, paper_config: dict[str, Any]) -> list[str]:
        if not bool(paper_config.get("realtime_enabled")):
            return []
        if not bool(paper_config.get("realtime_require_fresh_quote_for_orders")):
            return []
        gate = realtime_market_worker.quote_gate_result(
            symbol=symbol,
            stale_quote_threshold_seconds=int(paper_config.get("realtime_stale_quote_threshold_seconds") or 30),
        )
        return list(gate.get("reason_codes") or [])

    def _has_open_order(self, symbol: str) -> bool:
        return bool(
            self.db.scalar(
                select(PaperOrder.paper_order_id)
                .where(PaperOrder.symbol == symbol, PaperOrder.status.in_(OPEN_ORDER_STATUSES))
                .limit(1)
            )
        )

    def _sector(self, symbol: str) -> str | None:
        value = self.db.scalar(select(SymbolMaster.sector).where(SymbolMaster.symbol == symbol).limit(1))
        return str(value) if value else None

    @staticmethod
    def _position_market_value(row: PaperPosition) -> float:
        if row.market_value is not None:
            return float(row.market_value)
        price = row.last_price if row.last_price is not None else row.avg_price
        return float(price or 0.0) * int(row.qty or 0)

    @staticmethod
    def _data_quality_flags(candidate: ScreenResult, metadata: dict[str, Any]) -> dict[str, bool]:
        parsed = PaperBotExecutor._json_object(candidate.data_quality_flags_json)
        if not parsed:
            parsed = metadata.get("data_quality_flags") if isinstance(metadata.get("data_quality_flags"), dict) else {}
        normalized: dict[str, bool] = {}
        for key, value in parsed.items():
            if isinstance(value, bool):
                normalized[str(key)] = value
        return normalized

    @staticmethod
    def _positive_float(value: Any) -> float | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    @staticmethod
    def _decision_summary(decisions: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "preview_count": len([row for row in decisions if row.get("action") == "preview"]),
            "skipped_count": len([row for row in decisions if row.get("action") == "skipped"]),
            "rejected_count": len([row for row in decisions if row.get("action") == "rejected"]),
            "submitted_count": len([row for row in decisions if row.get("action") == "submitted"]),
        }

    @staticmethod
    def _decision_payload(
        decision: PaperBotDecision,
        *,
        reason_codes: list[str] | None = None,
        sizing: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        parsed_reasons = reason_codes if reason_codes is not None else PaperBotExecutor._json_list(decision.reason_codes_json)
        return {
            "symbol": decision.symbol,
            "strategy_tag": decision.strategy_tag,
            "action": decision.action if decision.action in BOT_ALLOWED_ACTIONS else str(decision.action),
            "total_score": decision.total_score,
            "qty": decision.qty,
            "limit_price": decision.limit_price,
            "stop_price": decision.stop_price,
            "target_price": decision.target_price,
            "risk_passed": bool(decision.risk_passed),
            "reason_codes": parsed_reasons,
            "paper_order_id": decision.paper_order_id,
            "sizing": sizing or {},
        }

    @staticmethod
    def _session_payload(session: dict[str, Any]) -> dict[str, Any]:
        return {
            "session": session.get("session"),
            "session_state": session.get("session_state"),
            "trade_date": session.get("trade_date"),
            "current_session_allows_preview": bool(session.get("current_session_allows_preview")),
            "reason_codes": list(session.get("reason_codes") or []),
        }

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
    def _json_list(value: str | None) -> list[str]:
        if not value:
            return []
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return [str(item) for item in parsed] if isinstance(parsed, list) else []

    def _counts(self) -> dict[str, int]:
        return {
            "paper_orders_count": int(self.db.scalar(select(func.count()).select_from(PaperOrder)) or 0),
            "paper_bot_runs_count": int(self.db.scalar(select(func.count()).select_from(PaperBotRun)) or 0),
            "paper_bot_decisions_count": int(
                self.db.scalar(select(func.count()).select_from(PaperBotDecision)) or 0
            ),
        }


def _merge_reason_codes(codes: list[str]) -> list[str]:
    merged: list[str] = []
    for code in codes:
        if code not in merged:
            merged.append(code)
    return merged
