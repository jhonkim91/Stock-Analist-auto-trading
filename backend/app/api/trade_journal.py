from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.services.trade_journal_service import TradeJournalService

router = APIRouter(prefix="/api/trade-journal", tags=["trade-journal"])


@router.get("/entries")
def trade_journal_entries(
    source: str = Query(default="all"),
    run_id: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return TradeJournalService(db).entries(source=source, run_id=run_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/csv")
def trade_journal_csv(
    source: str = Query(default="all"),
    run_id: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> Response:
    try:
        content = TradeJournalService(db).csv_text(source=source, run_id=run_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="trade-journal.csv"'},
    )
