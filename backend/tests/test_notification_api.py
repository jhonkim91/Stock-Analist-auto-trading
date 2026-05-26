from __future__ import annotations

import json


def test_notification_status_endpoint_redacts_env_values(client, monkeypatch):
    sentinel = "PHASE1_SENTINEL_SECRET_VALUE"
    monkeypatch.setenv("DISCORD_OPS_WEBHOOK_URL", sentinel)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", sentinel)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")

    response = client.get("/api/notifications/status")

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, ensure_ascii=False)
    assert payload["enabled"] is False
    assert payload["secrets_redacted"] is True
    assert "discord_ops" in {channel["alias"] for channel in payload["channels"]}
    assert "telegram_main" in {channel["alias"] for channel in payload["channels"]}
    assert sentinel not in serialized
    assert "123456789" not in serialized


def test_notification_test_endpoint_supports_disabled_dry_run(client, monkeypatch):
    sentinel = "PHASE1_SENTINEL_SECRET_VALUE"
    monkeypatch.setenv("DISCORD_OPS_WEBHOOK_URL", sentinel)

    response = client.post(
        "/api/notifications/test",
        json={"channel_alias": "discord_ops", "message": f"hello {sentinel}", "dry_run": True},
    )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, ensure_ascii=False)
    assert payload["ok"] is True
    assert payload["status"] == "disabled"
    assert payload["attempted"] is False
    assert payload["delivered"] is False
    assert sentinel not in serialized


def test_settings_endpoint_includes_redacted_notification_config(client):
    response = client.get("/api/settings")

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "notifications" in payload
    assert payload["notifications"]["notifications"]["channels"]["discord_ops"]["webhook_env"] == "***REDACTED***"
    assert payload["notifications"]["notifications"]["channels"]["telegram_main"]["bot_token_env"] == "***REDACTED***"
    assert payload["notifications"]["notifications"]["channels"]["telegram_main"]["chat_id_env"] == "***REDACTED***"
    assert "DISCORD_OPS_WEBHOOK_URL" not in serialized
    assert "TELEGRAM_BOT_TOKEN" not in serialized
    assert "TELEGRAM_CHAT_ID" not in serialized
