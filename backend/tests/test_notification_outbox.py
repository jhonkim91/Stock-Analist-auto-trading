from __future__ import annotations

import json

from sqlalchemy import func, select

from backend.app.models.tables import NotificationDeliveryLog, NotificationEvent
from backend.app.services.notification_outbox_service import NotificationOutboxService
from backend.app.services.notification_service import NotificationService


def _write_config(tmp_path, *, mode: str, dry_run: bool = False) -> None:
    tmp_path.joinpath("notifications.yaml").write_text(
        f"""
notifications:
  enabled: true
  default_dry_run: {str(dry_run).lower()}
  channels:
    telegram_main:
      type: telegram
      enabled: true
      mode: {mode}
      bot_token_env: TELEGRAM_BOT_TOKEN
      chat_id_env: TELEGRAM_CHAT_ID
      dry_run: {str(dry_run).lower()}
      parse_mode: null
""",
        encoding="utf-8",
    )


def test_outbox_enqueue_redacts_payload_and_does_not_dispatch(db_session, tmp_path, monkeypatch) -> None:
    _write_config(tmp_path, mode="mock")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "PHASE7_TOKEN_SHOULD_NOT_LEAK")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "PHASE7_CHAT_SHOULD_NOT_LEAK")
    service = NotificationOutboxService(
        db_session,
        notification_service=NotificationService(config_dir=tmp_path),
    )
    token_marker = "PHASE7_" + "TOKEN_SHOULD_NOT_LEAK"
    chat_marker = "PHASE7_" + "CHAT_SHOULD_NOT_LEAK"
    token_key = "access" + "_token"
    chat_key = "chat" + "_id"

    result = service.enqueue_event(
        event_type="paper_order_submitted",
        subject=f"paper-order-1 {token_key}={token_marker}",
        payload_summary={
            "symbol": "KR009",
            "qty": 3,
            token_key: token_marker,
            "nested": {chat_key: chat_marker},
        },
    )

    event = db_session.scalar(select(NotificationEvent).where(NotificationEvent.event_id == result["event_id"]))
    serialized = json.dumps(result, ensure_ascii=False) + event.payload_summary_json
    logs_count = int(db_session.scalar(select(func.count()).select_from(NotificationDeliveryLog)) or 0)

    assert result["ok"] is True
    assert result["status"] == "queued"
    assert result["delivery_attempted"] is False
    assert event.status == "pending"
    assert event.channel_alias == "telegram_main"
    assert event.subject == "paper-order-1 [REDACTED]"
    assert "KR009" in event.payload_summary_json
    assert token_marker not in serialized
    assert chat_marker not in serialized
    assert token_key not in event.payload_summary_json
    assert chat_key not in event.payload_summary_json
    assert logs_count == 0


def test_outbox_dispatch_failure_is_isolated_and_retriable(db_session, tmp_path, monkeypatch) -> None:
    _write_config(tmp_path, mode="live")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "PHASE7_TOKEN_SHOULD_NOT_LEAK")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "PHASE7_CHAT_SHOULD_NOT_LEAK")
    notification_service = NotificationService(config_dir=tmp_path)
    service = NotificationOutboxService(db_session, notification_service=notification_service)
    queued = service.enqueue_event(event_type="portfolio_snapshot", subject="snapshot")

    def _raise_delivery(raw, message):
        raise RuntimeError("forced notification failure")

    monkeypatch.setattr(notification_service, "dispatch", _raise_delivery)
    result = service.dispatch_pending()

    event = db_session.scalar(select(NotificationEvent).where(NotificationEvent.event_id == queued["event_id"]))
    log = db_session.scalar(select(NotificationDeliveryLog).where(NotificationDeliveryLog.event_id == queued["event_id"]))

    assert result["ok"] is True
    assert result["processed_count"] == 1
    assert result["retry_count"] == 1
    assert result["non_blocking"] is True
    assert event.status == "retry"
    assert log.status == "retry"
    assert log.attempt_count == 1
    assert log.last_error_code == "DELIVERY_FAILED"


def test_outbox_dispatch_uses_configured_template(db_session, tmp_path, monkeypatch) -> None:
    _write_config(tmp_path, mode="live")
    config_path = tmp_path / "notifications.yaml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + """
  templates:
    paper_order_submitted: "paper {symbol} {qty} {missing_field}"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "PHASE2_TOKEN_SHOULD_NOT_LEAK")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "PHASE2_CHAT_SHOULD_NOT_LEAK")
    notification_service = NotificationService(config_dir=tmp_path)
    service = NotificationOutboxService(db_session, notification_service=notification_service)
    queued = service.enqueue_event(
        event_type="paper_order_submitted",
        payload_summary={"symbol": "KR001", "qty": 4},
    )
    captured: dict[str, str] = {}

    def _capture_delivery(raw, message):
        captured["message"] = message
        return {"delivered": True}

    monkeypatch.setattr(notification_service, "dispatch", _capture_delivery)
    result = service.dispatch_pending()
    event = db_session.scalar(select(NotificationEvent).where(NotificationEvent.event_id == queued["event_id"]))

    assert result["ok"] is True
    assert result["sent_count"] == 1
    assert event.status == "sent"
    assert captured["message"] == "paper KR001 4 not_available"
    assert "PHASE2_TOKEN_SHOULD_NOT_LEAK" not in json.dumps(result, ensure_ascii=False)


def test_outbox_rejects_unknown_event_without_persistence(db_session, tmp_path) -> None:
    _write_config(tmp_path, mode="mock")
    service = NotificationOutboxService(
        db_session,
        notification_service=NotificationService(config_dir=tmp_path),
    )

    result = service.enqueue_event(event_type="unknown_event")
    events_count = int(db_session.scalar(select(func.count()).select_from(NotificationEvent)) or 0)

    assert result["ok"] is False
    assert result["status"] == "unsupported_event"
    assert result["persisted"] is False
    assert events_count == 0
