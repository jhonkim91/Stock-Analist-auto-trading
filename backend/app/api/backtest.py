from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.schemas import BacktestRunRequest
from backend.app.services.backtest_service import BacktestService

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("/run")
def run_backtest(payload: BacktestRunRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return BacktestService(db).run(
            strategy_name=payload.strategy_name,
            start_date=payload.start_date,
            end_date=payload.end_date,
            initial_equity=payload.initial_equity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs")
def list_backtest_runs(
    limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)
) -> list[dict[str, object]]:
    return BacktestService(db).list_runs(limit=limit)


@router.get("/runs/{run_id}")
def backtest_run_detail(run_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return BacktestService(db).get_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
