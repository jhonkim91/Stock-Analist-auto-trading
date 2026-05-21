from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from backend.app.core.paths import CONFIG_DIR


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    return data


@lru_cache(maxsize=1)
def get_settings() -> dict[str, Any]:
    """YAML 설정을 병합하고 환경 변수 override를 적용한다."""
    settings: dict[str, Any] = {}
    for name in ("app", "strategies", "risk", "backtest"):
        settings[name] = _load_yaml(CONFIG_DIR / f"{name}.yaml")

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        settings["app"].setdefault("database", {})["url"] = database_url

    return settings


def get_config(section: str) -> dict[str, Any]:
    """설정 섹션을 반환한다."""
    return get_settings()[section]
