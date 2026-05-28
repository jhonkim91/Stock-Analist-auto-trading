from __future__ import annotations

import hashlib
import json
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
KIS_OVERSEAS_REALTIME_QUOTE_TR_ID = "HDFSCNT0"
KIS_OVERSEAS_REALTIME_ASK_TR_ID = "HDFSASP0"
KIS_OVERSEAS_PAPER_NOTICE_TR_ID = "H0GSCNI9"


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
        enabled = _env_bool(
            PAPER_WEBSOCKET_ENABLED_ENV,
            default=bool((config or {}).get("realtime_websocket_enabled", False)),
        )
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
                "us_quote": KIS_OVERSEAS_REALTIME_QUOTE_TR_ID,
                "us_ask": KIS_OVERSEAS_REALTIME_ASK_TR_ID,
                "us_paper_notice": KIS_OVERSEAS_PAPER_NOTICE_TR_ID,
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
        market: str = "KR",
        exchange: str | None = None,
        subscribe: bool = True,
    ) -> dict[str, object]:
        """실제 WebSocket connect 없이 KIS paper 구독 메시지 형태를 redacted로 반환한다."""
        try:
            tr_id, tr_key = _subscription_tr_id_key(symbol=symbol, kind=kind, market=market, exchange=exchange)
        except ValueError as exc:
            return {
                "ok": False,
                "status": "subscription_invalid",
                "paper_only": True,
                "network_call_performed": False,
                "live_order_created": False,
                "reason": str(exc),
                "reason_codes": [str(exc)],
            }
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
        message = _subscription_message(
            approval_key="***REDACTED***",
            tr_id=tr_id,
            tr_key=tr_key,
            subscribe=subscribe,
            redact_tr_key=kind.strip().lower() == "notice",
        )
        return {
            "ok": True,
            "status": "subscription_preview",
            "paper_only": True,
            "subscription": message,
            "tr_id": tr_id,
            "tr_key_fingerprint": _fingerprint(tr_key),
            "market": _normalize_market(market),
            "exchange": _normalize_exchange(exchange) if _normalize_market(market) == "US" else None,
            "network_call_performed": False,
            "live_order_created": False,
            "reason": None,
            "reason_codes": [],
            "secrets_redacted": True,
        }

    def bounded_connect_smoke(
        self,
        *,
        symbol: str,
        kind: str = "quote",
        market: str = "KR",
        exchange: str | None = None,
        confirm: bool = False,
        receive_timeout_seconds: float = 3.0,
    ) -> dict[str, object]:
        """명시 gate가 열린 경우에만 WebSocket을 짧게 연결해 구독 ACK 또는 첫 메시지를 확인한다."""
        websocket_url = os.getenv(KIS_PAPER_WS_URL_ENV, DEFAULT_KIS_PAPER_WS_URL).strip() or DEFAULT_KIS_PAPER_WS_URL
        reason_codes = self._connect_gate_reasons(confirm=confirm, websocket_url=websocket_url)
        if reason_codes:
            return self._blocked_payload("websocket_connect_blocked", reason_codes)
        approval_key = os.getenv(KIS_WEBSOCKET_APPROVAL_KEY_ENV, "").strip()
        try:
            tr_id, tr_key = _subscription_tr_id_key(symbol=symbol, kind=kind, market=market, exchange=exchange)
        except ValueError as exc:
            return self._blocked_payload("websocket_connect_blocked", [str(exc)])

        message = _subscription_message(
            approval_key=approval_key,
            tr_id=tr_id,
            tr_key=tr_key,
            subscribe=True,
            redact_tr_key=False,
        )
        result = _run_bounded_websocket_smoke(
            websocket_url=websocket_url,
            message=message,
            tr_id=tr_id,
            tr_key=tr_key,
            timeout_seconds=min(max(receive_timeout_seconds, 0.5), 10.0),
        )
        result.update(
            {
                "paper_only": True,
                "market": _normalize_market(market),
                "exchange": _normalize_exchange(exchange) if _normalize_market(market) == "US" else None,
                "tr_id": tr_id,
                "tr_key_fingerprint": _fingerprint(tr_key),
                "approval_key_raw_value_persisted": False,
                "live_order_created": False,
                "secrets_redacted": True,
            }
        )
        return self.redactor.redact(result)

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

    def _connect_gate_reasons(self, *, confirm: bool, websocket_url: str) -> list[str]:
        reasons: list[str] = []
        if not confirm:
            reasons.append("KIS_WEBSOCKET_CONNECT_CONFIRM_REQUIRED")
        if not _env_true(PAPER_WEBSOCKET_ENABLED_ENV):
            reasons.append("PAPER_WEBSOCKET_DISABLED")
        if not _env_true(PAPER_WEBSOCKET_CONNECT_ENABLED_ENV):
            reasons.append("PAPER_WEBSOCKET_CONNECT_DISABLED")
        if os.getenv(KIS_ENV_ENV, "").strip().lower() != "paper":
            reasons.append("KIS_ENV_PAPER_REQUIRED")
        if not KisTokenManager.is_configured_value(os.getenv(KIS_WEBSOCKET_APPROVAL_KEY_ENV, "")):
            reasons.append("KIS_WEBSOCKET_APPROVAL_KEY_REQUIRED")
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


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _subscription_tr_id_key(
    *,
    symbol: str,
    kind: str,
    market: str,
    exchange: str | None,
) -> tuple[str, str]:
    normalized_kind = kind.strip().lower()
    normalized_market = _normalize_market(market)
    if normalized_market == "US":
        tr_id = {
            "quote": KIS_OVERSEAS_REALTIME_QUOTE_TR_ID,
            "ask": KIS_OVERSEAS_REALTIME_ASK_TR_ID,
            "notice": KIS_OVERSEAS_PAPER_NOTICE_TR_ID,
        }.get(normalized_kind)
        if tr_id is None:
            raise ValueError("KIS_WEBSOCKET_SUBSCRIPTION_KIND_UNSUPPORTED")
        if normalized_kind == "notice":
            return tr_id, os.getenv(KIS_HTS_ID_ENV, "").strip()
        normalized_exchange = _normalize_exchange(exchange)
        return tr_id, f"{_us_websocket_prefix(normalized_exchange)}{symbol.strip().upper()}"

    tr_id = {
        "quote": KIS_REALTIME_QUOTE_TR_ID,
        "ask": KIS_REALTIME_ASK_TR_ID,
        "notice": KIS_PAPER_NOTICE_TR_ID,
    }.get(normalized_kind)
    if tr_id is None:
        raise ValueError("KIS_WEBSOCKET_SUBSCRIPTION_KIND_UNSUPPORTED")
    tr_key = os.getenv(KIS_HTS_ID_ENV, "").strip() if normalized_kind == "notice" else symbol.strip()
    return tr_id, tr_key


def _subscription_message(
    *,
    approval_key: str,
    tr_id: str,
    tr_key: str,
    subscribe: bool,
    redact_tr_key: bool,
) -> dict[str, object]:
    return {
        "header": {
            "approval_key": approval_key,
            "custtype": "P",
            "tr_type": "1" if subscribe else "2",
            "content-type": "utf-8",
        },
        "body": {"input": {"tr_id": tr_id, "tr_key": "***REDACTED***" if redact_tr_key else tr_key}},
    }


def _normalize_market(value: str) -> str:
    normalized = str(value or "").strip().upper()
    return "US" if normalized in {"US", "USA", "OVERSEAS"} else "KR"


def _normalize_exchange(value: str | None) -> str:
    normalized = str(value or os.getenv("KIS_OVERSEAS_EXCHANGE_CODE", "NASD")).strip().upper()
    aliases = {"NASDAQ": "NASD", "NAS": "NASD"}
    normalized = aliases.get(normalized, normalized)
    if normalized != "NASD":
        raise ValueError("KIS_WEBSOCKET_OVERSEAS_EXCHANGE_UNSUPPORTED")
    return normalized


def _us_websocket_prefix(exchange: str) -> str:
    if exchange == "NASD":
        return "DNAS"
    raise ValueError("KIS_WEBSOCKET_OVERSEAS_EXCHANGE_UNSUPPORTED")


def _run_bounded_websocket_smoke(
    *,
    websocket_url: str,
    message: dict[str, object],
    tr_id: str,
    tr_key: str,
    timeout_seconds: float,
) -> dict[str, object]:
    import asyncio

    return asyncio.run(
        _bounded_websocket_smoke(
            websocket_url=websocket_url,
            message=message,
            tr_id=tr_id,
            tr_key=tr_key,
            timeout_seconds=timeout_seconds,
        )
    )


async def _bounded_websocket_smoke(
    *,
    websocket_url: str,
    message: dict[str, object],
    tr_id: str,
    tr_key: str,
    timeout_seconds: float,
) -> dict[str, object]:
    import asyncio
    import websockets

    started = datetime.now(UTC)
    try:
        async with websockets.connect(websocket_url, ping_interval=None, open_timeout=timeout_seconds) as websocket:
            await websocket.send(json.dumps(message, ensure_ascii=False))
            try:
                first_message = await asyncio.wait_for(websocket.recv(), timeout=timeout_seconds)
            except TimeoutError:
                first_message = None
            finally:
                unsubscribe = _subscription_message(
                    approval_key=str(message["header"]["approval_key"]),
                    tr_id=tr_id,
                    tr_key=tr_key,
                    subscribe=False,
                    redact_tr_key=False,
                )
                await websocket.send(json.dumps(unsubscribe, ensure_ascii=False))
    except Exception as exc:
        return {
            "ok": False,
            "status": "websocket_connect_failed",
            "network_call_performed": True,
            "reason": "KIS_WEBSOCKET_CONNECT_FAILED",
            "reason_codes": ["KIS_WEBSOCKET_CONNECT_FAILED"],
            "error_type": type(exc).__name__,
            "elapsed_ms": _elapsed_ms(started),
            "websocket_url": _safe_websocket_url_payload(websocket_url),
        }

    parsed = _parse_ws_message(first_message)
    return {
        "ok": True,
        "status": "websocket_message_received" if first_message is not None else "websocket_connected_no_message",
        "network_call_performed": True,
        "message_received": first_message is not None,
        "first_message": parsed,
        "elapsed_ms": _elapsed_ms(started),
        "websocket_url": _safe_websocket_url_payload(websocket_url),
        "reason": None,
        "reason_codes": [],
    }


def _parse_ws_message(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)
    payload: dict[str, object] = {
        "length": len(text),
        "sha256": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16],
        "raw_message_redacted": True,
    }
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                header = parsed.get("header") if isinstance(parsed.get("header"), dict) else {}
                body = parsed.get("body") if isinstance(parsed.get("body"), dict) else {}
                payload.update(
                    {
                        "kind": "json",
                        "tr_id": header.get("tr_id"),
                        "tr_key_fingerprint": _fingerprint(str(header.get("tr_key") or "")) if header.get("tr_key") else None,
                        "rt_cd": body.get("rt_cd"),
                        "msg1": body.get("msg1"),
                    }
                )
                return payload
        except json.JSONDecodeError:
            pass
    pipe_parts = text.split("|")
    payload.update(
        {
            "kind": "pipe" if len(pipe_parts) > 1 else "text",
            "tr_id": pipe_parts[1] if len(pipe_parts) > 1 else None,
            "data_count": pipe_parts[2] if len(pipe_parts) > 2 else None,
        }
    )
    return payload


def _elapsed_ms(started: datetime) -> float:
    return round((datetime.now(UTC) - started).total_seconds() * 1000, 3)


def _safe_websocket_url_payload(value: str) -> dict[str, object]:
    parsed = urlparse(value)
    return {
        "scheme": parsed.scheme,
        "host": parsed.hostname,
        "port": parsed.port,
        "paper_endpoint": _websocket_url_is_paper(value),
        "live_endpoint": _websocket_url_is_live(value),
    }


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
