from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.app.services.kis_token_manager import KisTokenManager, TokenLifecycleService


def test_kis_token_manager_records_metadata_without_raw_token(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    access_token = "RAW_PHASE3_ACCESS_TOKEN_SHOULD_NOT_PERSIST"
    refresh_token = "RAW_PHASE3_REFRESH_TOKEN_SHOULD_NOT_PERSIST"
    manager = KisTokenManager()

    manager.record_issued_token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    metadata = manager.metadata()
    serialized = json.dumps(metadata, ensure_ascii=False)
    internal_state = json.dumps(manager.__dict__, default=str, ensure_ascii=False)

    assert metadata["state"] == "METADATA_ONLY"
    assert metadata["token_issued"] is True
    assert metadata["refresh_token_present"] is True
    assert metadata["token_raw_value_persisted"] is False
    assert metadata["access_token"] == "***REDACTED***"
    assert metadata["refresh_token"] == "***REDACTED***"
    assert metadata["access_token_fingerprint"]
    assert access_token not in serialized
    assert refresh_token not in serialized
    assert access_token not in internal_state
    assert refresh_token not in internal_state
    assert not Path(".cache/kis/token.json").exists()


def test_token_lifecycle_remains_disabled_without_issuing_token(monkeypatch):
    sentinel = "PHASE3_SENTINEL_SECRET_VALUE"
    monkeypatch.setenv("KIS_APP_KEY", sentinel)
    monkeypatch.setenv("KIS_APP_SECRET", sentinel)

    status = TokenLifecycleService().status()
    serialized = json.dumps(status, ensure_ascii=False)

    assert status["state"] == "DISABLED_BLOCKED"
    assert status["token_issued"] is False
    assert status["token_refresh_enabled"] is False
    assert status["token_db_persistence_enabled"] is False
    assert status["token_raw_value_persisted"] is False
    assert status["disabled_reason"] == "KIS_PAPER_TOKEN_GATE_BLOCKED"
    assert sentinel not in serialized


def test_token_lifecycle_status_reports_ready_for_paper_issue_and_refresh(monkeypatch):
    sentinel = "PHASE3_SENTINEL_SECRET_VALUE"
    monkeypatch.setenv("KIS_ENV", "paper")
    monkeypatch.setenv("KIS_APP_KEY", sentinel)
    monkeypatch.setenv("KIS_APP_SECRET", sentinel)
    monkeypatch.setenv("KIS_TOKEN_ISSUE_ENABLED", "true")
    monkeypatch.setenv("KIS_PAPER_BASE_URL", "https://openapivts.koreainvestment.com:29443")
    monkeypatch.setenv("ENABLE_REAL_ORDER", "false")

    status = TokenLifecycleService().status()
    serialized = json.dumps(status, ensure_ascii=False)

    assert status["state"] == "READY_FOR_PAPER_TOKEN"
    assert status["token_issue_enabled"] is True
    assert status["token_refresh_enabled"] is True
    assert status["token_ensure_enabled"] is True
    assert status["token_refresh_supported"] is True
    assert status["token_refresh_fallback_to_issue"] is True
    assert status["token_gate_reason_codes"] == []
    assert status["disabled_reason"] is None
    assert status["live_endpoint_enabled"] is False
    assert sentinel not in serialized
