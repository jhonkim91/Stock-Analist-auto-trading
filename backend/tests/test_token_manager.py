from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.app.services.token_manager import KisTokenManager, TokenLifecycleService


def test_token_manager_status_uses_env_booleans_without_secret_values(monkeypatch):
    sentinel = "PHASE2_SENTINEL_SECRET_VALUE"
    monkeypatch.setenv("KIS_APP_KEY", sentinel)
    monkeypatch.setenv("KIS_APP_SECRET", sentinel)

    metadata = KisTokenManager().metadata()
    serialized = json.dumps(metadata, ensure_ascii=False)

    assert metadata["app_key_configured"] is True
    assert metadata["app_secret_configured"] is True
    assert metadata["token_issued"] is False
    assert metadata["token_cache_enabled"] is False
    assert sentinel not in serialized


def test_token_manager_keeps_raw_tokens_out_of_metadata_and_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    access_token = "RAW_ACCESS_TOKEN_PHASE2_SHOULD_NOT_LEAK"
    refresh_token = "RAW_REFRESH_TOKEN_PHASE2_SHOULD_NOT_LEAK"
    manager = KisTokenManager()

    manager.store_token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    metadata = manager.metadata()
    serialized = json.dumps(metadata, ensure_ascii=False)

    assert metadata["token_issued"] is True
    assert metadata["refresh_token_present"] is True
    assert metadata["access_token"] == "***REDACTED***"
    assert metadata["refresh_token"] == "***REDACTED***"
    assert access_token not in serialized
    assert refresh_token not in serialized
    assert not Path(".cache/kis/token.json").exists()


def test_token_lifecycle_service_preserves_fail_closed_status(monkeypatch):
    monkeypatch.setenv("KIS_APP_KEY", "PHASE2_SENTINEL_SECRET_VALUE")
    monkeypatch.setenv("KIS_APP_SECRET", "PHASE2_SENTINEL_SECRET_VALUE")

    status = TokenLifecycleService().status()

    assert status["state"] == "DISABLED_BLOCKED"
    assert status["token_issued"] is False
    assert status["token_refresh_enabled"] is False
    assert status["token_db_persistence_enabled"] is False
    assert status["disabled_reason"] == "phase_3_token_manager_metadata_only"
