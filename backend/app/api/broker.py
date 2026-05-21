from __future__ import annotations

from fastapi import APIRouter

from backend.app.models.schemas import BrokerPreviewRequest
from backend.app.services.broker_service import BrokerService

router = APIRouter(prefix="/api/broker", tags=["broker"])


@router.get("/status")
def broker_status() -> dict[str, object]:
    return BrokerService().status()


@router.post("/orders/preview")
def preview_order(payload: BrokerPreviewRequest) -> dict[str, object]:
    return BrokerService().preview_order(
        symbol=payload.symbol,
        side=payload.side,
        qty=payload.qty,
        limit_price=payload.limit_price,
        stop_price=payload.stop_price,
        strategy_tag=payload.strategy_tag,
    )
