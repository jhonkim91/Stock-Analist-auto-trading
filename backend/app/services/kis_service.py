from __future__ import annotations

import os
from typing import Any

from backend.app.services.market_data_import_service import DataSourceService
from backend.app.services.kis_request_signer import KisRequestSigner
from backend.app.services.kis_token_manager import KIS_APP_KEY_ENV, KIS_APP_SECRET_ENV, KisTokenManager

KIS_MARKET_DATA_SOURCE_ID = "kis_market_data"
DISABLED_REASON = "Phase 3C read-only foundation only"


class KisReadOnlyService:
    def __init__(self, source_service: DataSourceService | None = None) -> None:
        self.source_service = source_service or DataSourceService()
        self.token_manager = KisTokenManager()
        self.request_signer = KisRequestSigner()

    def status(self) -> dict[str, object]:
        """KIS read-only foundation 상태를 secret 값 없이 반환한다."""
        source = self._source()
        return {
            "source_id": source["source_id"],
            "enabled": bool(source["enabled"]),
            "network_enabled": bool(source["network_enabled"]),
            "read_only_enabled": bool(source["read_only_enabled"]),
            "app_key_configured": self._env_configured(KIS_APP_KEY_ENV),
            "app_secret_configured": self._env_configured(KIS_APP_SECRET_ENV),
            "token_cache_enabled": False,
            "broker_enabled": False,
            "websocket_enabled": False,
            "disabled_reason": DISABLED_REASON,
            "token_manager": self.token_manager.metadata(),
            "request_signing": self.request_signer.status(),
        }

    def config(self) -> dict[str, object]:
        """KIS market data source 설정을 redacted 상태로 반환한다."""
        source = self._source()
        return {
            "source_id": source["source_id"],
            "source_config": source,
            "app_key_configured": self._env_configured(KIS_APP_KEY_ENV),
            "app_secret_configured": self._env_configured(KIS_APP_SECRET_ENV),
            "token_cache_enabled": False,
            "broker_enabled": False,
            "websocket_enabled": False,
            "disabled_reason": DISABLED_REASON,
            "token_manager": self.token_manager.metadata(),
            "request_signing": self.request_signer.status(),
        }

    def validate_config(self) -> dict[str, object]:
        """환경변수 존재와 형식만 확인하며 KIS 외부 호출과 토큰 발급은 하지 않는다."""
        app_key = os.environ.get(KIS_APP_KEY_ENV, "")
        app_secret = os.environ.get(KIS_APP_SECRET_ENV, "")
        app_key_configured = self._is_configured_value(app_key)
        app_secret_configured = self._is_configured_value(app_secret)
        return {
            "source_id": KIS_MARKET_DATA_SOURCE_ID,
            "configured": app_key_configured and app_secret_configured,
            "app_key_configured": app_key_configured,
            "app_secret_configured": app_secret_configured,
            "app_key_format_valid": self._format_valid(app_key),
            "app_secret_format_valid": self._format_valid(app_secret),
            "network_call_performed": False,
            "token_issued": False,
            "token_cache_enabled": False,
            "token_raw_value_persisted": False,
            "hashkey_confirmed": False,
            "signing_enabled": False,
            "disabled_reason": DISABLED_REASON,
        }

    def _source(self) -> dict[str, Any]:
        for source in self.source_service.list_sources():
            if source["source_id"] == KIS_MARKET_DATA_SOURCE_ID:
                return source
        raise ValueError(f"KIS market data source를 찾을 수 없습니다: {KIS_MARKET_DATA_SOURCE_ID}")

    @classmethod
    def _env_configured(cls, name: str) -> bool:
        return KisTokenManager.env_configured(name)

    @staticmethod
    def _is_configured_value(value: str) -> bool:
        return KisTokenManager.is_configured_value(value)

    @classmethod
    def _format_valid(cls, value: str) -> bool:
        return cls._is_configured_value(value) and len(value.strip()) >= 8
