from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime

KIS_APP_KEY_ENV = "KIS_APP_KEY"
KIS_APP_SECRET_ENV = "KIS_APP_SECRET"


@dataclass(frozen=True)
class KisTokenMetadata:
    token_issued: bool = False
    refresh_token_present: bool = False
    expires_at: datetime | None = None
    access_token_fingerprint: str | None = None
    refresh_token_fingerprint: str | None = None


class KisTokenManager:
    """KIS token raw value를 저장하지 않고 lifecycle metadata만 유지한다."""

    def __init__(self) -> None:
        self._metadata = KisTokenMetadata()

    def record_issued_token(
        self,
        *,
        access_token: str,
        expires_at: datetime,
        refresh_token: str | None = None,
    ) -> None:
        self._metadata = KisTokenMetadata(
            token_issued=bool(access_token),
            refresh_token_present=bool(refresh_token),
            expires_at=expires_at,
            access_token_fingerprint=self._fingerprint(access_token) if access_token else None,
            refresh_token_fingerprint=self._fingerprint(refresh_token) if refresh_token else None,
        )

    def store_token(self, *, access_token: str, expires_at: datetime, refresh_token: str | None = None) -> None:
        """기존 호출부 호환용 alias이며 raw token은 저장하지 않는다."""
        self.record_issued_token(access_token=access_token, expires_at=expires_at, refresh_token=refresh_token)

    def clear(self) -> None:
        self._metadata = KisTokenMetadata()

    def metadata(self) -> dict[str, object]:
        metadata = self._metadata
        expires_at = metadata.expires_at
        token_issued = metadata.token_issued
        return {
            "state": "METADATA_ONLY" if token_issued else self.env_state(),
            "app_key_configured": self.env_configured(KIS_APP_KEY_ENV),
            "app_secret_configured": self.env_configured(KIS_APP_SECRET_ENV),
            "token_issued": token_issued,
            "refresh_token_present": metadata.refresh_token_present,
            "token_cache_enabled": False,
            "token_file_persistence_enabled": False,
            "token_db_persistence_enabled": False,
            "token_raw_value_persisted": False,
            "access_token": "***REDACTED***" if token_issued else None,
            "refresh_token": "***REDACTED***" if metadata.refresh_token_present else None,
            "access_token_fingerprint": metadata.access_token_fingerprint,
            "refresh_token_fingerprint": metadata.refresh_token_fingerprint,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "expired": bool(expires_at and expires_at <= datetime.now(UTC)),
        }

    @classmethod
    def env_state(cls) -> str:
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

    @staticmethod
    def _fingerprint(value: str | None) -> str | None:
        if not value:
            return None
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


class TokenLifecycleService:
    """KIS token lifecycle 상태를 fail-closed metadata로 반환한다."""

    def __init__(self, token_manager: KisTokenManager | None = None) -> None:
        self.token_manager = token_manager or KisTokenManager()

    def status(self) -> dict[str, object]:
        metadata = self.token_manager.metadata()
        state = metadata["state"]
        if metadata["app_key_configured"] and metadata["app_secret_configured"] and not metadata["token_issued"]:
            state = "DISABLED_BLOCKED"
        return {
            **metadata,
            "state": state,
            "token_refresh_enabled": False,
            "disabled_reason": "phase_3_token_manager_metadata_only",
        }
