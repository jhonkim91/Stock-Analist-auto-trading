from __future__ import annotations

from collections.abc import Mapping
from typing import Any

REDACTED = "***REDACTED***"
SENSITIVE_KEY_PARTS = (
    "secret",
    "token",
    "password",
    "app_key",
    "appkey",
    "app_secret",
    "appsecret",
    "authorization",
    "header",
    "account",
    "account_no",
    "cano",
    "chat_id",
    "webhook",
    "approval_key",
    "credential",
    "hashkey",
    "raw",
)


class CredentialRedactionService:
    """credential과 account 계열 값을 응답/로그용 payload에서 제거한다."""

    def redact(self, value: Any, key: str = "") -> Any:
        if self.is_sensitive_key(key):
            return REDACTED if value not in (None, "") else None
        if isinstance(value, Mapping):
            return {str(item_key): self.redact(item_value, str(item_key)) for item_key, item_value in value.items()}
        if isinstance(value, list):
            return [self.redact(item) for item in value]
        return value

    def remove_sensitive(self, value: Any, key: str = "") -> Any:
        if self.is_sensitive_key(key):
            return None
        if isinstance(value, Mapping):
            return {
                str(item_key): cleaned
                for item_key, item_value in value.items()
                if (cleaned := self.remove_sensitive(item_value, str(item_key))) is not None
            }
        if isinstance(value, list):
            return [self.remove_sensitive(item) for item in value]
        return value

    @staticmethod
    def is_sensitive_key(key: str) -> bool:
        normalized = key.lower()
        return any(part in normalized for part in SENSITIVE_KEY_PARTS)
