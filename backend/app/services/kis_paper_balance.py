from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from backend.app.services.token_manager import KIS_APP_KEY_ENV, KIS_APP_SECRET_ENV, KisTokenManager

KIS_ACCESS_TOKEN_ENV = "KIS_ACCESS_TOKEN"
KIS_ACCOUNT_NO_ENV = "KIS_ACCOUNT_NO"
KIS_PRODUCT_CODE_ENV = "KIS_PRODUCT_CODE"
KIS_PAPER_BASE_URL_ENV = "KIS_PAPER_BASE_URL"
ENABLE_REAL_ORDER_ENV = "ENABLE_REAL_ORDER"

DEFAULT_KIS_PAPER_BASE_URL = "https://openapivts.koreainvestment.com:29443"
KIS_PAPER_BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
KIS_PAPER_BALANCE_TR_ID = "VTTC8434R"
KIS_CUSTOMER_TYPE = "P"
KIS_LIVE_HOST = "openapi.koreainvestment.com"


class KisPaperBalanceConfigError(RuntimeError):
    """KIS 모의투자 잔고조회 설정이 안전 조건을 만족하지 못할 때 발생한다."""


class KisPaperBalanceRequestError(RuntimeError):
    """KIS 모의투자 잔고조회 호출이 실패했을 때 secret 없이 발생한다."""


@dataclass(frozen=True)
class KisPaperBalanceCredentials:
    app_key: str = field(repr=False)
    app_secret: str = field(repr=False)
    access_token: str = field(repr=False)
    account_no: str = field(repr=False)
    product_code: str = field(repr=False)
    base_url: str = DEFAULT_KIS_PAPER_BASE_URL
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "KisPaperBalanceCredentials":
        """잔고조회에 필요한 값만 env에서 읽고 raw 값은 반환 payload에 싣지 않는다."""
        credentials = cls(
            app_key=os.getenv(KIS_APP_KEY_ENV, "").strip(),
            app_secret=os.getenv(KIS_APP_SECRET_ENV, "").strip(),
            access_token=os.getenv(KIS_ACCESS_TOKEN_ENV, "").strip(),
            account_no=os.getenv(KIS_ACCOUNT_NO_ENV, "").strip(),
            product_code=os.getenv(KIS_PRODUCT_CODE_ENV, "").strip(),
            base_url=os.getenv(KIS_PAPER_BASE_URL_ENV, DEFAULT_KIS_PAPER_BASE_URL).strip()
            or DEFAULT_KIS_PAPER_BASE_URL,
        )
        missing = [
            name
            for name, configured in cls.configured_fields().items()
            if name in {"app_key_configured", "app_secret_configured", "access_token_configured"}
            and not configured
        ]
        if not cls._is_configured_value(credentials.account_no):
            missing.append("account_configured")
        if not cls._is_configured_value(credentials.product_code):
            missing.append("product_code_configured")
        if missing:
            raise KisPaperBalanceConfigError("KIS_PAPER_BALANCE_ENV_MISSING")
        if _is_live_base_url(credentials.base_url):
            raise KisPaperBalanceConfigError("KIS_LIVE_BASE_URL_BLOCKED")
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


class KisPaperBalanceClient:
    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self.http_client = http_client

    def fetch_balance(self) -> dict[str, Any]:
        """KIS 모의투자 주식잔고조회 API를 read-only로 호출하고 표준 payload로 변환한다."""
        credentials = KisPaperBalanceCredentials.from_env()
        request = self._request_payload(credentials)
        close_client = self.http_client is None
        client = self.http_client or httpx.Client(timeout=credentials.timeout_seconds)
        try:
            response = client.get(
                request["url"],
                headers=request["headers"],
                params=request["params"],
                timeout=credentials.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        except Exception as exc:
            raise KisPaperBalanceRequestError("KIS_PAPER_BALANCE_REQUEST_FAILED") from exc
        finally:
            if close_client:
                client.close()
        return map_kis_paper_balance_response(body)

    @staticmethod
    def _request_payload(credentials: KisPaperBalanceCredentials) -> dict[str, Any]:
        return {
            "url": f"{credentials.base_url.rstrip('/')}{KIS_PAPER_BALANCE_PATH}",
            "headers": {
                "authorization": f"Bearer {credentials.access_token}",
                "appkey": credentials.app_key,
                "appsecret": credentials.app_secret,
                "tr_id": KIS_PAPER_BALANCE_TR_ID,
                "custtype": KIS_CUSTOMER_TYPE,
            },
            "params": {
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
            },
        }


def map_kis_paper_balance_response(payload: Any) -> dict[str, Any]:
    """KIS output1/output2 응답을 `/api/paper/portfolio` 호환 payload로 매핑한다."""
    if not isinstance(payload, dict):
        raise KisPaperBalanceRequestError("KIS_PAPER_BALANCE_RESPONSE_INVALID")
    if str(payload.get("rt_cd", "0")) != "0":
        raise KisPaperBalanceRequestError("KIS_PAPER_BALANCE_RESPONSE_ERROR")

    raw_holdings = payload.get("output1") or []
    if not isinstance(raw_holdings, list):
        raise KisPaperBalanceRequestError("KIS_PAPER_BALANCE_OUTPUT1_INVALID")
    raw_summary = _first_mapping(payload.get("output2"))

    holdings = [_holding_payload(row) for row in raw_holdings if isinstance(row, dict)]
    account_summary = _summary_payload(raw_summary)
    now = datetime.now(UTC)
    snapshot = _snapshot_payload(account_summary, now)
    positions_summary = _positions_summary(holdings)
    return {
        "ok": True,
        "source": "kis_paper_balance",
        "snapshot": snapshot,
        "positions_summary": positions_summary,
        "holdings": holdings,
        "account_summary": account_summary,
        "kis_balance": {
            "enabled": True,
            "status": "ok",
            "endpoint_path": KIS_PAPER_BALANCE_PATH,
            "tr_id": KIS_PAPER_BALANCE_TR_ID,
            "holdings_count": len(holdings),
            "secrets_redacted": True,
            "read_only": True,
            "real_order_enabled": False,
        },
        "reason": None,
        "live_order_created": False,
        "broker_order_created": False,
        "network_call_performed": True,
    }


def kis_real_order_enabled() -> bool:
    value = os.getenv(ENABLE_REAL_ORDER_ENV, "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _is_live_base_url(base_url: str) -> bool:
    parsed = urlparse(base_url)
    return (parsed.hostname or "").lower() == KIS_LIVE_HOST


def _first_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    return {}


def _holding_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": str(row.get("pdno") or "").strip(),
        "name": str(row.get("prdt_name") or "").strip(),
        "quantity": _to_int(row.get("hldg_qty")),
        "orderable_quantity": _to_int(row.get("ord_psbl_qty")),
        "average_price": _to_float(row.get("pchs_avg_pric")),
        "purchase_amount": _to_float(row.get("pchs_amt")),
        "current_price": _to_float(row.get("prpr")),
        "evaluation_amount": _to_float(row.get("evlu_amt")),
        "profit_loss_amount": _to_float(row.get("evlu_pfls_amt")),
        "profit_loss_rate": _to_float(row.get("evlu_pfls_rt")),
    }


def _summary_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "cash_total": _to_float(row.get("dnca_tot_amt")),
        "securities_evaluation_amount": _to_float(row.get("scts_evlu_amt")),
        "total_evaluation_amount": _to_float(row.get("tot_evlu_amt")),
        "net_asset_amount": _to_float(row.get("nass_amt")),
        "total_purchase_amount": _to_float(row.get("pchs_amt_smtl_amt")),
        "total_stock_evaluation_amount": _to_float(row.get("evlu_amt_smtl_amt")),
        "total_profit_loss_amount": _to_float(row.get("evlu_pfls_smtl_amt")),
        "previous_total_asset_amount": _to_float(row.get("bfdy_tot_asst_evlu_amt")),
        "asset_change_amount": _to_float(row.get("asst_icdc_amt")),
        "asset_change_rate": _to_float(row.get("asst_icdc_erng_rt")),
    }


def _snapshot_payload(summary: dict[str, float | None], now: datetime) -> dict[str, Any]:
    cash_total = _number_or_zero(summary.get("cash_total"))
    market_value = _number_or_zero(
        summary.get("securities_evaluation_amount") or summary.get("total_stock_evaluation_amount")
    )
    total_equity = _number_or_zero(summary.get("total_evaluation_amount") or summary.get("net_asset_amount"))
    if total_equity == 0.0:
        total_equity = cash_total + market_value
    return {
        "snapshot_id": f"kis-paper-balance-{now.strftime('%Y%m%d%H%M%S')}",
        "snapshot_ts": now.isoformat(),
        "account_alias": "kis_paper",
        "cash_balance": cash_total,
        "buying_power": cash_total,
        "market_value": market_value,
        "total_equity": total_equity,
        "unrealized_pnl": _number_or_zero(summary.get("total_profit_loss_amount")),
        "realized_pnl": 0.0,
        "source": "kis_paper_balance",
        "status": "ok",
        "created_at": now.isoformat(),
    }


def _positions_summary(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "source": "kis_paper_balance",
        "count": len(holdings),
        "total_qty": sum(_to_int(holding.get("quantity")) for holding in holdings),
        "market_value": sum(_number_or_zero(holding.get("evaluation_amount")) for holding in holdings),
        "unrealized_pnl": sum(_number_or_zero(holding.get("profit_loss_amount")) for holding in holdings),
    }


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


def _number_or_zero(value: Any) -> float:
    parsed = _to_float(value)
    return parsed if parsed is not None else 0.0
