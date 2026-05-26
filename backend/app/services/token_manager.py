from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

KIS_APP_KEY_ENV = "KIS_APP_KEY"
KIS_APP_SECRET_ENV = "KIS_APP_SECRET"


@dataclass
class InMemoryTokenState:
    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: datetime | None = None


class KisTokenManager:
    def __init__(self) -> None:
        self._state = InMemoryTokenState()

    def store_token(self, *, access_token: str, expires_at: datetime, refresh_token: str | None = None) -> None:
        """raw token을 현재 process memory에만 보관한다."""
        self._state = InMemoryTokenState(access_token=access_token, refresh_token=refresh_token, expires_at=expires_at)

    def clear(self) -> None:
        """memory token 상태를 제거한다."""
        self._state = InMemoryTokenState()

    def metadata(self) -> dict[str, object]:
        """raw token 없이 token lifecycle metadata만 반환한다."""
        token_issued = bool(self._state.access_token)
        refresh_token_present = bool(self._state.refresh_token)
        expires_at = self._state.expires_at
        return {
            "state": "IN_MEMORY" if token_issued else self.env_state(),
            "app_key_configured": self.env_configured(KIS_APP_KEY_ENV),
            "app_secret_configured": self.env_configured(KIS_APP_SECRET_ENV),
            "token_issued": token_issued,
            "refresh_token_present": refresh_token_present,
            "token_cache_enabled": False,
            "token_file_persistence_enabled": False,
            "token_db_persistence_enabled": False,
            "access_token": "***REDACTED***" if token_issued else None,
            "refresh_token": "***REDACTED***" if refresh_token_present else None,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "expired": bool(expires_at and expires_at <= datetime.now(UTC)),
        }

    @classmethod
    def env_state(cls) -> str:
        """KIS env 설정 여부를 token 발급 없이 상태 문자열로 반환한다."""
        if cls.env_configured(KIS_APP_KEY_ENV) and cls.env_configured(KIS_APP_SECRET_ENV):
            return "CONFIGURED_NO_TOKEN"
        return "UNCONFIGURED"

    @classmethod
    def env_configured(cls, name: str) -> bool:
        return cls.is_configured_value(os.environ.get(name, ""))

    @staticmethod
    def is_configured_value(value: str) -> bool:
        stripped = value.strip()
        if not stripped:
            return False
        return "placeholder" not in stripped.lower()


class TokenLifecycleService:
    def __init__(self, token_manager: KisTokenManager | None = None) -> None:
        self.token_manager = token_manager or KisTokenManager()

    def status(self) -> dict[str, object]:
        """token 발급 없이 configured boolean과 in-memory metadata만 반환한다."""
        metadata = self.token_manager.metadata()
        state = metadata["state"]
        if metadata["app_key_configured"] and metadata["app_secret_configured"] and not metadata["token_issued"]:
            state = "DISABLED_BLOCKED"
        return {
            **metadata,
            "state": state,
            "token_refresh_enabled": False,
            "disabled_reason": "phase_2_token_manager_contract_only",
        }
