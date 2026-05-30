from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import func, select

from backend.app.models.tables import BrokerAuditEvent, Order
from backend.app.services.live_order_safety_service import (
    LiveOrderAuditService,
    LiveOrderSafetyService,
    LiveRateLimiter,
)


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
    assert "LIVE_TOKEN_REFRESH_NETWORK_DISABLED" in record["blockers"]
    assert record["live_order_created"] is False
    assert record["network_call_performed"] is False
    assert "LIVE_SAFETY_SENTINEL_SECRET" not in serialized
    assert "SENTINEL_SECRET_SYMBOL" not in serialized


def test_live_order_safety_preflight_accepts_configured_controls_with_token_refresh_readiness() -> None:
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
            "LIVE_TOKEN_REFRESH_NETWORK_ENABLED": "true",
            "KIS_LIVE_BASE_URL": "https://openapi.koreainvestment.com:9443",
            "KIS_APP_KEY": "key",
            "KIS_APP_SECRET": "s3cr3t",
            "KIS_REFRESH_TOKEN": "rtok",
            "ENABLE_REAL_ORDER": "false",
        }
    ).preflight()

    assert record["required_controls"]["kill_switch"]["passed"] is True
    assert record["required_controls"]["rate_limiter"]["passed"] is True
    assert record["required_controls"]["idempotency_key"]["passed"] is True
    assert record["required_controls"]["audit_log"]["passed"] is True
    assert record["required_controls"]["max_order_notional"]["passed"] is True
    assert record["required_controls"]["blacklist"]["passed"] is True
    assert record["required_controls"]["cooldown"]["passed"] is True
    assert record["required_controls"]["token_refresh"]["passed"] is True
    assert record["all_required_controls_passed"] is True
    assert record["blockers"] == []


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
    assert "LIVE_TOKEN_REFRESH_NETWORK_DISABLED" in record["blockers"]
    assert record["control_checks"]["rate_limiter"]["network_call_performed"] is False
    assert record["control_checks"]["idempotency"]["key_fingerprint"] is None
    assert record["control_checks"]["audit"]["audit_event_persisted"] is False


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


def test_live_rate_limiter_consumes_tokens_without_network_side_effects() -> None:
    current = {"value": 100.0}

    def clock() -> float:
        return current["value"]

    limiter = LiveRateLimiter(per_second=2, burst=2, clock=clock)

    first = limiter.check(consume=True)
    second = limiter.check(consume=True)
    third = limiter.check(consume=True)

    assert first["passed"] is True
    assert second["passed"] is True
    assert third["passed"] is False
    assert third["reason_codes"] == ["LIVE_ORDER_RATE_LIMIT_EXCEEDED"]
    assert third["network_call_performed"] is False
    assert third["live_order_created"] is False

    current["value"] = 101.1
    assert limiter.check(consume=True)["passed"] is True


def test_live_order_safety_detects_duplicate_idempotency_key_from_orders(db_session) -> None:
    db_session.add(
        Order(
            order_id="live-duplicate-source",
            symbol="AAPL",
            side="buy",
            qty=1,
            price=10.0,
            status="preview_only",
            idempotency_key="duplicate-live-key",
        )
    )
    db_session.commit()

    record = LiveOrderSafetyService(
        {
            "LIVE_SYMBOL_BLACKLIST": "BLOCKED",
        },
        db=db_session,
    ).evaluate_order_request(
        symbol="AAPL",
        side="buy",
        qty=1,
        limit_price=10.0,
        idempotency_key="duplicate-live-key",
    )

    idempotency = record["control_checks"]["idempotency"]
    assert "LIVE_ORDER_IDEMPOTENCY_KEY_DUPLICATE" in record["request_blockers"]
    assert idempotency["existing_order_id"] == "live-duplicate-source"
    assert idempotency["key_fingerprint"] is not None
    assert "duplicate-live-key" not in json.dumps(record, ensure_ascii=False)


def test_live_order_audit_service_persists_redacted_event_only_when_called(db_session) -> None:
    service = LiveOrderAuditService(db_session)
    event = service.build_event(
        event_type="live_order_safety_test",
        decision="deny",
        reason_codes=["LIVE_ORDER_IDEMPOTENCY_KEY_REQUIRED"],
        payload={
            "symbol": "AAPL",
            "access_token": "SENTINEL_TOKEN",
            "account_no": "SENTINEL_ACCOUNT",
            "safe": "ok",
        },
    )
    assert event["audit_event_persisted"] is False
    assert "SENTINEL_TOKEN" not in json.dumps(event, ensure_ascii=False)
    assert "SENTINEL_ACCOUNT" not in json.dumps(event, ensure_ascii=False)

    persisted = service.persist_event(event)
    count = int(db_session.scalar(select(func.count()).select_from(BrokerAuditEvent)) or 0)
    row = db_session.scalar(select(BrokerAuditEvent).where(BrokerAuditEvent.event_type == "live_order_safety_test"))

    assert persisted["audit_event_persisted"] is True
    assert count == 1
    assert row is not None
    assert row.broker_name == "kis_live"
    assert row.decision == "deny"
    assert "SENTINEL_TOKEN" not in row.sanitized_payload_json
    assert "SENTINEL_ACCOUNT" not in row.sanitized_payload_json
