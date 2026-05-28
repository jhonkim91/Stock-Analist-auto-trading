from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.database import SessionLocal, init_db
from backend.app.services.kis_token_manager import KisTokenManager
from backend.app.services.paper_sync_service import PaperSyncService
from tools.kis_paper_phase12c_dry_run import CONFIRMATION_TOKEN, sanitize_payload, write_record
from tools.kis_paper_phase21_service_lifecycle import (
    _temporary_config_dir,
    _temporary_us_env,
    _write_temporary_paper_config,
)
from tools.kis_paper_phase21_us_activation import (
    PHASE21_TOKEN_CONFIRMATION_TOKEN,
    _load_env_file,
    _terminal_status,
)


def run_phase21_followup_sync(
    *,
    symbol: str = "AAPL",
    exchange: str = "NASD",
    currency: str = "USD",
    scope: str = "all",
    confirm_sync: str | None = None,
    issue_token: bool = False,
    confirm_token: str | None = None,
    token_manager_factory: Callable[[], Any] | None = None,
    session_factory: Callable[[], Any] | None = None,
    config_dir: Path | None = None,
    sync_adapter: Any | None = None,
    env_file_path: Path | None = None,
    env_file_override: bool = False,
) -> dict[str, Any]:
    """Run a read-only KIS paper sync follow-up without creating or cancelling orders."""
    token_manager_factory = token_manager_factory or KisTokenManager
    record: dict[str, Any] = {
        "phase": "21-followup-sync",
        "generated_at": datetime.now(UTC).isoformat(),
        "paper_only": True,
        "market": "US",
        "symbol": symbol.strip().upper(),
        "exchange": exchange.strip().upper(),
        "currency": currency.strip().upper(),
        "scope": scope.strip().lower() if scope else "all",
        "submit_performed": False,
        "cancel_performed": False,
        "live_order_created": False,
        "raw_secret_printed": False,
        "network_call_performed": False,
        "steps": [],
    }

    if env_file_path is not None:
        env_load_result = _load_env_file(env_file_path, override=env_file_override)
        record["steps"].append({"name": "load_env_file", "result": sanitize_payload(env_load_result)})
        if not env_load_result.get("ok"):
            record.update(_terminal_status("env_file_load_failed", env_load_result))
            return _with_followup_completion_audit(record)

    if confirm_sync != CONFIRMATION_TOKEN:
        record.update(
            {
                "status": "confirmation_required",
                "reason_codes": ["PHASE21_FOLLOWUP_SYNC_CONFIRMATION_REQUIRED"],
            }
        )
        return _with_followup_completion_audit(record)

    if issue_token:
        token_result = token_manager_factory().issue_paper_access_token(
            confirm=confirm_token == PHASE21_TOKEN_CONFIRMATION_TOKEN,
            install_to_process_env=True,
        )
        record["steps"].append({"name": "issue_token", "result": sanitize_payload(token_result)})
        record["network_call_performed"] = bool(record["network_call_performed"] or token_result.get("network_call_performed"))
        if not token_result.get("ok"):
            record.update(_terminal_status("token_failed", token_result))
            return _with_followup_completion_audit(record)

    init_db()
    session_maker = session_factory or SessionLocal
    with _temporary_config_dir(config_dir) as active_config_dir:
        _write_temporary_paper_config(active_config_dir)
        with _temporary_us_env(exchange=exchange, currency=currency):
            db = session_maker()
            try:
                sync_service = PaperSyncService(db, config_dir=active_config_dir, adapter=sync_adapter)
                counts_before = sync_service._counts()
                record["counts_before"] = counts_before
                sync_result = sync_service.sync(scope=record["scope"])
                record["steps"].append({"name": "followup_sync", "result": sanitize_payload(sync_result)})
                record["network_call_performed"] = bool(record["network_call_performed"] or sync_result.get("network_call_performed"))
                counts_after = sync_service._counts()
                record["counts_after"] = counts_after
                evidence = _followup_sync_evidence(
                    counts_before=counts_before,
                    counts_after=counts_after,
                    sync_result=sync_result,
                )
                record["followup_evidence"] = sanitize_payload(evidence)
                if not sync_result.get("ok"):
                    record.update(_terminal_status("sync_failed", sync_result))
                    return _with_followup_completion_audit(record)
                if evidence["paper_fill_present"] and evidence["paper_position_present"]:
                    record.update({"status": "completed", "reason_codes": []})
                    return _with_followup_completion_audit(record)
                record.update(
                    {
                        "status": "sync_without_fill_or_position",
                        "reason_codes": [
                            code
                            for code, present in {
                                "PAPER_FILL_NOT_OBSERVED": evidence["paper_fill_present"],
                                "PAPER_POSITION_NOT_OBSERVED": evidence["paper_position_present"],
                            }.items()
                            if not present
                        ],
                    }
                )
                return _with_followup_completion_audit(record)
            finally:
                db.close()


def _followup_sync_evidence(
    *,
    counts_before: Mapping[str, Any],
    counts_after: Mapping[str, Any],
    sync_result: Mapping[str, Any],
) -> dict[str, Any]:
    fills_before = int(counts_before.get("paper_fills_count") or 0)
    fills_after = int(counts_after.get("paper_fills_count") or 0)
    positions_before = int(counts_before.get("paper_positions_count") or 0)
    positions_after = int(counts_after.get("paper_positions_count") or 0)
    orders_delta = int(counts_after.get("orders_count") or 0) - int(counts_before.get("orders_count") or 0)
    dedupe = sync_result.get("dedupe") if isinstance(sync_result.get("dedupe"), Mapping) else {}
    return {
        "sync_completed": bool(sync_result.get("ok")) and sync_result.get("status") == "sync_ok",
        "paper_fills_before": fills_before,
        "paper_fills_after": fills_after,
        "paper_fills_delta": fills_after - fills_before,
        "paper_fill_present": fills_after > 0,
        "fills_inserted": int(dedupe.get("fills_inserted") or 0),
        "paper_positions_before": positions_before,
        "paper_positions_after": positions_after,
        "paper_positions_delta": positions_after - positions_before,
        "paper_position_present": positions_after > 0,
        "positions_upserted": int(dedupe.get("positions_upserted") or 0),
        "orders_count_delta": orders_delta,
    }


def _with_followup_completion_audit(record: dict[str, Any]) -> dict[str, Any]:
    evidence = record.get("followup_evidence") if isinstance(record.get("followup_evidence"), Mapping) else {}
    requirements = {
        "paper_only": bool(record.get("paper_only")),
        "submit_not_performed": not bool(record.get("submit_performed")),
        "cancel_not_performed": not bool(record.get("cancel_performed")),
        "live_order_created_false": not bool(record.get("live_order_created")),
        "raw_secret_printed_false": not bool(record.get("raw_secret_printed")),
        "network_call_performed": bool(record.get("network_call_performed")),
        "sync_completed": bool(evidence.get("sync_completed")),
        "paper_fill_present": bool(evidence.get("paper_fill_present")),
        "paper_position_present": bool(evidence.get("paper_position_present")),
        "orders_count_unchanged": evidence.get("orders_count_delta") == 0,
    }
    missing = [key for key, value in requirements.items() if not value]
    record["completion_audit"] = {
        "scope": "phase21_followup_sync_fill_position",
        "complete": not missing,
        "requirements": requirements,
        "missing_requirements": missing,
    }
    return record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 21 read-only KIS paper follow-up sync helper")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--exchange", default="NASD")
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--scope", default="all")
    parser.add_argument("--issue-token", action="store_true")
    parser.add_argument("--confirm-token", default=None, help=f"must equal {PHASE21_TOKEN_CONFIRMATION_TOKEN}")
    parser.add_argument("--confirm-sync", default=None, help=f"must equal {CONFIRMATION_TOKEN}")
    parser.add_argument("--load-env-local", action="store_true")
    parser.add_argument("--env-file", default=".env.local")
    parser.add_argument("--env-file-override", action="store_true")
    parser.add_argument("--record-path", default=None, help="optional redacted .json record path inside the repo")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    record = run_phase21_followup_sync(
        symbol=args.symbol,
        exchange=args.exchange,
        currency=args.currency,
        scope=args.scope,
        confirm_sync=args.confirm_sync,
        issue_token=args.issue_token,
        confirm_token=args.confirm_token,
        env_file_path=Path(args.env_file) if args.load_env_local else None,
        env_file_override=args.env_file_override,
    )
    if args.record_path:
        write_record(record, PROJECT_ROOT / args.record_path)
    print(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0 if record.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
