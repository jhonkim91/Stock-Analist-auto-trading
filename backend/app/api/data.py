from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.schemas import ExternalPreviewDailyOhlcvRequest, ImportConfirmRequest, SeedResponse
from backend.app.services.market_data_import_service import (
    ImportRunBadRequestError,
    ImportRunConflictError,
    ImportRunNotFoundError,
    MarketDataImportService,
)
from backend.app.services.data_quality_summary_service import DataQualitySummaryService
from backend.app.services.market_data_service import MarketDataService

router = APIRouter(prefix="/api/data", tags=["data"])


@router.post("/seed", response_model=SeedResponse)
def seed_data(db: Session = Depends(get_db)) -> dict[str, int]:
    return MarketDataService(db).seed_sample_data()


@router.get("/status")
def data_status(db: Session = Depends(get_db)) -> dict[str, object]:
    return MarketDataService(db).status()


@router.get("/sources")
def data_sources(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    try:
        return MarketDataImportService(db).list_sources()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/external/providers")
def external_providers(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    try:
        return MarketDataImportService(db).list_external_providers()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/read-only/providers")
def read_only_providers(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    try:
        return MarketDataImportService(db).list_read_only_providers()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/quality-summary")
def data_quality_summary(
    market: str = Query(default="KR", min_length=1, max_length=16),
    venue: str = Query(default="KRX", min_length=1, max_length=32),
    lookback_trading_dates: int = Query(default=30, ge=1, le=252),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return DataQualitySummaryService(db).summary(
        market=market,
        venue=venue,
        lookback_trading_dates=lookback_trading_dates,
    )


@router.post("/external/preview-daily-ohlcv")
def preview_external_daily_ohlcv(
    payload: ExternalPreviewDailyOhlcvRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return MarketDataImportService(db).preview_external_daily_ohlcv(
            source_id=payload.source_id,
            symbol=payload.symbol,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/external/confirm-import")
def confirm_external_import(payload: ImportConfirmRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return MarketDataImportService(db).confirm_external_import(payload.run_id)
    except ImportRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImportRunConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ImportRunBadRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/external/fetch-runs")
def external_fetch_runs(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return MarketDataImportService(db).list_import_runs(limit=limit, provider_types={"external", "external_market_data"})


@router.get("/external/fetch-runs/{run_id}")
def external_fetch_run_detail(run_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        run = MarketDataImportService(db).get_import_run(run_id)
    except ImportRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if run["provider_type"] not in {"external", "external_market_data"}:
        raise HTTPException(status_code=404, detail="external fetch run을 찾을 수 없습니다.")
    return run


@router.get("/import-runs")
def import_runs(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return MarketDataImportService(db).list_import_runs(limit=limit)


@router.get("/import-runs/{run_id}")
def import_run_detail(run_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return MarketDataImportService(db).get_import_run(run_id)
    except ImportRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/validate-csv")
async def validate_csv(
    source_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV 파일만 업로드할 수 있습니다.")
    try:
        return MarketDataImportService(db).validate_csv(
            content=await file.read(),
            original_filename=file.filename,
            source_id=source_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/import-csv-confirmed")
def import_csv_confirmed(payload: ImportConfirmRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return MarketDataImportService(db).confirm_import(payload.run_id)
    except ImportRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImportRunConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ImportRunBadRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/quality")
def data_quality(
    run_id: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return MarketDataImportService(db).list_quality_checks(run_id=run_id, severity=severity, limit=limit)


@router.get("/quality/{run_id}")
def data_quality_for_run(
    run_id: str,
    severity: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return MarketDataImportService(db).list_quality_checks(run_id=run_id, severity=severity, limit=limit)


@router.post("/import/daily-ohlcv")
async def import_daily_ohlcv(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict[str, object]:
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV 파일만 업로드할 수 있습니다.")
    try:
        result = MarketDataService(db).import_daily_ohlcv_csv(await file.read())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **result}
