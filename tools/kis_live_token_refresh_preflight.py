from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.kis_token_manager import (  # noqa: E402
    ENABLE_REAL_ORDER_ENV,
    KIS_ACCESS_TOKEN_ENV,
    KIS_APP_KEY_ENV,
    KIS_APP_SECRET_ENV,
)
from backend.app.services.kis_live_token_refresh_service import (  # noqa: E402
    CONFIRM_LIVE_TOKEN_REFRESH,
    KIS_LIVE_BASE_URL_ENV,
    KIS_REFRESH_TOKEN_ENV,
    KisLiveTokenRefreshService,
    LIVE_CANARY_ENVIRONMENT_ENV,
    LIVE_TOKEN_REFRESH_CONFIRMATION_ENV,
    LIVE_TOKEN_REFRESH_ENABLED_ENV,
    LIVE_TOKEN_REFRESH_NETWORK_ENABLED_ENV,
    LIVE_TOKEN_REFRESH_PROCESS_ONLY_ENV,
)
from tools.env_file_loader import load_env_file, scan_env_file_keys  # noqa: E402
from tools.token_diagnostics import build_access_token_diagnostics  # noqa: E402

DEFAULT_RECORD_PATH = PROJECT_ROOT / "docs" / "research" / "kis-live-token-refresh-preflight-record.json"
LIVE_TOKEN_REFRESH_ENV_FILE_KEYS = (
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
)
TOKEN_DIAGNOSTIC_ENV_NAMES = (KIS_ACCESS_TOKEN_ENV, KIS_REFRESH_TOKEN_ENV)


def build_record(
    *,
    execute: bool,
    confirm: str,
    install_to_process_env: bool,
    env: Mapping[str, str] | None = None,
    env_file_load_result: Mapping[str, object] | None = None,
    env_file_presence_result: Mapping[str, object] | None = None,
    env_file_access_token: str | None = None,
) -> dict[str, object]:
    """KIS live token refresh readiness를 redacted record로 반환한다."""
    service = KisLiveTokenRefreshService(env)
    status = service.status()
    execution_requested = execute and confirm == CONFIRM_LIVE_TOKEN_REFRESH
    result = (
        service.refresh_access_token(confirm=True, install_to_process_env=install_to_process_env)
        if execution_requested
        else {
            "ok": False,
            "status": "live_token_refresh_preview_only",
            "token_refreshed": False,
            "network_call_performed": False,
            "live_order_created": False,
            "reason": "EXECUTE_CONFIRMATION_REQUIRED",
            "reason_codes": ["EXECUTE_CONFIRMATION_REQUIRED"],
        }
    )
    record: dict[str, object] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "execute_requested": bool(execute),
        "execute_confirmed": execution_requested,
        "install_to_process_env_requested": bool(install_to_process_env),
        "status": status,
        "result": result,
        "network_call_performed": bool(result.get("network_call_performed")),
        "live_order_created": False,
        "token_env_diagnostics": _token_env_diagnostics(
            service.env,
            status,
            env_file_presence_result,
            env_file_access_token=env_file_access_token,
        ),
        "secrets_redacted": True,
    }
    if env_file_load_result is not None:
        record["env_file_load"] = dict(env_file_load_result)
    return record


def build_parser() -> argparse.ArgumentParser:
    """KIS live token refresh preflight CLI parser를 생성한다."""
    parser = argparse.ArgumentParser(description="Redacted KIS live token refresh preflight")
    parser.add_argument("--execute", action="store_true", help="attempt live token refresh when all gates pass")
    parser.add_argument("--confirm", default="", help="must equal CONFIRM_KIS_LIVE_TOKEN_REFRESH for --execute")
    parser.add_argument("--install-to-process-env", action="store_true", help="install refreshed access token to process env")
    parser.add_argument(
        "--load-env-local",
        action="store_true",
        help="load allowlisted keys from .env.local into this helper process only",
    )
    parser.add_argument("--env-file", default=".env.local", help="env file path used with --load-env-local")
    parser.add_argument("--env-file-override", action="store_true", help="override existing process env values")
    parser.add_argument("--write-record", action="store_true", help="write redacted record under docs/research")
    parser.add_argument("--record-path", default=str(DEFAULT_RECORD_PATH), help="optional output path for --write-record")
    parser.add_argument("--fail-on-blocked", action="store_true", help="exit 2 when token refresh was not executed")
    return parser


def main(argv: list[str] | None = None) -> int:
    """KIS live token refresh preflight를 실행하고 raw secret 없이 JSON으로 출력한다."""
    parser = build_parser()
    args = parser.parse_args(argv)
    env_file_load_result = (
        load_env_file(
            Path(args.env_file),
            allowed_keys=LIVE_TOKEN_REFRESH_ENV_FILE_KEYS,
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
    env_file_token_values: dict[str, str] = {}
    if args.load_env_local:
        load_env_file(
            Path(args.env_file),
            allowed_keys=TOKEN_DIAGNOSTIC_ENV_NAMES,
            target=env_file_token_values,
            project_root=PROJECT_ROOT,
        )
    record = build_record(
        execute=bool(args.execute),
        confirm=str(args.confirm),
        install_to_process_env=bool(args.install_to_process_env),
        env_file_load_result=env_file_load_result,
        env_file_presence_result=env_file_presence_result,
        env_file_access_token=env_file_token_values.get(KIS_ACCESS_TOKEN_ENV),
    )
    if args.write_record:
        path = Path(args.record_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, sort_keys=True, default=str))
    if args.fail_on_blocked and not record["network_call_performed"]:
        return 2
    return 0


def _token_env_diagnostics(
    env: Mapping[str, str],
    status: Mapping[str, object],
    env_file_presence_result: Mapping[str, object] | None,
    env_file_access_token: str | None = None,
) -> dict[str, object]:
    presence = _env_file_key_presence(env_file_presence_result)
    access_token = _first_configured(env.get(KIS_ACCESS_TOKEN_ENV), env_file_access_token)
    access_token_configured = bool(access_token) or bool(presence.get(KIS_ACCESS_TOKEN_ENV))
    refresh_token_configured = bool(status.get("refresh_token_configured")) or bool(presence.get(KIS_REFRESH_TOKEN_ENV))
    diagnostics = {
        "access_token_configured": access_token_configured,
        "refresh_token_configured": refresh_token_configured,
        "access_token_without_refresh_token": access_token_configured and not refresh_token_configured,
        "refresh_token_required_variable": KIS_REFRESH_TOKEN_ENV,
        "access_token_variable": KIS_ACCESS_TOKEN_ENV,
        "access_token_cannot_satisfy_refresh_proof": access_token_configured and not refresh_token_configured,
        "values_redacted": True,
    }
    diagnostics.update(build_access_token_diagnostics(access_token))
    return diagnostics


def _env_file_key_presence(env_file_presence_result: Mapping[str, object] | None) -> dict[str, bool]:
    if not isinstance(env_file_presence_result, Mapping):
        return {}
    raw_presence = env_file_presence_result.get("key_presence")
    if not isinstance(raw_presence, Mapping):
        return {}
    return {str(name): bool(value) for name, value in raw_presence.items()}


def _configured(value: object) -> bool:
    stripped = str(value or "").strip()
    return bool(stripped and "placeholder" not in stripped.lower())


def _first_configured(*values: object) -> str | None:
    for value in values:
        if _configured(value):
            return str(value).strip()
    return None


if __name__ == "__main__":
    raise SystemExit(main())
