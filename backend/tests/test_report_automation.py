from __future__ import annotations

import json

from sqlalchemy import select

from backend.app.core.database import SessionLocal
from backend.app.models.tables import NotificationEvent
from backend.app.services.report_automation_service import ReportAutomationService
from tools import report_automation_runner


def _automation_env(monkeypatch) -> None:
    monkeypatch.setenv("REPORT_AUTOMATION_ENABLED", "true")
    monkeypatch.setenv("REPORT_AUTOMATION_MODE", "manual")
    monkeypatch.setenv("REPORT_AUTOMATION_DRY_RUN", "true")
    monkeypatch.setenv("REPORT_AUTOMATION_NOTIFY", "false")


def test_report_automation_status_is_disabled_by_default(client, monkeypatch):
    monkeypatch.delenv("REPORT_AUTOMATION_ENABLED", raising=False)
    monkeypatch.delenv("REPORT_AUTOMATION_MODE", raising=False)

    response = client.get("/api/reports/automation/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["mode"] == "disabled"
    assert payload["scheduler_enabled"] is False
    assert payload["auto_start"] is False
    assert payload["network_call_performed"] is False
    assert "daily_report_automation_completed" in payload["notification_events"]
    assert "report_automation_failed" in payload["notification_events"]


def test_report_automation_run_once_is_blocked_without_config(client):
    response = client.post(
        "/api/reports/automation/run-once",
        json={"report_types": ["daily"], "confirm": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["status"] == "blocked"
    assert payload["generated_count"] == 0
    assert payload["scheduler_started"] is False
    assert payload["network_call_performed"] is False
    assert "REPORT_AUTOMATION_DISABLED" in payload["reason_codes"]


def test_report_automation_generates_daily_weekly_and_queues_events(full_flow_client, monkeypatch):
    _automation_env(monkeypatch)

    response = full_flow_client.post(
        "/api/reports/automation/run-once",
        json={"report_types": ["daily", "weekly"], "confirm": True, "notify": False},
    )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, ensure_ascii=False)
    assert payload["ok"] is True
    assert payload["status"] == "completed"
    assert payload["generated_count"] == 2
    assert {report["report_type"] for report in payload["reports"]} == {"daily", "weekly"}
    assert {event["event_type"] for event in payload["notification_events"]} == {
        "daily_report_automation_completed",
        "weekly_report_automation_completed",
    }
    assert payload["dispatch_result"] is None
    assert payload["scheduler_started"] is False
    assert "TELEGRAM_BOT_TOKEN" not in serialized

    with SessionLocal() as db:
        event_types = {event.event_type for event in db.scalars(select(NotificationEvent)).all()}
    assert "daily_report_automation_completed" in event_types
    assert "weekly_report_automation_completed" in event_types


def test_report_automation_failure_queues_redacted_failure_event(db_session, monkeypatch):
    _automation_env(monkeypatch)

    result = ReportAutomationService(db_session).run_once(
        report_types=["daily"],
        notify=False,
        confirm=True,
    )

    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["generated_count"] == 0
    assert result["notification_events"][0]["event_type"] == "report_automation_failed"
    event = db_session.scalar(select(NotificationEvent))
    assert event is not None
    assert event.event_type == "report_automation_failed"
    assert "KIS_APP_SECRET" not in event.payload_summary_json


def test_report_automation_runner_defaults_to_status_only(capsys):
    exit_code = report_automation_runner.main([])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["execute_required"] is True
    assert payload["scheduler_enabled"] is False
    assert payload["network_call_performed"] is False
