from __future__ import annotations

import json

from backend.app.services.discord_webhook_notifier import DiscordWebhookNotifier
from backend.app.services.notification_service import SUPPORTED_NOTIFICATION_EVENTS, NotificationService


def _write_telegram_mock_config(tmp_path) -> None:
    tmp_path.joinpath("notifications.yaml").write_text(
        """
notifications:
  enabled: true
  default_dry_run: false
  channels:
    telegram_main:
      type: telegram
      enabled: true
      mode: mock
      bot_token_env: TELEGRAM_BOT_TOKEN
      chat_id_env: TELEGRAM_CHAT_ID
      dry_run: false
      parse_mode: null
    discord_ops:
      type: discord
      enabled: false
      mode: disabled
      webhook_env: DISCORD_OPS_WEBHOOK_URL
      dry_run: true
      allowed_mentions:
        parse: []
""",
        encoding="utf-8",
    )


def test_notification_status_is_telegram_first_and_lists_supported_events(tmp_path, monkeypatch) -> None:
    _write_telegram_mock_config(tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "PHASE7_TOKEN_SHOULD_NOT_LEAK")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "PHASE7_CHAT_SHOULD_NOT_LEAK")

    payload = NotificationService(config_dir=tmp_path).status()
    serialized = json.dumps(payload, ensure_ascii=False)

    assert [channel["alias"] for channel in payload["channels"]][:2] == ["telegram_main", "discord_ops"]
    assert payload["supported_events"] == list(SUPPORTED_NOTIFICATION_EVENTS)
    assert "paper_order_submitted" in payload["supported_events"]
    assert "kill_switch_triggered" in payload["supported_events"]
    assert payload["secrets_redacted"] is True
    assert "PHASE7_TOKEN_SHOULD_NOT_LEAK" not in serialized
    assert "PHASE7_CHAT_SHOULD_NOT_LEAK" not in serialized


def test_notification_test_defaults_to_telegram_mock_without_network(tmp_path, monkeypatch) -> None:
    _write_telegram_mock_config(tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "PHASE7_TOKEN_SHOULD_NOT_LEAK")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "PHASE7_CHAT_SHOULD_NOT_LEAK")

    payload = NotificationService(config_dir=tmp_path).send_test(
        message="paper order submitted",
        dry_run=False,
    )
    serialized = json.dumps(payload, ensure_ascii=False)

    assert payload["ok"] is True
    assert payload["status"] == "mock_sent"
    assert payload["attempted"] is False
    assert payload["delivered"] is True
    assert payload["channel"]["alias"] == "telegram_main"
    assert payload["payload_shape"]["parse_mode"] is None
    assert "PHASE7_TOKEN_SHOULD_NOT_LEAK" not in serialized
    assert "PHASE7_CHAT_SHOULD_NOT_LEAK" not in serialized


def test_discord_webhook_wrapper_keeps_allowed_mentions_disabled() -> None:
    payload = DiscordWebhookNotifier().build_payload("@everyone paper alert")

    assert payload["content"] == "@everyone paper alert"
    assert payload["allowed_mentions"]["parse"] == []
