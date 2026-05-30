from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from sqlalchemy.orm import Session

from backend.app.core.paths import CONFIG_DIR
from backend.app.services.notification_outbox_service import NotificationOutboxService
from backend.app.services.report_service import ReportService

ReportAutomationType = Literal["daily", "weekly"]
REPORT_AUTOMATION_ENABLED_ENV = "REPORT_AUTOMATION_ENABLED"
REPORT_AUTOMATION_MODE_ENV = "REPORT_AUTOMATION_MODE"
REPORT_AUTOMATION_DRY_RUN_ENV = "REPORT_AUTOMATION_DRY_RUN"
REPORT_AUTOMATION_NOTIFY_ENV = "REPORT_AUTOMATION_NOTIFY"
REPORTS_CONFIG_NAME = "reports.yaml"
SUPPORTED_REPORT_AUTOMATION_TYPES: tuple[ReportAutomationType, ...] = ("daily", "weekly")


class ReportAutomationConfigService:
    def __init__(self, config_dir: Path = CONFIG_DIR) -> None:
        self.config_dir = config_dir

    def load(self) -> tuple[dict[str, Any], list[str]]:
        """reports.yaml automation 설정을 읽고 env override를 적용한다."""
        config = self._default_config()
        reasons: list[str] = []
        path = self.config_dir / REPORTS_CONFIG_NAME
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as file:
                    raw = yaml.safe_load(file) or {}
            except Exception:
                return config, ["REPORT_AUTOMATION_CONFIG_PARSE_FAILED"]
            automation = raw.get("automation", raw) if isinstance(raw, dict) else {}
            if not isinstance(automation, dict):
                return config, ["REPORT_AUTOMATION_CONFIG_PARSE_FAILED"]
            config.update(
                {
                    "enabled": bool(automation.get("enabled", config["enabled"])),
                    "mode": str(automation.get("mode") or config["mode"]).strip().lower(),
                    "dry_run": bool(automation.get("dry_run", config["dry_run"])),
                    "notify_default": bool(automation.get("notify_default", config["notify_default"])),
                }
            )
        else:
            reasons.append("REPORT_AUTOMATION_CONFIG_NOT_FOUND")

        config["enabled"] = _env_bool(REPORT_AUTOMATION_ENABLED_ENV, default=bool(config["enabled"]))
        config["mode"] = os.getenv(REPORT_AUTOMATION_MODE_ENV, str(config["mode"])).strip().lower() or "disabled"
        config["dry_run"] = _env_bool(REPORT_AUTOMATION_DRY_RUN_ENV, default=bool(config["dry_run"]))
        config["notify_default"] = _env_bool(REPORT_AUTOMATION_NOTIFY_ENV, default=bool(config["notify_default"]))
        if config["mode"] not in {"disabled", "manual"}:
            config["mode"] = "disabled"
            reasons.append("REPORT_AUTOMATION_MODE_UNSUPPORTED")
        return config, reasons

    @staticmethod
    def _default_config() -> dict[str, Any]:
        return {
            "enabled": False,
            "mode": "disabled",
            "dry_run": True,
            "notify_default": False,
        }


class ReportAutomationService:
    """일간/주간 report run-once automation을 수동 gate 뒤에서 실행한다."""

    def __init__(self, db: Session, *, config_dir: Path = CONFIG_DIR) -> None:
        self.db = db
        self.report_service = ReportService(db)
        self.outbox = NotificationOutboxService(db)
        self.config_service = ReportAutomationConfigService(config_dir)

    def status(self) -> dict[str, Any]:
        """report automation 상태를 secret 없이 반환한다."""
        config, config_reasons = self.config_service.load()
        enabled = bool(config["enabled"])
        mode = str(config["mode"])
        dry_run = bool(config["dry_run"])
        notify_default = bool(config["notify_default"])
        reason_codes: list[str] = []
        if not enabled:
            reason_codes.append("REPORT_AUTOMATION_DISABLED")
        if mode == "disabled":
            reason_codes.append("REPORT_AUTOMATION_MODE_DISABLED")
        reason_codes.extend(config_reasons)
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
