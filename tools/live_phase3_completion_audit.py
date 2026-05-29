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

from backend.app.services.kis_token_manager import KIS_ACCESS_TOKEN_ENV  # noqa: E402
from tools.env_file_loader import load_env_file, scan_env_file_keys  # noqa: E402
from tools import kis_live_token_refresh_preflight, live_canary_preflight  # noqa: E402

DEFAULT_RECORD_PATH = PROJECT_ROOT / "docs" / "research" / "live-phase3-completion-audit.json"
DEFAULT_TEMPLATE_PATH = PROJECT_ROOT / "docs" / "research" / "live-phase3-process-env-template.ps1"
REQUIRED_ENV_NAMES = (
    "KIS_APP_KEY",
    "KIS_APP_SECRET",
    "KIS_LIVE_BASE_URL",
    "ENABLE_REAL_ORDER",
    "LIVE_TOKEN_REFRESH_ENABLED",
    "LIVE_TOKEN_REFRESH_PROCESS_ONLY",
    "LIVE_TOKEN_REFRESH_NETWORK_ENABLED",
    "LIVE_TOKEN_REFRESH_CONFIRMATION",
    "KIS_REFRESH_TOKEN",
    "LIVE_CANARY_CONFIRMATION",
    "LIVE_CANARY_REVIEWER",
    "LIVE_CANARY_ENVIRONMENT",
    "LIVE_CANARY_ROLLBACK_READY",
    "LIVE_CANARY_KILL_SWITCH_READY",
    "LIVE_CANARY_MINIMUM_SIZE_CONFIRMED",
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
TOKEN_DIAGNOSTIC_ENV_NAMES = (KIS_ACCESS_TOKEN_ENV, "KIS_REFRESH_TOKEN")
POWERSHELL_TEMPLATE_VALUES = (
    ("KIS_APP_KEY", "<kis_live_app_key>"),
    ("KIS_APP_SECRET", "<kis_live_app_credential>"),
    ("KIS_REFRESH_TOKEN", "<kis_refresh_token_from_authorization_code_flow>"),
    ("KIS_LIVE_BASE_URL", "https://openapi.koreainvestment.com:9443"),
    ("ENABLE_REAL_ORDER", "false"),
    ("LIVE_TOKEN_REFRESH_ENABLED", "true"),
    ("LIVE_TOKEN_REFRESH_PROCESS_ONLY", "true"),
    ("LIVE_TOKEN_REFRESH_NETWORK_ENABLED", "true"),
    ("LIVE_TOKEN_REFRESH_CONFIRMATION", "CONFIRM_KIS_LIVE_TOKEN_REFRESH"),
    ("LIVE_CANARY_CONFIRMATION", "CONFIRM_LIVE_CANARY_PHASE20"),
    ("LIVE_CANARY_REVIEWER", "<reviewer_id_no_secret>"),
    ("LIVE_CANARY_ENVIRONMENT", "prod-live-isolated"),
    ("LIVE_CANARY_ROLLBACK_READY", "true"),
    ("LIVE_CANARY_KILL_SWITCH_READY", "true"),
    ("LIVE_CANARY_MINIMUM_SIZE_CONFIRMED", "true"),
    ("LIVE_EMERGENCY_STOP_ARMED", "true"),
    ("LIVE_RATE_LIMIT_PER_SECOND", "2"),
    ("LIVE_RATE_LIMIT_BURST", "5"),
    ("LIVE_IDEMPOTENCY_REQUIRED", "true"),
    ("LIVE_AUDIT_LOG_ENABLED", "true"),
    ("LIVE_AUDIT_REDACTION_ENABLED", "true"),
    ("LIVE_MAX_ORDER_NOTIONAL", "100000"),
    ("LIVE_BLACKLIST_ENABLED", "true"),
    ("LIVE_SYMBOL_BLACKLIST", "LEVERAGED,INVERSE"),
    ("LIVE_ORDER_COOLDOWN_SECONDS", "30"),
)


def build_completion_audit(
    env: Mapping[str, str] | None = None,
    *,
    token_refresh_record: Mapping[str, Any] | None = None,
    canary_record: Mapping[str, Any] | None = None,
    env_file_load_result: Mapping[str, Any] | None = None,
    env_file_presence_result: Mapping[str, Any] | None = None,
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
    env_scope_status = _env_scope_status(REQUIRED_ENV_NAMES, current_env)
    record = {
        "phase": "3단계 실계좌 주문 연동",
        "generated_at": datetime.now(UTC).isoformat(),
        "complete": not missing_requirements,
        "requirements": requirements,
        "missing_requirements": missing_requirements,
        "blocker_sources": blocker_sources,
        "canary_status": canary.get("status"),
        "canary_execution_allowed": bool(canary.get("canary_execution_allowed")),
        "env_scope_status": env_scope_status,
        "missing_process_env_names": [
            name for name, status in env_scope_status.items() if not status["process_configured"]
        ],
        "missing_all_scopes_env_names": [
            name for name, status in env_scope_status.items() if not status["any_scope_configured"]
        ],
        "token_env_diagnostics": _token_env_diagnostics(current_env, env_scope_status, env_file_presence_result),
        "token_refresh_network_call_performed": bool(token_record.get("network_call_performed")),
        "live_order_created": False,
        "network_call_performed_by_audit": False,
        "secrets_redacted": bool(requirements["secrets_redacted"]),
        "next_required_action": _next_required_action(missing_requirements),
    }
    if env_file_load_result is not None:
        record["env_file_load"] = dict(env_file_load_result)
    return record


def write_completion_audit(record: Mapping[str, Any], path: Path = DEFAULT_RECORD_PATH) -> Path:
    """3단계 완료 감사 record를 raw secret 없이 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(record), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_powershell_env_template() -> str:
    """3단계 live proof 준비용 process-only PowerShell env template을 생성한다."""
    lines = [
        "# Live Phase 3 process-only environment template.",
        "# Replace placeholder values in a fresh PowerShell session. Do not commit real values.",
        "# This template does not run a network call or create an order.",
        "",
    ]
    lines.extend(f'$env:{name} = "{value}"' for name, value in POWERSHELL_TEMPLATE_VALUES)
    lines.extend(
        [
            "",
            "# No-network verification:",
            r".\.venv\Scripts\python.exe tools\live_phase3_completion_audit.py",
            r".\.venv\Scripts\python.exe tools\kis_live_token_refresh_preflight.py",
            "",
            "# Token refresh proof requires separate operator approval:",
            (
                r"# .\.venv\Scripts\python.exe tools\kis_live_token_refresh_preflight.py "
                "--execute --confirm CONFIRM_KIS_LIVE_TOKEN_REFRESH --write-record"
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def write_powershell_env_template(path: Path = DEFAULT_TEMPLATE_PATH) -> Path:
    """placeholder-only PowerShell env template을 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_powershell_env_template(), encoding="utf-8")
    return path


def build_parser() -> argparse.ArgumentParser:
    """3단계 completion audit CLI parser를 생성한다."""
    parser = argparse.ArgumentParser(description="No-network live Phase 3 completion audit")
    parser.add_argument("--write-record", action="store_true", help="write redacted audit under docs/research")
    parser.add_argument("--record-path", default=str(DEFAULT_RECORD_PATH), help="optional output path")
    parser.add_argument(
        "--load-env-local",
        action="store_true",
        help="load allowlisted keys from .env.local into this audit process only",
    )
    parser.add_argument("--env-file", default=".env.local", help="env file path used with --load-env-local")
    parser.add_argument("--env-file-override", action="store_true", help="override existing process env values")
    parser.add_argument("--print-powershell-template", action="store_true", help="print a placeholder env template")
    parser.add_argument("--write-powershell-template", action="store_true", help="write a placeholder env template")
    parser.add_argument("--template-path", default=str(DEFAULT_TEMPLATE_PATH), help="optional template output path")
    parser.add_argument("--fail-on-incomplete", action="store_true", help="exit 2 when Phase 3 is incomplete")
    return parser


def main(argv: list[str] | None = None) -> int:
    """3단계 완료 여부를 판정하고 raw secret 없이 JSON으로 출력한다."""
    parser = build_parser()
    args = parser.parse_args(argv)
    env_file_load_result = (
        load_env_file(
            Path(args.env_file),
            allowed_keys=REQUIRED_ENV_NAMES,
            override=bool(args.env_file_override),
            project_root=PROJECT_ROOT,
        )
        if args.load_env_local
        else None
    )
    env_file_presence_result = (
        scan_env_file_keys(
            Path(args.env_file),
            key_names=TOKEN_DIAGNOSTIC_ENV_NAMES,
            project_root=PROJECT_ROOT,
        )
        if args.load_env_local
        else None
    )
    record = build_completion_audit(
        env_file_load_result=env_file_load_result,
        env_file_presence_result=env_file_presence_result,
    )
    if args.write_record:
        write_completion_audit(record, Path(args.record_path))
    if args.write_powershell_template:
        write_powershell_env_template(Path(args.template_path))
    if args.print_powershell_template:
        print(build_powershell_env_template(), end="")
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


def _env_scope_status(names: tuple[str, ...], env: Mapping[str, str]) -> dict[str, dict[str, bool | str]]:
    return {name: _single_env_scope_status(name, env) for name in names}


def _single_env_scope_status(name: str, env: Mapping[str, str]) -> dict[str, bool | str]:
    process_configured = _configured(env.get(name))
    user_configured = _registry_env_configured(name, scope="user")
    machine_configured = _registry_env_configured(name, scope="machine")
    return {
        "process_configured": process_configured,
        "user_configured": user_configured,
        "machine_configured": machine_configured,
        "any_scope_configured": process_configured or user_configured or machine_configured,
        "values_redacted": True,
    }


def _token_env_diagnostics(
    env: Mapping[str, str],
    env_scope_status: Mapping[str, Mapping[str, object]],
    env_file_presence_result: Mapping[str, object] | None,
) -> dict[str, object]:
    presence = _env_file_key_presence(env_file_presence_result)
    access_process_configured = _configured(env.get(KIS_ACCESS_TOKEN_ENV))
    access_user_configured = _registry_env_configured(KIS_ACCESS_TOKEN_ENV, scope="user")
    access_machine_configured = _registry_env_configured(KIS_ACCESS_TOKEN_ENV, scope="machine")
    access_env_file_configured = bool(presence.get(KIS_ACCESS_TOKEN_ENV))
    refresh_status = env_scope_status.get("KIS_REFRESH_TOKEN", {})
    refresh_configured = bool(refresh_status.get("any_scope_configured")) or bool(presence.get("KIS_REFRESH_TOKEN"))
    access_configured = (
        access_process_configured
        or access_user_configured
        or access_machine_configured
        or access_env_file_configured
    )
    return {
        "access_token_configured": access_configured,
        "access_token_process_configured": access_process_configured,
        "access_token_user_configured": access_user_configured,
        "access_token_machine_configured": access_machine_configured,
        "access_token_env_file_configured": access_env_file_configured,
        "refresh_token_configured": refresh_configured,
        "access_token_without_refresh_token": access_configured and not refresh_configured,
        "refresh_token_required_variable": "KIS_REFRESH_TOKEN",
        "access_token_variable": KIS_ACCESS_TOKEN_ENV,
        "access_token_cannot_satisfy_refresh_proof": access_configured and not refresh_configured,
        "values_redacted": True,
    }


def _env_file_key_presence(env_file_presence_result: Mapping[str, object] | None) -> dict[str, bool]:
    if not isinstance(env_file_presence_result, Mapping):
        return {}
    raw_presence = env_file_presence_result.get("key_presence")
    if not isinstance(raw_presence, Mapping):
        return {}
    return {str(name): bool(value) for name, value in raw_presence.items()}


def _registry_env_configured(name: str, *, scope: str) -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg
    except ImportError:
        return False
    hive = winreg.HKEY_CURRENT_USER if scope == "user" else winreg.HKEY_LOCAL_MACHINE
    path = (
        "Environment"
        if scope == "user"
        else r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
    )
    try:
        with winreg.OpenKey(hive, path) as key:
            value, _value_type = winreg.QueryValueEx(key, name)
    except OSError:
        return False
    return _configured(value)


def _configured(value: object) -> bool:
    return bool(str(value or "").strip())


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
