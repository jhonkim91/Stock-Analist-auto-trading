from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from backend.app.core.paths import CONFIG_DIR

SENSITIVE_KEY_PARTS = (
    "secret",
    "token",
    "password",
    "api_key",
    "app_key",
    "appkey",
    "app_secret",
    "appsecret",
    "authorization",
    "account",
    "account_no",
    "cano",
    "hts_id",
    "approval_key",
    "webhook",
    "chat_id",
    "bot_token",
)


class SettingsService:
    def __init__(self, config_dir: Path = CONFIG_DIR) -> None:
        self.config_dir = config_dir

    def read_settings(self) -> dict[str, Any]:
        """backend/config/*.yaml만 읽어 read-only 설정 요약을 반환한다."""
        result: dict[str, Any] = {}
        for name in ("strategies", "risk", "backtest", "app", "data_sources", "notifications", "bot"):
            path = self.config_dir / f"{name}.yaml"
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8") as file:
                data = yaml.safe_load(file) or {}
            result[name] = self._redact(data)
        return result

    @classmethod
    def _redact(cls, value: Any, key: str = "") -> Any:
        if cls._is_sensitive_key(key):
            return "***REDACTED***"
        if isinstance(value, dict):
            redacted: dict[str, Any] = {}
            sensitive_index = 0
            for item_key, item_value in value.items():
                item_key_text = str(item_key)
                if cls._is_sensitive_key(item_key_text):
                    redacted[f"redacted_field_{sensitive_index}"] = "***REDACTED***"
                    sensitive_index += 1
                else:
                    redacted[item_key] = cls._redact(item_value, item_key_text)
            return redacted
        if isinstance(value, list):
            return [cls._redact(item) for item in value]
        return value

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        normalized = key.lower()
        return any(part in normalized for part in SENSITIVE_KEY_PARTS)
