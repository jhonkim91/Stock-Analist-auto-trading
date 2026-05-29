from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.kis_live_token_refresh_service import (  # noqa: E402
    CONFIRM_LIVE_TOKEN_REFRESH,
    KisLiveTokenRefreshService,
)

DEFAULT_RECORD_PATH = PROJECT_ROOT / "docs" / "research" / "kis-live-token-refresh-preflight-record.json"


def build_record(*, execute: bool, confirm: str, install_to_process_env: bool) -> dict[str, object]:
    """KIS live token refresh readiness를 redacted record로 반환한다."""
    service = KisLiveTokenRefreshService()
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
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "execute_requested": bool(execute),
        "execute_confirmed": execution_requested,
        "install_to_process_env_requested": bool(install_to_process_env),
        "status": status,
        "result": result,
        "network_call_performed": bool(result.get("network_call_performed")),
        "live_order_created": False,
        "secrets_redacted": True,
    }


def build_parser() -> argparse.ArgumentParser:
    """KIS live token refresh preflight CLI parser를 생성한다."""
    parser = argparse.ArgumentParser(description="Redacted KIS live token refresh preflight")
    parser.add_argument("--execute", action="store_true", help="attempt live token refresh when all gates pass")
    parser.add_argument("--confirm", default="", help="must equal CONFIRM_KIS_LIVE_TOKEN_REFRESH for --execute")
    parser.add_argument("--install-to-process-env", action="store_true", help="install refreshed access token to process env")
    parser.add_argument("--write-record", action="store_true", help="write redacted record under docs/research")
    parser.add_argument("--record-path", default=str(DEFAULT_RECORD_PATH), help="optional output path for --write-record")
    parser.add_argument("--fail-on-blocked", action="store_true", help="exit 2 when token refresh was not executed")
    return parser


def main(argv: list[str] | None = None) -> int:
    """KIS live token refresh preflight를 실행하고 raw secret 없이 JSON으로 출력한다."""
    parser = build_parser()
    args = parser.parse_args(argv)
    record = build_record(
        execute=bool(args.execute),
        confirm=str(args.confirm),
        install_to_process_env=bool(args.install_to_process_env),
    )
    if args.write_record:
        path = Path(args.record_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, sort_keys=True, default=str))
    if args.fail_on_blocked and not record["network_call_performed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
