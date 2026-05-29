from __future__ import annotations

from fastapi import APIRouter

from backend.app.models.schemas import RuntimeEnvToggleRequest
from backend.app.services.settings_service import SettingsService

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def read_settings() -> dict[str, object]:
    return SettingsService().read_settings()


@router.get("/runtime-env")
def read_runtime_env() -> dict[str, object]:
    return SettingsService().runtime_env_status()


@router.post("/runtime-env/toggle")
def update_runtime_env(payload: RuntimeEnvToggleRequest) -> dict[str, object]:
    return SettingsService().set_runtime_env_toggle(
        name=payload.name,
        enabled=payload.enabled,
        confirm=payload.confirm,
    )
