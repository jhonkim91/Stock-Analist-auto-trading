from __future__ import annotations

from fastapi import APIRouter

from backend.app.models.schemas import NotificationTestRequest
from backend.app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


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
