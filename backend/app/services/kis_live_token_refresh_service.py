from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from backend.app.services.kis_http_client import KisHttpClient
from backend.app.services.kis_token_manager import (
    ENABLE_REAL_ORDER_ENV,
    KIS_ACCESS_TOKEN_ENV,
    KIS_APP_KEY_ENV,
    KIS_APP_SECRET_ENV,
    KisTokenManager,
)

KIS_REFRESH_TOKEN_ENV = "KIS_REFRESH_TOKEN"
KIS_LIVE_BASE_URL_ENV = "KIS_LIVE_BASE_URL"
LIVE_TOKEN_REFRESH_ENABLED_ENV = "LIVE_TOKEN_REFRESH_ENABLED"
LIVE_TOKEN_REFRESH_PROCESS_ONLY_ENV = "LIVE_TOKEN_REFRESH_PROCESS_ONLY"
LIVE_TOKEN_REFRESH_NETWORK_ENABLED_ENV = "LIVE_TOKEN_REFRESH_NETWORK_ENABLED"
LIVE_TOKEN_REFRESH_CONFIRMATION_ENV = "LIVE_TOKEN_REFRESH_CONFIRMATION"
LIVE_CANARY_ENVIRONMENT_ENV = "LIVE_CANARY_ENVIRONMENT"
DEFAULT_KIS_LIVE_BASE_URL = "https://openapi.koreainvestment.com:9443"
KIS_LIVE_TOKEN_REFRESH_PATH = "/oauth2/tokenP"
KIS_LIVE_HOST = "openapi.koreainvestment.com"
CONFIRM_LIVE_TOKEN_REFRESH = "CONFIRM_KIS_LIVE_TOKEN_REFRESH"
LIVE_CANARY_ISOLATED_ENVIRONMENT = "prod-live-isolated"


class KisLiveTokenRefreshService:
    """KIS live access token refresh를 주문 실행과 분리해 fail-closed로 수행한다."""

    def __init__(
        self,
        env: Mapping[str, str] | None = None,
        *,
        token_manager: KisTokenManager | None = None,
    ) -> None:
        self.env = os.environ if env is None else env
        self.token_manager = token_manager or KisTokenManager()

    def status(self) -> dict[str, Any]:
        """live token refresh 구현 상태와 readiness를 secret 없이 반환한다."""
        readiness_codes = self._readiness_reason_codes()
        return {
            "implementation_present": True,
            "enabled": _env_true(self.env, LIVE_TOKEN_REFRESH_ENABLED_ENV),
            "network_enabled": _env_true(self.env, LIVE_TOKEN_REFRESH_NETWORK_ENABLED_ENV),
            "process_only": _env_true(self.env, LIVE_TOKEN_REFRESH_PROCESS_ONLY_ENV),
            "endpoint_path": KIS_LIVE_TOKEN_REFRESH_PATH,
            "base_url_host": _host(self._base_url()),
            "app_key_configured": _configured(self.env.get(KIS_APP_KEY_ENV, "")),
            "app_secret_configured": _configured(self.env.get(KIS_APP_SECRET_ENV, "")),
            "refresh_token_configured": _configured(self.env.get(KIS_REFRESH_TOKEN_ENV, "")),
            "can_refresh": not readiness_codes,
            "reason_codes": readiness_codes,
            "token_raw_value_persisted": False,
            "network_call_performed": False,
            "live_order_created": False,
            "secrets_redacted": True,
        }

    def refresh_access_token(
        self,
        *,
        confirm: bool = False,
        install_to_process_env: bool = False,
        http_client: Any | None = None,
        timeout_seconds: float = 10.0,
    ) -> dict[str, Any]:
        """명시 gate를 모두 통과한 경우에만 KIS live access token refresh를 호출한다."""
        gate = self._execution_reason_codes(confirm=confirm)
        if gate:
            return self._blocked_payload(gate)

        client = KisHttpClient(http_client=http_client, timeout_seconds=timeout_seconds, max_retries=0)
        result = client.request(
            "POST",
            f"{self._base_url().rstrip('/')}{KIS_LIVE_TOKEN_REFRESH_PATH}",
            json_body={
                "grant_type": "refresh_token",
                "appkey": str(self.env.get(KIS_APP_KEY_ENV, "")).strip(),
                "appsecret": str(self.env.get(KIS_APP_SECRET_ENV, "")).strip(),
                "refresh_token": str(self.env.get(KIS_REFRESH_TOKEN_ENV, "")).strip(),
            },
            retry_enabled=False,
            operation="kis_live_token_refresh",
            redact_body=False,
            correlation_prefix="kis-live-token-refresh",
        )
        if not result.ok:
            return {
                "ok": False,
                "status": "live_token_refresh_failed",
                "token_refreshed": False,
                "token_raw_value_persisted": False,
                "process_env_access_token_installed": False,
                "network_call_performed": bool(result.trace.get("network_call_performed")),
                "live_order_created": False,
                "reason": result.reason or "KIS_LIVE_TOKEN_REFRESH_FAILED",
                "reason_codes": [str(result.reason or "KIS_LIVE_TOKEN_REFRESH_FAILED")],
                "trace": result.trace,
                "metadata": self.token_manager.metadata(),
            }

        access_token = str(result.body.get("access_token") or result.body.get("token") or "").strip()
        if not access_token:
            return {
                "ok": False,
                "status": "live_token_refresh_failed",
                "token_refreshed": False,
                "token_raw_value_persisted": False,
                "process_env_access_token_installed": False,
                "network_call_performed": True,
                "live_order_created": False,
                "reason": "KIS_LIVE_TOKEN_REFRESH_RESPONSE_MISSING_ACCESS_TOKEN",
                "reason_codes": ["KIS_LIVE_TOKEN_REFRESH_RESPONSE_MISSING_ACCESS_TOKEN"],
                "trace": result.trace,
                "metadata": self.token_manager.metadata(),
            }

        self.token_manager.record_issued_token(
            access_token=access_token,
            refresh_token=str(self.env.get(KIS_REFRESH_TOKEN_ENV, "")).strip() or None,
            expires_at=_parse_expires_at(result.body),
        )
        if install_to_process_env:
            os.environ[KIS_ACCESS_TOKEN_ENV] = access_token
        return {
            "ok": True,
            "status": "live_token_refreshed",
            "token_refreshed": True,
            "token_raw_value_persisted": False,
            "process_env_access_token_installed": bool(install_to_process_env),
            "network_call_performed": True,
            "live_order_created": False,
            "reason": None,
            "reason_codes": [],
            "trace": result.trace,
            "metadata": self.token_manager.metadata(),
        }

    def _readiness_reason_codes(self) -> list[str]:
        reasons: list[str] = []
        if not _env_true(self.env, LIVE_TOKEN_REFRESH_ENABLED_ENV):
            reasons.append("LIVE_TOKEN_REFRESH_ENABLED_REQUIRED")
        if not _env_true(self.env, LIVE_TOKEN_REFRESH_PROCESS_ONLY_ENV):
            reasons.append("LIVE_TOKEN_REFRESH_PROCESS_ONLY_REQUIRED")
        if not _env_true(self.env, LIVE_TOKEN_REFRESH_NETWORK_ENABLED_ENV):
            reasons.append("LIVE_TOKEN_REFRESH_NETWORK_DISABLED")
        if not _configured(self.env.get(KIS_APP_KEY_ENV, "")):
            reasons.append("KIS_APP_KEY_REQUIRED_FOR_LIVE_TOKEN_REFRESH")
        if not _configured(self.env.get(KIS_APP_SECRET_ENV, "")):
            reasons.append("KIS_APP_SECRET_REQUIRED_FOR_LIVE_TOKEN_REFRESH")
        if not _configured(self.env.get(KIS_REFRESH_TOKEN_ENV, "")):
            reasons.append("KIS_REFRESH_TOKEN_REQUIRED_FOR_LIVE_TOKEN_REFRESH")
        if _host(self._base_url()) != KIS_LIVE_HOST:
            reasons.append("KIS_LIVE_BASE_URL_REQUIRED_FOR_TOKEN_REFRESH")
        if _env_true(self.env, ENABLE_REAL_ORDER_ENV):
            reasons.append("ENABLE_REAL_ORDER_MUST_BE_FALSE")
        return _merge_reason_codes(reasons)

    def _execution_reason_codes(self, *, confirm: bool) -> list[str]:
        reasons = self._readiness_reason_codes()
        if not confirm:
            reasons.append("LIVE_TOKEN_REFRESH_CONFIRM_REQUIRED")
        if str(self.env.get(LIVE_TOKEN_REFRESH_CONFIRMATION_ENV, "")).strip() != CONFIRM_LIVE_TOKEN_REFRESH:
            reasons.append("LIVE_TOKEN_REFRESH_CONFIRMATION_REQUIRED")
        if str(self.env.get(LIVE_CANARY_ENVIRONMENT_ENV, "")).strip() != LIVE_CANARY_ISOLATED_ENVIRONMENT:
            reasons.append("LIVE_CANARY_ENVIRONMENT_REQUIRED_FOR_TOKEN_REFRESH")
        return _merge_reason_codes(reasons)

    def _base_url(self) -> str:
        return str(self.env.get(KIS_LIVE_BASE_URL_ENV, DEFAULT_KIS_LIVE_BASE_URL)).strip() or DEFAULT_KIS_LIVE_BASE_URL

    def _blocked_payload(self, reason_codes: list[str]) -> dict[str, Any]:
        return {
            "ok": False,
            "status": "live_token_refresh_blocked",
            "token_refreshed": False,
            "token_raw_value_persisted": False,
            "process_env_access_token_installed": False,
            "network_call_performed": False,
            "live_order_created": False,
            "reason": reason_codes[0] if reason_codes else "LIVE_TOKEN_REFRESH_BLOCKED",
            "reason_codes": reason_codes,
            "metadata": self.token_manager.metadata(),
        }


def _env_true(env: Mapping[str, str], name: str) -> bool:
    return str(env.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def _configured(value: str | None) -> bool:
    stripped = str(value or "").strip()
    return bool(stripped and "placeholder" not in stripped.lower())


def _host(base_url: str) -> str | None:
    return (urlparse(base_url).hostname or "").lower() or None


def _parse_expires_at(payload: Mapping[str, Any]) -> datetime:
    explicit = payload.get("access_token_token_expired") or payload.get("expires_at")
    if explicit:
        text = str(explicit).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"):
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=UTC)
            except ValueError:
                pass
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
    try:
        expires_in = int(payload.get("expires_in") or 0)
    except (TypeError, ValueError):
        expires_in = 0
    return datetime.now(UTC) + timedelta(seconds=max(expires_in, 0) or 86400)


def _merge_reason_codes(codes: list[str]) -> list[str]:
    merged: list[str] = []
    for code in codes:
        if code not in merged:
            merged.append(code)
    return merged
