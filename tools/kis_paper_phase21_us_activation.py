from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.kis_paper_websocket_service import KisPaperWebSocketService
from backend.app.services.kis_token_manager import KisTokenManager
from tools.kis_paper_phase12c_dry_run import (
    CONFIRMATION_TOKEN,
    TRADING_WINDOW_CONFIRMATION_TOKEN,
    _parse_as_of,
    run_controlled_dry_run,
    sanitize_payload,
    write_record,
)

PHASE21_TOKEN_CONFIRMATION_TOKEN = "CONFIRM_KIS_PAPER_PHASE21_TOKEN"
PHASE21_WEBSOCKET_CONFIRMATION_TOKEN = "CONFIRM_KIS_PAPER_PHASE21_WEBSOCKET"


def run_phase21_us_activation(
    *,
    symbol: str = "AAPL",
    qty: int = 1,
    limit_price: float | None = None,
    exchange: str = "NASD",
    currency: str = "USD",
    issue_token: bool = False,
    issue_websocket_approval: bool = False,
    websocket_smoke: bool = False,
    execute_submit: bool = False,
    confirm_token: str | None = None,
    confirm_websocket: str | None = None,
    confirm_submit: str | None = None,
    confirm_cancel: str | None = None,
    confirm_trading_window: str | None = None,
    as_of: datetime | None = None,
    env: Mapping[str, str] | None = None,
    config: Mapping[str, Any] | None = None,
    token_manager_factory: Callable[[], Any] | None = None,
    websocket_service_factory: Callable[[], Any] | None = None,
    adapter_factory: Callable[[dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Run the Phase 21 US paper activation steps with redacted, one-shot semantics."""
    token_manager_factory = token_manager_factory or KisTokenManager
    websocket_service_factory = websocket_service_factory or KisPaperWebSocketService
    record: dict[str, Any] = {
        "phase": "21-US",
        "generated_at": datetime.now(UTC).isoformat(),
        "paper_only": True,
        "market": "US",
        "symbol": symbol.strip().upper(),
        "exchange": exchange.strip().upper(),
        "currency": currency.strip().upper(),
        "qty": qty,
        "live_order_created": False,
        "raw_secret_printed": False,
        "steps": [],
    }

    if issue_token:
        token_result = token_manager_factory().issue_paper_access_token(
            confirm=confirm_token == PHASE21_TOKEN_CONFIRMATION_TOKEN,
            install_to_process_env=True,
        )
        record["steps"].append({"name": "issue_token", "result": sanitize_payload(token_result)})
        if not token_result.get("ok"):
            record.update(_terminal_status("token_failed", token_result))
            return record

    websocket_service = websocket_service_factory()
    if issue_websocket_approval:
        approval_result = websocket_service.issue_approval_key(
            confirm=confirm_websocket == PHASE21_WEBSOCKET_CONFIRMATION_TOKEN,
            install_to_process_env=True,
        )
        record["steps"].append({"name": "issue_websocket_approval", "result": sanitize_payload(approval_result)})
        if not approval_result.get("ok"):
            record.update(_terminal_status("websocket_approval_failed", approval_result))
            return record

    preview = websocket_service.subscription_preview(
        symbol=symbol,
        kind="quote",
        market="US",
        exchange=exchange,
        subscribe=True,
    )
    record["steps"].append({"name": "websocket_us_subscription_preview", "result": sanitize_payload(preview)})
    if not preview.get("ok"):
        record.update(_terminal_status("websocket_subscription_preview_failed", preview))
        return record

    if websocket_smoke:
        smoke = websocket_service.bounded_connect_smoke(
            symbol=symbol,
            kind="quote",
            market="US",
            exchange=exchange,
            confirm=confirm_websocket == PHASE21_WEBSOCKET_CONFIRMATION_TOKEN,
        )
        record["steps"].append({"name": "websocket_us_bounded_smoke", "result": sanitize_payload(smoke)})
        if not smoke.get("ok"):
            record.update(_terminal_status("websocket_smoke_failed", smoke))
            return record

    if execute_submit:
        submit_record = run_controlled_dry_run(
            execute=True,
            symbol=symbol,
            side="buy",
            qty=qty,
            limit_price=limit_price,
            confirm_submit=confirm_submit,
            confirm_cancel=confirm_cancel,
            confirm_trading_window=confirm_trading_window,
            market="US",
            exchange=exchange,
            currency=currency,
            as_of=as_of,
            use_temporary_paper_config=True,
            env=env,
            config=config,
            adapter_factory=adapter_factory,
        )
        record["steps"].append({"name": "controlled_us_submit_list_sync_cancel", "result": sanitize_payload(submit_record)})
        record["network_call_performed"] = bool(submit_record.get("network_call_performed"))
        if submit_record.get("status") != "completed":
            record.update(
                {
                    "status": "submit_lifecycle_incomplete",
                    "reason_codes": list(submit_record.get("reason_codes") or [submit_record.get("status")]),
                    "live_order_created": False,
                }
            )
            return record

    record.update({"status": "completed", "reason_codes": [], "network_call_performed": bool(execute_submit)})
    return record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 21 US KIS paper activation helper")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--qty", type=int, default=1)
    parser.add_argument("--limit-price", type=float, default=None)
    parser.add_argument("--exchange", default="NASD")
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--issue-token", action="store_true")
    parser.add_argument("--issue-websocket-approval", action="store_true")
    parser.add_argument("--websocket-smoke", action="store_true")
    parser.add_argument("--execute-submit", action="store_true")
    parser.add_argument("--confirm-token", default=None, help=f"must equal {PHASE21_TOKEN_CONFIRMATION_TOKEN}")
    parser.add_argument("--confirm-websocket", default=None, help=f"must equal {PHASE21_WEBSOCKET_CONFIRMATION_TOKEN}")
    parser.add_argument("--confirm-submit", default=None, help=f"must equal {CONFIRMATION_TOKEN}")
    parser.add_argument("--confirm-cancel", default=None, help=f"must equal {CONFIRMATION_TOKEN}")
    parser.add_argument(
        "--confirm-trading-window",
        default=None,
        help=f"must equal {TRADING_WINDOW_CONFIRMATION_TOKEN}",
    )
    parser.add_argument(
        "--as-of",
        default=None,
        help="optional ISO timestamp used only for local trading-window validation",
    )
    parser.add_argument("--record-path", default=None, help="optional redacted .json record path inside the repo")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.qty <= 0:
        parser.error("--qty must be positive")
    record = run_phase21_us_activation(
        symbol=args.symbol,
        qty=args.qty,
        limit_price=args.limit_price,
        exchange=args.exchange,
        currency=args.currency,
        issue_token=bool(args.issue_token),
        issue_websocket_approval=bool(args.issue_websocket_approval),
        websocket_smoke=bool(args.websocket_smoke),
        execute_submit=bool(args.execute_submit),
        confirm_token=args.confirm_token,
        confirm_websocket=args.confirm_websocket,
        confirm_submit=args.confirm_submit,
        confirm_cancel=args.confirm_cancel,
        confirm_trading_window=args.confirm_trading_window,
        as_of=_parse_as_of(args.as_of),
    )
    if args.record_path:
        write_record(record, PROJECT_ROOT / args.record_path)
    print(json.dumps(record, indent=2, sort_keys=True, default=str))
    return 0 if record.get("status") == "completed" else 2


def _terminal_status(status: str, result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": status,
        "reason_codes": list(result.get("reason_codes") or [result.get("reason") or status]),
        "network_call_performed": bool(result.get("network_call_performed", False)),
        "live_order_created": False,
    }


if __name__ == "__main__":
    sys.exit(main())
