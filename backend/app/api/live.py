from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.brokers.base import BrokerOrderRequest
from backend.app.core.database import get_db
from backend.app.services.kis_live_broker_adapter import KisLiveBrokerAdapter
from backend.app.services.live_order_safety_service import LiveOrderSafetyService

router = APIRouter(tags=["live"])


class LiveOrderRouteRequest(BaseModel):
    """실계좌 주문 route scaffold의 요청 DTO다."""

    symbol: str = ""
    side: str = "buy"
    qty: int = 0
    limit_price: float | None = None
    stop_price: float | None = None
    idempotency_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LiveOrderCancelRouteRequest(BaseModel):
    """실계좌 주문 취소 route scaffold의 요청 DTO다."""

    broker_order_id: str = ""
    confirm: bool = False


@router.get("/api/live/status")
def live_route_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    """실계좌 public route scaffold 상태를 network 없이 반환한다."""
    adapter = _adapter(db)
    return _route_payload(
        {
            "ok": False,
            "status": "live_disabled",
            "operation": "live_route_status",
            "adapter": adapter.status(),
            "live_order_safety": adapter.safety_service.preflight(),
        },
        route="/api/live/status",
    )


@router.get("/api/kis/orders/status")
def kis_live_order_route_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    """KIS live order route scaffold 상태를 network 없이 반환한다."""
    adapter = _adapter(db)
    return _route_payload(
        {
            "ok": False,
            "status": "live_disabled",
            "operation": "kis_live_order_route_status",
            "adapter": adapter.status(),
            "live_order_safety": adapter.safety_service.preflight(),
        },
        route="/api/kis/orders/status",
    )


@router.get("/api/kis/orders")
def list_kis_live_orders(status: str | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    """실계좌 주문 목록 route를 등록하되 조회 실행은 disabled payload로 차단한다."""
    return _route_payload(_adapter(db).list_orders(status=status), route="/api/kis/orders")


@router.post("/api/kis/orders/preview")
def preview_kis_live_order(payload: LiveOrderRouteRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """실계좌 주문 후보를 안전장치로 평가하지만 network/order 생성은 하지 않는다."""
    result = _adapter(db).preview_order(_order_request(payload))
    return _route_payload(result, route="/api/kis/orders/preview")


@router.post("/api/kis/orders/submit")
def submit_kis_live_order(payload: LiveOrderRouteRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """실계좌 submit route를 등록하되 실행은 disabled payload로 차단한다."""
    result = _adapter(db).submit_order(_order_request(payload))
    return _route_payload(result, route="/api/kis/orders/submit")


@router.post("/api/kis/orders/cancel")
def cancel_kis_live_order(payload: LiveOrderCancelRouteRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """실계좌 cancel route를 등록하되 실행은 disabled payload로 차단한다."""
    result = _adapter(db).cancel_order(
        broker_order_id=payload.broker_order_id,
        confirm=payload.confirm,
    )
    return _route_payload(result, route="/api/kis/orders/cancel")


def _adapter(db: Session) -> KisLiveBrokerAdapter:
    return KisLiveBrokerAdapter(safety_service=LiveOrderSafetyService(db=db))


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


def _route_payload(payload: dict[str, Any], *, route: str) -> dict[str, Any]:
    payload.update(
        {
            "public_route_scaffold": True,
            "route_registered": True,
            "route": route,
            "route_network_enabled": False,
            "live_submit_blocked": True,
            "live_cancel_blocked": True,
            "live_order_created": False,
            "network_call_performed": False,
            "adapter_network_call_performed": False,
            "endpoint_called": False,
            "secrets_redacted": True,
        }
    )
    return payload
