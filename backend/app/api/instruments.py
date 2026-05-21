from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.repositories.market_repository import MarketRepository

router = APIRouter(prefix="/api/instruments", tags=["instruments"])


@router.get("")
def list_instruments(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return [
        {
            "symbol": row.symbol,
            "name": row.name,
            "asset_type": row.asset_type,
            "currency": row.currency,
            "market": row.market,
            "exchange": row.exchange,
            "sector": row.sector,
            "industry": row.industry,
            "is_active": row.is_active,
        }
        for row in MarketRepository(db).list_symbols()
    ]


@router.get("/{symbol}")
def get_instrument(symbol: str, db: Session = Depends(get_db)) -> dict[str, object]:
    row = MarketRepository(db).get_symbol(symbol)
    if row is None:
        raise HTTPException(status_code=404, detail="종목을 찾을 수 없습니다.")
    return {
        "symbol": row.symbol,
        "name": row.name,
        "asset_type": row.asset_type,
        "currency": row.currency,
        "market": row.market,
        "exchange": row.exchange,
        "sector": row.sector,
        "industry": row.industry,
        "is_active": row.is_active,
        "list_date": row.list_date,
        "delist_date": row.delist_date,
    }
