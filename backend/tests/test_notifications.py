from __future__ import annotations

import json

from backend.app.services.discord_notifier import DiscordNotifier
from backend.app.services.notification_service import NotificationService
from backend.app.services.telegram_notifier import TelegramNotifier


def test_default_notification_status_is_disabled_and_redacted(monkeypatch):
    sentinel = "PHASE1_SENTINEL_SECRET_VALUE"
    monkeypatch.setenv("DISCORD_OPS_WEBHOOK_URL", sentinel)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", sentinel)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")

    payload = NotificationService().status()
    serialized = json.dumps(payload, ensure_ascii=False)

    assert payload["enabled"] is False
    assert payload["network_delivery_allowed"] is False
    assert payload["secrets_redacted"] is True
    assert {channel["alias"] for channel in payload["channels"]} == {"discord_ops", "telegram_main"}
    assert sentinel not in serialized
    assert "123456789" not in serialized


def test_disabled_notification_test_is_safe_dry_run(monkeypatch):
    sentinel = "PHASE1_SENTINEL_SECRET_VALUE"
    monkeypatch.setenv("DISCORD_OPS_WEBHOOK_URL", sentinel)

    payload = NotificationService().send_test(
        channel_alias="discord_ops",
        message=f"dry-run {sentinel}",
        dry_run=True,
    )
    serialized = json.dumps(payload, ensure_ascii=False)

    assert payload["ok"] is True
    assert payload["status"] == "disabled"
    assert payload["attempted"] is False
    assert payload["delivered"] is False
    assert payload["dry_run"] is True
    assert payload["message_length"] == len(f"dry-run {sentinel}")
    assert sentinel not in serialized


def test_mock_notification_channel_does_not_require_network(tmp_path):
    (tmp_path / "notifications.yaml").write_text(
        """
notifications:
  enabled: true
  default_dry_run: false
  channels:
    discord_ops:
      type: discord
      enabled: true
      mode: mock
      webhook_env: DISCORD_OPS_WEBHOOK_URL
      dry_run: false
      allowed_mentions:
        parse: []
""",
        encoding="utf-8",
    )

    payload = NotificationService(config_dir=tmp_path).send_test(
        channel_alias="discord_ops",
        message="@everyone mock",
        dry_run=False,
    )

    assert payload["ok"] is True
    assert payload["status"] == "mock_sent"
    assert payload["attempted"] is False
    assert payload["delivered"] is True
    assert payload["payload_shape"]["allowed_mentions_parse"] == []


def test_discord_payload_disables_allowed_mentions():
    payload = DiscordNotifier().build_payload("@everyone ping")

    assert payload["content"] == "@everyone ping"
    assert payload["allowed_mentions"]["parse"] == []


def test_telegram_payload_uses_plain_text_by_default():
    payload = TelegramNotifier({"parse_mode": "MarkdownV2"}).build_payload(
        chat_id="redacted-chat",
        message="plain * text",
    )

    assert payload["text"] == "plain * text"
    assert "parse_mode" not in payload
