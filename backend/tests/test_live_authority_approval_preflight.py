from __future__ import annotations

import json

from tools import live_authority_approval_preflight, live_phase3_completion_audit


def test_live_authority_approval_preflight_is_blocked_and_redacted_by_default() -> None:
    env = {
        "KIS_APP_KEY": "LIVE_AUTHORITY_SENTINEL_SECRET",
        "KIS_APP_SECRET": "LIVE_AUTHORITY_SENTINEL_SECRET",
        "KIS_ACCOUNT_NO": "12345678",
    }

    record = live_authority_approval_preflight.build_record(
        approve=False,
        confirm="",
        operations="submit,cancel",
        env=env,
    )
    serialized = json.dumps(record, ensure_ascii=False, default=str)

    assert record["status"] == "approval_blocked"
    assert record["authority_approved"] is False
    assert record["network_call_performed"] is False
    assert record["live_order_created"] is False
    assert record["order_cancelled"] is False
    assert "LIVE_AUTHORITY_APPROVAL_CONFIRMATION_REQUIRED" in record["approval_blockers"]
    assert record["adapter_boundary"]["enabled"] is False
    assert record["adapter_boundary"]["network_enabled"] is False
    assert "LIVE_AUTHORITY_SENTINEL_SECRET" not in serialized
    assert "12345678" not in serialized


def test_live_authority_approval_preflight_records_approval_without_opening_adapter() -> None:
    record = live_authority_approval_preflight.build_record(
        approve=True,
        confirm=live_authority_approval_preflight.CONFIRM_LIVE_AUTHORITY_APPROVAL,
        operations="submit,cancel",
        env=_operator_ready_env(),
    )

    assert record["status"] == "approval_ready"
    assert record["authority_approved"] is True
    assert record["separate_user_approval"] is True
    assert record["reviewer_present"] is True
    assert record["environment_is_prod_live_isolated"] is True
    assert record["rollback_ready"] is True
    assert record["kill_switch_ready"] is True
    assert record["minimum_size_confirmed"] is True
    assert record["approval_blockers"] == []
    assert record["network_call_performed"] is False
    assert record["live_order_created"] is False
    assert record["order_cancelled"] is False
    assert record["adapter_boundary"]["enabled"] is False
    assert record["adapter_boundary"]["can_submit"] is False
    assert record["adapter_boundary"]["can_cancel"] is False


def test_completion_audit_consumes_authority_preflight_record_without_completing_phase(tmp_path) -> None:
    authority_record = live_authority_approval_preflight.build_record(
        approve=True,
        confirm=live_authority_approval_preflight.CONFIRM_LIVE_AUTHORITY_APPROVAL,
        operations="submit,cancel",
        env=_operator_ready_env(),
    )
    authority_path = tmp_path / "authority-record.json"
    live_authority_approval_preflight.write_record(authority_record, authority_path)
    loaded_record, source = live_phase3_completion_audit.load_authority_record(authority_path)
    token_record = {
        "network_call_performed": True,
        "live_order_created": False,
        "secrets_redacted": True,
        "result": {"token_refreshed": True},
        "status": {"reason_codes": []},
    }

    completion = live_phase3_completion_audit.build_completion_audit(
        _operator_ready_env(),
        token_refresh_record=token_record,
        authority_record=loaded_record,
        authority_record_source=source,
    )

    assert completion["live_authority_proof_record"]["submit_approval_proof_passed"] is True
    assert completion["live_authority_proof_record"]["cancel_approval_proof_passed"] is True
    assert completion["proof_gap_summary"]["submit_authority_approval_proof_recorded"] is True
    assert completion["proof_gap_summary"]["cancel_authority_approval_proof_recorded"] is True
    assert completion["requirements"]["token_refresh_real_call_proof"] is True
    assert completion["requirements"]["live_submit_authority_present"] is False
    assert completion["requirements"]["live_cancel_authority_present"] is False
    assert completion["complete"] is False


def test_live_authority_approval_preflight_rejects_real_order_enablement() -> None:
    env = _operator_ready_env()
    env["ENABLE_REAL_ORDER"] = "true"

    record = live_authority_approval_preflight.build_record(
        approve=True,
        confirm=live_authority_approval_preflight.CONFIRM_LIVE_AUTHORITY_APPROVAL,
        operations="submit,cancel",
        env=env,
    )

    assert record["authority_approved"] is False
    assert "ENABLE_REAL_ORDER_MUST_BE_FALSE_FOR_AUTHORITY_APPROVAL_PREFLIGHT" in record["approval_blockers"]
    assert record["network_call_performed"] is False
    assert record["live_order_created"] is False


def _operator_ready_env() -> dict[str, str]:
    return {
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
        "LIVE_TOKEN_REFRESH_CONFIRMATION": "CONFIRM_KIS_LIVE_TOKEN_REFRESH",
        "KIS_LIVE_BASE_URL": "https://openapi.koreainvestment.com:9443",
        "KIS_APP_KEY": "key",
        "KIS_APP_SECRET": "secret",
        "KIS_REFRESH_TOKEN": "refresh",
        "ENABLE_REAL_ORDER": "false",
    }
