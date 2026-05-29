from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.api.paper_execution_helpers import paper_only_execution_response
from backend.app.models.schemas import (
    PaperOrderCancelRequest,
    PaperOrderPreviewRequest,
    PaperOrderSubmitRequest,
    PaperBotRunRequest,
    PaperSyncRequest,
    KisWebSocketApprovalRequest,
    KisWebSocketSmokeRequest,
    KisWebSocketSubscriptionPreviewRequest,
)
from backend.app.services.kis_paper_websocket_service import KisPaperWebSocketService
from backend.app.services.paper_trading_service import PaperTradingService

router = APIRouter(prefix="/api/paper", tags=["paper"])


class PaperFillSimulationRequest(BaseModel):
    """local paper fill simulator 요청 DTO다."""

    paper_order_id: str
    fill_price: float
    qty: int | None = Field(default=None, ge=1)
    confirm: bool = False
    idempotency_key: str | None = None
    commission: float = 0.0
    slippage_bps: float = 0.0


class PaperRiskExitCheckRequest(BaseModel):
    """paper 스탑로스/트레일링 스탑 실행 요청 DTO다."""

    symbol: str
    current_price: float
    stop_price: float | None = None
    trailing_high_price: float | None = None
    trailing_stop_pct: float | None = None
    strategy_tag: str | None = None
    confirm: bool = False
    idempotency_key: str | None = None


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


@router.post("/orders")
def create_paper_order(payload: PaperOrderSubmitRequest, db: Session = Depends(get_db)) -> dict[str, object]:
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


@router.post("/orders/{paper_order_id}/cancel")
def cancel_paper_order_by_id(
    paper_order_id: str,
    payload: PaperOrderCancelRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    result = PaperTradingService(db).cancel_order(
        paper_order_id=paper_order_id,
        confirm=payload.confirm,
        idempotency_key=payload.idempotency_key,
    )
    return paper_only_execution_response(result, operation="paper_order_cancel")


@router.get("/orders")
def list_paper_orders(status: str | None = None, db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).list_orders(status=status)


@router.get("/orders/open")
def list_open_paper_orders(db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).list_open_orders()


@router.get("/orders/{paper_order_id}")
def get_paper_order(paper_order_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).get_order(paper_order_id=paper_order_id)


@router.post("/fill-simulator/run")
def run_paper_fill_simulator(payload: PaperFillSimulationRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).simulate_fill(
        paper_order_id=payload.paper_order_id,
        fill_price=payload.fill_price,
        qty=payload.qty,
        confirm=payload.confirm,
        idempotency_key=payload.idempotency_key,
        commission=payload.commission,
        slippage_bps=payload.slippage_bps,
    )


@router.get("/fills")
def list_paper_fills(symbol: str | None = None, db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).list_fills(symbol=symbol)


@router.get("/positions")
def list_paper_positions(symbol: str | None = None, db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).list_positions(symbol=symbol)


@router.get("/portfolio")
def paper_portfolio(db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).portfolio()


@router.get("/account")
def paper_account(db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).account()


@router.post("/sync")
def sync_paper(payload: PaperSyncRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).sync(scope=payload.scope)


@router.get("/realtime/status")
def paper_realtime_status(db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).realtime_status()


@router.post("/risk/exit-check")
def check_paper_risk_exit(payload: PaperRiskExitCheckRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).check_risk_exit(
        symbol=payload.symbol,
        current_price=payload.current_price,
        stop_price=payload.stop_price,
        trailing_high_price=payload.trailing_high_price,
        trailing_stop_pct=payload.trailing_stop_pct,
        strategy_tag=payload.strategy_tag,
        confirm=payload.confirm,
        idempotency_key=payload.idempotency_key,
    )


@router.get("/realtime/websocket/status")
def paper_websocket_status(db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).realtime_status()["websocket"]


@router.post("/realtime/websocket/approval")
def issue_paper_websocket_approval(payload: KisWebSocketApprovalRequest) -> dict[str, object]:
    return KisPaperWebSocketService().issue_approval_key(
        confirm=payload.confirm,
        install_to_process_env=payload.install_to_process_env,
    )


@router.post("/realtime/websocket/subscription/preview")
def preview_paper_websocket_subscription(payload: KisWebSocketSubscriptionPreviewRequest) -> dict[str, object]:
    return KisPaperWebSocketService().subscription_preview(
        symbol=payload.symbol,
        kind=payload.kind,
        market=payload.market,
        exchange=payload.exchange,
        subscribe=payload.subscribe,
    )


@router.post("/realtime/websocket/smoke")
def smoke_paper_websocket(payload: KisWebSocketSmokeRequest) -> dict[str, object]:
    return KisPaperWebSocketService().bounded_connect_smoke(
        symbol=payload.symbol,
        kind=payload.kind,
        market=payload.market,
        exchange=payload.exchange,
        confirm=payload.confirm,
        receive_timeout_seconds=payload.receive_timeout_seconds,
    )


@router.get("/dashboard")
def paper_dashboard(db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).dashboard()


@router.get("/bot/status")
def paper_bot_status(db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).bot_status()


@router.post("/bot/preview")
def preview_paper_bot(payload: PaperBotRunRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).bot_preview(
        trade_date=payload.trade_date,
        strategies=payload.strategies,
        max_candidates=payload.max_candidates,
    )


@router.post("/bot/run")
def run_paper_bot(payload: PaperBotRunRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).run_bot(
        trade_date=payload.trade_date,
        strategies=payload.strategies,
        max_candidates=payload.max_candidates,
        dry_run=payload.dry_run,
    )


@router.get("/bot/runs/{run_id}")
def get_paper_bot_run(run_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperTradingService(db).get_bot_run(run_id=run_id)
