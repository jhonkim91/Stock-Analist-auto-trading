from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.services.market_session_service import MarketSessionService
from backend.app.services.regime_service import RegimeService

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/regime")
def get_market_regime(as_of: date | None = None, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return RegimeService(db).detect_market_regime(as_of=as_of)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/sessions")
def get_market_session_windows(venue: str = Query(default="KRX", min_length=1, max_length=16)) -> dict[str, object]:
    service = MarketSessionService()
    session_windows = service.session_windows(venue=venue)
    normalized_venue = str(session_windows[0]["venue"]) if session_windows else venue.strip().upper()
    return {"venue": normalized_venue, "session_windows": session_windows}


@router.get("/session")
def get_market_session(
    venue: str = Query(default="KRX", min_length=1, max_length=16),
    as_of: datetime | None = None,
) -> dict[str, object]:
    return MarketSessionService().session_at(venue=venue, as_of=as_of)


@router.get("/calendar")
def get_market_calendar(
    start_date: date,
    end_date: date,
    venue: str = Query(default="KRX", min_length=1, max_length=16),
) -> dict[str, object]:
    try:
        calendar = MarketSessionService().trading_calendar(
            start_date=start_date,
            end_date=end_date,
            venue=venue,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    normalized_venue = str(calendar[0]["venue"]) if calendar else venue.strip().upper()
    return {"venue": normalized_venue, "calendar": calendar}
