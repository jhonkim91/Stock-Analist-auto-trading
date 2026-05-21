from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.services.indicator_service import IndicatorService

router = APIRouter(prefix="/api/indicators", tags=["indicators"])


@router.post("/recompute")
def recompute_indicators(db: Session = Depends(get_db)) -> dict[str, object]:
    return IndicatorService(db).recompute()
