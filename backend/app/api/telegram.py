from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.services.telegram_bot_service import TelegramBotService

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


class TelegramCommandRequest(BaseModel):
    """로컬 테스트와 webhook 연결 전 command dispatch 검증용 요청이다."""

    text: str = Field(min_length=1, max_length=1000)
    chat_id: str | None = None


@router.get("/status")
def telegram_status(db: Session = Depends(get_db)) -> dict[str, object]:
    return TelegramBotService(db).status()


@router.post("/command")
def dispatch_telegram_command(payload: TelegramCommandRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    return TelegramBotService(db).handle_text(payload.text, chat_id=payload.chat_id)
