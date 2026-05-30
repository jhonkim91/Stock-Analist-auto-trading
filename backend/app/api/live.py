"""KIS 실전(라이브) 주문 라우트.

⚠️ 게이트(LIVE_TRADING_ENABLED + LIVE_ORDER_SUBMIT_ENABLED + ENABLE_REAL_ORDER 등)가
모두 켜지고 실계좌 자격증명이 설정되어야만 실제 주문이 KIS 실전 API로 전송된다.
그 전에는 사유 코드와 함께 차단된다.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.app.brokers.base import BrokerOrderRequest
from backend.app.services.kis_live_order_executor import KisLiveOrderExecutor

router = APIRouter(tags=["live"])


class LiveOrderRouteRequest(BaseModel):
    """실계좌 주문 요청 DTO."""

    symbol: str = ""
    side: str = "buy"
    qty: int = 0
    limit_price: float | None = None
    stop_price: float | None = None
    confirm: bool = False
    idempotency_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LiveOrderCancelRouteRequest(BaseModel):
    """실계좌 주문 취소 요청 DTO."""

    broker_order_id: str = ""
    confirm: bool = False


def _executor() -> KisLiveOrderExecutor:
    return KisLiveOrderExecutor()


def _order_request(payload: LiveOrderRouteRequest) -> BrokerOrderRequest:
    return BrokerOrderRequest(
        symbol=payload.symbol,
        side=payload.side,
        qty=payload.qty,
        limit_price=payload.limit_price,
        stop_price=payload.stop_price,
        idempotency_key=payload.idempotency_key,
        metadata=payload.metadata,
    )


@router.get("/api/live/status")
def live_route_status() -> dict[str, Any]:
    """실전 주문 게이트 상태를 네트워크 없이 반환한다."""
    return {"route": "/api/live/status", **_executor().gate_status()}


@router.get("/api/kis/orders/status")
def kis_live_order_route_status() -> dict[str, Any]:
    """KIS 실전 주문 게이트 상태를 네트워크 없이 반환한다."""
    return {"route": "/api/kis/orders/status", **_executor().gate_status()}


@router.post("/api/kis/orders/preview")
def preview_kis_live_order(payload: LiveOrderRouteRequest) -> dict[str, Any]:
    """실전 주문 후보를 게이트 기준으로만 평가한다(네트워크/주문 생성 없음)."""
    gate = _executor().gate_status()
    return {
        "ok": gate["can_submit"],
        "status": "preview" if gate["can_submit"] else "preview_blocked",
        "operation": "preview_order",
        "mode": "live",
        "network_call_performed": False,
        "live_order_created": False,
        "symbol": payload.symbol,
        "side": payload.side,
        "qty": payload.qty,
        "limit_price": payload.limit_price,
        "gate": gate,
        "reason_codes": gate["reason_codes"],
        "secrets_redacted": True,
    }


@router.post("/api/kis/orders/submit")
def submit_kis_live_order(payload: LiveOrderRouteRequest) -> dict[str, Any]:
    """게이트가 모두 통과하면 KIS 실전 API로 실제 주문을 제출한다."""
    return _executor().submit_order(_order_request(payload), confirm=payload.confirm)


@router.post("/api/kis/orders/cancel")
def cancel_kis_live_order(payload: LiveOrderCancelRouteRequest) -> dict[str, Any]:
    """게이트가 모두 통과하면 KIS 실전 API로 주문을 취소한다."""
    return _executor().cancel_order(broker_order_id=payload.broker_order_id, confirm=payload.confirm)
