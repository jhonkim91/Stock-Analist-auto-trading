from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.paths import CONFIG_DIR
from backend.app.models.tables import Order, PaperBotDecision, PaperBotRun, PaperOrder, ScreenResult
from backend.app.services.market_session_service import MarketSessionService
from backend.app.services.paper_order_service import PaperOrderService
from backend.app.services.risk_service import RiskService
from backend.app.services.screener_service import ScreenerService

BOT_CONFIG_NAME = "bot.yaml"
BOT_MODES = {"manual", "run_once", "scheduled"}


class PaperBotConfigService:
    def __init__(self, config_dir: Path = CONFIG_DIR) -> None:
        self.config_dir = config_dir

    def load(self) -> tuple[dict[str, Any], list[str]]:
        """bot.yaml을 읽고 실패 시 scheduler/auto-submit disabled 상태로 닫는다."""
        path = self.config_dir / BOT_CONFIG_NAME
        if not path.exists():
            return self._closed_config(), ["BOT_CONFIG_LOAD_FAILED"]
        try:
            with path.open("r", encoding="utf-8") as file:
                raw = yaml.safe_load(file) or {}
        except Exception:
            return self._closed_config(), ["BOT_CONFIG_PARSE_FAILED"]
        bot = raw.get("bot", raw)
        if not isinstance(bot, dict):
            return self._closed_config(), ["BOT_CONFIG_PARSE_FAILED"]
        config = self._closed_config()
        try:
            config.update(
                {
                    "enabled": bool(bot.get("enabled", False)),
                    "scheduler_enabled": bool(bot.get("scheduler_enabled", False)),
                    "auto_submit": bool(bot.get("auto_submit", False)),
                    "kill_switch_enabled": bool(bot.get("kill_switch_enabled", True)),
                    "mode": str(bot.get("mode") or "manual"),
                    "loop_interval_seconds": int(bot.get("loop_interval_seconds") or 300),
                    "max_candidates": int(bot.get("max_candidates") or 5),
                    "default_strategy": str(bot.get("default_strategy") or "trend_breakout"),
                    "sync_enabled": bool(bot.get("sync_enabled", False)),
                    "notification_enabled": bool(bot.get("notification_enabled", False)),
                    "report_generation_enabled": bool(bot.get("report_generation_enabled", False)),
                }
            )
        except (TypeError, ValueError):
            return self._closed_config(), ["BOT_CONFIG_PARSE_FAILED"]
        config["auto_submit"] = self._env_bool("PAPER_BOT_AUTO_SUBMIT", bool(config["auto_submit"]))
        config["scheduler_enabled"] = self._env_bool("PAPER_BOT_SCHEDULER_ENABLED", bool(config["scheduler_enabled"]))
        config["kill_switch_enabled"] = self._env_bool("PAPER_BOT_KILL_SWITCH", bool(config["kill_switch_enabled"]))
        if config["mode"] not in BOT_MODES:
            config["mode"] = "manual"
        return config, []

    @staticmethod
    def _closed_config() -> dict[str, Any]:
        return {
            "enabled": False,
            "scheduler_enabled": False,
            "auto_submit": False,
            "kill_switch_enabled": True,
            "mode": "manual",
            "loop_interval_seconds": 300,
            "max_candidates": 5,
            "default_strategy": "trend_breakout",
            "sync_enabled": False,
            "notification_enabled": False,
            "report_generation_enabled": False,
        }

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}


class PaperBotService:
    def __init__(self, db: Session, *, config_dir: Path = CONFIG_DIR) -> None:
        self.db = db
        self.config_service = PaperBotConfigService(config_dir)

    def status(self) -> dict[str, Any]:
        """paper bot scheduler 상태를 secret 없이 fail-closed로 반환한다."""
        config, config_reasons = self.config_service.load()
        reason_codes = self._reason_codes(config, config_reasons)
        session = self._session_status()
        return {
            "enabled": bool(config["enabled"]),
            "scheduler_enabled": bool(config["scheduler_enabled"]),
            "auto_submit": bool(config["auto_submit"]),
            "kill_switch_enabled": bool(config["kill_switch_enabled"]),
            "mode": str(config["mode"]),
            "supported_modes": sorted(BOT_MODES),
            "loop_allowed": self._loop_allowed(config),
            "auto_submit_allowed": self._auto_submit_allowed(config),
            "session": session,
            "session_check_passed": bool(session["session_check_passed"]),
            "loop_interval_seconds": int(config["loop_interval_seconds"]),
            "max_candidates": int(config["max_candidates"]),
            "default_strategy": str(config["default_strategy"]),
            "sync_enabled": bool(config["sync_enabled"]),
            "notification_enabled": bool(config["notification_enabled"]),
            "report_generation_enabled": bool(config["report_generation_enabled"]),
            "reason_codes": reason_codes,
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": False,
            "counts": self._counts(),
        }

    def run_once(self, *, auto_submit: bool | None = None) -> dict[str, Any]:
        """preview decision loop를 실행하고 명시 opt-in 없이는 자동 submit을 차단한다."""
        status = self.status()
        requested_auto_submit = bool(auto_submit) if auto_submit is not None else bool(status["auto_submit"])
        auto_submit_allowed = (
            bool(status["auto_submit_allowed"])
            and requested_auto_submit
            and bool(status["session_check_passed"])
        )
        run = PaperBotRun(
            run_id=f"bot-{uuid4().hex[:16]}",
            mode="run_once",
            status="created",
            auto_submit_requested=requested_auto_submit,
            auto_submit_allowed=auto_submit_allowed,
            decision_count=0,
            submitted_count=0,
            reason_codes_json=json.dumps(status["reason_codes"], ensure_ascii=False),
        )
        self.db.add(run)
        self.db.commit()

        candidates: list[ScreenResult] = []
        decisions: list[dict[str, Any]] = []
        submitted_count = 0
        if status["enabled"] and not status["kill_switch_enabled"]:
            candidates = ScreenerService(self.db).latest_passed_results(
                limit=int(status["max_candidates"]),
                strategy_tag=str(status["default_strategy"]),
            )
            decisions, submitted_count = self._create_decisions(
                run_id=run.run_id,
                candidates=candidates,
                auto_submit_allowed=auto_submit_allowed,
            )

        steps = self._steps(
            enabled=bool(status["enabled"]),
            candidate_count=len(candidates),
            decision_count=len(decisions),
            auto_submit_requested=requested_auto_submit,
            auto_submit_allowed=auto_submit_allowed,
        )
        run.status = "completed_safely" if status["enabled"] else "disabled"
        if status["kill_switch_enabled"]:
            run.status = "blocked"
        run.decision_count = len(decisions)
        run.submitted_count = submitted_count
        self.db.add(run)
        self.db.commit()
        return {
            "ok": True,
            "status": run.status,
            "run_id": run.run_id,
            "run_once": True,
            "mode": "run_once",
            "auto_submit_requested": requested_auto_submit,
            "auto_submit_allowed": auto_submit_allowed,
            "paper_order_submitted": submitted_count > 0,
            "submitted_count": submitted_count,
            "decision_count": len(decisions),
            "decisions": decisions,
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": False,
            "steps": steps,
            "reason_codes": status["reason_codes"],
            "session": status["session"],
            "counts": self._counts(),
        }

    def loop_status(self) -> dict[str, Any]:
        """loop mode가 명시 enable 전에는 시작되지 않음을 반환한다."""
        status = self.status()
        return {
            "ok": True,
            "status": "loop_ready" if status["loop_allowed"] else "loop_disabled",
            "mode": "scheduled",
            "loop_allowed": status["loop_allowed"],
            "scheduler_enabled": status["scheduler_enabled"],
            "kill_switch_enabled": status["kill_switch_enabled"],
            "interval_seconds": status["loop_interval_seconds"],
            "reason_codes": status["reason_codes"],
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": False,
        }

    @staticmethod
    def _loop_allowed(config: dict[str, Any]) -> bool:
        return bool(config["enabled"]) and bool(config["scheduler_enabled"]) and not bool(config["kill_switch_enabled"])

    @staticmethod
    def _auto_submit_allowed(config: dict[str, Any]) -> bool:
        return bool(config["enabled"]) and bool(config["auto_submit"]) and not bool(config["kill_switch_enabled"])

    def stop(self) -> dict[str, Any]:
        """실행 중인 scheduler process를 만들지 않는 현재 MVP에서 stop 요청을 안전하게 수용한다."""
        status = self.status()
        return {
            "ok": True,
            "status": "stopped",
            "mode": "manual",
            "scheduler_enabled": False,
            "loop_allowed": False,
            "reason_codes": self._merge_reason_codes(status["reason_codes"], ["PAPER_BOT_STOP_REQUESTED"]),
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": False,
        }

    def _create_decisions(
        self,
        *,
        run_id: str,
        candidates: list[ScreenResult],
        auto_submit_allowed: bool,
    ) -> tuple[list[dict[str, Any]], int]:
        decisions: list[dict[str, Any]] = []
        submitted_count = 0
        seen: set[tuple[str, str]] = set()
        for candidate in candidates:
            identity = (candidate.symbol, candidate.strategy_tag)
            if identity in seen:
                continue
            seen.add(identity)
            risk_gate = RiskService().bot_candidate_gate(candidate)
            action = "preview" if risk_gate["passed"] else "rejected"
            paper_order_id = None
            reason_codes = list(risk_gate["reason_codes"])
            if auto_submit_allowed and risk_gate["passed"]:
                submit_result = PaperOrderService(self.db).submit_order(
                    symbol=candidate.symbol,
                    side="buy",
                    qty=int(candidate.position_size or 0),
                    confirm=True,
                    idempotency_key=f"{run_id}:{candidate.symbol}:{candidate.strategy_tag}",
                    limit_price=candidate.entry_price,
                    stop_price=candidate.stop_price,
                    strategy_tag=candidate.strategy_tag,
                )
                if submit_result.get("ok") and submit_result.get("order"):
                    action = "submitted"
                    paper_order_id = str(submit_result["order"]["paper_order_id"])
                    submitted_count += 1
                else:
                    action = "submit_blocked"
                    reason_codes = self._merge_reason_codes(reason_codes, list(submit_result.get("reason_codes") or []))

            decision = PaperBotDecision(
                run_id=run_id,
                symbol=candidate.symbol,
                strategy_tag=candidate.strategy_tag,
                action=action,
                total_score=candidate.total_score,
                qty=int(candidate.position_size or 0),
                limit_price=candidate.entry_price,
                stop_price=candidate.stop_price,
                target_price=candidate.target_price,
                risk_passed=bool(risk_gate["passed"]),
                reason_codes_json=json.dumps(reason_codes, ensure_ascii=False),
                paper_order_id=paper_order_id,
            )
            self.db.add(decision)
            decisions.append(self._decision_payload(decision, reason_codes))
        self.db.commit()
        return decisions, submitted_count

    @staticmethod
    def _decision_payload(decision: PaperBotDecision, reason_codes: list[str]) -> dict[str, Any]:
        return {
            "symbol": decision.symbol,
            "strategy_tag": decision.strategy_tag,
            "action": decision.action,
            "total_score": decision.total_score,
            "qty": decision.qty,
            "limit_price": decision.limit_price,
            "stop_price": decision.stop_price,
            "target_price": decision.target_price,
            "risk_passed": decision.risk_passed,
            "reason_codes": reason_codes,
            "paper_order_id": decision.paper_order_id,
        }

    @staticmethod
    def _steps(
        *,
        enabled: bool,
        candidate_count: int,
        decision_count: int,
        auto_submit_requested: bool,
        auto_submit_allowed: bool,
    ) -> list[dict[str, str]]:
        disabled_reason = "PAPER_BOT_DISABLED" if not enabled else "OK"
        return [
            {"name": "candidate_screening", "status": "completed" if enabled else "skipped", "reason": disabled_reason},
            {
                "name": "signal_selection",
                "status": "completed" if candidate_count else "skipped",
                "reason": "OK" if candidate_count else "PAPER_BOT_NO_CANDIDATES",
            },
            {
                "name": "risk_guard",
                "status": "completed" if decision_count else "skipped",
                "reason": "OK" if decision_count else "PAPER_BOT_NO_DECISIONS",
            },
            {
                "name": "order_preview",
                "status": "completed" if decision_count else "skipped",
                "reason": "OK" if decision_count else "PAPER_BOT_NO_DECISIONS",
            },
            {
                "name": "paper_submit",
                "status": "allowed" if auto_submit_allowed else "blocked",
                "reason": "OK"
                if auto_submit_allowed
                else ("PAPER_BOT_AUTO_SUBMIT_DISABLED" if auto_submit_requested else "PAPER_BOT_AUTO_SUBMIT_NOT_REQUESTED"),
            },
            {"name": "polling_sync", "status": "skipped", "reason": "PAPER_BOT_SYNC_DISABLED"},
            {"name": "notification", "status": "skipped", "reason": "PAPER_BOT_NOTIFICATION_DISABLED"},
            {"name": "report_generation", "status": "skipped", "reason": "PAPER_BOT_REPORT_DISABLED"},
        ]

    @staticmethod
    def _reason_codes(config: dict[str, Any], config_reasons: list[str]) -> list[str]:
        reasons = list(config_reasons)
        if not bool(config["enabled"]):
            reasons.append("PAPER_BOT_DISABLED")
        if not bool(config["scheduler_enabled"]):
            reasons.append("PAPER_BOT_SCHEDULER_DISABLED")
        if not bool(config["auto_submit"]):
            reasons.append("PAPER_BOT_AUTO_SUBMIT_DISABLED")
        if bool(config["kill_switch_enabled"]):
            reasons.append("PAPER_BOT_KILL_SWITCH_ACTIVE")
        return PaperBotService._merge_reason_codes(reasons, [])

    def _counts(self) -> dict[str, int]:
        return {
            "orders_count": int(self.db.scalar(select(func.count()).select_from(Order)) or 0),
            "paper_orders_count": int(self.db.scalar(select(func.count()).select_from(PaperOrder)) or 0),
            "paper_bot_runs_count": int(self.db.scalar(select(func.count()).select_from(PaperBotRun)) or 0),
            "paper_bot_decisions_count": int(self.db.scalar(select(func.count()).select_from(PaperBotDecision)) or 0),
        }

    @staticmethod
    def _session_status() -> dict[str, Any]:
        session = MarketSessionService().session_at()
        return {
            "session_checked": True,
            "session_check_passed": bool(session.get("current_session_allows_preview")),
            "session_state": session.get("session_state"),
            "session": session.get("session"),
            "trade_date": session.get("trade_date"),
            "reason_codes": list(session.get("reason_codes") or []),
        }

    @staticmethod
    def _merge_reason_codes(*groups: list[str]) -> list[str]:
        merged: list[str] = []
        for group in groups:
            for code in group:
                if code not in merged:
                    merged.append(code)
        return merged
