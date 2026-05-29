from __future__ import annotations

import json

from tools.env_file_loader import load_env_file, scan_env_file_keys
from tools import live_phase3_completion_audit
from backend.tests.test_token_diagnostics import _fake_jwt


def test_live_phase3_completion_audit_is_incomplete_and_redacted_by_default() -> None:
    env = {
        "KIS_APP_KEY": "PHASE3_COMPLETION_SECRET",
        "KIS_APP_SECRET": "PHASE3_COMPLETION_SECRET",
        "KIS_ACCOUNT_NO": "12345678",
    }

    record = live_phase3_completion_audit.build_completion_audit(env)
    serialized = json.dumps(record, ensure_ascii=False, default=str)

    assert record["complete"] is False
    assert record["live_order_created"] is False
    assert record["network_call_performed_by_audit"] is False
    assert record["secrets_redacted"] is True
    assert "token_refresh_real_call_proof" in record["missing_requirements"]
    assert "live_submit_authority_present" in record["missing_requirements"]
    assert record["env_scope_status"]["KIS_REFRESH_TOKEN"]["process_configured"] is False
    assert "KIS_REFRESH_TOKEN" in record["missing_process_env_names"]
    assert "PHASE3_COMPLETION_SECRET" not in serialized
    assert "12345678" not in serialized


def test_live_phase3_completion_audit_powershell_template_is_placeholder_only(tmp_path) -> None:
    template = live_phase3_completion_audit.build_powershell_env_template()

    assert '$env:KIS_REFRESH_TOKEN = "<kis_refresh_token_from_authorization_code_flow>"' in template
    assert '$env:ENABLE_REAL_ORDER = "false"' in template
    assert "CONFIRM_KIS_LIVE_TOKEN_REFRESH" in template
    assert "tools\\kis_live_token_refresh_preflight.py --execute" in template
    assert "PHASE3_COMPLETION_SECRET" not in template

    path = tmp_path / "phase3-template.ps1"
    written = live_phase3_completion_audit.write_powershell_env_template(path)

    assert written.read_text(encoding="utf-8") == template


def test_live_phase3_completion_audit_keeps_submit_authority_missing_even_with_operator_gates() -> None:
    env = {
        "LIVE_CANARY_CONFIRMATION": "CONFIRM_LIVE_CANARY_PHASE20",
        "LIVE_CANARY_REVIEWER": "reviewer@example.invalid",
        "LIVE_CANARY_ENVIRONMENT": "prod-live-isolated",
        "LIVE_CANARY_ROLLBACK_READY": "true",
        "LIVE_CANARY_KILL_SWITCH_READY": "true",
        "LIVE_CANARY_MINIMUM_SIZE_CONFIRMED": "true",
        "LIVE_EMERGENCY_STOP_ARMED": "true",
        "LIVE_RATE_LIMIT_PER_SECOND": "2",
        "LIVE_RATE_LIMIT_BURST": "5",
        "LIVE_IDEMPOTENCY_REQUIRED": "true",
        "LIVE_AUDIT_LOG_ENABLED": "true",
        "LIVE_AUDIT_REDACTION_ENABLED": "true",
        "LIVE_MAX_ORDER_NOTIONAL": "100000",
        "LIVE_BLACKLIST_ENABLED": "true",
        "LIVE_SYMBOL_BLACKLIST": "LEVERAGED,INVERSE",
        "LIVE_ORDER_COOLDOWN_SECONDS": "30",
        "LIVE_TOKEN_REFRESH_ENABLED": "true",
        "LIVE_TOKEN_REFRESH_PROCESS_ONLY": "true",
        "LIVE_TOKEN_REFRESH_NETWORK_ENABLED": "true",
        "KIS_LIVE_BASE_URL": "https://openapi.koreainvestment.com:9443",
        "KIS_APP_KEY": "key",
        "KIS_APP_SECRET": "secret",
        "KIS_REFRESH_TOKEN": "refresh",
        "ENABLE_REAL_ORDER": "false",
    }
    token_record = {
        "network_call_performed": True,
        "live_order_created": False,
        "secrets_redacted": True,
        "result": {"token_refreshed": True},
        "status": {"reason_codes": []},
    }

    record = live_phase3_completion_audit.build_completion_audit(env, token_refresh_record=token_record)

    assert record["requirements"]["token_refresh_real_call_proof"] is True
    assert record["requirements"]["kill_switch_ready"] is True
    assert record["env_scope_status"]["KIS_REFRESH_TOKEN"]["process_configured"] is True
    assert "KIS_REFRESH_TOKEN" not in record["missing_process_env_names"]
    assert record["complete"] is False
    assert "live_submit_authority_present" in record["missing_requirements"]
    assert "live_cancel_authority_present" in record["missing_requirements"]


def test_live_phase3_completion_audit_can_write_redacted_record(tmp_path) -> None:
    record = live_phase3_completion_audit.build_completion_audit({})
    path = tmp_path / "phase3-audit.json"

    written = live_phase3_completion_audit.write_completion_audit(record, path)
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert payload["complete"] is False
    assert payload["live_order_created"] is False
    assert payload["network_call_performed_by_audit"] is False


def test_live_phase3_completion_audit_can_use_env_file_loader_without_raw_secret(tmp_path) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "KIS_APP_" + "KEY=VALUE_A",
                "KIS_APP_" + "SECRET=VALUE_B",
                "KIS_REFRESH_" + "TOKEN = VALUE_C",
                "LIVE_TOKEN_REFRESH_ENABLED=true",
                "LIVE_TOKEN_REFRESH_PROCESS_ONLY=true",
                "LIVE_TOKEN_REFRESH_NETWORK_ENABLED=false",
                "ENABLE_REAL_ORDER=false",
            ]
        ),
        encoding="utf-8",
    )
    target: dict[str, str] = {}
    load_result = load_env_file(
        env_file,
        allowed_keys=live_phase3_completion_audit.REQUIRED_ENV_NAMES,
        target=target,
    )

    record = live_phase3_completion_audit.build_completion_audit(
        target,
        env_file_load_result=load_result,
    )
    serialized = json.dumps(record, ensure_ascii=False, default=str)

    assert record["env_scope_status"]["KIS_REFRESH_TOKEN"]["process_configured"] is True
    assert "KIS_REFRESH_TOKEN" not in record["missing_process_env_names"]
    assert record["network_call_performed_by_audit"] is False
    assert record["live_order_created"] is False
    assert record["env_file_load"]["loaded_secret_like_key_count"] == 6
    assert "VALUE_A" not in serialized
    assert "VALUE_B" not in serialized
    assert "VALUE_C" not in serialized


def test_live_phase3_completion_audit_identifies_access_token_without_refresh_token(tmp_path) -> None:
    env_file = tmp_path / ".env.local"
    access_token = _fake_jwt({"exp": 1_700_000_000})
    env_file.write_text("KIS_ACCESS_" + f"TOKEN={access_token}\n", encoding="utf-8")
    presence = scan_env_file_keys(
        env_file,
        key_names=live_phase3_completion_audit.TOKEN_DIAGNOSTIC_ENV_NAMES,
    )

    record = live_phase3_completion_audit.build_completion_audit(
        {},
        env_file_presence_result=presence,
        env_file_access_token=access_token,
    )
    serialized = json.dumps(record, ensure_ascii=False, default=str)

    assert record["token_env_diagnostics"]["access_token_configured"] is True
    assert record["token_env_diagnostics"]["refresh_token_configured"] is False
    assert record["token_env_diagnostics"]["access_token_without_refresh_token"] is True
    assert record["token_env_diagnostics"]["access_token_expired"] is True
    assert record["network_call_performed_by_audit"] is False
    assert record["live_order_created"] is False
    assert access_token not in serialized
