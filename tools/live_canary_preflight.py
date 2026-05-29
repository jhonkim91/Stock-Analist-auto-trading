from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.main import app
from backend.app.services.live_canary_governance_service import (
    CONFIRMATION_TOKEN,
    REQUIRED_CONFIRMATION_ENV,
    REQUIRED_ENVIRONMENT_ENV,
    REQUIRED_KILL_SWITCH_ENV,
    REQUIRED_MINIMUM_SIZE_ENV,
    REQUIRED_REVIEWER_ENV,
    REQUIRED_ROLLBACK_ENV,
    LiveCanaryGovernanceService,
)
from backend.app.services.live_order_safety_service import LiveOrderSafetyService
from backend.app.services.kis_live_broker_adapter import LIVE_DISABLED_REASON, KisLiveBrokerAdapter

DEFAULT_RECORD_PATH = PROJECT_ROOT / "docs" / "research" / "live-canary-phase20-preflight-record.json"
SENSITIVE_ENV_KEYS = (
    "KIS_APP_KEY",
    "KIS_APP_SECRET",
    "KIS_ACCESS_TOKEN",
    "KIS_ACCOUNT_NO",
    "KIS_PRODUCT_CODE",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
)


def build_live_canary_preflight(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Phase 20 live canary 가능 여부를 네트워크 없이 redacted payload로 평가한다."""
    current_env = os.environ if env is None else env
    route_paths = sorted(getattr(route, "path", "") for route in app.routes)
    live_adapter_status = KisLiveBrokerAdapter().status()
    safety_preflight = LiveOrderSafetyService(current_env).preflight()
    governance = LiveCanaryGovernanceService(current_env, project_root=PROJECT_ROOT).evaluate()
    operator_gates = governance["operator_gates"]
    public_route_checks = {
        "api_live_route_present": any(path.startswith("/api/live") for path in route_paths),
        "kis_order_route_present": any(path.startswith("/api/kis/orders") for path in route_paths),
        "kis_broker_route_present": any(path.startswith("/api/kis/broker") for path in route_paths),
        "kis_websocket_route_present": any(path.startswith("/api/kis/websocket") for path in route_paths),
    }
    blockers = list(governance["blockers"])
    blockers.extend(safety_preflight["blockers"])
    if not bool(live_adapter_status.get("enabled")):
        blockers.append(LIVE_DISABLED_REASON)
    if not bool(live_adapter_status.get("network_enabled")):
        blockers.append("LIVE_NETWORK_DISABLED")
    if not bool(live_adapter_status.get("submit_implementation_present")):
        blockers.append("LIVE_SUBMIT_NOT_IMPLEMENTED")
    elif not bool(live_adapter_status.get("can_submit")):
        blockers.append("LIVE_SUBMIT_DISABLED")
    if not bool(live_adapter_status.get("cancel_implementation_present")):
        blockers.append("LIVE_CANCEL_NOT_IMPLEMENTED")
    elif not bool(live_adapter_status.get("can_cancel")):
        blockers.append("LIVE_CANCEL_DISABLED")
    if not public_route_checks["api_live_route_present"]:
        blockers.append("LIVE_PUBLIC_ROUTE_ABSENT")
    if not public_route_checks["kis_order_route_present"]:
        blockers.append("KIS_LIVE_ORDER_ROUTE_ABSENT")
    if bool(current_env.get("ENABLE_LIVE_SUBMIT", "").strip().lower() in {"1", "true", "yes", "on"}):
        blockers.append("ENABLE_LIVE_SUBMIT_MUST_REMAIN_UNSET_IN_CURRENT_SCAFFOLD")
    if bool(current_env.get("LIVE_FALLBACK_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}):
        blockers.append("LIVE_FALLBACK_FORBIDDEN")

    canary_allowed = not blockers
    return {
        "phase": "Phase 20",
        "status": "ready" if canary_allowed else "blocked",
        "canary_execution_allowed": canary_allowed,
        "live_order_created": False,
        "order_cancelled": False,
        "network_call_performed": False,
        "endpoint_called": False,
        "secrets_redacted": True,
        "account_redacted": True,
        "generated_at": datetime.now(UTC).isoformat(),
        "operator_gates": operator_gates,
        "governance": governance,
        "safety_controls": safety_preflight,
        "public_route_checks": public_route_checks,
        "live_adapter_status": {
            "name": live_adapter_status.get("name"),
            "mode": live_adapter_status.get("mode"),
            "enabled": live_adapter_status.get("enabled"),
            "live_trading_enabled": live_adapter_status.get("live_trading_enabled"),
            "network_enabled": live_adapter_status.get("network_enabled"),
            "can_submit": live_adapter_status.get("can_submit"),
            "can_cancel": live_adapter_status.get("can_cancel"),
            "submit_implementation_present": live_adapter_status.get("submit_implementation_present"),
            "cancel_implementation_present": live_adapter_status.get("cancel_implementation_present"),
            "submit_network_enabled": live_adapter_status.get("submit_network_enabled"),
            "cancel_network_enabled": live_adapter_status.get("cancel_network_enabled"),
            "adapter_boundary": live_adapter_status.get("adapter_boundary"),
            "live_fallback_enabled": live_adapter_status.get("live_fallback_enabled"),
            "authority_contract": live_adapter_status.get("authority_contract"),
            "reason": live_adapter_status.get("reason"),
        },
        "credential_fields": {key: {"configured": _configured(current_env.get(key, ""))} for key in SENSITIVE_ENV_KEYS},
        "blockers": sorted(set(blockers)),
        "next_required_action": (
            "live canary execution remains blocked in this repository; the public route scaffold is disabled and "
            "requires separate live submit authority, reviewer, environment isolation, rollback proof, and token "
            "refresh proof before any live order network call"
        ),
    }


def write_preflight_record(record: dict[str, Any], path: Path = DEFAULT_RECORD_PATH) -> Path:
    """redacted Phase 20 preflight record를 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_parser() -> argparse.ArgumentParser:
    """Phase 20 live canary preflight CLI parser를 생성한다."""
    parser = argparse.ArgumentParser(description="Redacted, no-network Phase 20 live canary preflight")
    parser.add_argument("--write-record", action="store_true", help="write redacted record under docs/research")
    parser.add_argument("--record-path", default=str(DEFAULT_RECORD_PATH), help="optional output path for --write-record")
    parser.add_argument("--fail-on-blocked", action="store_true", help="exit 2 when canary is blocked")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Phase 20 preflight를 실행하고 raw secret 없이 JSON으로 출력한다."""
    parser = build_parser()
    args = parser.parse_args(argv)
    record = build_live_canary_preflight()
    if args.write_record:
        write_preflight_record(record, Path(args.record_path))
    print(json.dumps(record, ensure_ascii=False, sort_keys=True, default=str))
    if args.fail_on_blocked and not record["canary_execution_allowed"]:
        return 2
    return 0


def _configured(value: str | None) -> bool:
    return bool(value and value.strip() and value.strip().lower() not in {"changeme", "todo", "none", "null"})


if __name__ == "__main__":
    raise SystemExit(main())
