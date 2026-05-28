from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from backend.app.services.credential_redaction import CredentialRedactionService
from backend.app.services.kis_http_client import KisHttpClient
from backend.app.services.kis_token_manager import (
    ENABLE_REAL_ORDER_ENV,
    KIS_APP_KEY_ENV,
    KIS_APP_SECRET_ENV,
    KIS_ENV_ENV,
    KIS_PAPER_BASE_URL_ENV,
    DEFAULT_KIS_PAPER_BASE_URL,
    KisTokenManager,
)

KIS_WS_APPROVAL_PATH = "/oauth2/Approval"
KIS_WEBSOCKET_APPROVAL_ENABLED_ENV = "KIS_WEBSOCKET_APPROVAL_ENABLED"
KIS_WEBSOCKET_APPROVAL_KEY_ENV = "KIS_WEBSOCKET_APPROVAL_KEY"
KIS_HTS_ID_ENV = "KIS_HTS_ID"
KIS_PAPER_WS_URL_ENV = "KIS_PAPER_WS_URL"
PAPER_WEBSOCKET_ENABLED_ENV = "PAPER_WEBSOCKET_ENABLED"
PAPER_WEBSOCKET_CONNECT_ENABLED_ENV = "PAPER_WEBSOCKET_CONNECT_ENABLED"
DEFAULT_KIS_PAPER_WS_URL = "ws://ops.koreainvestment.com:31000"
KIS_LIVE_WS_PORT = 21000
KIS_PAPER_WS_PORT = 31000
KIS_REALTIME_QUOTE_TR_ID = "H0STCNT0"
KIS_REALTIME_ASK_TR_ID = "H0STASP0"
KIS_PAPER_NOTICE_TR_ID = "H0STCNI9"


@dataclass(frozen=True)
class KisWebSocketApprovalMetadata:
    approval_key_issued: bool = False
    approval_key_fingerprint: str | None = None
    expires_at: datetime | None = None


class KisPaperWebSocketService:
    """KIS paper WebSocket approval key와 bounded subscription metadata를 관리한다."""

    def __init__(
        self,
        *,
        http_client: Any | None = None,
        timeout_seconds: float = 10.0,
        redaction_service: CredentialRedactionService | None = None,
    ) -> None:
        self.http_client = http_client
        self.timeout_seconds = timeout_seconds
        self.redactor = redaction_service or CredentialRedactionService()
        self._metadata = KisWebSocketApprovalMetadata()

    def status(
        self,
        *,
        config: dict[str, object] | None = None,
        config_reasons: list[str] | None = None,
    ) -> dict[str, object]:
        """WebSocket 상태를 secret 없이 반환하고 기본값은 fail-closed로 유지한다."""
        websocket_url = os.getenv(KIS_PAPER_WS_URL_ENV, DEFAULT_KIS_PAPER_WS_URL).strip() or DEFAULT_KIS_PAPER_WS_URL
        configured_approval = KisTokenManager.is_configured_value(os.getenv(KIS_WEBSOCKET_APPROVAL_KEY_ENV, ""))
        enabled = _env_true(PAPER_WEBSOCKET_ENABLED_ENV)
        connect_enabled = enabled and _env_true(PAPER_WEBSOCKET_CONNECT_ENABLED_ENV)
        reason_codes = self._status_reason_codes(
            config=config or {},
            config_reasons=config_reasons or [],
            websocket_url=websocket_url,
            enabled=enabled,
            connect_enabled=connect_enabled,
            configured_approval=configured_approval,
        )
        return {
            "ok": True,
            "paper_only": True,
            "enabled": enabled,
            "connect_enabled": connect_enabled and not reason_codes,
            "websocket_enabled": enabled,
            "approval_key_configured": configured_approval or self._metadata.approval_key_issued,
            "approval_key_issued": self._metadata.approval_key_issued,
            "approval_key_fingerprint": self._metadata.approval_key_fingerprint,
            "approval_key_raw_value_persisted": False,
            "approval_key_process_env_installed": configured_approval,
            "approval_endpoint_path": KIS_WS_APPROVAL_PATH,
            "websocket_url": self._safe_websocket_url(websocket_url),
            "supported_tr_ids": {
                "quote": KIS_REALTIME_QUOTE_TR_ID,
                "ask": KIS_REALTIME_ASK_TR_ID,
                "paper_notice": KIS_PAPER_NOTICE_TR_ID,
            },
            "network_call_performed": False,
            "live_order_created": False,
            "reason": reason_codes[0] if reason_codes else None,
            "reason_codes": reason_codes,
            "secrets_redacted": True,
        }

    def issue_approval_key(
        self,
        *,
        confirm: bool = False,
        install_to_process_env: bool = False,
    ) -> dict[str, object]:
        """명시 gate가 열릴 때만 KIS paper WebSocket approval key를 발급한다."""
        websocket_url = os.getenv(KIS_PAPER_WS_URL_ENV, DEFAULT_KIS_PAPER_WS_URL).strip() or DEFAULT_KIS_PAPER_WS_URL
        reason_codes = self._approval_gate_reasons(confirm=confirm, websocket_url=websocket_url)
        if reason_codes:
            return self._blocked_payload("websocket_approval_blocked", reason_codes)

        base_url = os.getenv(KIS_PAPER_BASE_URL_ENV, DEFAULT_KIS_PAPER_BASE_URL).strip() or DEFAULT_KIS_PAPER_BASE_URL
        result = KisHttpClient(
            http_client=self.http_client,
            timeout_seconds=self.timeout_seconds,
            max_retries=0,
            redaction_service=self.redactor,
        ).request(
            "POST",
            f"{base_url.rstrip('/')}{KIS_WS_APPROVAL_PATH}",
            headers={"content-type": "application/json", "accept": "text/plain", "charset": "UTF-8"},
            json_body={
                "grant_type": "client_credentials",
                "appkey": os.getenv(KIS_APP_KEY_ENV, "").strip(),
                "secretkey": os.getenv(KIS_APP_SECRET_ENV, "").strip(),
            },
            retry_enabled=False,
            operation="kis_websocket_approval",
            redact_body=False,
            correlation_prefix="kis-ws-approval",
        )
        if not result.ok:
            return {
                "ok": False,
                "status": "websocket_approval_failed",
                "paper_only": True,
                "approval_key_issued": False,
                "approval_key_raw_value_persisted": False,
                "approval_key_process_env_installed": False,
                "network_call_performed": bool(result.trace.get("network_call_performed")),
                "live_order_created": False,
                "reason": result.reason or "KIS_WEBSOCKET_APPROVAL_FAILED",
                "reason_codes": [str(result.reason or "KIS_WEBSOCKET_APPROVAL_FAILED")],
                "trace": result.trace,
                "metadata": self.status(),
            }

        approval_key = str(result.body.get("approval_key") or "").strip()
        if not approval_key:
            return {
                "ok": False,
                "status": "websocket_approval_failed",
                "paper_only": True,
                "approval_key_issued": False,
                "approval_key_raw_value_persisted": False,
                "approval_key_process_env_installed": False,
                "network_call_performed": True,
                "live_order_created": False,
                "reason": "KIS_WEBSOCKET_APPROVAL_RESPONSE_MISSING_KEY",
                "reason_codes": ["KIS_WEBSOCKET_APPROVAL_RESPONSE_MISSING_KEY"],
                "trace": result.trace,
                "metadata": self.status(),
            }

        self._metadata = KisWebSocketApprovalMetadata(
            approval_key_issued=True,
            approval_key_fingerprint=_fingerprint(approval_key),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
        if install_to_process_env:
            os.environ[KIS_WEBSOCKET_APPROVAL_KEY_ENV] = approval_key
        return {
            "ok": True,
            "status": "websocket_approval_issued",
            "paper_only": True,
            "approval_key_issued": True,
            "approval_key_raw_value_persisted": False,
            "approval_key_process_env_installed": bool(install_to_process_env),
            "network_call_performed": True,
            "live_order_created": False,
            "reason": None,
            "reason_codes": [],
            "trace": result.trace,
            "metadata": self.status(),
        }

    def subscription_preview(
        self,
        *,
        symbol: str,
        kind: str = "quote",
        subscribe: bool = True,
    ) -> dict[str, object]:
        """실제 WebSocket connect 없이 KIS paper 구독 메시지 형태를 redacted로 반환한다."""
        normalized_kind = kind.strip().lower()
        tr_id = {
            "quote": KIS_REALTIME_QUOTE_TR_ID,
            "ask": KIS_REALTIME_ASK_TR_ID,
            "notice": KIS_PAPER_NOTICE_TR_ID,
        }.get(normalized_kind)
        if tr_id is None:
            return {
                "ok": False,
                "status": "subscription_invalid",
                "paper_only": True,
                "network_call_performed": False,
                "live_order_created": False,
                "reason": "KIS_WEBSOCKET_SUBSCRIPTION_KIND_UNSUPPORTED",
                "reason_codes": ["KIS_WEBSOCKET_SUBSCRIPTION_KIND_UNSUPPORTED"],
            }
        tr_key = os.getenv(KIS_HTS_ID_ENV, "").strip() if normalized_kind == "notice" else symbol.strip()
        if not tr_key:
            return {
                "ok": False,
                "status": "subscription_invalid",
                "paper_only": True,
                "network_call_performed": False,
                "live_order_created": False,
                "reason": "KIS_WEBSOCKET_TR_KEY_REQUIRED",
                "reason_codes": ["KIS_WEBSOCKET_TR_KEY_REQUIRED"],
            }
        message = {
            "header": {
                "approval_key": "***REDACTED***",
                "custtype": "P",
                "tr_type": "1" if subscribe else "2",
                "content-type": "utf-8",
            },
            "body": {"input": {"tr_id": tr_id, "tr_key": "***REDACTED***" if normalized_kind == "notice" else tr_key}},
        }
        return {
            "ok": True,
            "status": "subscription_preview",
            "paper_only": True,
            "subscription": message,
            "tr_id": tr_id,
            "tr_key_fingerprint": _fingerprint(tr_key),
            "network_call_performed": False,
            "live_order_created": False,
            "reason": None,
            "reason_codes": [],
            "secrets_redacted": True,
        }

    def _approval_gate_reasons(self, *, confirm: bool, websocket_url: str) -> list[str]:
        reasons: list[str] = []
        if not confirm:
            reasons.append("KIS_WEBSOCKET_APPROVAL_CONFIRM_REQUIRED")
        if not _env_true(KIS_WEBSOCKET_APPROVAL_ENABLED_ENV):
            reasons.append("KIS_WEBSOCKET_APPROVAL_DISABLED")
        if os.getenv(KIS_ENV_ENV, "").strip().lower() != "paper":
            reasons.append("KIS_ENV_PAPER_REQUIRED")
        if not KisTokenManager.env_configured(KIS_APP_KEY_ENV) or not KisTokenManager.env_configured(KIS_APP_SECRET_ENV):
            reasons.append("KIS_APP_CREDENTIALS_MISSING")
        base_url = os.getenv(KIS_PAPER_BASE_URL_ENV, DEFAULT_KIS_PAPER_BASE_URL).strip() or DEFAULT_KIS_PAPER_BASE_URL
        if _is_live_rest_base_url(base_url):
            reasons.append("KIS_LIVE_BASE_URL_BLOCKED")
        if not _is_paper_rest_base_url(base_url):
            reasons.append("KIS_PAPER_BASE_URL_REQUIRED")
        if _websocket_url_is_live(websocket_url):
            reasons.append("KIS_LIVE_WEBSOCKET_URL_BLOCKED")
        if not _websocket_url_is_paper(websocket_url):
            reasons.append("KIS_PAPER_WEBSOCKET_URL_REQUIRED")
        if _env_true(ENABLE_REAL_ORDER_ENV):
            reasons.append("ENABLE_REAL_ORDER_MUST_BE_FALSE")
        return _merge_reason_codes(reasons)

    def _status_reason_codes(
        self,
        *,
        config: dict[str, object],
        config_reasons: list[str],
        websocket_url: str,
        enabled: bool,
        connect_enabled: bool,
        configured_approval: bool,
    ) -> list[str]:
        reasons = list(config_reasons)
        if not enabled:
            reasons.append("PAPER_WEBSOCKET_DISABLED")
        if connect_enabled and not configured_approval and not self._metadata.approval_key_issued:
            reasons.append("KIS_WEBSOCKET_APPROVAL_KEY_REQUIRED")
        if str(config.get("kis_env") or os.getenv(KIS_ENV_ENV, "")).strip().lower() != "paper":
            reasons.append("KIS_ENV_PAPER_REQUIRED")
        if bool(config.get("live_fallback_enabled", False)) or bool(config.get("live_order_enabled", False)):
            reasons.append("KIS_LIVE_PATH_BLOCKED")
        if _websocket_url_is_live(websocket_url):
            reasons.append("KIS_LIVE_WEBSOCKET_URL_BLOCKED")
        if not _websocket_url_is_paper(websocket_url):
            reasons.append("KIS_PAPER_WEBSOCKET_URL_REQUIRED")
        return _merge_reason_codes(reasons)

    def _blocked_payload(self, status: str, reason_codes: list[str]) -> dict[str, object]:
        return {
            "ok": False,
            "status": status,
            "paper_only": True,
            "approval_key_issued": False,
            "approval_key_raw_value_persisted": False,
            "approval_key_process_env_installed": False,
            "network_call_performed": False,
            "live_order_created": False,
            "reason": reason_codes[0] if reason_codes else "KIS_WEBSOCKET_APPROVAL_DISABLED",
            "reason_codes": reason_codes,
            "metadata": self.status(),
        }

    @staticmethod
    def _safe_websocket_url(value: str) -> dict[str, object]:
        parsed = urlparse(value)
        return {
            "scheme": parsed.scheme,
            "host": parsed.hostname,
            "port": parsed.port,
            "paper_endpoint": _websocket_url_is_paper(value),
            "live_endpoint": _websocket_url_is_live(value),
        }


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _is_live_rest_base_url(base_url: str) -> bool:
    return (urlparse(base_url).hostname or "").lower() == "openapi.koreainvestment.com"


def _is_paper_rest_base_url(base_url: str) -> bool:
    return (urlparse(base_url).hostname or "").lower() == "openapivts.koreainvestment.com"


def _websocket_url_is_live(value: str) -> bool:
    parsed = urlparse(value)
    return (parsed.hostname or "").lower() == "ops.koreainvestment.com" and parsed.port == KIS_LIVE_WS_PORT


def _websocket_url_is_paper(value: str) -> bool:
    parsed = urlparse(value)
    return (parsed.hostname or "").lower() == "ops.koreainvestment.com" and parsed.port == KIS_PAPER_WS_PORT


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _merge_reason_codes(codes: list[str]) -> list[str]:
    merged: list[str] = []
    for code in codes:
        if code not in merged:
            merged.append(code)
    return merged
