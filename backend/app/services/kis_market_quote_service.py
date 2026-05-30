from __future__ import annotations

import os
from datetime import UTC, date, datetime
from typing import Any

from backend.app.services.kis_http_client import KisHttpClient
from backend.app.services.kis_token_manager import (
    DEFAULT_KIS_PAPER_BASE_URL,
    ENABLE_REAL_ORDER_ENV,
    KIS_ACCESS_TOKEN_ENV,
    KIS_APP_KEY_ENV,
    KIS_APP_SECRET_ENV,
    KIS_ENV_ENV,
    KIS_PAPER_BASE_URL_ENV,
    KisTokenManager,
)

KIS_MARKET_QUOTE_ENABLED_ENV = "KIS_MARKET_QUOTE_ENABLED"
KIS_DOMESTIC_QUOTE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
KIS_DOMESTIC_QUOTE_TR_ID = "FHKST01010100"


class KisMarketQuoteService:
    """KIS paper 현재가 조회를 명시 gate 뒤에서 실행하고 실패 사유를 fallback에 넘긴다."""

    def __init__(self, *, http_client: Any | None = None) -> None:
        self.http_client = http_client

    def fetch_quote(self, symbol: str) -> dict[str, Any]:
        """국내주식 현재가를 조회하되 gate가 닫혀 있으면 네트워크 없이 blocked를 반환한다."""
        normalized = symbol.strip().upper()
        reason_codes = self._gate_reasons(normalized)
        if reason_codes:
            return self._blocked_payload(normalized, reason_codes)
        base_url = os.getenv(KIS_PAPER_BASE_URL_ENV, DEFAULT_KIS_PAPER_BASE_URL).strip() or DEFAULT_KIS_PAPER_BASE_URL
        client = KisHttpClient(http_client=self.http_client, max_retries=0)
        result = client.request(
            "GET",
            f"{base_url.rstrip('/')}{KIS_DOMESTIC_QUOTE_PATH}",
            headers={
                "authorization": f"Bearer {os.getenv(KIS_ACCESS_TOKEN_ENV, '').strip()}",
                "appkey": os.getenv(KIS_APP_KEY_ENV, "").strip(),
                "appsecret": os.getenv(KIS_APP_SECRET_ENV, "").strip(),
                "tr_id": KIS_DOMESTIC_QUOTE_TR_ID,
                "custtype": "P",
            },
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": normalized,
            },
            operation="kis_market_quote",
            tr_id=KIS_DOMESTIC_QUOTE_TR_ID,
        )
        if not result.ok:
            return {
                "ok": False,
                "status": "quote_failed",
                "symbol": normalized,
                "quote": None,
                "reason_codes": [str(result.reason or "KIS_MARKET_QUOTE_FAILED")],
                "network_call_performed": bool(result.trace.get("network_call_performed")),
                "trace": result.trace,
            }
        quote = self._parse_quote(normalized, result.body)
        if quote is None:
            return {
                "ok": False,
                "status": "quote_parse_failed",
                "symbol": normalized,
                "quote": None,
                "reason_codes": ["KIS_MARKET_QUOTE_PARSE_FAILED"],
                "network_call_performed": True,
                "trace": result.trace,
            }
        return {
            "ok": True,
            "status": "quote_loaded",
            "symbol": normalized,
            "quote": quote,
            "reason_codes": [],
            "network_call_performed": True,
            "trace": result.trace,
        }

    @classmethod
    def _gate_reasons(cls, symbol: str) -> list[str]:
        reasons: list[str] = []
        if not symbol:
            reasons.append("KIS_MARKET_QUOTE_SYMBOL_REQUIRED")
        if not _env_true(KIS_MARKET_QUOTE_ENABLED_ENV):
            reasons.append("KIS_MARKET_QUOTE_DISABLED")
        if os.getenv(KIS_ENV_ENV, "").strip().lower() != "paper":
            reasons.append("KIS_ENV_PAPER_REQUIRED")
        for env_name, reason in (
            (KIS_APP_KEY_ENV, "KIS_APP_KEY_REQUIRED"),
            (KIS_APP_SECRET_ENV, "KIS_APP_SECRET_REQUIRED"),
            (KIS_ACCESS_TOKEN_ENV, "KIS_ACCESS_TOKEN_REQUIRED"),
        ):
            if not KisTokenManager.env_configured(env_name):
                reasons.append(reason)
        base_url = os.getenv(KIS_PAPER_BASE_URL_ENV, DEFAULT_KIS_PAPER_BASE_URL).strip() or DEFAULT_KIS_PAPER_BASE_URL
        if "openapi.koreainvestment.com" in base_url.lower() and "openapivts" not in base_url.lower():
            reasons.append("KIS_LIVE_BASE_URL_BLOCKED")
        if _env_true(ENABLE_REAL_ORDER_ENV):
            reasons.append("ENABLE_REAL_ORDER_MUST_BE_FALSE")
        return _merge_reason_codes(reasons)

    @staticmethod
    def _blocked_payload(symbol: str, reason_codes: list[str]) -> dict[str, Any]:
        return {
            "ok": False,
            "status": "quote_blocked",
            "symbol": symbol,
            "quote": None,
            "reason_codes": reason_codes,
            "network_call_performed": False,
        }

    @classmethod
    def _parse_quote(cls, symbol: str, body: dict[str, Any]) -> dict[str, Any] | None:
        output = body.get("output")
        if not isinstance(output, dict):
            output = body
        current_price = _float_value(output, "stck_prpr", "prpr", "last", "current_price")
        if current_price is None:
            return None
        previous_change = _float_value(output, "prdy_vrss", "change")
        change_pct = _float_value(output, "prdy_ctrt", "change_pct")
        if change_pct is not None and abs(change_pct) > 1:
            change_pct = change_pct / 100
        return {
            "available": True,
            "symbol": symbol,
            "trade_date": _date_value(output, "stck_bsop_date", "trade_date"),
            "current_price": current_price,
            "open": _float_value(output, "stck_oprc", "open"),
            "high": _float_value(output, "stck_hgpr", "high"),
            "low": _float_value(output, "stck_lwpr", "low"),
            "close": current_price,
            "change": previous_change,
            "change_pct": change_pct,
            "volume": _int_value(output, "acml_vol", "volume"),
            "turnover_value": _float_value(output, "acml_tr_pbmn", "turnover_value"),
            "source": "kis_paper_quote",
            "quote_ts": datetime.now(UTC).isoformat(),
        }


def _float_value(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        raw = payload.get(key)
        if raw in {None, ""}:
            continue
        try:
            return float(str(raw).replace(",", ""))
        except (TypeError, ValueError):
            continue
    return None


def _int_value(payload: dict[str, Any], *keys: str) -> int | None:
    value = _float_value(payload, *keys)
    return None if value is None else int(value)


def _date_value(payload: dict[str, Any], *keys: str) -> date | None:
    for key in keys:
        raw = payload.get(key)
        if raw in {None, ""}:
            continue
        text = str(raw).strip()
        for fmt in ("%Y%m%d", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                pass
    return None


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _merge_reason_codes(codes: list[str]) -> list[str]:
    merged: list[str] = []
    for code in codes:
        if code not in merged:
            merged.append(code)
    return merged
