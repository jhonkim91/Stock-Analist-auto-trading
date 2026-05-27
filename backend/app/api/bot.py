from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.schemas import PaperBotRunRequest
from backend.app.services.paper_bot_service import PaperBotService

router = APIRouter(prefix="/api/bot", tags=["bot"])


@router.get("/status")
def bot_status(db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperBotService(db).status()


@router.post("/run-once")
def bot_run_once(payload: PaperBotRunRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperBotService(db).run_once(auto_submit=payload.auto_submit)


@router.post("/stop")
def bot_stop(db: Session = Depends(get_db)) -> dict[str, object]:
    return PaperBotService(db).stop()
