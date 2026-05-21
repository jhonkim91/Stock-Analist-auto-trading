from __future__ import annotations

from fastapi import APIRouter

from backend.app.services.settings_service import SettingsService

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def read_settings() -> dict[str, object]:
    return SettingsService().read_settings()
