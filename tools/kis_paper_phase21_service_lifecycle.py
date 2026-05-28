from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.database import SessionLocal, init_db
from backend.app.services.paper_order_service import PaperOrderService
from backend.app.services.paper_sync_service import PaperSyncService
from tools.kis_paper_phase12c_dry_run import (
    CONFIRMATION_TOKEN,
    TRADING_WINDOW_CONFIRMATION_TOKEN,
    _digest,
    _parse_as_of,
    _trading_window_status,
    sanitize_payload,
    write_record,
)


def run_phase21_service_lifecycle(
    *,
    symbol: str = "AAPL",
    qty: int = 1,
    limit_price: float | None = None,
    exchange: str = "NASD",
    currency: str = "USD",
    confirm_submit: str | None = None,
    confirm_sync: str | None = None,
    confirm_cancel: str | None = None,
    confirm_trading_window: str | None = None,
    as_of: datetime | None = None,
    session_factory: Callable[[], Any] | None = None,
    config_dir: Path | None = None,
    submit_adapter: Any | None = None,
    sync_adapter: Any | None = None,
) -> dict[str, Any]:
    """Run a one-shot service-level KIS paper submit -> sync -> optional cancel lifecycle."""
    record: dict[str, Any] = {
        "phase": "21-service-lifecycle",
        "generated_at": datetime.now(UTC).isoformat(),
        "paper_only": True,
        "market": "US",
        "symbol": symbol.strip().upper(),
        "exchange": exchange.strip().upper(),
        "currency": currency.strip().upper(),
        "qty": qty,
        "live_order_created": False,
        "raw_secret_printed": False,
        "network_call_performed": False,
        "steps": [],
    }
    if confirm_submit != CONFIRMATION_TOKEN or confirm_sync != CONFIRMATION_TOKEN:
        record.update(
            {
                "status": "confirmation_required",
                "reason_codes": ["PHASE21_SERVICE_SUBMIT_SYNC_CONFIRMATION_REQUIRED"],
            }
        )
        return _with_completion_audit(record)
    if confirm_trading_window != TRADING_WINDOW_CONFIRMATION_TOKEN:
        record.update(
            {
                "status": "trading_window_confirmation_required",
                "reason_codes": ["PHASE12C_TRADING_WINDOW_CONFIRMATION_REQUIRED"],
            }
        )
        return _with_completion_audit(record)

    trading_window = _trading_window_status(market="US", as_of=as_of)
    record["trading_window"] = trading_window
    if not trading_window["ok"]:
        record.update(
            {
                "status": "trading_window_closed",
                "reason_codes": list(trading_window["reason_codes"]),
            }
        )
        return _with_completion_audit(record)

    init_db()
    session_maker = session_factory or SessionLocal
    with _temporary_config_dir(config_dir) as active_config_dir:
        _write_temporary_paper_config(active_config_dir)
        with _temporary_us_env(exchange=exchange, currency=currency):
            db = session_maker()
            try:
                order_service = PaperOrderService(db, config_dir=active_config_dir, adapter=submit_adapter)
                sync_service = PaperSyncService(db, config_dir=active_config_dir, adapter=sync_adapter)
                counts_before = order_service._counts()
                record["counts_before"] = counts_before
                idempotency_key = f"phase21-service-{_digest(datetime.now(UTC).isoformat())}"
                submit_result = order_service.submit_order(
                    symbol=symbol.strip().upper(),
                    side="buy",
                    qty=qty,
                    limit_price=limit_price,
                    strategy_tag="phase21-service",
                    venue=exchange.strip().upper(),
                    confirm=True,
                    idempotency_key=idempotency_key,
                )
                record["steps"].append({"name": "service_submit", "result": sanitize_payload(submit_result)})
                record["network_call_performed"] = bool(submit_result.get("network_call_performed"))
                if not submit_result.get("ok"):
                    record.update({"status": "submit_failed", "reason_codes": submit_result.get("reason_codes", [])})
                    return _with_completion_audit(record)

                sync_result = sync_service.sync(scope="all")
                record["steps"].append({"name": "service_sync", "result": sanitize_payload(sync_result)})
                record["network_call_performed"] = bool(record["network_call_performed"] or sync_result.get("network_call_performed"))
                counts_after_sync = order_service._counts()
                evidence = _service_lifecycle_evidence(
                    counts_before=counts_before,
                    counts_after=counts_after_sync,
                    submit_result=submit_result,
                    sync_result=sync_result,
                )
                record["lifecycle_evidence"] = sanitize_payload(evidence)
                if not sync_result.get("ok"):
                    cancel_result = _service_cancel(order_service, submit_result, confirm_cancel=confirm_cancel)
                    record["steps"].append({"name": "service_cancel_after_sync_failed", "result": sanitize_payload(cancel_result)})
                    record["counts_after"] = order_service._counts()
                    record.update(
                        {
                            "status": "sync_failed",
                            "reason_codes": sync_result.get("reason_codes", []),
                            "cancel_attempted": True,
                        }
                    )
                    return _with_completion_audit(record)

                if evidence["filled_position_observed"]:
                    record["counts_after"] = counts_after_sync
                    record.update(
                        {
                            "status": "completed",
                            "reason_codes": [],
                            "cancel_skipped": True,
                            "cancel_skipped_reason": "FILLED_POSITION_OBSERVED_AFTER_SYNC",
                        }
                    )
                    return _with_completion_audit(record)

                cancel_result = _service_cancel(order_service, submit_result, confirm_cancel=confirm_cancel)
                record["steps"].append({"name": "service_cancel_after_unfilled_sync", "result": sanitize_payload(cancel_result)})
                record["counts_after"] = order_service._counts()
                record.update(
                    {
                        "status": "submitted_sync_without_fill_or_position",
                        "reason_codes": ["FILL_OR_POSITION_NOT_OBSERVED"],
                        "cancel_attempted": True,
                    }
                )
                return _with_completion_audit(record)
            finally:
                db.close()


def _service_lifecycle_evidence(
    *,
    counts_before: Mapping[str, Any],
    counts_after: Mapping[str, Any],
    submit_result: Mapping[str, Any],
    sync_result: Mapping[str, Any],
) -> dict[str, Any]:
    fills_delta = int(counts_after.get("paper_fills_count") or 0) - int(counts_before.get("paper_fills_count") or 0)
    positions_delta = int(counts_after.get("paper_positions_count") or 0) - int(counts_before.get("paper_positions_count") or 0)
    orders_delta = int(counts_after.get("paper_orders_count") or 0) - int(counts_before.get("paper_orders_count") or 0)
    orders_count_delta = int(counts_after.get("orders_count") or 0) - int(counts_before.get("orders_count") or 0)
    fills_inserted = int((sync_result.get("dedupe") or {}).get("fills_inserted") or 0)
    positions_upserted = int((sync_result.get("dedupe") or {}).get("positions_upserted") or 0)
    position_changed = positions_delta > 0 or positions_upserted > 0
    return {
        "paper_order_created": bool(submit_result.get("paper_order_created")),
        "broker_order_created": bool(submit_result.get("broker_order_created")),
        "paper_orders_delta": orders_delta,
        "orders_count_delta": orders_count_delta,
        "paper_fills_delta": fills_delta,
        "paper_positions_delta": positions_delta,
        "fills_inserted": fills_inserted,
        "positions_upserted": positions_upserted,
        "paper_fill_created": fills_delta > 0 or fills_inserted > 0,
        "paper_position_changed": position_changed,
        "filled_position_observed": (fills_delta > 0 or fills_inserted > 0) and position_changed,
    }


def _with_completion_audit(record: dict[str, Any]) -> dict[str, Any]:
    """Attach the concrete evidence required for the service lifecycle goal."""
    evidence = record.get("lifecycle_evidence") if isinstance(record.get("lifecycle_evidence"), Mapping) else {}
    requirements = {
        "paper_only": bool(record.get("paper_only")),
        "live_order_created_false": not bool(record.get("live_order_created")),
        "raw_secret_printed_false": not bool(record.get("raw_secret_printed")),
        "network_call_performed": bool(record.get("network_call_performed")),
        "service_lifecycle_completed": record.get("status") == "completed",
        "paper_order_created": bool(evidence.get("paper_order_created")),
        "broker_order_created": bool(evidence.get("broker_order_created")),
        "paper_fill_created": bool(evidence.get("paper_fill_created")),
        "paper_position_changed": bool(evidence.get("paper_position_changed")),
        "orders_count_unchanged": evidence.get("orders_count_delta") == 0,
    }
    missing = [key for key, value in requirements.items() if not value]
    record["completion_audit"] = {
        "scope": "phase21_service_lifecycle_order_fill_position",
        "complete": not missing,
        "requirements": requirements,
        "missing_requirements": missing,
    }
    return record


def _service_cancel(order_service: PaperOrderService, submit_result: Mapping[str, Any], *, confirm_cancel: str | None) -> dict[str, Any]:
    if confirm_cancel != CONFIRMATION_TOKEN:
        return {
            "ok": False,
            "status": "cancel_skipped",
            "reason_codes": ["PHASE21_SERVICE_CANCEL_CONFIRMATION_REQUIRED"],
            "network_call_performed": False,
        }
    order = submit_result.get("order") if isinstance(submit_result.get("order"), Mapping) else {}
    paper_order_id = str(order.get("paper_order_id") or "")
    if not paper_order_id:
        return {
            "ok": False,
            "status": "cancel_skipped",
            "reason_codes": ["PAPER_ORDER_ID_MISSING"],
            "network_call_performed": False,
        }
    return order_service.cancel_order(
        paper_order_id=paper_order_id,
        confirm=True,
        idempotency_key=f"phase21-service-cancel-{_digest(paper_order_id)}",
    )


@contextmanager
def _temporary_config_dir(config_dir: Path | None):
    if config_dir is not None:
        config_dir.mkdir(parents=True, exist_ok=True)
        yield config_dir
        return
    with TemporaryDirectory(prefix="kis-paper-phase21-service-") as directory:
        yield Path(directory)


def _write_temporary_paper_config(config_dir: Path) -> None:
    config_dir.joinpath("paper.yaml").write_text(
        """
paper:
  mode: "paper"
  enabled: true
  can_create: true
  can_simulate_fills: false
  preview_only: false
  kill_switch_enabled: false
  network_enabled: true
  live_order_enabled: false
  broker_order_enabled: false
risk_gate:
  allow_buy_preview: true
  allow_sell_preview: true
  allow_short_sell: false
  max_order_qty: 1000000
  max_order_notional: 100000000
audit:
  persistence_enabled: false
  sanitize_enabled: true
simulator:
  enabled: false
  auto_fill_on_create: false
broker_adapter:
  name: "kis_paper"
  enabled: true
  official_endpoint_confirmed: true
  official_balance_endpoint_confirmed: true
  balance_inquiry_enabled: true
  live_fallback_enabled: false
""".lstrip(),
        encoding="utf-8",
    )


@contextmanager
def _temporary_us_env(*, exchange: str, currency: str):
    updates = {
        "PAPER_TRADING_MARKET": "US",
        "KIS_OVERSEAS_EXCHANGE_CODE": exchange.strip().upper() or "NASD",
        "KIS_OVERSEAS_CURRENCY": currency.strip().upper() or "USD",
        "KIS_OVERSEAS_ORDER_SESSION": "regular",
    }
    previous = {key: os.environ.get(key) for key in updates}
    try:
        os.environ.update(updates)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 21 service-level KIS paper lifecycle helper")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--qty", type=int, default=1)
    parser.add_argument("--limit-price", type=float, default=None)
    parser.add_argument("--exchange", default="NASD")
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--confirm-submit", default=None, help=f"must equal {CONFIRMATION_TOKEN}")
    parser.add_argument("--confirm-sync", default=None, help=f"must equal {CONFIRMATION_TOKEN}")
    parser.add_argument("--confirm-cancel", default=None, help=f"must equal {CONFIRMATION_TOKEN}")
    parser.add_argument(
        "--confirm-trading-window",
        default=None,
        help=f"must equal {TRADING_WINDOW_CONFIRMATION_TOKEN}",
    )
    parser.add_argument("--as-of", default=None, help="optional ISO timestamp used only for local trading-window validation")
    parser.add_argument("--record-path", default=None, help="optional redacted .json record path inside the repo")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.qty <= 0:
        parser.error("--qty must be positive")
    record = run_phase21_service_lifecycle(
        symbol=args.symbol,
        qty=args.qty,
        limit_price=args.limit_price,
        exchange=args.exchange,
        currency=args.currency,
        confirm_submit=args.confirm_submit,
        confirm_sync=args.confirm_sync,
        confirm_cancel=args.confirm_cancel,
        confirm_trading_window=args.confirm_trading_window,
        as_of=_parse_as_of(args.as_of),
    )
    if args.record_path:
        write_record(record, PROJECT_ROOT / args.record_path)
    print(json.dumps(record, indent=2, sort_keys=True, default=str))
    return 0 if record.get("status") == "completed" else 2


if __name__ == "__main__":
    sys.exit(main())
