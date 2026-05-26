from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.services.indicator_service import IndicatorService

router = APIRouter(prefix="/api/indicators", tags=["indicators"])


@router.post("/recompute")
def recompute_indicators(
    symbol: str | None = Query(default=None, min_length=1, max_length=32),
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return IndicatorService(db).recompute(symbol=symbol, start_date=start_date, end_date=end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
