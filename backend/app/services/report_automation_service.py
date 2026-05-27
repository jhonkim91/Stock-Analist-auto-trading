from __future__ import annotations

import os
from datetime import date
from typing import Any, Literal

from sqlalchemy.orm import Session

from backend.app.services.notification_outbox_service import NotificationOutboxService
from backend.app.services.report_service import ReportService

ReportAutomationType = Literal["daily", "weekly"]
REPORT_AUTOMATION_ENABLED_ENV = "REPORT_AUTOMATION_ENABLED"
REPORT_AUTOMATION_MODE_ENV = "REPORT_AUTOMATION_MODE"
REPORT_AUTOMATION_DRY_RUN_ENV = "REPORT_AUTOMATION_DRY_RUN"
REPORT_AUTOMATION_NOTIFY_ENV = "REPORT_AUTOMATION_NOTIFY"
SUPPORTED_REPORT_AUTOMATION_TYPES: tuple[ReportAutomationType, ...] = ("daily", "weekly")


class ReportAutomationService:
    """일간/주간 report run-once automation을 disabled-by-default로 실행한다."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.report_service = ReportService(db)
        self.outbox = NotificationOutboxService(db)

    def status(self) -> dict[str, Any]:
        """report automation 상태를 secret 없이 반환한다."""
        mode = os.getenv(REPORT_AUTOMATION_MODE_ENV, "disabled").strip().lower() or "disabled"
        if mode not in {"disabled", "manual"}:
            mode = "disabled"
        enabled = _env_bool(REPORT_AUTOMATION_ENABLED_ENV, default=False)
        dry_run = _env_bool(REPORT_AUTOMATION_DRY_RUN_ENV, default=True)
        notify_default = _env_bool(REPORT_AUTOMATION_NOTIFY_ENV, default=False)
        reason_codes: list[str] = []
        if not enabled:
            reason_codes.append("REPORT_AUTOMATION_DISABLED")
        if mode == "disabled":
            reason_codes.append("REPORT_AUTOMATION_MODE_DISABLED")
        return {
            "enabled": enabled,
            "mode": mode,
            "dry_run": dry_run,
            "notify_default": notify_default,
            "scheduler_enabled": False,
            "auto_start": False,
            "supported_report_types": list(SUPPORTED_REPORT_AUTOMATION_TYPES),
            "public_surface": {
                "status_route": "GET /api/reports/automation/status",
                "run_once_route": "POST /api/reports/automation/run-once",
                "cli": "tools/report_automation_runner.py",
            },
            "notification_events": [
                "daily_report_automation_completed",
                "weekly_report_automation_completed",
                "report_automation_failed",
            ],
            "secrets_redacted": True,
            "network_call_performed": False,
            "reason_codes": reason_codes,
        }

    def run_once(
        self,
        *,
        report_types: list[ReportAutomationType] | None = None,
        report_date: date | None = None,
        notify: bool | None = None,
        channel_alias: str | None = None,
        dry_run: bool | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """명시적 gate 통과 시 daily/weekly report를 생성하고 outbox event를 남긴다."""
        status = self.status()
        selected_types = self._normalize_report_types(report_types)
        effective_notify = status["notify_default"] if notify is None else bool(notify)
        effective_dry_run = status["dry_run"] if dry_run is None else bool(dry_run)
        if not confirm:
            return self._blocked_result(
                status=status,
                selected_types=selected_types,
                reason_codes=["REPORT_AUTOMATION_CONFIRMATION_REQUIRED"],
                notify=effective_notify,
                dry_run=effective_dry_run,
            )
        if not status["enabled"] or status["mode"] == "disabled":
            return self._blocked_result(
                status=status,
                selected_types=selected_types,
                reason_codes=status["reason_codes"],
                notify=effective_notify,
                dry_run=effective_dry_run,
            )

        reports: list[dict[str, Any]] = []
        notification_events: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for report_type in selected_types:
            try:
                report = self._generate_report(report_type, report_date)
            except Exception as exc:
                errors.append({"report_type": report_type, "reason": str(exc)})
                notification_events.append(
                    self._enqueue_event(
                        event_type="report_automation_failed",
                        subject=f"report_automation:{report_type}",
                        payload_summary={
                            "report_type": report_type,
                            "status": "failed",
                            "reason": str(exc),
                            "network_call_performed": False,
                        },
                        channel_alias=channel_alias,
                    )
                )
                continue
            reports.append(report)
            notification_events.append(
                self._enqueue_event(
                    event_type=f"{report_type}_report_automation_completed",
                    subject=str(report["report_id"]),
                    payload_summary={
                        "report_id": report["report_id"],
                        "report_type": report_type,
                        "status": "completed",
                        "path": report["path"],
                        "chars": report["chars"],
                        "network_call_performed": False,
                    },
                    channel_alias=channel_alias,
                )
            )

        dispatch_result: dict[str, Any] | None = None
        if effective_notify and notification_events:
            dispatch_result = self.outbox.dispatch_pending(limit=len(notification_events))

        automation_status = "completed" if reports and not errors else "failed" if errors and not reports else "partial_failed"
        return {
            "ok": not errors,
            "status": automation_status,
            "enabled": status["enabled"],
            "mode": status["mode"],
            "dry_run": effective_dry_run,
            "notify_requested": effective_notify,
            "report_types": selected_types,
            "reports": reports,
            "generated_count": len(reports),
            "errors": errors,
            "notification_events": notification_events,
            "dispatch_result": dispatch_result,
            "scheduler_started": False,
            "auto_start": False,
            "network_call_performed": False,
            "secrets_redacted": True,
        }

    def _generate_report(self, report_type: ReportAutomationType, report_date: date | None) -> dict[str, Any]:
        if report_type == "daily":
            return self.report_service.generate_daily_report(report_date)
        if report_type == "weekly":
            return self.report_service.generate_weekly_report(report_date)
        raise ValueError(f"unsupported report_type: {report_type}")

    def _enqueue_event(
        self,
        *,
        event_type: str,
        subject: str,
        payload_summary: dict[str, Any],
        channel_alias: str | None,
    ) -> dict[str, Any]:
        try:
            return self.outbox.enqueue_event(
                event_type=event_type,
                subject=subject,
                payload_summary=payload_summary,
                channel_alias=channel_alias,
            )
        except Exception as exc:
            return {
                "ok": False,
                "status": "notification_enqueue_failed",
                "event_type": event_type,
                "persisted": False,
                "reason_codes": ["REPORT_AUTOMATION_NOTIFICATION_ENQUEUE_FAILED"],
                "reason": str(exc),
                "secrets_redacted": True,
            }

    @staticmethod
    def _normalize_report_types(report_types: list[ReportAutomationType] | None) -> list[ReportAutomationType]:
        selected = report_types or list(SUPPORTED_REPORT_AUTOMATION_TYPES)
        normalized: list[ReportAutomationType] = []
        for report_type in selected:
            if report_type in SUPPORTED_REPORT_AUTOMATION_TYPES and report_type not in normalized:
                normalized.append(report_type)
        return normalized or list(SUPPORTED_REPORT_AUTOMATION_TYPES)

    @staticmethod
    def _blocked_result(
        *,
        status: dict[str, Any],
        selected_types: list[ReportAutomationType],
        reason_codes: list[str],
        notify: bool,
        dry_run: bool,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "status": "blocked",
            "enabled": status["enabled"],
            "mode": status["mode"],
            "dry_run": dry_run,
            "notify_requested": notify,
            "report_types": selected_types,
            "reports": [],
            "generated_count": 0,
            "errors": [],
            "notification_events": [],
            "dispatch_result": None,
            "scheduler_started": False,
            "auto_start": False,
            "network_call_performed": False,
            "secrets_redacted": True,
            "reason_codes": reason_codes,
        }


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
