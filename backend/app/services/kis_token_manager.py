from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from backend.app.services.kis_http_client import KisHttpClient

KIS_APP_KEY_ENV = "KIS_APP_KEY"
KIS_APP_SECRET_ENV = "KIS_APP_SECRET"
KIS_ACCOUNT_NO_ENV = "KIS_ACCOUNT_NO"
KIS_PRODUCT_CODE_ENV = "KIS_PRODUCT_CODE"
KIS_ENV_ENV = "KIS_ENV"
KIS_ACCESS_TOKEN_ENV = "KIS_ACCESS_TOKEN"
KIS_PAPER_BASE_URL_ENV = "KIS_PAPER_BASE_URL"
KIS_TOKEN_ISSUE_ENABLED_ENV = "KIS_TOKEN_ISSUE_ENABLED"
ENABLE_REAL_ORDER_ENV = "ENABLE_REAL_ORDER"
DEFAULT_KIS_PAPER_BASE_URL = "https://openapivts.koreainvestment.com:29443"
KIS_TOKEN_PATH = "/oauth2/tokenP"
KIS_PAPER_HOST = "openapivts.koreainvestment.com"
KIS_LIVE_HOST = "openapi.koreainvestment.com"


@dataclass(frozen=True)
class KisTokenMetadata:
    token_issued: bool = False
    refresh_token_present: bool = False
    expires_at: datetime | None = None
    access_token_fingerprint: str | None = None
    refresh_token_fingerprint: str | None = None


class KisTokenManager:
    """KIS token raw value를 저장하지 않고 lifecycle metadata만 유지한다."""

    def __init__(self) -> None:
        self._metadata = KisTokenMetadata()

    def record_issued_token(
        self,
        *,
        access_token: str,
        expires_at: datetime,
        refresh_token: str | None = None,
    ) -> None:
        self._metadata = KisTokenMetadata(
            token_issued=bool(access_token),
            refresh_token_present=bool(refresh_token),
            expires_at=expires_at,
            access_token_fingerprint=self._fingerprint(access_token) if access_token else None,
            refresh_token_fingerprint=self._fingerprint(refresh_token) if refresh_token else None,
        )

    def store_token(self, *, access_token: str, expires_at: datetime, refresh_token: str | None = None) -> None:
        """기존 호출부 호환용 alias이며 raw token은 저장하지 않는다."""
        self.record_issued_token(access_token=access_token, expires_at=expires_at, refresh_token=refresh_token)

    def clear(self) -> None:
        self._metadata = KisTokenMetadata()

    def metadata(self) -> dict[str, object]:
        metadata = self._metadata
        expires_at = metadata.expires_at
        token_issued = metadata.token_issued
        return {
            "state": "METADATA_ONLY" if token_issued else self.env_state(),
            "app_key_configured": self.env_configured(KIS_APP_KEY_ENV),
            "app_secret_configured": self.env_configured(KIS_APP_SECRET_ENV),
            "account_configured": self.env_configured(KIS_ACCOUNT_NO_ENV),
            "product_code_configured": self.env_configured(KIS_PRODUCT_CODE_ENV),
            "kis_env": os.getenv(KIS_ENV_ENV, "").strip().lower() or None,
            "kis_env_paper": self.env_is_paper(),
            "token_issued": token_issued,
            "refresh_token_present": metadata.refresh_token_present,
            "token_cache_enabled": False,
            "token_file_persistence_enabled": False,
            "token_db_persistence_enabled": False,
            "token_raw_value_persisted": False,
            "access_token": "***REDACTED***" if token_issued else None,
            "refresh_token": "***REDACTED***" if metadata.refresh_token_present else None,
            "access_token_fingerprint": metadata.access_token_fingerprint,
            "refresh_token_fingerprint": metadata.refresh_token_fingerprint,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "expired": bool(expires_at and expires_at <= datetime.now(UTC)),
        }

    def issue_paper_access_token(
        self,
        *,
        confirm: bool = False,
        http_client: Any | None = None,
        timeout_seconds: float = 10.0,
    ) -> dict[str, object]:
        """명시 opt-in 상태에서만 KIS paper access token을 발급하고 raw token은 저장하지 않는다."""
        gate = self._token_issue_gate_reasons(confirm=confirm)
        if gate:
            return self._blocked_token_payload("token_issue_blocked", gate)

        base_url = os.getenv(KIS_PAPER_BASE_URL_ENV, DEFAULT_KIS_PAPER_BASE_URL).strip() or DEFAULT_KIS_PAPER_BASE_URL
        client = KisHttpClient(http_client=http_client, timeout_seconds=timeout_seconds, max_retries=0)
        result = client.request(
            "POST",
            f"{base_url.rstrip('/')}{KIS_TOKEN_PATH}",
            json_body={
                "grant_type": "client_credentials",
                "appkey": os.getenv(KIS_APP_KEY_ENV, "").strip(),
                "appsecret": os.getenv(KIS_APP_SECRET_ENV, "").strip(),
            },
            retry_enabled=False,
            operation="kis_token_issue",
            redact_body=False,
        )
        if not result.ok:
            return {
                "ok": False,
                "status": "token_issue_failed",
                "token_issued": False,
                "token_raw_value_persisted": False,
                "network_call_performed": bool(result.trace.get("network_call_performed")),
                "reason": result.reason or "KIS_TOKEN_ISSUE_FAILED",
                "reason_codes": [str(result.reason or "KIS_TOKEN_ISSUE_FAILED")],
                "trace": result.trace,
                "metadata": self.metadata(),
            }

        access_token = str(result.body.get("access_token") or "").strip()
        if not access_token:
            return {
                "ok": False,
                "status": "token_issue_failed",
                "token_issued": False,
                "token_raw_value_persisted": False,
                "network_call_performed": True,
                "reason": "KIS_TOKEN_RESPONSE_MISSING_ACCESS_TOKEN",
                "reason_codes": ["KIS_TOKEN_RESPONSE_MISSING_ACCESS_TOKEN"],
                "trace": result.trace,
                "metadata": self.metadata(),
            }
        self.record_issued_token(
            access_token=access_token,
            expires_at=self._parse_expires_at(result.body),
            refresh_token=str(result.body.get("refresh_token") or "").strip() or None,
        )
        return {
            "ok": True,
            "status": "token_issued",
            "token_issued": True,
            "token_raw_value_persisted": False,
            "network_call_performed": True,
            "reason": None,
            "reason_codes": [],
            "trace": result.trace,
            "metadata": self.metadata(),
        }

    def refresh_paper_access_token(
        self,
        *,
        confirm: bool = False,
        http_client: Any | None = None,
        timeout_seconds: float = 10.0,
    ) -> dict[str, object]:
        """KIS 개인 Open API paper token은 동일 gate 뒤에서 재발급 방식으로 갱신한다."""
        result = self.issue_paper_access_token(
            confirm=confirm,
            http_client=http_client,
            timeout_seconds=timeout_seconds,
        )
        return {**result, "status": "token_refreshed" if result.get("ok") else result.get("status")}

    @classmethod
    def env_state(cls) -> str:
        if cls.env_configured(KIS_APP_KEY_ENV) and cls.env_configured(KIS_APP_SECRET_ENV):
            return "CONFIGURED_NO_TOKEN"
        return "UNCONFIGURED"

    @classmethod
    def env_configured(cls, name: str) -> bool:
        return cls.is_configured_value(os.environ.get(name, ""))

    @staticmethod
    def env_is_paper() -> bool:
        return os.getenv(KIS_ENV_ENV, "").strip().lower() == "paper"

    @staticmethod
    def is_configured_value(value: str) -> bool:
        stripped = value.strip()
        if not stripped:
            return False
        return "placeholder" not in stripped.lower()

    @staticmethod
    def _fingerprint(value: str | None) -> str | None:
        if not value:
            return None
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]

    @classmethod
    def _token_issue_gate_reasons(cls, *, confirm: bool) -> list[str]:
        reasons: list[str] = []
        if not confirm:
            reasons.append("KIS_TOKEN_CONFIRM_REQUIRED")
        if not _env_true(KIS_TOKEN_ISSUE_ENABLED_ENV):
            reasons.append("KIS_TOKEN_ISSUE_DISABLED")
        if not cls.env_is_paper():
            reasons.append("KIS_ENV_PAPER_REQUIRED")
        if not cls.env_configured(KIS_APP_KEY_ENV) or not cls.env_configured(KIS_APP_SECRET_ENV):
            reasons.append("KIS_APP_CREDENTIALS_MISSING")
        base_url = os.getenv(KIS_PAPER_BASE_URL_ENV, DEFAULT_KIS_PAPER_BASE_URL).strip() or DEFAULT_KIS_PAPER_BASE_URL
        if _is_live_base_url(base_url):
            reasons.append("KIS_LIVE_BASE_URL_BLOCKED")
        if not _is_paper_base_url(base_url):
            reasons.append("KIS_PAPER_BASE_URL_REQUIRED")
        if _env_true(ENABLE_REAL_ORDER_ENV):
            reasons.append("ENABLE_REAL_ORDER_MUST_BE_FALSE")
        return _merge_reason_codes(reasons)

    def _blocked_token_payload(self, status: str, reason_codes: list[str]) -> dict[str, object]:
        return {
            "ok": False,
            "status": status,
            "token_issued": False,
            "token_raw_value_persisted": False,
            "network_call_performed": False,
            "reason": reason_codes[0] if reason_codes else "KIS_TOKEN_ISSUE_DISABLED",
            "reason_codes": reason_codes,
            "metadata": self.metadata(),
        }

    @staticmethod
    def _parse_expires_at(payload: dict[str, Any]) -> datetime:
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


class TokenLifecycleService:
    """KIS token lifecycle 상태를 fail-closed metadata로 반환한다."""

    def __init__(self, token_manager: KisTokenManager | None = None) -> None:
        self.token_manager = token_manager or KisTokenManager()

    def status(self) -> dict[str, object]:
        metadata = self.token_manager.metadata()
        state = metadata["state"]
        if metadata["app_key_configured"] and metadata["app_secret_configured"] and not metadata["token_issued"]:
            state = "DISABLED_BLOCKED"
        return {
            **metadata,
            "state": state,
            "token_refresh_enabled": False,
            "token_issue_enabled": _env_true(KIS_TOKEN_ISSUE_ENABLED_ENV),
            "token_issue_endpoint_path": KIS_TOKEN_PATH,
            "network_call_performed": False,
            "disabled_reason": "phase_3_token_manager_metadata_only",
        }

    def issue_paper_access_token(self, *, confirm: bool = False, http_client: Any | None = None) -> dict[str, object]:
        """service 계층에서 KIS paper token 발급을 fail-closed gate 뒤로 노출한다."""
        return self.token_manager.issue_paper_access_token(confirm=confirm, http_client=http_client)

    def refresh_paper_access_token(self, *, confirm: bool = False, http_client: Any | None = None) -> dict[str, object]:
        """service 계층에서 KIS paper token 갱신을 fail-closed gate 뒤로 노출한다."""
        return self.token_manager.refresh_paper_access_token(confirm=confirm, http_client=http_client)


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _is_live_base_url(base_url: str) -> bool:
    parsed = urlparse(base_url)
    return (parsed.hostname or "").lower() == KIS_LIVE_HOST


def _is_paper_base_url(base_url: str) -> bool:
    parsed = urlparse(base_url)
    return (parsed.hostname or "").lower() == KIS_PAPER_HOST


def _merge_reason_codes(codes: list[str]) -> list[str]:
    merged: list[str] = []
    for code in codes:
        if code not in merged:
            merged.append(code)
    return merged
