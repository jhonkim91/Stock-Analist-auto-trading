from __future__ import annotations

import json
import os

from sqlalchemy import select

from backend.app.models.tables import PaperAuditEvent
from backend.app.services.paper_sync_worker_service import PaperSyncWorkerService
from backend.app.services.telegram_bot_service import TelegramBotService
from backend.app.services.telegram_polling_service import TelegramPollingService
from tools import report_automation_runner
from backend.app.jobs import paper_sync_runner, telegram_polling_runner, telegram_report_runner


class _TelegramResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, object]:
        return self._payload


class _TelegramClient:
    def __init__(self, updates: list[dict[str, object]]) -> None:
        self.updates = updates
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, *, headers: dict[str, str], json: dict[str, object], timeout: float) -> _TelegramResponse:
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        if url.endswith("/getUpdates"):
            return _TelegramResponse({"ok": True, "result": self.updates})
        return _TelegramResponse({"ok": True, "result": {"message_id": 1}})


def test_telegram_webhook_dispatches_search_command_without_secret_leak(full_flow_client, monkeypatch) -> None:
    monkeypatch.setenv("KIS_MARKET_QUOTE_ENABLED", "false")

    response = full_flow_client.post(
        "/api/telegram/webhook",
        json={"update_id": 1001, "message": {"chat": {"id": 12345}, "text": "/search KR009"}},
    )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, ensure_ascii=False)
    assert payload["ok"] is True
    assert payload["webhook_update_received"] is True
    assert payload["command"] == "/search"
    assert payload["payload"]["quote"]["fallback_used"] is True
    assert payload["network_call_performed"] is False
    assert "TELEGRAM_BOT_TOKEN" not in serialized
    assert "12345" not in serialized


def test_telegram_polling_default_off_and_confirmation_gated(client) -> None:
    status = client.get("/api/telegram/polling/status")
    blocked = client.post("/api/telegram/polling/run-once", json={"confirm": False})

    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload["polling_allowed"] is False
    assert status_payload["auto_start"] is False
    assert "TELEGRAM_BOT_DISABLED" in status_payload["reason_codes"]
    assert blocked.status_code == 200
    blocked_payload = blocked.json()
    assert blocked_payload["status"] == "polling_blocked"
    assert blocked_payload["network_call_performed"] is False
    assert "TELEGRAM_POLLING_CONFIRMATION_REQUIRED" in blocked_payload["reason_codes"]


def test_telegram_polling_get_updates_dispatches_commands_without_reply_network(db_session, monkeypatch) -> None:
    marker = "test-token-value"
    monkeypatch.setenv("TELEGRAM_BOT_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_POLLING_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", marker)
    monkeypatch.setenv("TELEGRAM_POLLING_DRY_RUN", "true")
    client = _TelegramClient(
        [
            {
                "update_id": 10,
                "message": {"chat": {"id": 12345}, "text": "/help"},
            }
        ]
    )

    result = TelegramPollingService(db_session, http_client=client).run_once(confirm=True)
    serialized = json.dumps(result, ensure_ascii=False)
    events = list(db_session.scalars(select(PaperAuditEvent)).all())

    assert result["ok"] is True
    assert result["updates_received"] == 1
    assert result["commands_dispatched"] == 1
    assert result["reply_attempts"] == 0
    assert result["next_offset"] == 11
    assert result["network_call_performed"] is True
    assert len(client.calls) == 1
    assert marker not in serialized
    assert "12345" not in serialized
    assert {event.event_type for event in events} == {"telegram_command", "telegram_polling_run"}


def test_telegram_polling_can_send_replies_when_explicitly_enabled(db_session, monkeypatch) -> None:
    marker = "test-token-value"
    monkeypatch.setenv("TELEGRAM_BOT_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_POLLING_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", marker)
    client = _TelegramClient(
        [
            {
                "update_id": 20,
                "message": {"chat": {"id": 67890}, "text": "/help"},
            }
        ]
    )

    result = TelegramPollingService(db_session, http_client=client).run_once(
        confirm=True,
        dry_run=False,
        send_replies=True,
    )
    serialized = json.dumps(result, ensure_ascii=False)

    assert result["ok"] is True
    assert result["reply_attempts"] == 1
    assert len(client.calls) == 2
    assert str(client.calls[0]["url"]).endswith("/getUpdates")
    assert str(client.calls[1]["url"]).endswith("/sendMessage")
    assert marker not in serialized
    assert "67890" not in serialized


def test_telegram_bot_command_controls_paper_bot_runtime_env(db_session, monkeypatch) -> None:
    service = TelegramBotService(db_session)

    status = service.handle_text("/bot status")
    blocked = service.handle_text("/bot auto on")
    enabled = service.handle_text("/bot enable confirm")
    enabled_env = os.environ["PAPER_BOT_ENABLED"]
    auto_on = service.handle_text("/bot auto on confirm")
    auto_env = os.environ["PAPER_BOT_AUTO_SUBMIT"]
    run = service.handle_text("/bot run confirm auto_submit=false")
    disabled = service.handle_text("/bot disable confirm")

    assert status["ok"] is True
    assert status["payload"]["enabled"] is False
    assert "TELEGRAM_BOT_CONTROL_CONFIRM_REQUIRED" in blocked["reason_codes"]
    assert enabled["status"] == "updated"
    assert enabled["payload"]["enabled"] is True
    assert enabled_env == "true"
    assert auto_on["payload"]["auto_submit"] is True
    assert auto_env == "true"
    assert run["payload"]["live_order_created"] is False
    assert run["payload"]["network_call_performed"] is False
    assert disabled["status"] == "updated"
    assert os.environ["PAPER_BOT_ENABLED"] == "false"
    assert os.environ["PAPER_BOT_AUTO_SUBMIT"] == "false"


def test_telegram_report_scheduler_is_default_off_and_confirmation_gated(client) -> None:
    status = client.get("/api/telegram/scheduler/status")
    blocked = client.post("/api/telegram/scheduler/run-once", json={"slot": "pre_market", "confirm": False})

    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload["scheduler_enabled"] is False
    assert status_payload["auto_start"] is False
    assert "TELEGRAM_REPORT_SCHEDULER_DISABLED" in status_payload["reason_codes"]
    assert blocked.status_code == 200
    blocked_payload = blocked.json()
    assert blocked_payload["status"] == "blocked"
    assert blocked_payload["generated_count"] == 0
    assert blocked_payload["network_call_performed"] is False
    assert "TELEGRAM_REPORT_CONFIRMATION_REQUIRED" in blocked_payload["reason_codes"]


def test_telegram_report_scheduler_manual_dry_run_sends_latest_report_summary(full_flow_client, monkeypatch) -> None:
    monkeypatch.setenv("REPORT_AUTOMATION_ENABLED", "true")
    monkeypatch.setenv("REPORT_AUTOMATION_MODE", "manual")
    monkeypatch.setenv("REPORT_AUTOMATION_DRY_RUN", "true")
    monkeypatch.setenv("TELEGRAM_REPORT_DRY_RUN", "true")

    response = full_flow_client.post(
        "/api/telegram/scheduler/run-once",
        json={
            "slot": "manual",
            "report_types": ["daily"],
            "channel_alias": "telegram_main",
            "dry_run": True,
            "confirm": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, ensure_ascii=False)
    assert payload["ok"] is True
    assert payload["status"] == "completed"
    assert payload["generated_count"] == 1
    assert payload["delivery_count"] == 1
    assert payload["deliveries"][0]["status"] == "dry_run"
    assert payload["network_call_performed"] is False
    assert "TELEGRAM_BOT_TOKEN" not in serialized


def test_paper_sync_worker_default_off_and_confirm_gate(client) -> None:
    status = client.get("/api/paper/sync-worker/status")
    blocked = client.post("/api/paper/sync-worker/run-once", json={"scope": "all", "confirm": False})

    assert status.status_code == 200
    assert status.json()["enabled"] is False
    assert status.json()["auto_start"] is False
    assert "PAPER_SYNC_WORKER_DISABLED" in status.json()["reason_codes"]
    assert blocked.status_code == 200
    payload = blocked.json()
    assert payload["status"] == "worker_blocked"
    assert payload["sync_performed"] is False
    assert payload["network_call_performed"] is False
    assert "PAPER_SYNC_WORKER_CONFIRMATION_REQUIRED" in payload["reason_codes"]


def test_paper_sync_worker_enabled_calls_sync_gate_without_live_network(db_session, monkeypatch) -> None:
    monkeypatch.setenv("PAPER_SYNC_WORKER_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRADING_NETWORK_ENABLED", "false")
    monkeypatch.setenv("ENABLE_REAL_ORDER", "false")

    result = PaperSyncWorkerService(db_session).run_once(scope="all", confirm=True)
    events = list(db_session.scalars(select(PaperAuditEvent).where(PaperAuditEvent.event_type == "paper_sync_worker")).all())

    assert result["worker_run_performed"] is True
    assert result["sync_performed"] is False
    assert result["network_call_performed"] is False
    assert result["live_order_created"] is False
    assert "PAPER_NETWORK_DISABLED" in result["reason_codes"]
    assert len(events) == 1
    assert events[0].decision == "allow"


def test_runner_defaults_are_status_only(capsys) -> None:
    telegram_exit = telegram_report_runner.main([])
    telegram_payload = json.loads(capsys.readouterr().out)
    polling_exit = telegram_polling_runner.main([])
    polling_payload = json.loads(capsys.readouterr().out)
    paper_exit = paper_sync_runner.main([])
    paper_payload = json.loads(capsys.readouterr().out)
    report_exit = report_automation_runner.main([])
    report_payload = json.loads(capsys.readouterr().out)

    assert telegram_exit == 0
    assert telegram_payload["execute_required"] is True
    assert telegram_payload["network_call_performed"] is False
    assert polling_exit == 0
    assert polling_payload["execute_required"] is True
    assert polling_payload["network_call_performed"] is False
    assert paper_exit == 0
    assert paper_payload["execute_required"] is True
    assert paper_payload["network_call_performed"] is False
    assert report_exit == 0
    assert report_payload["execute_required"] is True
