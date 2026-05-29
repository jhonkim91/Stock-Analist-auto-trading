from __future__ import annotations

import json
from datetime import UTC, datetime

from backend.app.services.live_order_safety_service import LiveOrderSafetyService


def test_live_order_safety_preflight_blocks_by_default_and_redacts_values() -> None:
    record = LiveOrderSafetyService(
        {
            "KIS_APP_SECRET": "LIVE_SAFETY_SENTINEL_SECRET",
            "LIVE_SYMBOL_BLACKLIST": "SENTINEL_SECRET_SYMBOL",
        }
    ).preflight()
    serialized = json.dumps(record, ensure_ascii=False)

    assert record["all_required_controls_passed"] is False
    assert "LIVE_KILL_SWITCH_READY_REQUIRED" in record["blockers"]
    assert "LIVE_RATE_LIMIT_PER_SECOND_REQUIRED" in record["blockers"]
    assert "LIVE_IDEMPOTENCY_REQUIRED_FLAG_MISSING" in record["blockers"]
    assert "LIVE_TOKEN_REFRESH_NETWORK_IMPLEMENTATION_ABSENT" in record["blockers"]
    assert record["live_order_created"] is False
    assert record["network_call_performed"] is False
    assert "LIVE_SAFETY_SENTINEL_SECRET" not in serialized
    assert "SENTINEL_SECRET_SYMBOL" not in serialized


def test_live_order_safety_preflight_accepts_configured_controls_except_live_token_refresh() -> None:
    record = LiveOrderSafetyService(
        {
            "LIVE_CANARY_KILL_SWITCH_READY": "true",
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
        }
    ).preflight()

    assert record["required_controls"]["kill_switch"]["passed"] is True
    assert record["required_controls"]["rate_limiter"]["passed"] is True
    assert record["required_controls"]["idempotency_key"]["passed"] is True
    assert record["required_controls"]["audit_log"]["passed"] is True
    assert record["required_controls"]["max_order_notional"]["passed"] is True
    assert record["required_controls"]["blacklist"]["passed"] is True
    assert record["required_controls"]["cooldown"]["passed"] is True
    assert record["required_controls"]["token_refresh"]["passed"] is False
    assert record["all_required_controls_passed"] is False
    assert record["blockers"] == ["LIVE_TOKEN_REFRESH_NETWORK_IMPLEMENTATION_ABSENT"]


def test_live_order_safety_preflight_rejects_unsafe_rate_and_notional_caps() -> None:
    record = LiveOrderSafetyService(
        {
            "LIVE_RATE_LIMIT_PER_SECOND": "25",
            "LIVE_RATE_LIMIT_BURST": "100",
            "LIVE_MAX_ORDER_NOTIONAL": "5000000",
        }
    ).preflight()

    assert "LIVE_RATE_LIMIT_PER_SECOND_TOO_HIGH" in record["blockers"]
    assert "LIVE_RATE_LIMIT_BURST_TOO_HIGH" in record["blockers"]
    assert "LIVE_MAX_ORDER_NOTIONAL_TOO_HIGH_FOR_CANARY" in record["blockers"]


def test_live_order_safety_evaluates_order_specific_controls_without_live_side_effects() -> None:
    record = LiveOrderSafetyService(
        {
            "LIVE_CANARY_KILL_SWITCH_READY": "true",
            "LIVE_EMERGENCY_STOP_ARMED": "true",
            "LIVE_RATE_LIMIT_PER_SECOND": "2",
            "LIVE_RATE_LIMIT_BURST": "5",
            "LIVE_IDEMPOTENCY_REQUIRED": "true",
            "LIVE_AUDIT_LOG_ENABLED": "true",
            "LIVE_AUDIT_REDACTION_ENABLED": "true",
            "LIVE_MAX_ORDER_NOTIONAL": "100000",
            "LIVE_BLACKLIST_ENABLED": "true",
            "LIVE_SYMBOL_BLACKLIST": "BLOCKED",
            "LIVE_ORDER_COOLDOWN_SECONDS": "60",
            "LIVE_LAST_ORDER_SYMBOL": "AAPL",
            "LIVE_LAST_ORDER_TS": datetime.now(UTC).isoformat(),
            "LIVE_TOKEN_REFRESH_ENABLED": "true",
            "LIVE_TOKEN_REFRESH_PROCESS_ONLY": "true",
        }
    ).evaluate_order_request(
        symbol="AAPL",
        side="buy",
        qty=2,
        limit_price=60000.0,
        idempotency_key=None,
    )

    assert record["decision"] == "deny"
    assert record["live_order_created"] is False
    assert record["network_call_performed"] is False
    assert "LIVE_ORDER_IDEMPOTENCY_KEY_REQUIRED" in record["request_blockers"]
    assert "LIVE_ORDER_NOTIONAL_EXCEEDS_LIMIT" in record["request_blockers"]
    assert "LIVE_ORDER_COOLDOWN_ACTIVE" in record["request_blockers"]
    assert "LIVE_TOKEN_REFRESH_NETWORK_IMPLEMENTATION_ABSENT" in record["blockers"]


def test_live_order_safety_blocks_blacklisted_symbol() -> None:
    record = LiveOrderSafetyService(
        {
            "LIVE_SYMBOL_BLACKLIST": "BLOCKED,OTHER",
        }
    ).evaluate_order_request(
        symbol="blocked",
        side="sell",
        qty=1,
        limit_price=10.0,
        idempotency_key="safe-key",
    )

    assert "LIVE_ORDER_SYMBOL_BLACKLISTED" in record["request_blockers"]
