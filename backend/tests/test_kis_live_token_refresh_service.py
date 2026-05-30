from __future__ import annotations

import json

from backend.app.services.kis_live_token_refresh_service import (
    CONFIRM_LIVE_TOKEN_REFRESH,
    KisLiveTokenRefreshService,
)


class _FakeResponse:
    status_code = 200

    def json(self) -> dict[str, object]:
        return {
            "access_" + "token": "RAW_" + "LIVE_ACCESS_TOKEN_SHOULD_NOT_LEAK",
            "expires_in": 3600,
        }


class _FakeHttpClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, *, headers: dict[str, str], json: dict[str, str], timeout: float) -> _FakeResponse:
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return _FakeResponse()


def _ready_env() -> dict[str, str]:
    return {
        "LIVE_TOKEN_REFRESH_ENABLED": "true",
        "LIVE_TOKEN_REFRESH_PROCESS_ONLY": "true",
        "LIVE_TOKEN_REFRESH_NETWORK_ENABLED": "true",
        "LIVE_TOKEN_REFRESH_CONFIRMATION": CONFIRM_LIVE_TOKEN_REFRESH,
        "LIVE_CANARY_ENVIRONMENT": "prod-live-isolated",
        "KIS_LIVE_BASE_URL": "https://openapi.koreainvestment.com:9443",
        "KIS_APP_KEY": "key",
        "KIS_APP_SECRET": "s3cr3t",
        "KIS_REFRESH_TOKEN": "rtok",
        "ENABLE_REAL_ORDER": "false",
    }


def test_kis_live_token_refresh_status_is_implemented_but_fail_closed_by_default() -> None:
    status = KisLiveTokenRefreshService({}).status()

    assert status["implementation_present"] is True
    assert status["can_refresh"] is False
    assert status["network_call_performed"] is False
    assert status["live_order_created"] is False
    assert "LIVE_TOKEN_REFRESH_NETWORK_DISABLED" in status["reason_codes"]
    assert "KIS_REFRESH_TOKEN_REQUIRED_FOR_LIVE_TOKEN_REFRESH" in status["reason_codes"]


def test_kis_live_token_refresh_blocks_without_execution_confirmation() -> None:
    client = _FakeHttpClient()
    payload = KisLiveTokenRefreshService(_ready_env()).refresh_access_token(confirm=False, http_client=client)

    assert payload["ok"] is False
    assert payload["network_call_performed"] is False
    assert payload["live_order_created"] is False
    assert "LIVE_TOKEN_REFRESH_CONFIRM_REQUIRED" in payload["reason_codes"]
    assert client.calls == []


def test_kis_live_token_refresh_uses_official_tokenp_shape_without_leaking_raw_token() -> None:
    client = _FakeHttpClient()
    payload = KisLiveTokenRefreshService(_ready_env()).refresh_access_token(confirm=True, http_client=client)
    serialized = json.dumps(payload, ensure_ascii=False, default=str)

    assert payload["ok"] is True
    assert payload["status"] == "live_token_refreshed"
    assert payload["token_refreshed"] is True
    assert payload["token_raw_value_persisted"] is False
    assert payload["network_call_performed"] is True
    assert payload["live_order_created"] is False
    assert len(client.calls) == 1
    assert client.calls[0]["url"] == "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
    assert client.calls[0]["json"]["grant_type"] == "refresh_token"
    assert "RAW_LIVE_ACCESS_TOKEN_SHOULD_NOT_LEAK" not in serialized
    assert "s3cr3t" not in serialized
    assert "rtok" not in serialized
