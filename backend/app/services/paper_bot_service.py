from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.paths import CONFIG_DIR
from backend.app.models.tables import Order, PaperOrder

BOT_CONFIG_NAME = "bot.yaml"


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
        return config, []

    @staticmethod
    def _closed_config() -> dict[str, Any]:
        return {
            "enabled": False,
            "scheduler_enabled": False,
            "auto_submit": False,
            "kill_switch_enabled": True,
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
        return {
            "enabled": bool(config["enabled"]),
            "scheduler_enabled": bool(config["scheduler_enabled"]),
            "auto_submit": bool(config["auto_submit"]),
            "kill_switch_enabled": bool(config["kill_switch_enabled"]),
            "loop_allowed": self._loop_allowed(config),
            "auto_submit_allowed": self._auto_submit_allowed(config),
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
        """paper bot flow를 안전한 no-op 단계로 실행하고 자동 submit은 명시 opt-in 없이는 차단한다."""
        status = self.status()
        requested_auto_submit = bool(auto_submit) if auto_submit is not None else bool(status["auto_submit"])
        auto_submit_allowed = bool(status["auto_submit_allowed"]) and requested_auto_submit
        steps = [
            self._step("candidate_screening", "skipped", "PAPER_BOT_DISABLED"),
            self._step("signal_selection", "skipped", "PAPER_BOT_DISABLED"),
            self._step("risk_guard", "skipped", "PAPER_BOT_DISABLED"),
            self._step("order_preview", "skipped", "PAPER_BOT_DISABLED"),
            self._step(
                "paper_submit",
                "blocked",
                "PAPER_BOT_AUTO_SUBMIT_DISABLED" if requested_auto_submit else "PAPER_BOT_AUTO_SUBMIT_NOT_REQUESTED",
            ),
            self._step("polling_sync", "skipped", "PAPER_BOT_SYNC_DISABLED"),
            self._step("notification", "skipped", "PAPER_BOT_NOTIFICATION_DISABLED"),
            self._step("report_generation", "skipped", "PAPER_BOT_REPORT_DISABLED"),
        ]
        return {
            "ok": True,
            "status": "completed_safely" if status["enabled"] else "disabled",
            "run_once": True,
            "auto_submit_requested": requested_auto_submit,
            "auto_submit_allowed": auto_submit_allowed,
            "paper_order_submitted": False,
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": False,
            "steps": steps,
            "reason_codes": status["reason_codes"],
            "counts": self._counts(),
        }

    def loop_status(self) -> dict[str, Any]:
        """loop mode가 명시 enable 전에는 시작되지 않음을 반환한다."""
        status = self.status()
        return {
            "ok": True,
            "status": "loop_ready" if status["loop_allowed"] else "loop_disabled",
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

    @staticmethod
    def _step(name: str, status: str, reason: str) -> dict[str, str]:
        return {"name": name, "status": status, "reason": reason}

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
        }

    @staticmethod
    def _merge_reason_codes(*groups: list[str]) -> list[str]:
        merged: list[str] = []
        for group in groups:
            for code in group:
                if code not in merged:
                    merged.append(code)
        return merged
