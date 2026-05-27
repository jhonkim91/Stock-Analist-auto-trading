from __future__ import annotations

import json

from tools import live_canary_preflight


def test_live_canary_preflight_is_blocked_and_redacted_by_default() -> None:
    env = {
        "KIS_APP_KEY": "PHASE20_SENTINEL_SECRET",
        "KIS_APP_SECRET": "PHASE20_SENTINEL_SECRET",
        "KIS_ACCOUNT_NO": "12345678",
    }

    record = live_canary_preflight.build_live_canary_preflight(env)
    serialized = json.dumps(record, ensure_ascii=False)

    assert record["status"] == "blocked"
    assert record["canary_execution_allowed"] is False
    assert record["network_call_performed"] is False
    assert record["live_order_created"] is False
    assert record["secrets_redacted"] is True
    assert record["credential_fields"]["KIS_APP_KEY"]["configured"] is True
    assert "PHASE20_SENTINEL_SECRET" not in serialized
    assert "12345678" not in serialized
    assert "LIVE_SUBMIT_NOT_IMPLEMENTED" in record["blockers"]
    assert "KIS_LIVE_ORDER_ROUTE_ABSENT" in record["blockers"]


def test_live_canary_preflight_still_blocks_with_operator_gates_set() -> None:
    env = {
        "LIVE_CANARY_CONFIRMATION": live_canary_preflight.CONFIRMATION_TOKEN,
        "LIVE_CANARY_REVIEWER": "reviewer@example.invalid",
        "LIVE_CANARY_ENVIRONMENT": "prod-live-isolated",
        "LIVE_CANARY_ROLLBACK_READY": "true",
        "LIVE_CANARY_KILL_SWITCH_READY": "true",
        "LIVE_CANARY_MINIMUM_SIZE_CONFIRMED": "true",
    }

    record = live_canary_preflight.build_live_canary_preflight(env)

    assert all(record["operator_gates"].values())
    assert record["canary_execution_allowed"] is False
    assert record["live_adapter_status"]["enabled"] is False
    assert record["public_route_checks"]["kis_order_route_present"] is False
    assert "KIS_LIVE_BROKER_DISABLED_PLACEHOLDER" in record["blockers"]


def test_live_canary_preflight_blocks_accidental_live_enablement() -> None:
    record = live_canary_preflight.build_live_canary_preflight(
        {
            "ENABLE_LIVE_SUBMIT": "true",
            "LIVE_FALLBACK_ENABLED": "true",
        }
    )

    assert "ENABLE_LIVE_SUBMIT_MUST_REMAIN_UNSET_IN_CURRENT_SCAFFOLD" in record["blockers"]
    assert "LIVE_FALLBACK_FORBIDDEN" in record["blockers"]
