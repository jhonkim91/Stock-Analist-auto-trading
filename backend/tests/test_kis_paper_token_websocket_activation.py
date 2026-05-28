from __future__ import annotations

import json
import os

from backend.app.main import app
from backend.app.services.kis_paper_websocket_service import (
    KIS_WEBSOCKET_APPROVAL_KEY_ENV,
    KisPaperWebSocketService,
)
from backend.app.services.token_manager import KIS_ACCESS_TOKEN_ENV, KisTokenManager


class _FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, object]:
        return self.payload


class _FakeHttpClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, *, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers or {}, "json": json or {}, "timeout": timeout})
        return _FakeResponse(self.payload)


def _enable_paper_auth_env(monkeypatch) -> None:
    monkeypatch.setenv("KIS_ENV", "paper")
    monkeypatch.setenv("ENABLE_REAL_ORDER", "false")
    monkeypatch.setenv("KIS_APP_KEY", "TEST_APP_KEY")
    monkeypatch.setenv("KIS_APP_SECRET", "TEST_APP_SECRET")
    monkeypatch.setenv("KIS_PAPER_BASE_URL", "https://openapivts.koreainvestment.com:29443")


def test_kis_token_issue_can_install_access_token_process_only_without_leaking(monkeypatch) -> None:
    raw_token = "RAW_PHASE21_ACCESS_TOKEN_SHOULD_NOT_LEAK"
    _enable_paper_auth_env(monkeypatch)
    monkeypatch.setenv("KIS_TOKEN_ISSUE_ENABLED", "true")
    monkeypatch.delenv(KIS_ACCESS_TOKEN_ENV, raising=False)
    client = _FakeHttpClient({"access_token": raw_token, "expires_in": 3600})

    result = KisTokenManager().issue_paper_access_token(
        confirm=True,
        install_to_process_env=True,
        http_client=client,
    )
    serialized = json.dumps(result, ensure_ascii=False, default=str)

    assert result["ok"] is True
    assert result["token_issued"] is True
    assert result["process_env_access_token_installed"] is True
    assert os.environ[KIS_ACCESS_TOKEN_ENV] == raw_token
    assert client.calls[0]["url"].endswith("/oauth2/tokenP")
    assert client.calls[0]["json"]["appkey"] == "TEST_APP_KEY"
    assert raw_token not in serialized
    assert result["metadata"]["access_token"] == "***REDACTED***"


def test_token_issue_api_remains_blocked_without_confirm_or_gate(client, monkeypatch) -> None:
    _enable_paper_auth_env(monkeypatch)
    monkeypatch.delenv("KIS_TOKEN_ISSUE_ENABLED", raising=False)

    response = client.post("/api/kis/token/issue", json={"confirm": False, "install_to_process_env": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["network_call_performed"] is False
    assert payload["process_env_access_token_installed"] is False
    assert "KIS_TOKEN_CONFIRM_REQUIRED" in payload["reason_codes"]
    assert "KIS_TOKEN_ISSUE_DISABLED" in payload["reason_codes"]


def test_paper_websocket_approval_can_install_key_process_only_without_leaking(monkeypatch) -> None:
    raw_approval = "RAW_PHASE21_APPROVAL_KEY_SHOULD_NOT_LEAK"
    _enable_paper_auth_env(monkeypatch)
    monkeypatch.setenv("KIS_WEBSOCKET_APPROVAL_ENABLED", "true")
    monkeypatch.delenv(KIS_WEBSOCKET_APPROVAL_KEY_ENV, raising=False)
    client = _FakeHttpClient({"approval_key": raw_approval})
    service = KisPaperWebSocketService(http_client=client)

    result = service.issue_approval_key(confirm=True, install_to_process_env=True)
    serialized = json.dumps(result, ensure_ascii=False, default=str)

    assert result["ok"] is True
    assert result["approval_key_issued"] is True
    assert result["approval_key_process_env_installed"] is True
    assert os.environ[KIS_WEBSOCKET_APPROVAL_KEY_ENV] == raw_approval
    assert client.calls[0]["url"].endswith("/oauth2/Approval")
    assert client.calls[0]["json"]["secretkey"] == "TEST_APP_SECRET"
    assert raw_approval not in serialized
    assert result["metadata"]["approval_key_configured"] is True
    assert result["metadata"]["approval_key_raw_value_persisted"] is False


def test_paper_websocket_routes_are_paper_only_and_do_not_register_kis_websocket(client, monkeypatch) -> None:
    _enable_paper_auth_env(monkeypatch)
    route_paths = {getattr(route, "path", "") for route in app.routes}

    assert "/api/paper/realtime/websocket/status" in route_paths
    assert "/api/paper/realtime/websocket/approval" in route_paths
    assert not any(path.startswith("/api/kis/websocket") for path in route_paths)

    status = client.get("/api/paper/realtime/websocket/status").json()
    blocked_approval = client.post("/api/paper/realtime/websocket/approval", json={"confirm": False}).json()
    subscription = client.post(
        "/api/paper/realtime/websocket/subscription/preview",
        json={"symbol": "005930", "kind": "quote", "subscribe": True},
    ).json()
    serialized = json.dumps({"status": status, "approval": blocked_approval, "subscription": subscription})

    assert status["websocket_enabled"] is False
    assert status["network_call_performed"] is False
    assert blocked_approval["network_call_performed"] is False
    assert "KIS_WEBSOCKET_APPROVAL_CONFIRM_REQUIRED" in blocked_approval["reason_codes"]
    assert subscription["ok"] is True
    assert subscription["tr_id"] == "H0STCNT0"
    assert subscription["subscription"]["header"]["approval_key"] == "***REDACTED***"
    assert "TEST_APP_SECRET" not in serialized
