from __future__ import annotations

import json
import os
from datetime import date
from typing import Any, Literal

from sqlalchemy.orm import Session

from backend.app.models.tables import PaperAuditEvent
from backend.app.services.report_automation_service import ReportAutomationService
from backend.app.services.report_notification_service import ReportNotificationService

TelegramReportSlot = Literal["manual", "pre_market", "post_market", "weekly"]

TELEGRAM_REPORT_SCHEDULER_ENABLED_ENV = "TELEGRAM_REPORT_SCHEDULER_ENABLED"
TELEGRAM_PRE_MARKET_REPORT_ENABLED_ENV = "TELEGRAM_PRE_MARKET_REPORT_ENABLED"
TELEGRAM_POST_MARKET_REPORT_ENABLED_ENV = "TELEGRAM_POST_MARKET_REPORT_ENABLED"
TELEGRAM_WEEKLY_REPORT_ENABLED_ENV = "TELEGRAM_WEEKLY_REPORT_ENABLED"
TELEGRAM_REPORT_DRY_RUN_ENV = "TELEGRAM_REPORT_DRY_RUN"
TELEGRAM_PRE_MARKET_REPORT_TIME_ENV = "TELEGRAM_PRE_MARKET_REPORT_TIME"
TELEGRAM_POST_MARKET_REPORT_TIME_ENV = "TELEGRAM_POST_MARKET_REPORT_TIME"
TELEGRAM_WEEKLY_REPORT_TIME_ENV = "TELEGRAM_WEEKLY_REPORT_TIME"
DEFAULT_TELEGRAM_CHANNEL_ALIAS = "telegram_main"
SUPPORTED_TELEGRAM_REPORT_SLOTS = {"manual", "pre_market", "post_market", "weekly"}


class TelegramReportSchedulerService:
    """Telegram daily/weekly report 예약 실행 구조를 수동 gate 뒤에서 제공한다."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def status(self) -> dict[str, Any]:
        """Telegram report scheduler 상태를 secret 없이 반환한다."""
        scheduler_enabled = _env_true(TELEGRAM_REPORT_SCHEDULER_ENABLED_ENV)
        pre_market_enabled = _env_true(TELEGRAM_PRE_MARKET_REPORT_ENABLED_ENV)
        post_market_enabled = _env_true(TELEGRAM_POST_MARKET_REPORT_ENABLED_ENV)
        weekly_enabled = _env_true(TELEGRAM_WEEKLY_REPORT_ENABLED_ENV)
        return {
            "enabled": scheduler_enabled,
            "scheduler_enabled": scheduler_enabled,
            "auto_start": False,
            "dry_run_default": _env_bool(TELEGRAM_REPORT_DRY_RUN_ENV, default=True),
            "default_channel_alias": DEFAULT_TELEGRAM_CHANNEL_ALIAS,
            "supported_slots": sorted(SUPPORTED_TELEGRAM_REPORT_SLOTS),
            "slots": {
                "manual": {
                    "enabled": True,
                    "report_types": ["daily", "weekly"],
                    "requires_confirm": True,
                    "time": None,
                },
                "pre_market": {
                    "enabled": scheduler_enabled and pre_market_enabled,
                    "report_types": ["daily"],
                    "requires_confirm": True,
                    "time": os.getenv(TELEGRAM_PRE_MARKET_REPORT_TIME_ENV, "08:30"),
                },
                "post_market": {
                    "enabled": scheduler_enabled and post_market_enabled,
                    "report_types": ["daily"],
                    "requires_confirm": True,
                    "time": os.getenv(TELEGRAM_POST_MARKET_REPORT_TIME_ENV, "16:10"),
                },
                "weekly": {
                    "enabled": scheduler_enabled and weekly_enabled,
                    "report_types": ["weekly"],
                    "requires_confirm": True,
                    "time": os.getenv(TELEGRAM_WEEKLY_REPORT_TIME_ENV, "16:30"),
                },
            },
            "public_surface": {
                "status_route": "GET /api/telegram/scheduler/status",
                "run_once_route": "POST /api/telegram/scheduler/run-once",
                "webhook_route": "POST /api/telegram/webhook",
                "cli": "backend.app.jobs.telegram_report_runner",
            },
            "network_call_performed": False,
            "live_order_created": False,
            "secrets_redacted": True,
            "reason_codes": [] if scheduler_enabled else ["TELEGRAM_REPORT_SCHEDULER_DISABLED"],
        }

    def run_once(
        self,
        *,
        slot: TelegramReportSlot = "manual",
        report_types: list[str] | None = None,
        report_date: date | None = None,
        channel_alias: str | None = DEFAULT_TELEGRAM_CHANNEL_ALIAS,
        dry_run: bool | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """선택한 report slot을 1회 실행하고 Telegram-safe summary delivery를 수행한다."""
        normalized_slot = str(slot or "manual").strip().lower()
        status = self.status()
        if normalized_slot not in SUPPORTED_TELEGRAM_REPORT_SLOTS:
            return self._blocked(
                status=status,
                slot=normalized_slot,
                reason_codes=["TELEGRAM_REPORT_SLOT_UNSUPPORTED"],
                report_types=[],
            )
        selected_types = self._report_types_for_slot(normalized_slot, report_types)
        if not confirm:
            result = self._blocked(
                status=status,
                slot=normalized_slot,
                reason_codes=["TELEGRAM_REPORT_CONFIRMATION_REQUIRED"],
                report_types=selected_types,
            )
            self._audit(result)
            return result
        slot_status = status["slots"][normalized_slot]
        if normalized_slot != "manual" and not bool(slot_status["enabled"]):
            result = self._blocked(
                status=status,
                slot=normalized_slot,
                reason_codes=["TELEGRAM_REPORT_SLOT_DISABLED"],
                report_types=selected_types,
            )
            self._audit(result)
            return result

        automation = ReportAutomationService(self.db).run_once(
            report_types=selected_types,
            report_date=report_date,
            notify=False,
            channel_alias=channel_alias or DEFAULT_TELEGRAM_CHANNEL_ALIAS,
            dry_run=True,
            confirm=True,
        )
        deliveries: list[dict[str, Any]] = []
        effective_dry_run = status["dry_run_default"] if dry_run is None else bool(dry_run)
        for report in automation.get("reports") or []:
            deliveries.append(
                ReportNotificationService(self.db).notify(
                    report_id=str(report["report_id"]),
                    mode="summary",
                    channel_alias=channel_alias or DEFAULT_TELEGRAM_CHANNEL_ALIAS,
                    dry_run=effective_dry_run,
                )
            )
        reason_codes = self._merge_reason_codes(
            list(automation.get("reason_codes") or []),
            [code for delivery in deliveries for code in delivery.get("reason_codes") or []],
        )
        ok = bool(automation.get("ok")) and all(delivery.get("ok") for delivery in deliveries)
        result = {
            "ok": ok,
            "status": "completed" if ok else str(automation.get("status") or "failed"),
            "slot": normalized_slot,
            "report_types": selected_types,
            "generated_count": int(automation.get("generated_count") or 0),
            "reports": automation.get("reports") or [],
            "deliveries": deliveries,
            "delivery_count": len(deliveries),
            "dry_run": effective_dry_run,
            "channel_alias": channel_alias or DEFAULT_TELEGRAM_CHANNEL_ALIAS,
            "scheduler_started": False,
            "auto_start": False,
            "network_call_performed": any(bool(delivery.get("attempted")) for delivery in deliveries),
            "live_order_created": False,
            "secrets_redacted": True,
            "reason_codes": reason_codes,
        }
        self._audit(result)
        return result

    def _blocked(
        self,
        *,
        status: dict[str, Any],
        slot: str,
        reason_codes: list[str],
        report_types: list[str],
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "status": "blocked",
            "slot": slot,
            "report_types": report_types,
            "generated_count": 0,
            "reports": [],
            "deliveries": [],
            "delivery_count": 0,
            "dry_run": status.get("dry_run_default", True),
            "scheduler_started": False,
            "auto_start": False,
            "network_call_performed": False,
            "live_order_created": False,
            "secrets_redacted": True,
            "reason_codes": reason_codes,
        }

    def _audit(self, result: dict[str, Any]) -> None:
        self.db.add(
            PaperAuditEvent(
                event_type="telegram_report_scheduler",
                decision="allow" if result.get("ok") else "deny",
                reason_codes_json=json.dumps(result.get("reason_codes") or [], ensure_ascii=False),
                payload_json=json.dumps(
                    {
                        "slot": result.get("slot"),
                        "status": result.get("status"),
                        "generated_count": result.get("generated_count"),
                        "delivery_count": result.get("delivery_count"),
                        "network_call_performed": result.get("network_call_performed"),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
        )
        self.db.commit()

    @staticmethod
    def _report_types_for_slot(slot: str, requested: list[str] | None) -> list[str]:
        if requested:
            selected = [item for item in requested if item in {"daily", "weekly"}]
            return list(dict.fromkeys(selected)) or ["daily"]
        if slot == "weekly":
            return ["weekly"]
        if slot in {"pre_market", "post_market"}:
            return ["daily"]
        return ["daily", "weekly"]

    @staticmethod
    def _merge_reason_codes(*groups: list[str]) -> list[str]:
        merged: list[str] = []
        for group in groups:
            for code in group:
                if code not in merged:
                    merged.append(code)
        return merged


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
