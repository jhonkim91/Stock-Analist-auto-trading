from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.schemas import SeedResponse
from backend.app.services.market_data_service import MarketDataService

router = APIRouter(prefix="/api/data", tags=["data"])


@router.post("/seed", response_model=SeedResponse)
def seed_data(db: Session = Depends(get_db)) -> dict[str, int]:
    return MarketDataService(db).seed_sample_data()


@router.get("/status")
def data_status(db: Session = Depends(get_db)) -> dict[str, object]:
    return MarketDataService(db).status()


@router.post("/import/daily-ohlcv")
async def import_daily_ohlcv(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict[str, object]:
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV 파일만 업로드할 수 있습니다.")
    try:
        result = MarketDataService(db).import_daily_ohlcv_csv(await file.read())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **result}
