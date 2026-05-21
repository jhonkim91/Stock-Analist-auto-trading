from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.services.kis_service import KisReadOnlyService

router = APIRouter(prefix="/api/kis", tags=["kis"])


@router.get("/status")
def kis_status() -> dict[str, object]:
    try:
        return KisReadOnlyService().status()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/config")
def kis_config() -> dict[str, object]:
    try:
        return KisReadOnlyService().config()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/config/validate")
def validate_kis_config() -> dict[str, object]:
    try:
        return KisReadOnlyService().validate_config()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
