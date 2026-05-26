from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.schemas import PaperOrderPreviewRequest
from backend.app.services.paper_trading_service import PaperTradingService

router = APIRouter(prefix="/api/paper", tags=["paper"])


@router.get("/status")
def paper_status(db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).status()


@router.post("/orders/preview")
def preview_paper_order(payload: PaperOrderPreviewRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).preview_order(
        symbol=payload.symbol,
        side=payload.side,
        qty=payload.qty,
        limit_price=payload.limit_price,
        stop_price=payload.stop_price,
        strategy_tag=payload.strategy_tag,
        venue=payload.venue,
        as_of=payload.as_of,
    )
