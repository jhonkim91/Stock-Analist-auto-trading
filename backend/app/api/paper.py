from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.api.paper_execution_helpers import paper_only_execution_response
from backend.app.models.schemas import (
    PaperOrderCancelRequest,
    PaperOrderPreviewRequest,
    PaperOrderSubmitRequest,
    PaperBotRunRequest,
    PaperSyncRequest,
)
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


@router.post("/orders/submit")
def submit_paper_order(payload: PaperOrderSubmitRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    result = PaperTradingService(db).submit_order(
        symbol=payload.symbol,
        side=payload.side,
        qty=payload.qty,
        limit_price=payload.limit_price,
        stop_price=payload.stop_price,
        strategy_tag=payload.strategy_tag,
        venue=payload.venue,
        as_of=payload.as_of,
        confirm=payload.confirm,
        idempotency_key=payload.idempotency_key,
    )
    return paper_only_execution_response(result, operation="paper_order_submit")


@router.post("/orders/cancel")
def cancel_paper_order(payload: PaperOrderCancelRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    result = PaperTradingService(db).cancel_order(
        paper_order_id=payload.paper_order_id,
        confirm=payload.confirm,
        idempotency_key=payload.idempotency_key,
    )
    return paper_only_execution_response(result, operation="paper_order_cancel")


@router.get("/orders")
def list_paper_orders(status: str | None = None, db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).list_orders(status=status)


@router.get("/fills")
def list_paper_fills(symbol: str | None = None, db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).list_fills(symbol=symbol)


@router.get("/positions")
def list_paper_positions(symbol: str | None = None, db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).list_positions(symbol=symbol)


@router.get("/portfolio")
def paper_portfolio(db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).portfolio()


@router.post("/sync")
def sync_paper(payload: PaperSyncRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).sync(scope=payload.scope)


@router.get("/bot/status")
def paper_bot_status(db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).bot_status()


@router.post("/bot/run")
def run_paper_bot(payload: PaperBotRunRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).run_bot_once(auto_submit=payload.auto_submit)
