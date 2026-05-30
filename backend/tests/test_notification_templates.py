from __future__ import annotations

import json

from backend.app.services.notification_service import NotificationService
from backend.app.services.notification_template_service import NotificationTemplateService


def test_template_service_redacts_sensitive_payload_and_fills_missing_values() -> None:
    token_key = "access" + "_token"
    chat_key = "chat" + "_id"
    token_value = "PHASE2_TOKEN_SHOULD_NOT_LEAK"
    chat_value = "PHASE2_CHAT_SHOULD_NOT_LEAK"
    service = NotificationTemplateService(
        {
            "paper_order_submitted": "symbol={symbol}; qty={qty}; reason={reason}; summary={summary}",
        }
    )

    message = service.render(
        event_type="paper_order_submitted",
        subject=f"{chat_key}={chat_value}",
        payload_summary={
            "symbol": "KR001",
            "qty": 3,
            token_key: token_value,
            "nested": {chat_key: chat_value},
        },
    )

    assert "symbol=KR001" in message
    assert "qty=3" in message
    assert "reason=not_available" in message
    assert token_value not in message
    assert chat_value not in message
    assert token_key not in message
    assert chat_key not in message


def test_notification_service_loads_configured_template_events(tmp_path) -> None:
    tmp_path.joinpath("notifications.yaml").write_text(
        """
notifications:
  enabled: false
  default_dry_run: true
  channels:
    telegram_main:
      type: telegram
      enabled: false
      mode: disabled
      bot_token_env: TELEGRAM_BOT_TOKEN
      chat_id_env: TELEGRAM_CHAT_ID
      dry_run: true
      parse_mode: null
  templates:
    portfolio_snapshot: "equity={total_equity}; positions={positions_count}"
""",
        encoding="utf-8",
    )

    service = NotificationService(config_dir=tmp_path)
    status = service.status()
    message = service.render_event_message(
        event_type="portfolio_snapshot",
        subject="snapshot",
        payload_summary={"total_equity": 1000000, "positions_count": 2},
    )
    serialized = json.dumps(status, ensure_ascii=False)

    assert status["enabled"] is False
    assert "portfolio_snapshot" in status["template_events"]
    assert "TELEGRAM_BOT_TOKEN" not in serialized
    assert "TELEGRAM_CHAT_ID" not in serialized
    assert message == "equity=1000000; positions=2"
