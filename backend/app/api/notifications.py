from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter

from backend.app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationTestRequest(BaseModel):
    channel_alias: str | None = None
    message: str = Field(default="notification test", max_length=1000)
    dry_run: bool = True


@router.get("/status")
def notification_status() -> dict[str, object]:
    return NotificationService().status()


@router.post("/test")
def test_notification(payload: NotificationTestRequest) -> dict[str, object]:
    return NotificationService().send_test(
        channel_alias=payload.channel_alias,
        message=payload.message,
        dry_run=payload.dry_run,
    )
