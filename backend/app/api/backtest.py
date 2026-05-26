from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.schemas import BacktestRunRequest
from backend.app.services.backtest_service import BacktestService
from backend.app.services.validation_service import StrategyValidationService, ValidationReportService

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("/run")
def run_backtest(payload: BacktestRunRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return BacktestService(db).run(
            strategy_name=payload.strategy_name,
            start_date=payload.start_date,
            end_date=payload.end_date,
            initial_equity=payload.initial_equity,
            top_n=payload.top_n,
            max_positions=payload.max_positions,
            rebalance_frequency=payload.rebalance_frequency,
            weighting=payload.weighting,
            allow_overlap_positions=payload.allow_overlap_positions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/strategy-summary")
def strategy_summary(
    lookback_days: int = Query(default=252, ge=1, le=1000),
    baseline_run_id: str | None = Query(default=None),
    baseline_snapshot: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        parsed_snapshot: dict[str, object] | None = None
        if baseline_snapshot:
            loaded_snapshot = json.loads(baseline_snapshot)
            if not isinstance(loaded_snapshot, dict):
                raise ValueError("baseline_snapshot은 JSON object여야 합니다.")
            parsed_snapshot = loaded_snapshot
        summary = StrategyValidationService(db).strategy_summary(
            lookback_days=lookback_days,
            baseline_run_id=baseline_run_id,
            baseline_snapshot=parsed_snapshot,
        )
        return ValidationReportService().write_strategy_validation_summary(summary, lookback_days=lookback_days)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="baseline_snapshot JSON 파싱에 실패했습니다.") from exc
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


@router.get("/runs/{run_id}/trades")
def backtest_run_trades(run_id: str, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    try:
        return BacktestService(db).get_run_trades(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
