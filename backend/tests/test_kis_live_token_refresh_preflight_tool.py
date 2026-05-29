from __future__ import annotations

import json

from tools.env_file_loader import load_env_file, scan_env_file_keys
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


def test_kis_live_token_refresh_preflight_can_use_env_file_loader_without_raw_secret(tmp_path) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "KIS_APP_" + "KEY=VALUE_A",
                "KIS_APP_" + "SECRET='VALUE_B'",
                "KIS_REFRESH_" + "TOKEN = \"VALUE_C\"",
                "LIVE_TOKEN_REFRESH_ENABLED=true",
                "LIVE_TOKEN_REFRESH_PROCESS_ONLY=true",
            ]
        ),
        encoding="utf-8",
    )
    target: dict[str, str] = {}
    load_result = load_env_file(
        env_file,
        allowed_keys=kis_live_token_refresh_preflight.LIVE_TOKEN_REFRESH_ENV_FILE_KEYS,
        target=target,
    )

    record = kis_live_token_refresh_preflight.build_record(
        execute=False,
        confirm="",
        install_to_process_env=False,
        env=target,
        env_file_load_result=load_result,
    )
    serialized = json.dumps(record, ensure_ascii=False, default=str)

    assert record["status"]["app_key_configured"] is True
    assert record["status"]["app_secret_configured"] is True
    assert record["status"]["refresh_token_configured"] is True
    assert record["network_call_performed"] is False
    assert record["env_file_load"]["loaded_secret_like_key_count"] == 5
    assert "VALUE_A" not in serialized
    assert "VALUE_B" not in serialized
    assert "VALUE_C" not in serialized


def test_kis_live_token_refresh_preflight_identifies_access_token_only_env_file(tmp_path) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text("KIS_ACCESS_" + "TOKEN=ACCESS_ONLY_VALUE\n", encoding="utf-8")
    presence = scan_env_file_keys(
        env_file,
        key_names=kis_live_token_refresh_preflight.TOKEN_DIAGNOSTIC_ENV_NAMES,
    )

    record = kis_live_token_refresh_preflight.build_record(
        execute=False,
        confirm="",
        install_to_process_env=False,
        env={},
        env_file_presence_result=presence,
    )
    serialized = json.dumps(record, ensure_ascii=False, default=str)

    assert record["status"]["refresh_token_configured"] is False
    assert record["token_env_diagnostics"]["access_token_configured"] is True
    assert record["token_env_diagnostics"]["refresh_token_configured"] is False
    assert record["token_env_diagnostics"]["access_token_without_refresh_token"] is True
    assert record["network_call_performed"] is False
    assert "ACCESS_ONLY_VALUE" not in serialized
