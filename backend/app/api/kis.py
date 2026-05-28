from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.models.schemas import KisTokenIssueRequest
from backend.app.services.kis_service import KisReadOnlyService
from backend.app.services.token_manager import TokenLifecycleService

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


@router.get("/token/status")
def kis_token_status() -> dict[str, object]:
    return TokenLifecycleService().status()


@router.post("/token/issue")
def issue_kis_paper_token(payload: KisTokenIssueRequest) -> dict[str, object]:
    return TokenLifecycleService().issue_paper_access_token(
        confirm=payload.confirm,
        install_to_process_env=payload.install_to_process_env,
    )


@router.post("/token/refresh")
def refresh_kis_paper_token(payload: KisTokenIssueRequest) -> dict[str, object]:
    return TokenLifecycleService().refresh_paper_access_token(
        confirm=payload.confirm,
        install_to_process_env=payload.install_to_process_env,
    )
