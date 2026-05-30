from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from backend.app.services.kis_token_manager import KisTokenManager


class _FakeResponse:
    status_code = 200

    def json(self) -> dict[str, object]:
        return {"access_token": "RAW_" + "TOKEN_SHOULD_NOT_LEAK", "expires_in": 3600}


class _FakeHttpClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, *, headers: dict[str, str], json: dict[str, str], timeout: float) -> _FakeResponse:
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return _FakeResponse()


def test_kis_token_issue_is_fail_closed_and_redacted(monkeypatch) -> None:
    secret = "TOKEN_PHASE1_SECRET"
    monkeypatch.setenv("KIS_ENV", "paper")
    monkeypatch.setenv("KIS_APP_KEY", secret)
    monkeypatch.setenv("KIS_APP_SECRET", secret)
    monkeypatch.setenv("KIS_TOKEN_ISSUE_ENABLED", "true")
    monkeypatch.setenv("KIS_PAPER_BASE_URL", "https://openapivts.koreainvestment.com:29443")
    monkeypatch.setenv("ENABLE_REAL_ORDER", "false")
    manager = KisTokenManager()
    client = _FakeHttpClient()

    blocked = manager.issue_paper_access_token(confirm=False, http_client=client)
    issued = manager.issue_paper_access_token(confirm=True, http_client=client)
    serialized = json.dumps(issued, ensure_ascii=False, default=str)
    internal_state = json.dumps(manager.__dict__, ensure_ascii=False, default=str)

    assert blocked["ok"] is False
    assert blocked["network_call_performed"] is False
    assert "KIS_TOKEN_CONFIRM_REQUIRED" in blocked["reason_codes"]
    assert issued["ok"] is True
    assert issued["token_issued"] is True
    assert issued["metadata"]["access_token"] == "***REDACTED***"
    assert issued["metadata"]["access_token_fingerprint"]
    assert issued["token_raw_value_persisted"] is False
    assert len(client.calls) == 1
    assert client.calls[0]["url"].endswith("/oauth2/tokenP")
    raw_token = "RAW_" + "TOKEN_SHOULD_NOT_LEAK"
    assert raw_token not in serialized
    assert raw_token not in internal_state
    assert secret not in serialized


def test_ensure_paper_access_token_refreshes_expired_cache_without_secret_leak(tmp_path, monkeypatch) -> None:
    cache_path = tmp_path / "kis-token.json"
    expired_at = datetime.now(UTC) - timedelta(minutes=1)
    old_access = "RAW_OLD_ACCESS_TOKEN_SHOULD_NOT_LEAK"
    old_refresh = "RAW_OLD_REFRESH_TOKEN_SHOULD_NOT_LEAK"
    cache_path.write_text(
        json.dumps(
            {
                "access_token": old_access,
                "refresh_token": old_refresh,
                "expires_at": expired_at.isoformat(),
            }
        ),
        encoding="utf-8",
    )
    secret = "TOKEN_PHASE1_SECRET"
    monkeypatch.setenv("KIS_ENV", "paper")
    monkeypatch.setenv("KIS_APP_KEY", secret)
    monkeypatch.setenv("KIS_APP_SECRET", secret)
    monkeypatch.setenv("KIS_TOKEN_ISSUE_ENABLED", "true")
    monkeypatch.setenv("KIS_TOKEN_CACHE_ENABLED", "true")
    monkeypatch.setenv("KIS_TOKEN_CACHE_PATH", str(cache_path))
    monkeypatch.setenv("KIS_PAPER_BASE_URL", "https://openapivts.koreainvestment.com:29443")
    monkeypatch.setenv("ENABLE_REAL_ORDER", "false")
    manager = KisTokenManager()
    client = _FakeHttpClient()

    refreshed = manager.ensure_paper_access_token(confirm=True, http_client=client)
    serialized = json.dumps(refreshed, ensure_ascii=False, default=str)
    cache_payload = json.loads(cache_path.read_text(encoding="utf-8"))

    assert refreshed["ok"] is True
    assert refreshed["status"] == "token_refreshed"
    assert refreshed["network_call_performed"] is True
    assert refreshed["token_cache_write_performed"] is True
    assert client.calls[0]["json"]["grant_type"] == "refresh_token"
    assert client.calls[0]["json"]["refresh_token"] == old_refresh
    assert cache_payload["access_token"] == "RAW_" + "TOKEN_SHOULD_NOT_LEAK"
    assert cache_payload["refresh_token"] == old_refresh
    assert old_access not in serialized
    assert old_refresh not in serialized
    assert secret not in serialized
