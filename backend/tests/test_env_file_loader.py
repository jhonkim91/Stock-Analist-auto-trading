from __future__ import annotations

import json

from tools.env_file_loader import load_env_file, parse_env_line, scan_env_file_keys


def test_env_file_loader_parses_spacing_quotes_and_redacts_secret_names(tmp_path) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "export KIS_REFRESH_TOKEN = \"REFRESH_SECRET_VALUE\"",
                "LIVE_TOKEN_REFRESH_ENABLED=true",
                "PAPER_BOT_CONFIRM =true",
                "UNRELATED_SECRET=IGNORED_SECRET_VALUE",
            ]
        ),
        encoding="utf-8",
    )
    target = {"PAPER_BOT_CONFIRM": "false"}

    result = load_env_file(
        env_file,
        allowed_keys=("KIS_REFRESH_TOKEN", "LIVE_TOKEN_REFRESH_ENABLED", "PAPER_BOT_CONFIRM"),
        target=target,
    )
    serialized = json.dumps(result, ensure_ascii=False, sort_keys=True)

    assert result["ok"] is True
    assert target["KIS_REFRESH_TOKEN"] == "REFRESH_SECRET_VALUE"
    assert target["LIVE_TOKEN_REFRESH_ENABLED"] == "true"
    assert target["PAPER_BOT_CONFIRM"] == "false"
    assert result["loaded_keys"] == []
    assert "PAPER_BOT_CONFIRM" in result["skipped_existing_keys"]
    assert "KIS_REFRESH_TOKEN" not in result["loaded_keys"]
    assert "UNRELATED_SECRET" not in result["ignored_keys"]
    assert result["loaded_count"] == 2
    assert result["loaded_secret_like_key_count"] == 2
    assert result["ignored_secret_like_key_count"] == 1
    assert "REFRESH_SECRET_VALUE" not in serialized
    assert "IGNORED_SECRET_VALUE" not in serialized


def test_parse_env_line_accepts_export_and_spaces() -> None:
    assert parse_env_line(" export LIVE_TOKEN_REFRESH_ENABLED = 'true' ") == (
        "LIVE_TOKEN_REFRESH_ENABLED",
        "true",
    )


def test_scan_env_file_keys_reports_presence_without_values(tmp_path) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "KIS_ACCESS_" + "TOKEN=ACCESS_VALUE",
                "KIS_REFRESH_" + "TOKEN=<placeholder>",
                "UNRELATED_KEY=VISIBLE_BUT_UNREQUESTED",
            ]
        ),
        encoding="utf-8",
    )

    result = scan_env_file_keys(env_file, key_names=("KIS_ACCESS_TOKEN", "KIS_REFRESH_TOKEN"))
    serialized = json.dumps(result, ensure_ascii=False, sort_keys=True)

    assert result["ok"] is True
    assert result["key_presence"]["KIS_ACCESS_TOKEN"] is True
    assert result["key_presence"]["KIS_REFRESH_TOKEN"] is False
    assert result["configured_count"] == 1
    assert "ACCESS_VALUE" not in serialized
    assert "VISIBLE_BUT_UNREQUESTED" not in serialized
