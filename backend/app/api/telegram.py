from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.schemas import TelegramReportSchedulerRunRequest, TelegramWebhookRequest
from backend.app.services.telegram_bot_service import TelegramBotService
from backend.app.services.telegram_report_scheduler_service import TelegramReportSchedulerService

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


@router.post("/webhook")
def dispatch_telegram_webhook(payload: TelegramWebhookRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    return TelegramBotService(db).handle_update(payload.model_dump(exclude_none=True))


@router.get("/scheduler/status")
def telegram_scheduler_status(db: Session = Depends(get_db)) -> dict[str, object]:
    return TelegramReportSchedulerService(db).status()


@router.post("/scheduler/run-once")
def run_telegram_scheduler(
    payload: TelegramReportSchedulerRunRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return TelegramReportSchedulerService(db).run_once(
        slot=payload.slot,
        report_types=payload.report_types,
        report_date=payload.report_date,
        channel_alias=payload.channel_alias,
        dry_run=payload.dry_run,
        confirm=payload.confirm,
    )
