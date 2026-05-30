from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.brokers.base import BrokerOrderRequest
from backend.app.brokers.kis_paper import (
    BROKER_MODE_ENV,
    DEFAULT_KIS_PAPER_BASE_URL,
    KIS_ACCESS_TOKEN_ENV,
    KIS_ACCOUNT_NO_ENV,
    KIS_ENV_ENV,
    KIS_PAPER_BASE_URL_ENV,
    KIS_PRODUCT_CODE_ENV,
    PAPER_BOT_CONFIRM_ENV,
    PAPER_ORDER_SUBMIT_ENABLED_ENV,
    REQUIRED_PAPER_BROKER_MODE,
    KisPaperBrokerAdapter,
    KisPaperCredentials,
    _is_live_base_url,
)
from backend.app.core.paths import CONFIG_DIR
from backend.app.services.paper_trading_service import PaperConfigService
from backend.app.services.token_manager import KIS_APP_KEY_ENV, KIS_APP_SECRET_ENV

CONFIRMATION_TOKEN = "CONFIRM_KIS_PAPER_PHASE12C"
TRADING_WINDOW_CONFIRMATION_TOKEN = "CONFIRM_KIS_PAPER_TRADING_WINDOW"
US_EASTERN = ZoneInfo("America/New_York")
US_PREMARKET_SESSION_START = time(4, 0)
US_REGULAR_SESSION_START = time(9, 30)
US_REGULAR_SESSION_END = time(16, 0)
KIS_CREDENTIAL_ENV_KEYS = (
    KIS_APP_KEY_ENV,
    KIS_APP_SECRET_ENV,
    KIS_ACCESS_TOKEN_ENV,
    KIS_ACCOUNT_NO_ENV,
    KIS_PRODUCT_CODE_ENV,
)
RUNTIME_GATE_ENV_KEYS = (
    KIS_ENV_ENV,
    "PAPER_TRADING_ENABLED",
    "PAPER_TRADING_CAN_CREATE",
    "PAPER_TRADING_NETWORK_ENABLED",
    PAPER_ORDER_SUBMIT_ENABLED_ENV,
    PAPER_BOT_CONFIRM_ENV,
)
CONFIG_GATE_KEYS = (
    "enabled",
    "configured_can_create",
    "paper_bot_confirm_enabled",
    "network_enabled",
    "broker_adapter_enabled",
    "official_endpoint_confirmed",
)
IDENTIFIER_KEYS = {
    "broker_order_id",
    "broker_fill_id",
    "paper_order_id",
    "idempotency_key",
}
SENSITIVE_KEYS = {
    "account_no",
    "account_number",
    "access_token",
    "app_key",
    "app_secret",
    "appkey",
    "appsecret",
    "approval_key",
    "authorization",
    "cano",
    "chat_id",
    "refresh_token",
    "secretkey",
    "token",
}


def phase12c_preflight(
    env: Mapping[str, str] | None = None,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return redacted Phase 12C gate status without reading or printing raw values."""
    current_env = os.environ if env is None else env
    loaded_config, config_reasons = _load_config(config)
    credential_status = {
        key: KisPaperCredentials._is_configured_value(current_env.get(key, "")) for key in KIS_CREDENTIAL_ENV_KEYS
    }
    runtime_status = {
        key: (
            str(current_env.get(key, "")).strip().lower() == "paper"
            if key == KIS_ENV_ENV
            else _is_true(current_env.get(key, ""))
        )
        for key in RUNTIME_GATE_ENV_KEYS
    }
    config_status = {key: bool(loaded_config.get(key, False)) for key in CONFIG_GATE_KEYS}
    kill_switch_off = _is_false(current_env.get("PAPER_TRADING_KILL_SWITCH", ""))
    config_kill_switch_off = not bool(loaded_config.get("kill_switch_enabled", True))
    broker_mode_paper = str(current_env.get(BROKER_MODE_ENV, "")).strip().lower() == REQUIRED_PAPER_BROKER_MODE
    real_order_enabled = _is_true(current_env.get("ENABLE_REAL_ORDER", ""))
    bot_auto_submit_enabled = _is_true(current_env.get("PAPER_BOT_AUTO_SUBMIT", ""))
    base_url = current_env.get(KIS_PAPER_BASE_URL_ENV, "").strip() or DEFAULT_KIS_PAPER_BASE_URL
    base_url_live = _is_live_base_url(base_url)
    blockers: list[str] = []
    blockers.extend([f"{key}_MISSING" for key, configured in credential_status.items() if not configured])
    blockers.extend([f"{key}_REQUIRED" for key, configured in runtime_status.items() if not configured])
    blockers.extend([f"PAPER_CONFIG_{key.upper()}_REQUIRED" for key, enabled in config_status.items() if not enabled])
    blockers.extend(config_reasons)
    if str(loaded_config.get("mode") or "") != "paper":
        blockers.append("PAPER_CONFIG_MODE_PAPER_REQUIRED")
    if not broker_mode_paper:
        blockers.append("BROKER_MODE_PAPER_KIS_REQUIRED")
    if not kill_switch_off:
        blockers.append("PAPER_TRADING_KILL_SWITCH_FALSE_REQUIRED")
    if not config_kill_switch_off:
        blockers.append("PAPER_CONFIG_KILL_SWITCH_FALSE_REQUIRED")
    if bool(loaded_config.get("live_order_enabled", False)) or bool(loaded_config.get("live_fallback_enabled", False)):
        blockers.append("PAPER_CONFIG_LIVE_FLAGS_MUST_BE_FALSE")
    if real_order_enabled:
        blockers.append("ENABLE_REAL_ORDER_MUST_BE_FALSE")
    if bot_auto_submit_enabled:
        blockers.append("PAPER_BOT_AUTO_SUBMIT_MUST_BE_FALSE")
    if base_url_live:
        blockers.append("KIS_LIVE_BASE_URL_BLOCKED")
    return {
        "ok": not blockers,
        "credential_fields": {key: {"configured": configured} for key, configured in credential_status.items()},
        "runtime_gates": {
            **{key: {"enabled": enabled} for key, enabled in runtime_status.items()},
            "PAPER_TRADING_KILL_SWITCH": {"explicit_false": kill_switch_off},
            BROKER_MODE_ENV: {"paper_kis": broker_mode_paper},
        },
        "config_gates": {
            "mode": str(loaded_config.get("mode") or "disabled"),
            **{key: {"enabled": enabled} for key, enabled in config_status.items()},
            "kill_switch_enabled": bool(loaded_config.get("kill_switch_enabled", True)),
            "live_order_enabled": bool(loaded_config.get("live_order_enabled", False)),
            "live_fallback_enabled": bool(loaded_config.get("live_fallback_enabled", False)),
        },
        "safety_gates": {
            "ENABLE_REAL_ORDER": {"enabled": real_order_enabled},
            "PAPER_BOT_AUTO_SUBMIT": {"enabled": bot_auto_submit_enabled},
            KIS_PAPER_BASE_URL_ENV: {"configured": bool(current_env.get(KIS_PAPER_BASE_URL_ENV, "").strip()), "live_host": base_url_live},
        },
        "blockers": blockers,
    }


def run_controlled_dry_run(
    *,
    execute: bool,
    symbol: str,
    side: str,
    qty: int,
    limit_price: float | None,
    confirm_submit: str | None,
    confirm_cancel: str | None,
    confirm_trading_window: str | None = None,
    market: str = "KR",
    exchange: str = "KRX",
    currency: str = "KRW",
    as_of: datetime | None = None,
    env: Mapping[str, str] | None = None,
    config: Mapping[str, Any] | None = None,
    adapter_factory: Callable[[dict[str, Any]], Any] | None = None,
    use_temporary_paper_config: bool = False,
    allow_premarket_submit: bool = False,
) -> dict[str, Any]:
    """Run Phase 12C preflight or a fully gated controlled paper-network dry-run."""
    current_env = os.environ if env is None else env
    loaded_config, _ = _load_config(config)
    if use_temporary_paper_config:
        loaded_config = _temporary_phase12c_config(loaded_config)
    factory = adapter_factory or (lambda config: KisPaperBrokerAdapter(config=config))
    preflight = phase12c_preflight(current_env, config=loaded_config)
    record: dict[str, Any] = {
        "phase": "12C",
        "generated_at": datetime.now(UTC).isoformat(),
        "execute_requested": execute,
        "paper_only": True,
        "market": market.strip().upper(),
        "exchange": exchange.strip().upper(),
        "currency": currency.strip().upper(),
        "live_order_created": False,
        "network_call_performed": False,
        "temporary_config_used": use_temporary_paper_config,
        "allow_premarket_submit": allow_premarket_submit,
        "preflight": preflight,
        "steps": [],
    }
    if not execute:
        record["status"] = "preflight_only"
        return record
    if confirm_submit != CONFIRMATION_TOKEN or confirm_cancel != CONFIRMATION_TOKEN:
        record.update(
            {
                "status": "confirmation_required",
                "reason_codes": ["PHASE12C_SUBMIT_CANCEL_CONFIRMATION_REQUIRED"],
            }
        )
        return record
    if not preflight["ok"]:
        record.update({"status": "preflight_stopped", "reason_codes": preflight["blockers"]})
        return record
    if confirm_trading_window != TRADING_WINDOW_CONFIRMATION_TOKEN:
        record.update(
            {
                "status": "trading_window_confirmation_required",
                "reason_codes": ["PHASE12C_TRADING_WINDOW_CONFIRMATION_REQUIRED"],
            }
        )
        return record
    trading_window = _trading_window_status(market=market, as_of=as_of)
    record["trading_window"] = trading_window
    if not trading_window["ok"]:
        record.update(
            {
                "status": "trading_window_closed",
                "reason_codes": list(trading_window["reason_codes"]),
            }
        )
        return record
    request = BrokerOrderRequest(
        symbol=symbol.strip(),
        side=side.strip().lower(),
        qty=qty,
        limit_price=limit_price,
        idempotency_key=f"phase12c-{_digest(datetime.now(UTC).isoformat())}",
        metadata=_order_metadata(
            market=market,
            exchange=exchange,
            currency=currency,
            order_session=str(trading_window.get("session") or ""),
        ),
    )

    kill_switch_adapter = factory(
        _adapter_config(loaded_config, kill_switch_enabled=True, market=market, exchange=exchange, currency=currency)
    )
    kill_switch_result = kill_switch_adapter.submit_order(request)
    record["steps"].append({"name": "kill_switch_block", "result": sanitize_payload(kill_switch_result)})
    if bool(kill_switch_result.get("network_call_performed")) or "KILL_SWITCH_ACTIVE" not in kill_switch_result.get(
        "reason_codes", []
    ):
        record.update({"status": "kill_switch_proof_failed", "reason_codes": ["KILL_SWITCH_PROOF_FAILED"]})
        return record

    open_adapter = factory(
        _adapter_config(loaded_config, kill_switch_enabled=False, market=market, exchange=exchange, currency=currency)
    )
    submit_result = open_adapter.submit_order(request)
    record["steps"].append({"name": "submit", "result": sanitize_payload(submit_result)})
    record["network_call_performed"] = bool(submit_result.get("network_call_performed"))
    if not submit_result.get("ok"):
        record.update({"status": "submit_failed", "reason_codes": submit_result.get("reason_codes", [])})
        return record

    broker_order_id = str(submit_result.get("broker_order_id") or "")
    listed = open_adapter.list_orders(status="open")
    record["steps"].append({"name": "list_orders", "result": sanitize_payload(listed)})
    if not listed.get("ok"):
        cancel_result = _attempt_cancel(open_adapter, broker_order_id)
        record["steps"].append({"name": "cancel_after_query_failed", "result": sanitize_payload(cancel_result)})
        record.update(
            {
                "status": "query_failed",
                "reason_codes": listed.get("reason_codes", []),
                "kill_switch_reenabled": True,
            }
        )
        return record

    synced = open_adapter.sync(scope="all")
    record["steps"].append({"name": "sync", "result": sanitize_payload(synced)})
    if not synced.get("ok"):
        cancel_result = _attempt_cancel(open_adapter, broker_order_id)
        record["steps"].append({"name": "cancel_after_sync_failed", "result": sanitize_payload(cancel_result)})
        record.update(
            {
                "status": "sync_failed",
                "reason_codes": synced.get("reason_codes", []),
                "kill_switch_reenabled": True,
            }
        )
        return record

    lifecycle_evidence = _lifecycle_evidence(synced, broker_order_id=broker_order_id, symbol=symbol, qty=qty)
    record["lifecycle_evidence"] = sanitize_payload(lifecycle_evidence)
    if lifecycle_evidence["order_filled"]:
        record["steps"].append(
            {
                "name": "cancel_skipped_after_fill",
                "result": {
                    "ok": True,
                    "status": "cancel_skipped",
                    "reason_codes": ["ORDER_ALREADY_FILLED_AFTER_SYNC"],
                    "network_call_performed": False,
                    "lifecycle_evidence": sanitize_payload(lifecycle_evidence),
                },
            }
        )
        record.update(
            {
                "status": "completed",
                "reason_codes": [],
                "order_identifier": _hash_identifier(broker_order_id),
                "kill_switch_reenabled": True,
                "cancel_skipped": True,
                "cancel_skipped_reason": "ORDER_ALREADY_FILLED_AFTER_SYNC",
            }
        )
        return record

    cancel_result = _attempt_cancel(open_adapter, broker_order_id)
    record["steps"].append({"name": "cancel", "result": sanitize_payload(cancel_result)})
    if not cancel_result.get("ok"):
        record.update(
            {
                "status": "cancel_failed",
                "reason_codes": cancel_result.get("reason_codes", []),
                "kill_switch_reenabled": True,
            }
        )
        return record

    record.update(
        {
            "status": "completed",
            "reason_codes": [],
            "order_identifier": _hash_identifier(broker_order_id),
            "kill_switch_reenabled": True,
        }
    )
    return record


def _lifecycle_evidence(synced: Mapping[str, Any], *, broker_order_id: str, symbol: str, qty: int) -> dict[str, Any]:
    """Summarize submit -> sync evidence without leaking broker identifiers."""
    normalized_symbol = symbol.strip().upper()
    orders = [row for row in synced.get("orders") or [] if isinstance(row, Mapping)]
    fills = [row for row in synced.get("fills") or [] if isinstance(row, Mapping)]
    positions = [row for row in synced.get("positions") or [] if isinstance(row, Mapping)]
    matching_order = _matching_order(orders, broker_order_id=broker_order_id, symbol=normalized_symbol)
    filled_qty = _int_or_zero(matching_order.get("filled_qty") or matching_order.get("qty")) if matching_order else 0
    remaining_qty = _int_or_zero(matching_order.get("remaining_qty")) if matching_order else 0
    status = str(matching_order.get("status") or "").strip().lower() if matching_order else ""
    order_filled = status in {"filled", "fully_filled"} or (
        bool(matching_order) and filled_qty >= int(qty) and remaining_qty <= 0
    )
    matching_positions = [
        row
        for row in positions
        if str(row.get("symbol") or row.get("pdno") or row.get("ovrs_pdno") or "").strip().upper() == normalized_symbol
    ]
    position_qty = sum(_int_or_zero(row.get("qty") or row.get("quantity") or row.get("hldg_qty")) for row in matching_positions)
    return {
        "order_seen": bool(matching_order),
        "order_status": status or None,
        "order_filled": bool(order_filled),
        "filled_qty": filled_qty,
        "remaining_qty": remaining_qty,
        "fills_count": len(fills),
        "positions_count": len(positions),
        "position_changed": bool(position_qty),
        "position_qty": position_qty,
        "portfolio_seen": isinstance(synced.get("portfolio"), Mapping),
    }


def _matching_order(
    orders: list[Mapping[str, Any]],
    *,
    broker_order_id: str,
    symbol: str,
) -> Mapping[str, Any] | None:
    for order in orders:
        if broker_order_id and str(order.get("broker_order_id") or "") == broker_order_id:
            return order
    for order in orders:
        order_symbol = str(order.get("symbol") or order.get("pdno") or order.get("ovrs_pdno") or "").strip().upper()
        if symbol and order_symbol == symbol:
            return order
    return None


def _int_or_zero(value: Any) -> int:
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return 0


def _attempt_cancel(adapter: Any, broker_order_id: str) -> dict[str, Any]:
    """Attempt to cancel only the broker order created by this Phase 12C run."""
    if not broker_order_id:
        return {
            "ok": False,
            "status": "cancel_skipped",
            "reason_codes": ["BROKER_ORDER_ID_MISSING"],
            "network_call_performed": False,
        }
    return adapter.cancel_order(broker_order_id=broker_order_id, confirm=True)


def sanitize_payload(value: Any) -> Any:
    """Return a JSON-safe payload with broker identifiers and sensitive keys redacted."""
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            lower_key = key.lower()
            if lower_key in SENSITIVE_KEYS:
                sanitized[key] = "***REDACTED***"
            elif lower_key in IDENTIFIER_KEYS:
                sanitized[key] = _hash_identifier(raw_value)
            else:
                sanitized[key] = sanitize_payload(raw_value)
        return sanitized
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_payload(item) for item in value]
    return value


def write_record(record: dict[str, Any], path: Path) -> Path:
    """Write a redacted Phase 12C record under the repository workspace."""
    resolved = path.resolve()
    root = PROJECT_ROOT.resolve()
    if root not in resolved.parents and resolved != root:
        raise ValueError("record path must stay inside the repository")
    if resolved.suffix.lower() != ".json":
        raise ValueError("record path must be a .json file")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return resolved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 12C KIS paper controlled dry-run helper")
    parser.add_argument("--execute", action="store_true", help="perform the controlled paper network dry-run")
    parser.add_argument("--symbol", default="005930", help="domestic stock code for the minimum-size paper order")
    parser.add_argument("--side", default="buy", choices=["buy", "sell"], help="paper order side")
    parser.add_argument("--qty", type=int, default=1, help="minimum paper order quantity")
    parser.add_argument("--limit-price", type=float, default=None, help="optional paper limit price")
    parser.add_argument("--market", default="KR", choices=["KR", "US"], help="paper market for request metadata")
    parser.add_argument("--exchange", default=None, help="KRX for KR or NASD/NYSE/AMEX for US")
    parser.add_argument("--currency", default=None, help="KRW for KR or USD for US")
    parser.add_argument("--confirm-submit", default=None, help=f"must equal {CONFIRMATION_TOKEN} when executing")
    parser.add_argument("--confirm-cancel", default=None, help=f"must equal {CONFIRMATION_TOKEN} when executing")
    parser.add_argument(
        "--confirm-trading-window",
        default=None,
        help=f"must equal {TRADING_WINDOW_CONFIRMATION_TOKEN} when executing",
    )
    parser.add_argument("--record-path", default=None, help="optional redacted .json record path inside the repo")
    parser.add_argument(
        "--temporary-paper-config",
        action="store_true",
        help="use a process-only Phase 12C paper config override without writing backend/config/paper.yaml",
    )
    parser.add_argument(
        "--as-of",
        default=None,
        help="optional ISO timestamp used only for local trading-window validation",
    )
    parser.add_argument(
        "--allow-premarket-submit",
        action="store_true",
        help="deprecated compatibility flag; US paper submit remains regular-session only",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.qty <= 0:
        parser.error("--qty must be positive")
    record = run_controlled_dry_run(
        execute=bool(args.execute),
        symbol=args.symbol,
        side=args.side,
        qty=args.qty,
        limit_price=args.limit_price,
        market=args.market,
        exchange=args.exchange or ("NASD" if args.market == "US" else "KRX"),
        currency=args.currency or ("USD" if args.market == "US" else "KRW"),
        confirm_submit=args.confirm_submit,
        confirm_cancel=args.confirm_cancel,
        confirm_trading_window=args.confirm_trading_window,
        as_of=_parse_as_of(args.as_of),
        use_temporary_paper_config=bool(args.temporary_paper_config),
        allow_premarket_submit=bool(args.allow_premarket_submit),
    )
    if args.record_path:
        write_record(record, PROJECT_ROOT / args.record_path)
    print(json.dumps(record, indent=2, sort_keys=True))
    if not args.execute:
        return 0
    return 0 if record.get("status") == "completed" else 2


def _trading_window_status(*, market: str, as_of: datetime | None = None) -> dict[str, Any]:
    """Return a local static regular-session guard before a US paper submit."""
    normalized_market = market.strip().upper()
    now = as_of or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    if normalized_market not in {"US", "USA", "OVERSEAS"}:
        return {
            "ok": True,
            "market": normalized_market or "KR",
            "reason_codes": [],
            "source": "no_local_regular_session_guard_for_market",
        }
    local = now.astimezone(US_EASTERN)
    local_time = local.time()
    in_premarket = US_PREMARKET_SESSION_START <= local_time < US_REGULAR_SESSION_START
    in_regular_hours = US_REGULAR_SESSION_START <= local_time < US_REGULAR_SESSION_END
    is_weekday = local.weekday() < 5
    ok = bool(is_weekday and in_regular_hours)
    session = "premarket" if in_premarket else "regular" if in_regular_hours else "closed"
    next_regular_session_start = _next_us_regular_session_start(local)
    return {
        "ok": ok,
        "market": "US",
        "timezone": "America/New_York",
        "local_time": local.isoformat(),
        "weekday": local.strftime("%A"),
        "session": session if is_weekday else "closed",
        "premarket_session_start": "04:00",
        "premarket_session_end": "09:30",
        "regular_session_start": "09:30",
        "regular_session_end": "16:00",
        "next_regular_session_start": next_regular_session_start.isoformat(),
        "calendar_quality": "static_weekday_regular_session_guard",
        "reason_codes": [] if ok else ["US_REGULAR_SESSION_REQUIRED"],
    }


def _next_us_regular_session_start(local: datetime) -> datetime:
    """Return the next static weekday regular-session start in America/New_York."""
    candidate = local.replace(
        hour=US_REGULAR_SESSION_START.hour,
        minute=US_REGULAR_SESSION_START.minute,
        second=0,
        microsecond=0,
    )
    if local.weekday() >= 5 or local >= candidate:
        candidate = candidate + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate = candidate + timedelta(days=1)
    return candidate


def _parse_as_of(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    return datetime.fromisoformat(normalized)


def _adapter_config(
    config: Mapping[str, Any],
    *,
    kill_switch_enabled: bool,
    market: str = "KR",
    exchange: str = "KRX",
    currency: str = "KRW",
) -> dict[str, Any]:
    normalized_market = market.strip().upper()
    normalized_exchange = exchange.strip().upper()
    normalized_currency = currency.strip().upper()
    adapter_config = {
        "mode": "paper",
        "kis_env": "paper",
        "broker_mode": REQUIRED_PAPER_BROKER_MODE,
        "market": normalized_market,
        "venue": normalized_exchange,
        "currency": normalized_currency,
        "overseas_exchange": normalized_exchange if normalized_market in {"US", "USA", "OVERSEAS"} else "NASD",
        "enabled": True,
        "configured_can_create": True,
        "paper_order_submit_enabled": True,
        "paper_bot_confirm_enabled": True,
        "preview_only": False,
        "kill_switch_enabled": kill_switch_enabled,
        "network_enabled": True,
        "balance_inquiry_enabled": True,
        "broker_adapter_enabled": True,
        "official_endpoint_confirmed": True,
        "official_balance_endpoint_confirmed": True,
        "live_order_enabled": False,
        "live_fallback_enabled": False,
    }
    adapter_config.update({key: config[key] for key in config if key in adapter_config})
    adapter_config["mode"] = "paper"
    adapter_config["market"] = normalized_market
    adapter_config["venue"] = normalized_exchange
    adapter_config["currency"] = normalized_currency
    adapter_config["overseas_exchange"] = normalized_exchange if normalized_market in {"US", "USA", "OVERSEAS"} else "NASD"
    adapter_config["kill_switch_enabled"] = kill_switch_enabled
    adapter_config["live_order_enabled"] = False
    adapter_config["live_fallback_enabled"] = False
    return adapter_config


def _order_metadata(*, market: str, exchange: str, currency: str, order_session: str = "") -> dict[str, str]:
    normalized_market = market.strip().upper()
    normalized_exchange = exchange.strip().upper()
    normalized_currency = currency.strip().upper()
    normalized_order_session = order_session.strip().lower()
    if normalized_market in {"US", "USA", "OVERSEAS"}:
        metadata = {
            "market": "US",
            "venue": normalized_exchange or "NASD",
            "exchange": normalized_exchange or "NASD",
            "currency": normalized_currency or "USD",
        }
        if normalized_order_session:
            metadata["order_session"] = normalized_order_session
        return metadata
    return {"exchange": normalized_exchange or "KRX"}


def _temporary_phase12c_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return a process-only paper config for one controlled Phase 12C dry-run."""
    temporary = dict(config)
    temporary.update(
        {
            "mode": "paper",
            "kis_env": "paper",
            "broker_mode": REQUIRED_PAPER_BROKER_MODE,
            "enabled": True,
            "configured_can_create": True,
            "paper_order_submit_enabled": True,
            "paper_bot_confirm_enabled": True,
            "preview_only": False,
            "kill_switch_enabled": False,
            "network_enabled": True,
            "balance_inquiry_enabled": True,
            "broker_adapter_enabled": True,
            "official_endpoint_confirmed": True,
            "official_balance_endpoint_confirmed": True,
            "live_order_enabled": False,
            "live_fallback_enabled": False,
        }
    )
    return temporary


def _load_config(config: Mapping[str, Any] | None = None) -> tuple[dict[str, Any], list[str]]:
    if config is not None:
        return dict(config), []
    loaded, reasons = PaperConfigService(CONFIG_DIR).load()
    return dict(loaded), list(reasons)


def _hash_identifier(value: Any) -> str:
    return f"sha256:{_digest(str(value))}"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _is_true(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_false(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"0", "false", "no", "off"}


if __name__ == "__main__":
    sys.exit(main())
