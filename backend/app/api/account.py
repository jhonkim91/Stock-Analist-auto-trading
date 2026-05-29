from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.services.account_service import AccountService

router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("/summary")
def account_summary(db: Session = Depends(get_db)) -> dict[str, object]:
    return AccountService(db).summary()


@router.get("/holdings")
def account_holdings(db: Session = Depends(get_db)) -> dict[str, object]:
    return AccountService(db).holdings()


@router.get("/report")
def account_report(db: Session = Depends(get_db)) -> dict[str, object]:
    return AccountService(db).report()
