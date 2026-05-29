from __future__ import annotations

import json

from tools import kis_live_token_refresh_preflight


def test_kis_live_token_refresh_preflight_is_preview_only_by_default(monkeypatch) -> None:
    monkeypatch.setenv("KIS_APP_KEY", "KEY")
    monkeypatch.setenv("KIS_APP_SECRET", "SECRET")
    record = kis_live_token_refresh_preflight.build_record(
        execute=False,
        confirm="",
        install_to_process_env=False,
    )
    serialized = json.dumps(record, ensure_ascii=False, default=str)

    assert record["execute_requested"] is False
    assert record["execute_confirmed"] is False
    assert record["network_call_performed"] is False
    assert record["live_order_created"] is False
    assert record["result"]["status"] == "live_token_refresh_preview_only"
    assert "SECRET" not in serialized


def test_kis_live_token_refresh_preflight_requires_exact_confirmation(monkeypatch) -> None:
    monkeypatch.setenv("LIVE_TOKEN_REFRESH_ENABLED", "true")
    monkeypatch.setenv("LIVE_TOKEN_REFRESH_PROCESS_ONLY", "true")
    monkeypatch.setenv("LIVE_TOKEN_REFRESH_NETWORK_ENABLED", "true")
    monkeypatch.setenv("KIS_APP_KEY", "KEY")
    monkeypatch.setenv("KIS_APP_SECRET", "SECRET")
    monkeypatch.setenv("KIS_REFRESH_TOKEN", "RTOK")

    record = kis_live_token_refresh_preflight.build_record(
        execute=True,
        confirm="wrong",
        install_to_process_env=True,
    )

    assert record["execute_requested"] is True
    assert record["execute_confirmed"] is False
    assert record["network_call_performed"] is False
    assert record["result"]["reason_codes"] == ["EXECUTE_CONFIRMATION_REQUIRED"]
