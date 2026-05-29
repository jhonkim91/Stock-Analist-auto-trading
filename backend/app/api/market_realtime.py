from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.services.market_realtime_service import MarketRealtimeService

router = APIRouter(prefix="/api/market-realtime", tags=["market-realtime"])


@router.get("/search")
def search_symbols(
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return MarketRealtimeService(db).search_symbols(q=q, limit=limit)


@router.get("/symbols/{symbol}")
def symbol_detail(symbol: str, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return MarketRealtimeService(db).symbol_detail(symbol)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/symbols/{symbol}/chart")
def symbol_chart(
    symbol: str,
    limit: int = Query(default=120, ge=5, le=500),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return MarketRealtimeService(db).chart(symbol=symbol, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/rankings")
def market_rankings(
    metric: str = Query(default="total_score"),
    limit: int = Query(default=20, ge=1, le=100),
    trade_date: date | None = None,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return MarketRealtimeService(db).rankings(metric=metric, limit=limit, trade_date=trade_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
