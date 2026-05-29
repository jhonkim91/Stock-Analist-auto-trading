from __future__ import annotations

import json

from backend.app.services.live_canary_governance_service import (
    CONFIRMATION_TOKEN,
    LiveCanaryGovernanceService,
)


def test_live_canary_governance_blocks_by_default_without_network_calls(tmp_path) -> None:
    record = LiveCanaryGovernanceService({}, project_root=tmp_path).evaluate()

    assert record["passed"] is False
    assert "CONFIRMATION_REQUIRED" in record["blockers"]
    assert "REVIEWER_PRESENT_REQUIRED" in record["blockers"]
    assert "ROLLBACK_RUNBOOK_PRESENT_REQUIRED" in record["blockers"]
    assert record["network_call_performed"] is False
    assert record["live_order_created"] is False


def test_live_canary_governance_accepts_reviewer_env_and_rollback_runbook(tmp_path) -> None:
    runbook = tmp_path / "docs" / "LIVE_CANARY_RUNBOOK.md"
    runbook.parent.mkdir(parents=True)
    runbook.write_text("## Rollback 절차\nLIVE_CANARY_ROLLBACK_READY=true\n", encoding="utf-8")
    env = {
        "LIVE_CANARY_CONFIRMATION": CONFIRMATION_TOKEN,
        "LIVE_CANARY_REVIEWER": "reviewer@example.invalid",
        "LIVE_CANARY_ENVIRONMENT": "prod-live-isolated",
        "LIVE_CANARY_ROLLBACK_READY": "true",
        "LIVE_CANARY_KILL_SWITCH_READY": "true",
        "LIVE_CANARY_MINIMUM_SIZE_CONFIRMED": "true",
    }

    record = LiveCanaryGovernanceService(env, project_root=tmp_path).evaluate()
    serialized = json.dumps(record, ensure_ascii=False)

    assert record["passed"] is True
    assert record["blockers"] == []
    assert record["operator_gates"]["rollback_runbook_present"] is True
    assert record["operator_gates"]["rollback_runbook_has_steps"] is True
    assert record["reviewer_fingerprint"]
    assert "reviewer@example.invalid" not in serialized
