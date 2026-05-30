"""KIS 실전(라이브) 주문 실행기.

⚠️ 실계좌에 실제 주문이 나가는 경로다. 실제 금전 손실 위험이 있다.

설계 원칙(안전 + 정확성):
- 검증된 모의 어댑터(kis_paper)의 요청 본문 빌더/응답 파서를 그대로 재사용한다.
  라이브는 base URL(실전 호스트), TR ID(모의 V → 실전 T 접두), 토큰/계좌만 다르다.
- 모의 코드 경로는 전혀 건드리지 않는다(오염 방지).
- 여러 토글이 모두 켜져야만 실행된다(LIVE_TRADING_ENABLED + LIVE_ORDER_SUBMIT_ENABLED +
  ENABLE_REAL_ORDER), 킬 스위치/주문 확인/주문당 최대 금액 가드를 유지한다.
- 라이브 호스트가 아니면 거부한다(모의 호스트로 실주문 오발송 방지).
"""

from __future__ import annotations

import os
from typing import Any

from backend.app.brokers.base import BrokerOrderRequest
from backend.app.brokers.kis_paper import (
    KIS_CUSTOMER_TYPE,
    KIS_LIVE_HOST,
    KIS_ORDER_CASH_PATH,
    KisPaperBrokerRequestError,
    KisPaperCredentials,
    KisPaperRequestMapper,
    KisPaperResponseMapper,
)
from backend.app.services.credential_redaction import CredentialRedactionService
from backend.app.services.kis_http_client import KisHttpClient

DEFAULT_KIS_LIVE_BASE_URL = "https://openapi.koreainvestment.com:9443"

# 토글/가드 env
LIVE_TRADING_ENABLED_ENV = "LIVE_TRADING_ENABLED"
LIVE_ORDER_SUBMIT_ENABLED_ENV = "LIVE_ORDER_SUBMIT_ENABLED"
LIVE_ORDER_CONFIRM_REQUIRED_ENV = "LIVE_ORDER_CONFIRM_REQUIRED"
LIVE_KILL_SWITCH_ENV = "LIVE_KILL_SWITCH"
ENABLE_REAL_ORDER_ENV = "ENABLE_REAL_ORDER"
LIVE_MAX_ORDER_NOTIONAL_ENV = "LIVE_MAX_ORDER_NOTIONAL"
KIS_LIVE_BASE_URL_ENV = "KIS_LIVE_BASE_URL"

_TRUE = {"1", "true", "yes", "on"}


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in _TRUE


def _first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return default


def live_tr_id(paper_tr_id: str, *, override_env: str | None = None) -> str:
    """모의 TR ID(V 접두)를 실전 TR ID(T 접두)로 바꾼다. env 오버라이드 우선."""
    if override_env:
        override = os.getenv(override_env, "").strip()
        if override:
            return override
    if paper_tr_id[:1].upper() == "V":
        return "T" + paper_tr_id[1:]
    return paper_tr_id


# 모의 → 실전 TR ID 오버라이드 env 매핑(선택). 미설정 시 V→T 자동 치환.
_TR_OVERRIDE_ENV = {
    "buy": "KIS_LIVE_BUY_TR_ID",
    "sell": "KIS_LIVE_SELL_TR_ID",
    "cancel": "KIS_LIVE_CANCEL_TR_ID",
}


class KisLiveOrderExecutor:
    """실전 주문 제출/취소를 수행한다(게이트 통과 시에만)."""

    def __init__(self, *, http_client: Any | None = None, timeout_seconds: float = 10.0) -> None:
        self.http_client = http_client
        self.timeout_seconds = timeout_seconds
        self.redaction_service = CredentialRedactionService()

    # ---------------------------------------------------------------- credentials
    def _base_url(self) -> str:
        return _first_env(KIS_LIVE_BASE_URL_ENV, default=DEFAULT_KIS_LIVE_BASE_URL)

    def _credentials(self) -> KisPaperCredentials:
        """라이브 자격증명 묶음(모의 dataclass 재사용; 매퍼는 account/product만 사용)."""
        return KisPaperCredentials(
            app_key=_first_env("KIS_LIVE_APP_KEY", "KIS_APP_KEY"),
            app_secret=_first_env("KIS_LIVE_APP_SECRET", "KIS_APP_SECRET"),
            access_token=_first_env("KIS_LIVE_ACCESS_TOKEN", "KIS_ACCESS_TOKEN"),
            account_no=_first_env("KIS_LIVE_ACCOUNT_NO", "KIS_ACCOUNT_NO"),
            product_code=_first_env("KIS_LIVE_PRODUCT_CODE", "KIS_PRODUCT_CODE"),
            base_url=self._base_url(),
        )

    @staticmethod
    def _credentials_present(creds: KisPaperCredentials) -> bool:
        return all([creds.app_key, creds.app_secret, creds.access_token, creds.account_no, creds.product_code])

    @staticmethod
    def _is_live_host(base_url: str) -> bool:
        return KIS_LIVE_HOST in base_url

    # ---------------------------------------------------------------- gates
    def _max_notional(self) -> float | None:
        raw = os.getenv(LIVE_MAX_ORDER_NOTIONAL_ENV, "").strip()
        if not raw:
            return None
        try:
            value = float(raw)
        except ValueError:
            return None
        return value if value > 0 else None

    def _base_gate_reasons(self, creds: KisPaperCredentials) -> list[str]:
        reasons: list[str] = []
        if not _bool_env(LIVE_TRADING_ENABLED_ENV):
            reasons.append("LIVE_TRADING_DISABLED")
        if not _bool_env(ENABLE_REAL_ORDER_ENV):
            reasons.append("ENABLE_REAL_ORDER_REQUIRED")
        if _bool_env(LIVE_KILL_SWITCH_ENV):
            reasons.append("LIVE_KILL_SWITCH_ACTIVE")
        if not self._credentials_present(creds):
            reasons.append("KIS_LIVE_CREDENTIALS_MISSING")
        if not self._is_live_host(creds.base_url):
            reasons.append("KIS_LIVE_BASE_URL_REQUIRED")
        return reasons

    def gate_status(self) -> dict[str, Any]:
        creds = self._credentials()
        reasons = list(self._base_gate_reasons(creds))
        if not _bool_env(LIVE_ORDER_SUBMIT_ENABLED_ENV):
            reasons.append("LIVE_ORDER_SUBMIT_DISABLED")
        return {
            "live_trading_enabled": _bool_env(LIVE_TRADING_ENABLED_ENV),
            "live_order_submit_enabled": _bool_env(LIVE_ORDER_SUBMIT_ENABLED_ENV),
            "real_order_enabled": _bool_env(ENABLE_REAL_ORDER_ENV),
            "kill_switch": _bool_env(LIVE_KILL_SWITCH_ENV),
            "confirm_required": _bool_env(LIVE_ORDER_CONFIRM_REQUIRED_ENV, default=True),
            "credentials_present": self._credentials_present(creds),
            "base_url_host": KIS_LIVE_HOST if self._is_live_host(creds.base_url) else "non_live",
            "max_order_notional": self._max_notional(),
            "can_submit": not reasons,
            "reason_codes": reasons,
            "secrets_redacted": True,
        }

    # ---------------------------------------------------------------- submit
    def submit_order(self, request: BrokerOrderRequest, *, confirm: bool = False) -> dict[str, Any]:
        creds = self._credentials()
        reasons = list(self._base_gate_reasons(creds))
        if not _bool_env(LIVE_ORDER_SUBMIT_ENABLED_ENV):
            reasons.append("LIVE_ORDER_SUBMIT_DISABLED")
        if _bool_env(LIVE_ORDER_CONFIRM_REQUIRED_ENV, default=True) and not confirm:
            reasons.append("LIVE_ORDER_CONFIRM_REQUIRED")
        # 주문당 최대 금액 가드(지정가일 때만 계산 가능)
        max_notional = self._max_notional()
        if max_notional is not None and request.limit_price is not None:
            if float(request.qty) * float(request.limit_price) > max_notional:
                reasons.append("LIVE_MAX_ORDER_NOTIONAL_EXCEEDED")
        if reasons:
            return self._blocked("submit_blocked", reasons, request=request)

        try:
            tr_id, body = KisPaperRequestMapper.order_cash_body(request, creds)
        except KisPaperBrokerRequestError as exc:
            return self._blocked("submit_invalid", [str(exc)], request=request)

        side = request.side.strip().lower()
        override = _TR_OVERRIDE_ENV.get(side)
        tr = live_tr_id(tr_id, override_env=override)
        path = KIS_ORDER_CASH_PATH if not _is_overseas(request) else None
        if path is None:
            # 라이브는 현재 국내(KRX) 현금 주문만 지원한다.
            return self._blocked("submit_unsupported", ["KIS_LIVE_OVERSEAS_ORDER_UNSUPPORTED"], request=request)

        result = self._post(path, tr, creds, body)
        if not result["ok"]:
            return self._failed("submit_failed", result, request=request)
        try:
            mapped = KisPaperResponseMapper.submit_response(result["body"], request)
        except KisPaperBrokerRequestError as exc:
            return self._failed("submit_response_error", {"reason": str(exc), "body": {}}, request=request)
        return {
            "ok": True,
            "status": "submitted",
            "operation": "submit_order",
            "mode": "live",
            "live_order_created": True,
            "order_created": True,
            "broker_order_created": True,
            "network_call_performed": True,
            "tr_id": tr,
            "broker_order_id": mapped["broker_order_id"],
            "broker_order_status": mapped["broker_order_status"],
            "broker_message_code": mapped.get("broker_message_code", ""),
            "broker_message": mapped.get("broker_message", ""),
            "order": mapped["order"],
            "reason_codes": [],
            "secrets_redacted": True,
        }

    # ---------------------------------------------------------------- cancel
    def cancel_order(self, *, broker_order_id: str, confirm: bool = False) -> dict[str, Any]:
        creds = self._credentials()
        reasons = list(self._base_gate_reasons(creds))
        if not broker_order_id.strip():
            reasons.append("LIVE_CANCEL_BROKER_ORDER_ID_REQUIRED")
        if _bool_env(LIVE_ORDER_CONFIRM_REQUIRED_ENV, default=True) and not confirm:
            reasons.append("LIVE_CANCEL_CONFIRM_REQUIRED")
        if reasons:
            return self._blocked("cancel_blocked", reasons)

        try:
            path, tr_id, body = KisPaperRequestMapper.cancel_request(broker_order_id, creds)
        except KisPaperBrokerRequestError as exc:
            return self._blocked("cancel_invalid", [str(exc)])
        tr = live_tr_id(tr_id, override_env=_TR_OVERRIDE_ENV["cancel"])
        result = self._post(path, tr, creds, body)
        if not result["ok"]:
            return self._failed("cancel_failed", result)
        mapped = KisPaperResponseMapper.cancel_response(result["body"], broker_order_id)
        return {
            "ok": True,
            "status": "cancelled",
            "operation": "cancel_order",
            "mode": "live",
            "order_cancelled": True,
            "live_order_created": False,
            "network_call_performed": True,
            "tr_id": tr,
            "broker_order_id": broker_order_id,
            "broker_message_code": mapped.get("broker_message_code", ""),
            "broker_message": mapped.get("broker_message", ""),
            "reason_codes": [],
            "secrets_redacted": True,
        }

    # ---------------------------------------------------------------- http
    def _post(self, path: str, tr_id: str, creds: KisPaperCredentials, body: dict[str, str]) -> dict[str, Any]:
        url = f"{creds.base_url.rstrip('/')}{path}"
        headers = {
            "authorization": f"Bearer {creds.access_token}",
            "appkey": creds.app_key,
            "appsecret": creds.app_secret,
            "tr_id": tr_id,
            "custtype": KIS_CUSTOMER_TYPE,
            "content-type": "application/json; charset=utf-8",
        }
        result = KisHttpClient(
            http_client=self.http_client,
            timeout_seconds=self.timeout_seconds,
            max_retries=0,
            redaction_service=self.redaction_service,
        ).request(
            "POST",
            url,
            headers=headers,
            json_body=body,
            retry_enabled=False,
            operation="POST",
            tr_id=tr_id,
            redact_body=False,
            correlation_prefix="kis-live",
        )
        if not result.ok:
            response_body = result.body if isinstance(result.body, dict) else {}
            return {"ok": False, "reason": result.reason, "body": self.redaction_service.redact(response_body)}
        response_body = result.body
        if not isinstance(response_body, dict):
            return {"ok": False, "reason": "KIS_LIVE_RESPONSE_ERROR", "body": {}}
        if str(response_body.get("rt_cd", "0")) != "0":
            return {
                "ok": False,
                "reason": "KIS_LIVE_RESPONSE_ERROR",
                "body": self.redaction_service.redact(response_body),
                "broker_message_code": str(response_body.get("msg_cd") or ""),
                "broker_message": str(response_body.get("msg1") or "").strip(),
            }
        return {"ok": True, "reason": None, "body": response_body}

    # ---------------------------------------------------------------- payloads
    def _blocked(self, status: str, reason_codes: list[str], *, request: BrokerOrderRequest | None = None) -> dict[str, Any]:
        payload = {
            "ok": False,
            "status": status,
            "mode": "live",
            "live_order_created": False,
            "order_created": False,
            "network_call_performed": False,
            "reason_codes": _dedupe(reason_codes),
            "secrets_redacted": True,
        }
        if request is not None:
            payload.update({"symbol": request.symbol, "side": request.side, "qty": request.qty})
        return payload

    def _failed(self, status: str, result: dict[str, Any], *, request: BrokerOrderRequest | None = None) -> dict[str, Any]:
        payload = {
            "ok": False,
            "status": status,
            "mode": "live",
            "live_order_created": False,
            "network_call_performed": True,
            "reason_codes": [str(result.get("reason") or "KIS_LIVE_RESPONSE_ERROR")],
            "broker_message_code": str(result.get("broker_message_code") or ""),
            "broker_message": str(result.get("broker_message") or ""),
            "secrets_redacted": True,
        }
        if request is not None:
            payload.update({"symbol": request.symbol, "side": request.side, "qty": request.qty})
        return payload


def _is_overseas(request: BrokerOrderRequest) -> bool:
    venue = str((request.metadata or {}).get("venue") or (request.metadata or {}).get("market") or "").strip().upper()
    return venue in {"US", "NASD", "NYSE", "AMEX", "NAS", "NYS"}


def _dedupe(codes: list[str]) -> list[str]:
    seen: list[str] = []
    for code in codes:
        if code not in seen:
            seen.append(code)
    return seen
