from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.models.schemas import RuntimeEnvPresetRequest, RuntimeEnvToggleRequest
from backend.app.services.settings_service import SettingsService

router = APIRouter(prefix="/api/settings", tags=["settings"])


class EnvironmentValueRequest(BaseModel):
    key: str
    value: str = ""
    confirm: bool = False


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


@router.post("/runtime-env/preset")
def apply_runtime_env_preset(payload: RuntimeEnvPresetRequest) -> dict[str, object]:
    return SettingsService().set_runtime_env_preset(
        name=payload.name,
        confirm=payload.confirm,
    )


@router.get("/environment")
def read_environment() -> dict[str, object]:
    """입력 가능한 자격증명/환경 값의 마스킹된 현재 상태를 반환한다."""
    return SettingsService().environment_status()


@router.post("/environment")
def set_environment(payload: EnvironmentValueRequest) -> dict[str, object]:
    """자격증명/환경 값 하나를 저장(영속)하고 현재 프로세스에 반영한다."""
    return SettingsService().set_environment_value(
        key=payload.key,
        value=payload.value,
        confirm=payload.confirm,
    )
