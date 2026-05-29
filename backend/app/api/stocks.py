from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.services.market_realtime_service import MarketRealtimeService

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("/search")
def search_stocks(
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Telegram과 UI가 공유할 종목 검색 payload를 반환한다."""
    return MarketRealtimeService(db).search_symbols(q=q, limit=limit)


@router.get("/{symbol}")
def stock_detail(symbol: str, db: Session = Depends(get_db)) -> dict[str, object]:
    """KIS 현재가 우선, DB 최신 데이터 fallback 방식으로 종목 상세를 반환한다."""
    try:
        return MarketRealtimeService(db).symbol_detail(symbol)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
