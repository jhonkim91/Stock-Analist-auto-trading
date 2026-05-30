from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.kis_live_broker_adapter import KisLiveBrokerAdapter  # noqa: E402
from backend.app.services.kis_live_token_refresh_service import (  # noqa: E402
    KIS_LIVE_BASE_URL_ENV,
    KIS_REFRESH_TOKEN_ENV,
    LIVE_CANARY_ENVIRONMENT_ENV,
    LIVE_TOKEN_REFRESH_CONFIRMATION_ENV,
    LIVE_TOKEN_REFRESH_ENABLED_ENV,
    LIVE_TOKEN_REFRESH_NETWORK_ENABLED_ENV,
    LIVE_TOKEN_REFRESH_PROCESS_ONLY_ENV,
)
from backend.app.services.kis_token_manager import (  # noqa: E402
    ENABLE_REAL_ORDER_ENV,
    KIS_APP_KEY_ENV,
    KIS_APP_SECRET_ENV,
)
from backend.app.services.live_canary_governance_service import (  # noqa: E402
    REQUIRED_CONFIRMATION_ENV,
    REQUIRED_ENVIRONMENT_ENV,
    REQUIRED_KILL_SWITCH_ENV,
    REQUIRED_MINIMUM_SIZE_ENV,
    REQUIRED_REVIEWER_ENV,
    REQUIRED_ROLLBACK_ENV,
    LiveCanaryGovernanceService,
)
from backend.app.services.live_order_safety_service import LiveOrderSafetyService  # noqa: E402
from tools.env_file_loader import load_env_file  # noqa: E402

CONFIRM_LIVE_AUTHORITY_APPROVAL = "CONFIRM_LIVE_AUTHORITY_APPROVAL"
DEFAULT_RECORD_PATH = PROJECT_ROOT / "docs" / "research" / "live-authority-approval-record.json"
ENV_FILE_KEYS = (
    ENABLE_REAL_ORDER_ENV,
    KIS_APP_KEY_ENV,
    KIS_APP_SECRET_ENV,
    KIS_LIVE_BASE_URL_ENV,
    KIS_REFRESH_TOKEN_ENV,
    LIVE_CANARY_ENVIRONMENT_ENV,
    LIVE_TOKEN_REFRESH_CONFIRMATION_ENV,
    LIVE_TOKEN_REFRESH_ENABLED_ENV,
    LIVE_TOKEN_REFRESH_NETWORK_ENABLED_ENV,
    LIVE_TOKEN_REFRESH_PROCESS_ONLY_ENV,
    REQUIRED_CONFIRMATION_ENV,
    REQUIRED_REVIEWER_ENV,
    REQUIRED_ENVIRONMENT_ENV,
    REQUIRED_ROLLBACK_ENV,
    REQUIRED_KILL_SWITCH_ENV,
    REQUIRED_MINIMUM_SIZE_ENV,
    "LIVE_EMERGENCY_STOP_ARMED",
    "LIVE_RATE_LIMIT_PER_SECOND",
    "LIVE_RATE_LIMIT_BURST",
    "LIVE_IDEMPOTENCY_REQUIRED",
    "LIVE_AUDIT_LOG_ENABLED",
    "LIVE_AUDIT_REDACTION_ENABLED",
    "LIVE_MAX_ORDER_NOTIONAL",
    "LIVE_BLACKLIST_ENABLED",
    "LIVE_SYMBOL_BLACKLIST",
    "LIVE_ORDER_COOLDOWN_SECONDS",
)


def build_record(
    *,
    approve: bool,
    confirm: str,
    operations: str,
    env: Mapping[str, str] | None = None,
    env_file_load_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """live submit/cancel authority 승인 증거를 네트워크 없이 redacted record로 만든다."""
    current_env = os.environ if env is None else env
    requested_operations = _parse_operations(operations)
    governance = LiveCanaryGovernanceService(current_env, project_root=PROJECT_ROOT).evaluate()
    safety = LiveOrderSafetyService(current_env).preflight()
    adapter_status = KisLiveBrokerAdapter().status()
    approval_requested = bool(approve and confirm == CONFIRM_LIVE_AUTHORITY_APPROVAL)
    blockers = _approval_blockers(
        approval_requested=approval_requested,
        requested_operations=requested_operations,
        governance=governance,
        safety=safety,
        adapter_status=adapter_status,
        env=current_env,
    )
    approved = not blockers
    operator_gates = dict(governance.get("operator_gates") or {})
    record: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "approval_ready" if approved else "approval_blocked",
        "approve_requested": bool(approve),
        "approve_confirmed": approval_requested,
        "operations": sorted(f"live_{operation}_authority" for operation in requested_operations),
        "authority_approved": approved,
        "separate_user_approval": approval_requested,
        "reviewer_present": bool(governance.get("reviewer_present")),
        "reviewer_fingerprint": governance.get("reviewer_fingerprint"),
        "environment_is_prod_live_isolated": bool(operator_gates.get("environment_is_prod_live")),
        "rollback_ready": bool(operator_gates.get("rollback_ready")),
        "kill_switch_ready": bool(operator_gates.get("kill_switch_ready")),
        "minimum_size_confirmed": bool(operator_gates.get("minimum_size_confirmed")),
        "governance": governance,
        "safety_controls": safety,
        "adapter_boundary": {
            "enabled": bool(adapter_status.get("enabled")),
            "can_submit": bool(adapter_status.get("can_submit")),
            "can_cancel": bool(adapter_status.get("can_cancel")),
            "network_enabled": bool(adapter_status.get("network_enabled")),
            "submit_implementation_present": bool(adapter_status.get("submit_implementation_present")),
            "cancel_implementation_present": bool(adapter_status.get("cancel_implementation_present")),
            "authority_contract": adapter_status.get("authority_contract"),
        },
        "approval_blockers": blockers,
        "network_call_performed": False,
        "live_order_created": False,
        "order_cancelled": False,
        "secrets_redacted": True,
    }
    if env_file_load_result is not None:
        record["env_file_load"] = dict(env_file_load_result)
    return record


def write_record(record: Mapping[str, Any], path: Path = DEFAULT_RECORD_PATH) -> Path:
    """live authority approval preflight record를 raw secret 없이 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(record), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_parser() -> argparse.ArgumentParser:
    """live authority approval preflight CLI parser를 생성한다."""
    parser = argparse.ArgumentParser(description="No-network live authority approval preflight")
    parser.add_argument("--approve", action="store_true", help="record explicit submit/cancel authority approval")
    parser.add_argument("--confirm", default="", help="must equal CONFIRM_LIVE_AUTHORITY_APPROVAL for --approve")
    parser.add_argument("--operations", default="submit,cancel", help="comma-separated operations: submit,cancel")
    parser.add_argument(
        "--load-env-local",
        action="store_true",
        help="load allowlisted keys from .env.local into this helper process only",
    )
    parser.add_argument("--env-file", default=".env.local", help="env file path used with --load-env-local")
    parser.add_argument("--env-file-override", action="store_true", help="override existing process env values")
    parser.add_argument("--write-record", action="store_true", help="write redacted authority approval record")
    parser.add_argument("--record-path", default=str(DEFAULT_RECORD_PATH), help="optional output path")
    parser.add_argument("--fail-on-blocked", action="store_true", help="exit 2 when approval is blocked")
    return parser


def main(argv: list[str] | None = None) -> int:
    """live authority approval preflight를 실행하고 raw secret 없이 JSON으로 출력한다."""
    parser = build_parser()
    args = parser.parse_args(argv)
    env_file_load_result = (
        load_env_file(
            Path(args.env_file),
            allowed_keys=ENV_FILE_KEYS,
            override=bool(args.env_file_override),
            project_root=PROJECT_ROOT,
        )
        if args.load_env_local
        else None
    )
    record = build_record(
        approve=bool(args.approve),
        confirm=str(args.confirm),
        operations=str(args.operations),
        env_file_load_result=env_file_load_result,
    )
    if args.write_record:
        write_record(record, Path(args.record_path))
    print(json.dumps(record, ensure_ascii=False, sort_keys=True, default=str))
    if args.fail_on_blocked and not record["authority_approved"]:
        return 2
    return 0


def _approval_blockers(
    *,
    approval_requested: bool,
    requested_operations: set[str],
    governance: Mapping[str, Any],
    safety: Mapping[str, Any],
    adapter_status: Mapping[str, Any],
    env: Mapping[str, str],
) -> list[str]:
    blockers: list[str] = []
    if not approval_requested:
        blockers.append("LIVE_AUTHORITY_APPROVAL_CONFIRMATION_REQUIRED")
    if not requested_operations:
        blockers.append("LIVE_AUTHORITY_OPERATION_REQUIRED")
    if "submit" in requested_operations and not bool(adapter_status.get("submit_implementation_present")):
        blockers.append("LIVE_SUBMIT_IMPLEMENTATION_REQUIRED")
    if "cancel" in requested_operations and not bool(adapter_status.get("cancel_implementation_present")):
        blockers.append("LIVE_CANCEL_IMPLEMENTATION_REQUIRED")
    if bool(adapter_status.get("enabled")) or bool(adapter_status.get("network_enabled")):
        blockers.append("LIVE_ADAPTER_MUST_REMAIN_DISABLED_FOR_AUTHORITY_APPROVAL_PREFLIGHT")
    if _env_true(env.get(ENABLE_REAL_ORDER_ENV, "")):
        blockers.append("ENABLE_REAL_ORDER_MUST_BE_FALSE_FOR_AUTHORITY_APPROVAL_PREFLIGHT")
    blockers.extend(str(item) for item in governance.get("blockers", []) or [])
    blockers.extend(str(item) for item in safety.get("blockers", []) or [])
    return sorted(set(blockers))


def _parse_operations(value: str) -> set[str]:
    operations: set[str] = set()
    for item in str(value or "").replace(";", ",").split(","):
        normalized = item.strip().lower()
        if normalized in {"both", "submit_cancel", "submit+cancel"}:
            operations.update({"submit", "cancel"})
        elif normalized in {"submit", "cancel"}:
            operations.add(normalized)
    return operations


def _env_true(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    raise SystemExit(main())
