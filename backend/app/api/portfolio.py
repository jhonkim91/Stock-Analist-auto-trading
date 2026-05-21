from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/risk")
def get_portfolio_risk(db: Session = Depends(get_db)) -> dict[str, object]:
    return PortfolioService(db).risk_summary()
