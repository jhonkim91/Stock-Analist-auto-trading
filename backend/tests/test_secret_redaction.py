from __future__ import annotations

import json

from tools.secret_scan import SecretFinding, candidate_paths, scan_paths
from backend.app.services.credential_redaction import CredentialRedactionService, REDACTED


def test_secret_scan_detects_raw_values_without_printing_secret(tmp_path):
    safe = tmp_path / "safe.env"
    unsafe = tmp_path / "unsafe.env"
    raw_secret = "A" * 16
    safe.write_text(
        "\n".join(
            [
                "KIS_APP_KEY=<placeholder>",
                "KIS_APP_SECRET=***REDACTED***",
                "TELEGRAM_CHAT_ID=<placeholder>",
            ]
        ),
        encoding="utf-8",
    )
    unsafe.write_text("KIS_APP_SECRET=" + raw_secret + "\n", encoding="utf-8")

    findings = scan_paths([safe, unsafe], root=tmp_path)

    assert findings == [SecretFinding(path=unsafe.relative_to(tmp_path), line_number=1, label="kis_raw_secret")]
    assert raw_secret not in repr(findings[0])


def test_repository_secret_scan_passes_current_tree():
    findings = scan_paths(candidate_paths())

    assert findings == []


def test_status_and_settings_endpoints_do_not_return_env_secrets(client, monkeypatch):
    sentinel = "PHASE9_" + "SECRET_" + "SENTINEL_" + "VALUE"
    monkeypatch.setenv("KIS_APP_KEY", sentinel)
    monkeypatch.setenv("KIS_APP_SECRET", sentinel)
    monkeypatch.setenv("DISCORD_OPS_WEBHOOK_URL", sentinel)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", sentinel)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")

    responses = [
        client.get("/api/settings"),
        client.get("/api/notifications/status"),
        client.get("/api/broker/status"),
        client.get("/api/paper/status"),
        client.get("/api/paper/bot/status"),
    ]

    for response in responses:
        assert response.status_code == 200
        serialized = json.dumps(response.json(), ensure_ascii=False)
        assert sentinel not in serialized
        assert "123456789" not in serialized

    settings_serialized = json.dumps(responses[0].json()).lower()
    for key in ("app_key", "app_secret", "token", "password", "account_no", "hts_id", "access_token", "refresh_token"):
        assert key not in settings_serialized


def test_credential_redaction_removes_nested_sensitive_values():
    payload = {
        "symbol": "005930",
        "account_no": "12345678",
        "headers": {"authorization": "Bearer RAW_TOKEN"},
        "nested": [{"chat_id": "123456789", "safe": "ok"}],
    }
    service = CredentialRedactionService()

    redacted = service.redact(payload)
    removed = service.remove_sensitive(payload)

    assert redacted["account_no"] == REDACTED
    assert redacted["headers"] == REDACTED
    assert redacted["nested"][0]["chat_id"] == REDACTED
    assert removed == {"symbol": "005930", "nested": [{"safe": "ok"}]}
