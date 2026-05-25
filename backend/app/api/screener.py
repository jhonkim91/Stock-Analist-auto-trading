from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.schemas import ScreenerRunRequest, ScreenerStrategyResponse
from backend.app.services.screener_service import ScreenerService
from backend.app.strategies.registry import list_strategy_metadata

router = APIRouter(prefix="/api/screener", tags=["screener"])


@router.get("/strategies", response_model=list[ScreenerStrategyResponse])
def list_strategies() -> list[dict[str, object]]:
    """프론트 전략 선택 UI에 필요한 default/available 메타데이터를 반환한다."""
    return list_strategy_metadata()


@router.post("/run")
def run_screener(payload: ScreenerRunRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return ScreenerService(db).run(payload.trade_date, payload.strategies)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/results")
def list_results(
    trade_date: str | None = Query(default=None),
    strategy_name: str | None = Query(default=None),
    passed: bool | None = Query(default=None),
    grade: str | None = Query(default=None),
    q: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str = Query(default="desc"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    parsed_date = None
    if trade_date:
        from datetime import date

        parsed_date = date.fromisoformat(trade_date)
    return ScreenerService(db).list_results(
        trade_date=parsed_date,
        strategy_name=strategy_name,
        passed=passed,
        grade=grade,
        q=q,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
    )
