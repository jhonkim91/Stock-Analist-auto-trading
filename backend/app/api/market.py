from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.services.regime_service import RegimeService

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/regime")
def get_market_regime(db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return RegimeService(db).detect_market_regime()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
