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

from tools import kis_live_token_refresh_preflight, live_canary_preflight  # noqa: E402

DEFAULT_RECORD_PATH = PROJECT_ROOT / "docs" / "research" / "live-phase3-completion-audit.json"


def build_completion_audit(
    env: Mapping[str, str] | None = None,
    *,
    token_refresh_record: Mapping[str, Any] | None = None,
    canary_record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """실계좌 주문 연동 3단계 완료 여부를 네트워크 없이 항목별로 판정한다."""
    current_env = os.environ if env is None else env
    token_record = dict(token_refresh_record or _preview_token_refresh_record())
    canary = dict(canary_record or live_canary_preflight.build_live_canary_preflight(current_env))
    safety_controls = dict(canary.get("safety_controls") or {})
    control_checks = dict(safety_controls.get("required_controls") or {})
    public_route_checks = dict(canary.get("public_route_checks") or {})
    live_adapter_status = dict(canary.get("live_adapter_status") or {})

    requirements = {
        "kill_switch_ready": _control_passed(control_checks, "kill_switch"),
        "rate_limiter_ready": _control_passed(control_checks, "rate_limiter"),
        "idempotency_required": _control_passed(control_checks, "idempotency_key"),
        "audit_log_ready": _control_passed(control_checks, "audit_log"),
        "max_order_notional_ready": _control_passed(control_checks, "max_order_notional"),
        "blacklist_ready": _control_passed(control_checks, "blacklist"),
        "cooldown_ready": _control_passed(control_checks, "cooldown"),
        "token_refresh_control_ready": _control_passed(control_checks, "token_refresh"),
        "token_refresh_real_call_proof": _token_refresh_proof_passed(token_record),
        "live_public_route_scaffold_present": bool(public_route_checks.get("api_live_route_present"))
        and bool(public_route_checks.get("kis_order_route_present")),
        "live_broker_route_not_public": not bool(public_route_checks.get("kis_broker_route_present")),
        "live_websocket_route_not_public": not bool(public_route_checks.get("kis_websocket_route_present")),
        "live_submit_authority_present": bool(live_adapter_status.get("enabled"))
        and bool(live_adapter_status.get("can_submit"))
        and bool(live_adapter_status.get("network_enabled"))
        and bool(canary.get("canary_execution_allowed")),
        "live_cancel_authority_present": bool(live_adapter_status.get("enabled"))
        and bool(live_adapter_status.get("can_cancel"))
        and bool(live_adapter_status.get("network_enabled"))
        and bool(canary.get("canary_execution_allowed")),
        "no_live_order_created_during_audit": not bool(canary.get("live_order_created"))
        and not bool(token_record.get("live_order_created")),
        "no_order_cancelled_during_audit": not bool(canary.get("order_cancelled")),
        "secrets_redacted": bool(canary.get("secrets_redacted")) and bool(token_record.get("secrets_redacted")),
    }
    missing_requirements = [name for name, passed in requirements.items() if not passed]
    blocker_sources = {
        "canary_blockers": sorted(set(str(item) for item in canary.get("blockers", []) or [])),
        "safety_blockers": sorted(set(str(item) for item in safety_controls.get("blockers", []) or [])),
        "token_refresh_blockers": sorted(
            set(str(item) for item in (token_record.get("status", {}) or {}).get("reason_codes", []) or [])
        ),
    }
    return {
        "phase": "3단계 실계좌 주문 연동",
        "generated_at": datetime.now(UTC).isoformat(),
        "complete": not missing_requirements,
        "requirements": requirements,
        "missing_requirements": missing_requirements,
        "blocker_sources": blocker_sources,
        "canary_status": canary.get("status"),
        "canary_execution_allowed": bool(canary.get("canary_execution_allowed")),
        "token_refresh_network_call_performed": bool(token_record.get("network_call_performed")),
        "live_order_created": False,
        "network_call_performed_by_audit": False,
        "secrets_redacted": bool(requirements["secrets_redacted"]),
        "next_required_action": _next_required_action(missing_requirements),
    }


def write_completion_audit(record: Mapping[str, Any], path: Path = DEFAULT_RECORD_PATH) -> Path:
    """3단계 완료 감사 record를 raw secret 없이 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(record), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_parser() -> argparse.ArgumentParser:
    """3단계 completion audit CLI parser를 생성한다."""
    parser = argparse.ArgumentParser(description="No-network live Phase 3 completion audit")
    parser.add_argument("--write-record", action="store_true", help="write redacted audit under docs/research")
    parser.add_argument("--record-path", default=str(DEFAULT_RECORD_PATH), help="optional output path")
    parser.add_argument("--fail-on-incomplete", action="store_true", help="exit 2 when Phase 3 is incomplete")
    return parser


def main(argv: list[str] | None = None) -> int:
    """3단계 완료 여부를 판정하고 raw secret 없이 JSON으로 출력한다."""
    parser = build_parser()
    args = parser.parse_args(argv)
    record = build_completion_audit()
    if args.write_record:
        write_completion_audit(record, Path(args.record_path))
    print(json.dumps(record, ensure_ascii=False, sort_keys=True, default=str))
    if args.fail_on_incomplete and not record["complete"]:
        return 2
    return 0


def _preview_token_refresh_record() -> dict[str, Any]:
    return kis_live_token_refresh_preflight.build_record(
        execute=False,
        confirm="",
        install_to_process_env=False,
    )


def _control_passed(controls: Mapping[str, Any], name: str) -> bool:
    control = controls.get(name)
    return bool(isinstance(control, Mapping) and control.get("passed"))


def _token_refresh_proof_passed(record: Mapping[str, Any]) -> bool:
    result = record.get("result") if isinstance(record.get("result"), Mapping) else {}
    return (
        bool(record.get("network_call_performed"))
        and bool(result.get("token_refreshed"))
        and bool(record.get("secrets_redacted"))
        and not bool(record.get("live_order_created"))
    )


def _next_required_action(missing_requirements: list[str]) -> str:
    if not missing_requirements:
        return "3단계 완료 조건이 모두 충족됐다. 별도 승인된 운영 절차에 따라 최종 검증 후 단계 완료 커밋을 남긴다."
    if "token_refresh_real_call_proof" in missing_requirements:
        return "KIS_REFRESH_TOKEN과 live token refresh gate를 process env에 주입한 뒤 별도 승인된 token refresh proof를 먼저 생성한다."
    if "live_submit_authority_present" in missing_requirements:
        return "실제 live submit/cancel authority는 별도 사용자 승인과 운영 canary 조건이 충족될 때만 구현/활성화한다."
    return "missing_requirements를 순서대로 해소한 뒤 completion audit을 재실행한다."


if __name__ == "__main__":
    raise SystemExit(main())
