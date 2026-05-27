from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from backend.app.brokers.base import BrokerAdapter, BrokerCapabilityError, BrokerOrderRequest
from backend.app.services.credential_redaction import CredentialRedactionService
from backend.app.services.token_manager import KIS_APP_KEY_ENV, KIS_APP_SECRET_ENV, KisTokenManager

CONFIRMATION_REQUIRED = "KIS_PAPER_OFFICIAL_ENDPOINT_CONFIRMATION_REQUIRED"
CANCEL_CONFIRMATION_REQUIRED = "KIS_PAPER_CANCEL_CONFIRMATION_REQUIRED"
SYNC_CONFIRMATION_REQUIRED = "KIS_PAPER_SYNC_CONFIRMATION_REQUIRED"
KIS_PAPER_NETWORK_DISABLED = "KIS_PAPER_NETWORK_DISABLED"
KIS_PAPER_CREDENTIALS_MISSING = "KIS_PAPER_CREDENTIALS_MISSING"
KIS_PAPER_RESPONSE_ERROR = "KIS_PAPER_RESPONSE_ERROR"
KIS_PAPER_RATE_LIMITED = "KIS_PAPER_RATE_LIMITED"
KIS_PAPER_TIMEOUT = "KIS_PAPER_TIMEOUT"
KIS_PAPER_TRANSPORT_ERROR = "KIS_PAPER_TRANSPORT_ERROR"
KIS_LIVE_BASE_URL_BLOCKED = "KIS_LIVE_BASE_URL_BLOCKED"

KIS_ACCESS_TOKEN_ENV = "KIS_ACCESS_TOKEN"
KIS_ACCOUNT_NO_ENV = "KIS_ACCOUNT_NO"
KIS_PRODUCT_CODE_ENV = "KIS_PRODUCT_CODE"
KIS_PAPER_BASE_URL_ENV = "KIS_PAPER_BASE_URL"
ENABLE_REAL_ORDER_ENV = "ENABLE_REAL_ORDER"

DEFAULT_KIS_PAPER_BASE_URL = "https://openapivts.koreainvestment.com:29443"
KIS_LIVE_HOST = "openapi.koreainvestment.com"
KIS_CUSTOMER_TYPE = "P"

KIS_ORDER_CASH_PATH = "/uapi/domestic-stock/v1/trading/order-cash"
KIS_ORDER_CANCEL_PATH = "/uapi/domestic-stock/v1/trading/order-rvsecncl"
KIS_DAILY_CCLD_PATH = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
KIS_BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"

KIS_PAPER_BUY_TR_ID = "VTTC0012U"
KIS_PAPER_SELL_TR_ID = "VTTC0011U"
KIS_PAPER_CANCEL_TR_ID = "VTTC0013U"
KIS_PAPER_DAILY_CCLD_TR_ID = "VTTC0081R"
KIS_PAPER_BALANCE_TR_ID = "VTTC8434R"

SUPPORTED_SYNC_SCOPES = {"orders", "fills", "positions", "portfolio", "all"}
SENSITIVE_RESPONSE_KEYS = {"CANO", "ACNT_PRDT_CD", "authorization", "appkey", "appsecret"}


class KisPaperBrokerRequestError(RuntimeError):
    """KIS paper 요청이 안전 조건 또는 응답 조건을 만족하지 못할 때 사용한다."""


@dataclass(frozen=True)
class KisPaperCredentials:
    """KIS paper adapter가 env에서만 읽는 credential bundle."""

    app_key: str = field(repr=False)
    app_secret: str = field(repr=False)
    access_token: str = field(repr=False)
    account_no: str = field(repr=False)
    product_code: str = field(repr=False)
    base_url: str = DEFAULT_KIS_PAPER_BASE_URL

    @classmethod
    def from_env(cls) -> "KisPaperCredentials":
        credentials = cls(
            app_key=os.getenv(KIS_APP_KEY_ENV, "").strip(),
            app_secret=os.getenv(KIS_APP_SECRET_ENV, "").strip(),
            access_token=os.getenv(KIS_ACCESS_TOKEN_ENV, "").strip(),
            account_no=os.getenv(KIS_ACCOUNT_NO_ENV, "").strip(),
            product_code=os.getenv(KIS_PRODUCT_CODE_ENV, "").strip(),
            base_url=os.getenv(KIS_PAPER_BASE_URL_ENV, DEFAULT_KIS_PAPER_BASE_URL).strip()
            or DEFAULT_KIS_PAPER_BASE_URL,
        )
        missing = [name for name, configured in cls.configured_fields().items() if not configured]
        if missing:
            raise KisPaperBrokerRequestError(KIS_PAPER_CREDENTIALS_MISSING)
        if _is_live_base_url(credentials.base_url):
            raise KisPaperBrokerRequestError(KIS_LIVE_BASE_URL_BLOCKED)
        return credentials

    @classmethod
    def configured_fields(cls) -> dict[str, bool]:
        return {
            "app_key_configured": KisTokenManager.env_configured(KIS_APP_KEY_ENV),
            "app_secret_configured": KisTokenManager.env_configured(KIS_APP_SECRET_ENV),
            "access_token_configured": cls._is_configured_value(os.getenv(KIS_ACCESS_TOKEN_ENV, "")),
            "account_configured": cls._is_configured_value(os.getenv(KIS_ACCOUNT_NO_ENV, "")),
            "product_code_configured": cls._is_configured_value(os.getenv(KIS_PRODUCT_CODE_ENV, "")),
        }

    @staticmethod
    def _is_configured_value(value: str) -> bool:
        return KisTokenManager.is_configured_value(value)


class KisPaperRequestMapper:
    """공식 샘플에서 확인된 KIS paper 주문/조회 field만 생성한다."""

    @staticmethod
    def order_cash_body(request: BrokerOrderRequest, credentials: KisPaperCredentials) -> tuple[str, dict[str, str]]:
        side = request.side.strip().lower()
        if side not in {"buy", "sell"}:
            raise KisPaperBrokerRequestError("KIS_PAPER_INVALID_ORDER_SIDE")
        if request.qty <= 0:
            raise KisPaperBrokerRequestError("KIS_PAPER_INVALID_ORDER_QTY")
        if request.stop_price is not None:
            raise KisPaperBrokerRequestError("KIS_PAPER_STOP_ORDER_UNSUPPORTED")

        tr_id = KIS_PAPER_BUY_TR_ID if side == "buy" else KIS_PAPER_SELL_TR_ID
        ord_dvsn = "00" if request.limit_price is not None else "01"
        ord_unpr = _price_to_kis_string(request.limit_price)
        body = {
            "CANO": credentials.account_no,
            "ACNT_PRDT_CD": credentials.product_code,
            "PDNO": request.symbol.strip(),
            "ORD_DVSN": ord_dvsn,
            "ORD_QTY": str(int(request.qty)),
            "ORD_UNPR": ord_unpr,
            "EXCG_ID_DVSN_CD": _exchange_from_metadata(request.metadata),
            "SLL_TYPE": "01" if side == "sell" else "",
            "CNDT_PRIC": "",
        }
        return tr_id, body

    @staticmethod
    def cancel_body(broker_order_id: str, credentials: KisPaperCredentials) -> dict[str, str]:
        order_key = decode_broker_order_key(broker_order_id)
        return {
            "CANO": credentials.account_no,
            "ACNT_PRDT_CD": credentials.product_code,
            "KRX_FWDG_ORD_ORGNO": order_key["krx_fwdg_ord_orgno"],
            "ORGN_ODNO": order_key["odno"],
            "ORD_DVSN": order_key["ord_dvsn"],
            "RVSE_CNCL_DVSN_CD": "02",
            "ORD_QTY": order_key["qty"],
            "ORD_UNPR": order_key["price"],
            "QTY_ALL_ORD_YN": "Y",
            "EXCG_ID_DVSN_CD": order_key["excg_id_dvsn_cd"],
        }

    @staticmethod
    def daily_ccld_params(credentials: KisPaperCredentials, status: str | None = None) -> dict[str, str]:
        today = datetime.now(UTC).date().strftime("%Y%m%d")
        ccld_dvsn = "00"
        if status and status.strip().lower() in {"filled", "partially_filled"}:
            ccld_dvsn = "01"
        elif status and status.strip().lower() in {"open", "submitted", "pending"}:
            ccld_dvsn = "02"
        return {
            "CANO": credentials.account_no,
            "ACNT_PRDT_CD": credentials.product_code,
            "INQR_STRT_DT": today,
            "INQR_END_DT": today,
            "SLL_BUY_DVSN_CD": "00",
            "PDNO": "",
            "CCLD_DVSN": ccld_dvsn,
            "INQR_DVSN": "00",
            "INQR_DVSN_3": "00",
            "ORD_GNO_BRNO": "",
            "ODNO": "",
            "INQR_DVSN_1": "",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
            "EXCG_ID_DVSN_CD": "KRX",
        }

    @staticmethod
    def balance_params(credentials: KisPaperCredentials) -> dict[str, str]:
        return {
            "CANO": credentials.account_no,
            "ACNT_PRDT_CD": credentials.product_code,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "01",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "00",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }


class KisPaperResponseMapper:
    """KIS paper response를 내부 표준 payload로 변환하고 raw payload 노출을 막는다."""

    @staticmethod
    def submit_response(body: dict[str, Any], request: BrokerOrderRequest) -> dict[str, Any]:
        output = _first_mapping(body.get("output"))
        order_no = _first_value(output, "ODNO", "odno", "odno_orgno", "ORGN_ODNO")
        org_no = _first_value(output, "KRX_FWDG_ORD_ORGNO", "krx_fwdg_ord_orgno", "ORD_GNO_BRNO", "ord_gno_brno")
        if not order_no or not org_no:
            raise KisPaperBrokerRequestError("KIS_PAPER_ORDER_RESPONSE_KEY_MISSING")
        broker_order_id = encode_broker_order_key(
            krx_fwdg_ord_orgno=org_no,
            odno=order_no,
            qty=str(int(request.qty)),
            price=_price_to_kis_string(request.limit_price),
            ord_dvsn="00" if request.limit_price is not None else "01",
            excg_id_dvsn_cd=_exchange_from_metadata(request.metadata),
        )
        return {
            "broker_order_id": broker_order_id,
            "broker_order_status": "submitted",
            "broker_message_code": str(body.get("msg_cd") or ""),
            "broker_message": str(body.get("msg1") or "").strip(),
            "order": {
                "symbol": request.symbol.strip(),
                "side": request.side.strip().lower(),
                "qty": int(request.qty),
                "filled_qty": 0,
                "remaining_qty": int(request.qty),
                "status": "submitted",
            },
        }

    @staticmethod
    def cancel_response(body: dict[str, Any], broker_order_id: str) -> dict[str, Any]:
        return {
            "broker_order_id": broker_order_id,
            "broker_order_status": "cancelled",
            "broker_message_code": str(body.get("msg_cd") or ""),
            "broker_message": str(body.get("msg1") or "").strip(),
        }

    @staticmethod
    def daily_orders_response(body: dict[str, Any]) -> dict[str, Any]:
        rows = body.get("output1") or body.get("output") or []
        if not isinstance(rows, list):
            raise KisPaperBrokerRequestError("KIS_PAPER_DAILY_CCLD_OUTPUT_INVALID")
        orders = [order for row in rows if isinstance(row, dict) and (order := _order_from_daily_row(row)) is not None]
        fills = [fill for row in rows if isinstance(row, dict) and (fill := _fill_from_daily_row(row)) is not None]
        return {
            "orders": orders,
            "fills": fills,
            "broker_message_code": str(body.get("msg_cd") or ""),
            "broker_message": str(body.get("msg1") or "").strip(),
        }

    @staticmethod
    def balance_response(body: dict[str, Any]) -> dict[str, Any]:
        holdings = body.get("output1") or []
        if not isinstance(holdings, list):
            raise KisPaperBrokerRequestError("KIS_PAPER_BALANCE_OUTPUT_INVALID")
        summary = _first_mapping(body.get("output2"))
        positions = [_position_from_balance_row(row) for row in holdings if isinstance(row, dict)]
        positions = [position for position in positions if position is not None]
        snapshot = _portfolio_snapshot_from_summary(summary)
        return {
            "positions": positions,
            "portfolio": snapshot,
            "broker_message_code": str(body.get("msg_cd") or ""),
            "broker_message": str(body.get("msg1") or "").strip(),
        }


class KisPaperBrokerAdapter(BrokerAdapter):
    name = "kis_paper"
    mode = "paper"

    def __init__(
        self,
        *,
        config: dict[str, Any] | None = None,
        http_client: Any | None = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 1,
        redaction_service: CredentialRedactionService | None = None,
    ) -> None:
        self.config = config or {}
        self.http_client = http_client
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.redaction_service = redaction_service or CredentialRedactionService()

    def status(self) -> dict[str, Any]:
        """KIS paper adapter 상태를 secret 없이 반환한다."""
        credentials = KisPaperCredentials.configured_fields()
        network_enabled = bool(self.config.get("network_enabled", False))
        endpoint_confirmed = bool(self.config.get("official_endpoint_confirmed", False))
        enabled = self._status_enabled(credentials)
        return {
            "name": self.name,
            "mode": self.mode,
            "enabled": enabled,
            "paper_trading_enabled": bool(self.config.get("enabled", False)),
            "live_trading_enabled": False,
            "network_enabled": network_enabled,
            "can_preview": False,
            "can_submit": enabled and bool(self.config.get("configured_can_create", False)),
            "can_cancel": enabled and bool(self.config.get("configured_can_create", False)),
            "can_list_orders": enabled,
            "can_sync": enabled,
            "token_required": True,
            "token_issued": credentials["access_token_configured"],
            "token_persistence_enabled": False,
            "official_endpoint_confirmed": endpoint_confirmed,
            "credential_fields": credentials,
            "reason": None if enabled else CONFIRMATION_REQUIRED,
        }

    def preview_order(self, request: BrokerOrderRequest) -> dict[str, Any]:
        """KIS adapter preview는 구현 범위가 아니므로 실행하지 않는다."""
        raise BrokerCapabilityError(CONFIRMATION_REQUIRED)

    def submit_order(self, request: BrokerOrderRequest) -> dict[str, Any]:
        """KIS 모의투자 현금 주문을 paper-only gate 통과 시에만 전송한다."""
        gate = self._gate_reasons(require_create=True, require_kill_switch_off=True)
        if gate:
            return self._blocked_payload("submit_blocked", gate, operation="submit")
        try:
            credentials = KisPaperCredentials.from_env()
            tr_id, body = KisPaperRequestMapper.order_cash_body(request, credentials)
            response = self._request("POST", KIS_ORDER_CASH_PATH, tr_id=tr_id, body=body, credentials=credentials)
            if not response["ok"]:
                return self._error_payload("submit_failed", response, operation="submit")
            mapped = KisPaperResponseMapper.submit_response(response["body"], request)
        except KisPaperBrokerRequestError as exc:
            return self._blocked_payload("submit_blocked", [str(exc)], operation="submit")
        return {
            "ok": True,
            "status": "submitted",
            "paper_only": True,
            "paper_order_created": False,
            "live_order_created": False,
            "broker_order_created": True,
            "network_call_performed": True,
            "reason": "KIS_PAPER_ORDER_SUBMITTED",
            "reason_codes": [],
            "broker_order_id": mapped["broker_order_id"],
            "broker_order_status": mapped["broker_order_status"],
            "broker_message_code": mapped["broker_message_code"],
            "broker_message": mapped["broker_message"],
            "order": mapped["order"],
            "broker_trace": response["trace"],
        }

    def cancel_order(self, *, broker_order_id: str, confirm: bool = False) -> dict[str, Any]:
        """KIS 모의투자 주문취소를 paper-only gate 통과 시에만 전송한다."""
        if not confirm:
            return self._blocked_payload("confirm_required", ["PAPER_CONFIRM_TRUE_REQUIRED"], operation="cancel")
        gate = self._gate_reasons(require_create=True, require_kill_switch_off=True)
        if gate:
            cancel_gate = [CANCEL_CONFIRMATION_REQUIRED if code == CONFIRMATION_REQUIRED else code for code in gate]
            return self._blocked_payload("cancel_blocked", cancel_gate, operation="cancel")
        try:
            credentials = KisPaperCredentials.from_env()
            body = KisPaperRequestMapper.cancel_body(broker_order_id, credentials)
            response = self._request(
                "POST",
                KIS_ORDER_CANCEL_PATH,
                tr_id=KIS_PAPER_CANCEL_TR_ID,
                body=body,
                credentials=credentials,
            )
            if not response["ok"]:
                return self._error_payload("cancel_failed", response, operation="cancel")
            mapped = KisPaperResponseMapper.cancel_response(response["body"], broker_order_id)
        except KisPaperBrokerRequestError as exc:
            return self._blocked_payload("cancel_blocked", [str(exc)], operation="cancel")
        return {
            "ok": True,
            "status": "cancelled",
            "paper_only": True,
            "cancel_supported": True,
            "order_cancelled": True,
            "paper_order_created": False,
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": True,
            "reason": "KIS_PAPER_ORDER_CANCELLED",
            "reason_codes": [],
            "broker_order_id": mapped["broker_order_id"],
            "broker_order_status": mapped["broker_order_status"],
            "broker_message_code": mapped["broker_message_code"],
            "broker_message": mapped["broker_message"],
            "broker_trace": response["trace"],
        }

    def list_orders(self, *, status: str | None = None) -> dict[str, Any]:
        """KIS 모의투자 일별 주문체결 조회를 paper-only gate 통과 시에만 실행한다."""
        gate = self._gate_reasons(require_create=False, require_kill_switch_off=False)
        if gate:
            return self._blocked_payload("query_blocked", gate, operation="list_orders")
        try:
            credentials = KisPaperCredentials.from_env()
            params = KisPaperRequestMapper.daily_ccld_params(credentials, status=status)
            response = self._request(
                "GET",
                KIS_DAILY_CCLD_PATH,
                tr_id=KIS_PAPER_DAILY_CCLD_TR_ID,
                params=params,
                credentials=credentials,
            )
            if not response["ok"]:
                return self._error_payload("query_failed", response, operation="list_orders")
            mapped = KisPaperResponseMapper.daily_orders_response(response["body"])
        except KisPaperBrokerRequestError as exc:
            return self._blocked_payload("query_blocked", [str(exc)], operation="list_orders")
        return {
            "ok": True,
            "status": "query_ok",
            "paper_only": True,
            "orders": mapped["orders"],
            "fills": mapped["fills"],
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": True,
            "reason": None,
            "reason_codes": [],
            "broker_message_code": mapped["broker_message_code"],
            "broker_message": mapped["broker_message"],
            "broker_trace": response["trace"],
        }

    def sync(self, *, scope: str = "all") -> dict[str, Any]:
        """KIS 모의투자 주문/체결/잔고 조회를 조합해 sync payload를 생성한다."""
        normalized_scope = scope.strip().lower() if scope else "all"
        if normalized_scope not in SUPPORTED_SYNC_SCOPES:
            return self._blocked_payload(
                "invalid_scope",
                ["PAPER_SYNC_SCOPE_UNSUPPORTED"],
                operation="sync",
                extra={"scope": scope, "supported_scopes": sorted(SUPPORTED_SYNC_SCOPES)},
            )
        gate = self._gate_reasons(require_create=False, require_kill_switch_off=False)
        if gate:
            sync_gate = [SYNC_CONFIRMATION_REQUIRED if code == CONFIRMATION_REQUIRED else code for code in gate]
            return self._blocked_payload("sync_blocked", sync_gate, operation="sync", extra={"scope": normalized_scope})

        orders: list[dict[str, Any]] = []
        fills: list[dict[str, Any]] = []
        positions: list[dict[str, Any]] = []
        portfolio: dict[str, Any] | None = None
        traces: list[dict[str, Any]] = []
        try:
            credentials = KisPaperCredentials.from_env()
            if normalized_scope in {"orders", "fills", "all"}:
                params = KisPaperRequestMapper.daily_ccld_params(credentials)
                order_response = self._request(
                    "GET",
                    KIS_DAILY_CCLD_PATH,
                    tr_id=KIS_PAPER_DAILY_CCLD_TR_ID,
                    params=params,
                    credentials=credentials,
                )
                traces.append(order_response["trace"])
                if not order_response["ok"]:
                    return self._error_payload("sync_failed", order_response, operation="sync")
                mapped_orders = KisPaperResponseMapper.daily_orders_response(order_response["body"])
                orders = mapped_orders["orders"]
                fills = mapped_orders["fills"]
            if normalized_scope in {"positions", "portfolio", "all"}:
                balance_response = self._request(
                    "GET",
                    KIS_BALANCE_PATH,
                    tr_id=KIS_PAPER_BALANCE_TR_ID,
                    params=KisPaperRequestMapper.balance_params(credentials),
                    credentials=credentials,
                )
                traces.append(balance_response["trace"])
                if not balance_response["ok"]:
                    return self._error_payload("sync_failed", balance_response, operation="sync")
                mapped_balance = KisPaperResponseMapper.balance_response(balance_response["body"])
                positions = mapped_balance["positions"]
                portfolio = mapped_balance["portfolio"]
        except KisPaperBrokerRequestError as exc:
            return self._blocked_payload("sync_blocked", [str(exc)], operation="sync", extra={"scope": normalized_scope})
        return {
            "ok": True,
            "status": "sync_ok",
            "scope": normalized_scope,
            "synced_scopes": _expanded_scopes(normalized_scope),
            "sync_performed": True,
            "paper_only": True,
            "orders": orders,
            "fills": fills,
            "positions": positions,
            "portfolio": portfolio,
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": True,
            "synthetic_positions_touched": False,
            "reason": None,
            "reason_codes": [],
            "broker_trace": self.redaction_service.redact(
                {
                    "operation": "sync",
                    "adapter": self.name,
                    "paper_only": True,
                    "scope": normalized_scope,
                    "network_call_performed": True,
                    "request_count": len(traces),
                    "traces": traces,
                    "secrets_redacted": True,
                }
            ),
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        tr_id: str,
        credentials: KisPaperCredentials,
        body: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = f"{credentials.base_url.rstrip('/')}{path}"
        headers = self._headers(credentials, tr_id)
        close_client = self.http_client is None
        client = self.http_client or httpx.Client(timeout=self.timeout_seconds)
        retry_allowed = method.upper() == "GET"
        max_attempts = 1 + (self.max_retries if retry_allowed else 0)
        last_error = KIS_PAPER_TRANSPORT_ERROR
        started = time.perf_counter()
        status_code: int | None = None
        try:
            for attempt in range(max_attempts):
                try:
                    response = self._send_request(
                        client,
                        method,
                        url,
                        headers=headers,
                        body=body,
                        params=params,
                    )
                    status_code = int(response.status_code)
                    trace = self._trace(
                        operation=method,
                        method=method,
                        path=path,
                        tr_id=tr_id,
                        credentials=credentials,
                        status_code=status_code,
                        started=started,
                        retry_count=attempt,
                        request_fields=body or params or {},
                    )
                    if status_code == 429:
                        trace["rate_limited"] = True
                        return {"ok": False, "reason": KIS_PAPER_RATE_LIMITED, "trace": trace, "body": {}}
                    if status_code >= 500 and attempt + 1 < max_attempts:
                        last_error = KIS_PAPER_TRANSPORT_ERROR
                        continue
                    if status_code >= 400:
                        return {"ok": False, "reason": KIS_PAPER_RESPONSE_ERROR, "trace": trace, "body": {}}
                    response_body = response.json()
                    if not isinstance(response_body, dict):
                        return {"ok": False, "reason": KIS_PAPER_RESPONSE_ERROR, "trace": trace, "body": {}}
                    if str(response_body.get("rt_cd", "0")) != "0":
                        trace["broker_message_code"] = str(response_body.get("msg_cd") or "")
                        return {
                            "ok": False,
                            "reason": KIS_PAPER_RESPONSE_ERROR,
                            "trace": trace,
                            "body": self.redaction_service.redact(response_body),
                        }
                    return {"ok": True, "reason": None, "trace": trace, "body": response_body}
                except httpx.TimeoutException:
                    last_error = KIS_PAPER_TIMEOUT
                    if attempt + 1 >= max_attempts:
                        break
                except httpx.TransportError:
                    last_error = KIS_PAPER_TRANSPORT_ERROR
                    if attempt + 1 >= max_attempts:
                        break
        finally:
            if close_client:
                client.close()
        trace = self._trace(
            operation=method,
            method=method,
            path=path,
            tr_id=tr_id,
            credentials=credentials,
            status_code=status_code,
            started=started,
            retry_count=max_attempts - 1,
            request_fields=body or params or {},
        )
        return {"ok": False, "reason": last_error, "trace": trace, "body": {}}

    def _send_request(
        self,
        client: Any,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: dict[str, str] | None,
        params: dict[str, str] | None,
    ) -> Any:
        if method.upper() == "POST":
            return client.post(url, headers=headers, json=body or {}, timeout=self.timeout_seconds)
        return client.get(url, headers=headers, params=params or {}, timeout=self.timeout_seconds)

    @staticmethod
    def _headers(credentials: KisPaperCredentials, tr_id: str) -> dict[str, str]:
        return {
            "authorization": f"Bearer {credentials.access_token}",
            "appkey": credentials.app_key,
            "appsecret": credentials.app_secret,
            "tr_id": tr_id,
            "custtype": KIS_CUSTOMER_TYPE,
            "content-type": "application/json; charset=utf-8",
        }

    def _gate_reasons(self, *, require_create: bool, require_kill_switch_off: bool) -> list[str]:
        reasons: list[str] = []
        if str(self.config.get("mode") or "disabled") != "paper":
            reasons.append("KIS_PAPER_MODE_REQUIRED")
        if not bool(self.config.get("enabled", False)):
            reasons.append("PAPER_TRADING_DISABLED")
        if require_create and not bool(self.config.get("configured_can_create", False)):
            reasons.append("PAPER_CREATE_DISABLED")
        if not bool(self.config.get("network_enabled", False)):
            reasons.append(KIS_PAPER_NETWORK_DISABLED)
        if not bool(self.config.get("broker_adapter_enabled", False)):
            reasons.append("KIS_PAPER_ADAPTER_DISABLED")
        if not bool(self.config.get("official_endpoint_confirmed", False)):
            reasons.append(CONFIRMATION_REQUIRED)
        if bool(self.config.get("preview_only", True)) and require_create:
            reasons.append("PAPER_PREVIEW_ONLY")
        if require_kill_switch_off and bool(self.config.get("kill_switch_enabled", True)):
            reasons.append("KILL_SWITCH_ACTIVE")
        if bool(self.config.get("live_order_enabled", False)) or bool(self.config.get("live_fallback_enabled", False)):
            reasons.append("KIS_LIVE_PATH_BLOCKED")
        if _real_order_enabled():
            reasons.append("ENABLE_REAL_ORDER_MUST_BE_FALSE")
        if not all(KisPaperCredentials.configured_fields().values()):
            reasons.append(KIS_PAPER_CREDENTIALS_MISSING)
        if _is_live_base_url(os.getenv(KIS_PAPER_BASE_URL_ENV, DEFAULT_KIS_PAPER_BASE_URL)):
            reasons.append(KIS_LIVE_BASE_URL_BLOCKED)
        return _merge_reason_codes(reasons)

    def _status_enabled(self, credentials: dict[str, bool]) -> bool:
        return not self._gate_reasons(require_create=False, require_kill_switch_off=False) and all(credentials.values())

    def _blocked_payload(
        self,
        status: str,
        reason_codes: list[str],
        *,
        operation: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "status": status,
            "paper_only": True,
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": False,
            "sync_performed": False,
            "order_cancelled": False,
            "reason": reason_codes[0] if reason_codes else KIS_PAPER_NETWORK_DISABLED,
            "reason_codes": _merge_reason_codes(reason_codes),
            "broker_trace": self.redaction_service.redact(
                {
                    "operation": operation,
                    "adapter": self.name,
                    "paper_only": True,
                    "network_call_performed": False,
                    "reason_codes": reason_codes,
                    "secrets_redacted": True,
                }
            ),
            **(extra or {}),
        }

    def _error_payload(self, status: str, response: dict[str, Any], *, operation: str) -> dict[str, Any]:
        reason = str(response.get("reason") or KIS_PAPER_RESPONSE_ERROR)
        return {
            "ok": False,
            "status": status,
            "paper_only": True,
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": bool(response.get("trace", {}).get("network_call_performed", True)),
            "sync_performed": False,
            "order_cancelled": False,
            "reason": reason,
            "reason_codes": [reason],
            "broker_trace": response.get("trace", {}),
        }

    def _trace(
        self,
        *,
        operation: str,
        method: str,
        path: str,
        tr_id: str,
        credentials: KisPaperCredentials,
        status_code: int | None,
        started: float,
        retry_count: int,
        request_fields: dict[str, Any],
    ) -> dict[str, Any]:
        parsed = urlparse(credentials.base_url)
        trace = {
            "operation": operation.lower(),
            "adapter": self.name,
            "mode": self.mode,
            "paper_only": True,
            "live_fallback_enabled": False,
            "method": method.upper(),
            "endpoint_path": path,
            "tr_id": tr_id,
            "base_host": parsed.hostname,
            "status_code": status_code,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "retry_count": retry_count,
            "rate_limited": False,
            "network_call_performed": True,
            "request_field_names": sorted(key for key in request_fields if key not in SENSITIVE_RESPONSE_KEYS),
            "secrets_redacted": True,
        }
        return self.redaction_service.redact(trace)


def encode_broker_order_key(
    *,
    krx_fwdg_ord_orgno: str,
    odno: str,
    qty: str,
    price: str,
    ord_dvsn: str,
    excg_id_dvsn_cd: str,
) -> str:
    return "|".join(
        [
            krx_fwdg_ord_orgno.strip(),
            odno.strip(),
            str(qty).strip(),
            str(price).strip(),
            ord_dvsn.strip(),
            excg_id_dvsn_cd.strip(),
        ]
    )


def decode_broker_order_key(value: str) -> dict[str, str]:
    parts = value.split("|")
    if len(parts) != 6 or not parts[0].strip() or not parts[1].strip():
        raise KisPaperBrokerRequestError("KIS_PAPER_CANCEL_ORDER_KEY_REQUIRED")
    return {
        "krx_fwdg_ord_orgno": parts[0].strip(),
        "odno": parts[1].strip(),
        "qty": parts[2].strip() or "0",
        "price": parts[3].strip() or "0",
        "ord_dvsn": parts[4].strip() or "00",
        "excg_id_dvsn_cd": parts[5].strip() or "KRX",
    }


def _order_from_daily_row(row: dict[str, Any]) -> dict[str, Any] | None:
    order_no = _first_value(row, "odno", "ODNO", "orgn_odno", "ORGN_ODNO")
    org_no = _first_value(row, "ord_gno_brno", "ORD_GNO_BRNO", "krx_fwdg_ord_orgno", "KRX_FWDG_ORD_ORGNO")
    symbol = _first_value(row, "pdno", "PDNO")
    if not order_no or not org_no or not symbol:
        return None
    qty = _to_int(_first_value(row, "ord_qty", "ORD_QTY"))
    filled_qty = _to_int(_first_value(row, "tot_ccld_qty", "TOT_CCLD_QTY", "ccld_qty", "CCLD_QTY"))
    remaining_qty = max(qty - filled_qty, 0)
    side_code = _first_value(row, "sll_buy_dvsn_cd", "SLL_BUY_DVSN_CD")
    side_name = _first_value(row, "sll_buy_dvsn_name", "SLL_BUY_DVSN_NAME")
    side = "sell" if side_code == "01" or "매도" in side_name else "buy" if side_code == "02" or "매수" in side_name else ""
    price = _to_float(_first_value(row, "ord_unpr", "ORD_UNPR"))
    status = "submitted" if remaining_qty else "filled" if filled_qty else "unknown"
    order_key = encode_broker_order_key(
        krx_fwdg_ord_orgno=org_no,
        odno=order_no,
        qty=str(qty),
        price=_price_to_kis_string(price),
        ord_dvsn=_first_value(row, "ord_dvsn_cd", "ORD_DVSN_CD") or "00",
        excg_id_dvsn_cd=_first_value(row, "excg_id_dvsn_cd", "EXCG_ID_DVSN_CD") or "KRX",
    )
    return {
        "broker_order_id": order_key,
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "filled_qty": filled_qty,
        "remaining_qty": remaining_qty,
        "limit_price": price,
        "status": status,
        "broker_order_status": status,
        "broker_synced_at": datetime.now(UTC).isoformat(),
    }


def _fill_from_daily_row(row: dict[str, Any]) -> dict[str, Any] | None:
    filled_qty = _to_int(_first_value(row, "tot_ccld_qty", "TOT_CCLD_QTY", "ccld_qty", "CCLD_QTY"))
    if filled_qty <= 0:
        return None
    order = _order_from_daily_row(row)
    if order is None:
        return None
    fill_price = _to_float(_first_value(row, "avg_prvs", "AVG_PRVS", "ord_unpr", "ORD_UNPR")) or 0.0
    return {
        "broker_fill_id": f"{order['broker_order_id']}|fill",
        "broker_order_id": order["broker_order_id"],
        "symbol": order["symbol"],
        "side": order["side"],
        "qty": filled_qty,
        "price": fill_price,
        "fill_ts": datetime.now(UTC).isoformat(),
        "status": "filled",
    }


def _position_from_balance_row(row: dict[str, Any]) -> dict[str, Any] | None:
    symbol = _first_value(row, "pdno", "PDNO")
    if not symbol:
        return None
    qty = _to_int(_first_value(row, "hldg_qty", "HLDG_QTY"))
    avg_price = _to_float(_first_value(row, "pchs_avg_pric", "PCHS_AVG_PRIC")) or 0.0
    last_price = _to_float(_first_value(row, "prpr", "PRPR"))
    market_value = _to_float(_first_value(row, "evlu_amt", "EVLU_AMT"))
    return {
        "symbol": symbol,
        "qty": qty,
        "avg_price": avg_price,
        "last_price": last_price,
        "market_value": market_value,
        "unrealized_pnl": _to_float(_first_value(row, "evlu_pfls_amt", "EVLU_PFLS_AMT")),
        "broker_position_key": f"kis_paper|{symbol}",
        "account_alias": "kis_paper",
        "broker_synced_at": datetime.now(UTC).isoformat(),
    }


def _portfolio_snapshot_from_summary(row: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(UTC)
    cash_balance = _to_float(_first_value(row, "dnca_tot_amt", "DNCA_TOT_AMT")) or 0.0
    market_value = _to_float(
        _first_value(row, "scts_evlu_amt", "SCTS_EVLU_AMT", "evlu_amt_smtl_amt", "EVLU_AMT_SMTL_AMT")
    ) or 0.0
    total_equity = _to_float(_first_value(row, "tot_evlu_amt", "TOT_EVLU_AMT", "nass_amt", "NASS_AMT"))
    return {
        "snapshot_id": f"kis-paper-sync-{now.strftime('%Y%m%d%H%M%S')}",
        "snapshot_ts": now.isoformat(),
        "account_alias": "kis_paper",
        "cash_balance": cash_balance,
        "buying_power": cash_balance,
        "market_value": market_value,
        "total_equity": total_equity if total_equity is not None else cash_balance + market_value,
        "unrealized_pnl": _to_float(_first_value(row, "evlu_pfls_smtl_amt", "EVLU_PFLS_SMTL_AMT")) or 0.0,
        "realized_pnl": 0.0,
        "source": "kis_paper",
        "status": "synced",
    }


def _exchange_from_metadata(metadata: dict[str, Any]) -> str:
    value = str(metadata.get("excg_id_dvsn_cd") or metadata.get("venue") or "KRX").strip().upper()
    return value if value in {"KRX", "NXT", "SOR"} else "KRX"


def _price_to_kis_string(value: float | int | str | None) -> str:
    if value is None:
        return "0"
    parsed = _to_float(value)
    return "0" if parsed is None else str(int(parsed))


def _first_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    return {}


def _first_value(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _to_int(value: Any) -> int:
    parsed = _to_float(value)
    return int(parsed) if parsed is not None else 0


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _expanded_scopes(scope: str) -> list[str]:
    if scope == "all":
        return ["orders", "fills", "positions", "portfolio"]
    return [scope]


def _merge_reason_codes(codes: list[str]) -> list[str]:
    merged: list[str] = []
    for code in codes:
        if code not in merged:
            merged.append(code)
    return merged


def _real_order_enabled() -> bool:
    return os.getenv(ENABLE_REAL_ORDER_ENV, "false").strip().lower() in {"1", "true", "yes", "on"}


def _is_live_base_url(base_url: str) -> bool:
    parsed = urlparse(base_url)
    return (parsed.hostname or "").lower() == KIS_LIVE_HOST
