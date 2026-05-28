from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import MutableMapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.brokers.kis_paper import DEFAULT_KIS_PAPER_BASE_URL, KIS_ACCESS_TOKEN_ENV, KIS_PAPER_BASE_URL_ENV
from backend.app.services.kis_http_client import KisHttpClient
from backend.app.services.kis_paper_websocket_service import KisPaperWebSocketService
from backend.app.services.kis_token_manager import KIS_ENV_ENV, KisTokenManager
from backend.app.services.token_manager import KIS_APP_KEY_ENV, KIS_APP_SECRET_ENV
from tools.kis_paper_phase12c_dry_run import (
    CONFIRMATION_TOKEN,
    TRADING_WINDOW_CONFIRMATION_TOKEN,
    _parse_as_of,
    _trading_window_status,
    run_controlled_dry_run,
    sanitize_payload,
    write_record,
)
from tools.kis_paper_phase21_service_lifecycle import run_phase21_service_lifecycle

PHASE21_TOKEN_CONFIRMATION_TOKEN = "CONFIRM_KIS_PAPER_PHASE21_TOKEN"
PHASE21_WEBSOCKET_CONFIRMATION_TOKEN = "CONFIRM_KIS_PAPER_PHASE21_WEBSOCKET"
KIS_OVERSEAS_PRICE_PATH = "/uapi/overseas-price/v1/quotations/price"
KIS_OVERSEAS_PRICE_TR_ID = "HHDFS00000300"
KIS_OVERSEAS_PRICE_EXCHANGE_CODES = {
    "AMEX": "AMS",
    "AMS": "AMS",
    "NAS": "NAS",
    "NASD": "NAS",
    "NASDAQ": "NAS",
    "NYS": "NYS",
    "NYSE": "NYS",
}
PHASE21_ENV_FILE_KEYS = {
    "BROKER_MODE",
    "ENABLE_REAL_ORDER",
    "KIS_ACCESS_TOKEN",
    "KIS_ACCOUNT_NO",
    "KIS_APP_KEY",
    "KIS_APP_SECRET",
    "KIS_ENV",
    "KIS_OVERSEAS_CURRENCY",
    "KIS_OVERSEAS_EXCHANGE_CODE",
    "KIS_OVERSEAS_ORDER_SESSION",
    "KIS_PAPER_BASE_URL",
    "KIS_PRODUCT_CODE",
    "KIS_TOKEN_ISSUE_ENABLED",
    "KIS_WEBSOCKET_APPROVAL_ENABLED",
    "KIS_WEBSOCKET_APPROVAL_KEY",
    "PAPER_BOT_AUTO_SUBMIT",
    "PAPER_BOT_CONFIRM",
    "PAPER_ORDER_SUBMIT_ENABLED",
    "PAPER_TRADING_CAN_CREATE",
    "PAPER_TRADING_ENABLED",
    "PAPER_TRADING_KILL_SWITCH",
    "PAPER_TRADING_MARKET",
    "PAPER_TRADING_NETWORK_ENABLED",
    "PAPER_WEBSOCKET_CONNECT_ENABLED",
}
SECRET_LIKE_ENV_NAME_PARTS = ("ACCOUNT", "APP_KEY", "APP_SECRET", "CHAT_ID", "DATABASE_URL", "KEY", "SECRET", "TOKEN", "WEBHOOK")


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
    execute_service_lifecycle: bool = False,
    derive_limit_from_price: bool = False,
    limit_premium_bps: int = 300,
    confirm_token: str | None = None,
    confirm_websocket: str | None = None,
    confirm_submit: str | None = None,
    confirm_sync: str | None = None,
    confirm_cancel: str | None = None,
    confirm_trading_window: str | None = None,
    as_of: datetime | None = None,
    allow_premarket_submit: bool = False,
    env: Mapping[str, str] | None = None,
    config: Mapping[str, Any] | None = None,
    token_manager_factory: Callable[[], Any] | None = None,
    websocket_service_factory: Callable[[], Any] | None = None,
    adapter_factory: Callable[[dict[str, Any]], Any] | None = None,
    session_factory: Callable[[], Any] | None = None,
    config_dir: Path | None = None,
    submit_adapter: Any | None = None,
    sync_adapter: Any | None = None,
    env_file_path: Path | None = None,
    env_file_override: bool = False,
    price_http_client: Any | None = None,
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
        "network_call_performed": False,
        "steps": [],
    }
    effective_limit_price = limit_price
    if execute_submit and execute_service_lifecycle:
        record.update(
            {
                "status": "invalid_request",
                "reason_codes": ["PHASE21_SINGLE_SUBMIT_PATH_REQUIRED"],
                "network_call_performed": False,
            }
        )
        return _with_completion_audit(record)

    if env_file_path is not None:
        env_load_result = _load_env_file(env_file_path, override=env_file_override)
        record["steps"].append({"name": "load_env_file", "result": sanitize_payload(env_load_result)})
        if not env_load_result.get("ok"):
            record.update(_terminal_status("env_file_load_failed", env_load_result))
            return _with_completion_audit(record)

    if issue_token:
        token_result = token_manager_factory().issue_paper_access_token(
            confirm=confirm_token == PHASE21_TOKEN_CONFIRMATION_TOKEN,
            install_to_process_env=True,
        )
        record["steps"].append({"name": "issue_token", "result": sanitize_payload(token_result)})
        record["network_call_performed"] = bool(record["network_call_performed"] or token_result.get("network_call_performed"))
        if not token_result.get("ok"):
            record.update(_terminal_status("token_failed", token_result))
            return _with_completion_audit(record)

    websocket_service = websocket_service_factory()
    if issue_websocket_approval:
        approval_result = websocket_service.issue_approval_key(
            confirm=confirm_websocket == PHASE21_WEBSOCKET_CONFIRMATION_TOKEN,
            install_to_process_env=True,
        )
        record["steps"].append({"name": "issue_websocket_approval", "result": sanitize_payload(approval_result)})
        record["network_call_performed"] = bool(record["network_call_performed"] or approval_result.get("network_call_performed"))
        if not approval_result.get("ok"):
            record.update(_terminal_status("websocket_approval_failed", approval_result))
            return _with_completion_audit(record)

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
        return _with_completion_audit(record)

    if websocket_smoke:
        smoke = websocket_service.bounded_connect_smoke(
            symbol=symbol,
            kind="quote",
            market="US",
            exchange=exchange,
            confirm=confirm_websocket == PHASE21_WEBSOCKET_CONFIRMATION_TOKEN,
        )
        record["steps"].append({"name": "websocket_us_bounded_smoke", "result": sanitize_payload(smoke)})
        record["network_call_performed"] = bool(record["network_call_performed"] or smoke.get("network_call_performed"))
        if not smoke.get("ok"):
            record.update(_terminal_status("websocket_smoke_failed", smoke))
            return _with_completion_audit(record)

    if derive_limit_from_price and (execute_submit or execute_service_lifecycle) and effective_limit_price is None:
        price_window = _trading_window_status(market="US", as_of=as_of)
        if not price_window["ok"]:
            record["steps"].append(
                {
                    "name": "derive_limit_from_price_skipped",
                    "result": {
                        "ok": False,
                        "status": "trading_window_closed",
                        "reason_codes": list(price_window["reason_codes"]),
                        "trading_window": price_window,
                        "network_call_performed": False,
                    },
                }
            )
        else:
            price_result = _fetch_overseas_price(symbol=symbol, exchange=exchange, http_client=price_http_client)
            if price_result.get("ok") and price_result.get("last_price_available"):
                price_result["derived_limit_price"] = _derive_limit_price(
                    float(price_result["last_price"]),
                    premium_bps=limit_premium_bps,
                )
                price_result["limit_premium_bps"] = limit_premium_bps
                effective_limit_price = float(price_result["derived_limit_price"])
            record["steps"].append({"name": "derive_limit_from_price", "result": sanitize_payload(price_result)})
            record["network_call_performed"] = bool(record["network_call_performed"] or price_result.get("network_call_performed"))
            if not price_result.get("ok"):
                record.update(_terminal_status("price_lookup_failed", price_result))
                return _with_completion_audit(record)
            if effective_limit_price is None:
                record.update(
                    {
                        "status": "price_lookup_failed",
                        "reason_codes": ["KIS_OVERSEAS_PRICE_LAST_PRICE_MISSING"],
                        "network_call_performed": bool(record["network_call_performed"]),
                        "live_order_created": False,
                    }
                )
                return _with_completion_audit(record)

    if execute_submit:
        submit_record = run_controlled_dry_run(
            execute=True,
            symbol=symbol,
            side="buy",
            qty=qty,
            limit_price=effective_limit_price,
            confirm_submit=confirm_submit,
            confirm_cancel=confirm_cancel,
            confirm_trading_window=confirm_trading_window,
            market="US",
            exchange=exchange,
            currency=currency,
            as_of=as_of,
            use_temporary_paper_config=True,
            allow_premarket_submit=allow_premarket_submit,
            env=env,
            config=config,
            adapter_factory=adapter_factory,
        )
        record["steps"].append({"name": "controlled_us_submit_list_sync_cancel", "result": sanitize_payload(submit_record)})
        record["network_call_performed"] = bool(record["network_call_performed"] or submit_record.get("network_call_performed"))
        if submit_record.get("status") != "completed":
            record.update(
                {
                    "status": "submit_lifecycle_incomplete",
                    "reason_codes": list(submit_record.get("reason_codes") or [submit_record.get("status")]),
                    "live_order_created": False,
                }
            )
            return _with_completion_audit(record)

    if execute_service_lifecycle:
        service_record = run_phase21_service_lifecycle(
            symbol=symbol,
            qty=qty,
            limit_price=effective_limit_price,
            exchange=exchange,
            currency=currency,
            confirm_submit=confirm_submit,
            confirm_sync=confirm_sync or confirm_submit,
            confirm_cancel=confirm_cancel,
            confirm_trading_window=confirm_trading_window,
            as_of=as_of,
            session_factory=session_factory,
            config_dir=config_dir,
            submit_adapter=submit_adapter,
            sync_adapter=sync_adapter,
        )
        record["steps"].append({"name": "service_us_submit_sync_cancel", "result": sanitize_payload(service_record)})
        record["network_call_performed"] = bool(record["network_call_performed"] or service_record.get("network_call_performed"))
        if service_record.get("status") != "completed":
            record.update(
                {
                    "status": "service_lifecycle_incomplete",
                    "reason_codes": list(service_record.get("reason_codes") or [service_record.get("status")]),
                    "live_order_created": False,
                }
            )
            return _with_completion_audit(record)

    record.update({"status": "completed", "reason_codes": [], "network_call_performed": bool(record["network_call_performed"])})
    return _with_completion_audit(record)


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
    parser.add_argument("--execute-service-lifecycle", action="store_true")
    parser.add_argument(
        "--derive-limit-from-price",
        action="store_true",
        help="during US regular session only, fetch read-only KIS overseas price and derive limit price when --limit-price is omitted",
    )
    parser.add_argument("--limit-premium-bps", type=int, default=300)
    parser.add_argument("--confirm-token", default=None, help=f"must equal {PHASE21_TOKEN_CONFIRMATION_TOKEN}")
    parser.add_argument("--confirm-websocket", default=None, help=f"must equal {PHASE21_WEBSOCKET_CONFIRMATION_TOKEN}")
    parser.add_argument("--confirm-submit", default=None, help=f"must equal {CONFIRMATION_TOKEN}")
    parser.add_argument("--confirm-sync", default=None, help=f"must equal {CONFIRMATION_TOKEN}")
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
    parser.add_argument(
        "--allow-premarket-submit",
        action="store_true",
        help="deprecated compatibility flag; US paper submit remains regular-session only",
    )
    parser.add_argument(
        "--load-env-local",
        action="store_true",
        help="load .env.local into this helper process only; raw values are not printed",
    )
    parser.add_argument("--env-file", default=".env.local", help="env file path used with --load-env-local")
    parser.add_argument(
        "--env-file-override",
        action="store_true",
        help="override already configured process env values when loading --env-file",
    )
    parser.add_argument("--record-path", default=None, help="optional redacted .json record path inside the repo")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.qty <= 0:
        parser.error("--qty must be positive")
    if args.execute_submit and args.execute_service_lifecycle:
        parser.error("--execute-submit and --execute-service-lifecycle cannot be used together")
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
        execute_service_lifecycle=bool(args.execute_service_lifecycle),
        derive_limit_from_price=bool(args.derive_limit_from_price),
        limit_premium_bps=int(args.limit_premium_bps),
        confirm_token=args.confirm_token,
        confirm_websocket=args.confirm_websocket,
        confirm_submit=args.confirm_submit,
        confirm_sync=args.confirm_sync,
        confirm_cancel=args.confirm_cancel,
        confirm_trading_window=args.confirm_trading_window,
        as_of=_parse_as_of(args.as_of),
        allow_premarket_submit=bool(args.allow_premarket_submit),
        env_file_path=Path(args.env_file) if args.load_env_local else None,
        env_file_override=bool(args.env_file_override),
    )
    if args.record_path:
        write_record(record, PROJECT_ROOT / args.record_path)
    print(json.dumps(record, indent=2, sort_keys=True, default=str))
    return 0 if record.get("status") == "completed" else 2


def _with_completion_audit(record: dict[str, Any]) -> dict[str, Any]:
    """Attach goal-level completion evidence without changing helper step status."""
    record["completion_audit"] = _phase21_goal_completion_audit(record)
    return record


def _phase21_goal_completion_audit(record: Mapping[str, Any]) -> dict[str, Any]:
    token_step = _step_result(record, "issue_token")
    approval_step = _step_result(record, "issue_websocket_approval")
    smoke_step = _step_result(record, "websocket_us_bounded_smoke")
    service_step = _step_result(record, "service_us_submit_sync_cancel")
    service_evidence = (
        service_step.get("lifecycle_evidence") if isinstance(service_step.get("lifecycle_evidence"), Mapping) else {}
    )
    service_audit = (
        service_step.get("completion_audit") if isinstance(service_step.get("completion_audit"), Mapping) else {}
    )
    requirements = {
        "paper_only": bool(record.get("paper_only")),
        "live_order_created_false": not bool(record.get("live_order_created")),
        "raw_secret_printed_false": not bool(record.get("raw_secret_printed")),
        "token_issued": bool(token_step.get("ok") and token_step.get("token_issued")),
        "network_call_performed": bool(record.get("network_call_performed")),
        "websocket_approval_issued": bool(approval_step.get("ok") and approval_step.get("network_call_performed")),
        "websocket_smoke_message_received": bool(smoke_step.get("ok") and smoke_step.get("message_received")),
        "service_lifecycle_completed": service_step.get("status") == "completed",
        "paper_order_created": bool(service_evidence.get("paper_order_created")),
        "broker_order_created": bool(service_evidence.get("broker_order_created")),
        "paper_fill_created": bool(service_evidence.get("paper_fill_created")),
        "paper_position_changed": bool(service_evidence.get("paper_position_changed")),
        "orders_count_unchanged": service_evidence.get("orders_count_delta") == 0,
        "service_completion_audit_passed": bool(service_audit.get("complete")),
    }
    missing = [key for key, value in requirements.items() if not value]
    return {
        "scope": "phase21_token_network_websocket_order_fill_position",
        "complete": not missing,
        "requirements": requirements,
        "missing_requirements": missing,
    }


def _step_result(record: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    steps = record.get("steps")
    if not isinstance(steps, list):
        return {}
    for step in steps:
        if not isinstance(step, Mapping) or step.get("name") != name:
            continue
        result = step.get("result")
        return result if isinstance(result, Mapping) else {}
    return {}


def _terminal_status(status: str, result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": status,
        "reason_codes": list(result.get("reason_codes") or [result.get("reason") or status]),
        "network_call_performed": bool(result.get("network_call_performed", False)),
        "live_order_created": False,
    }


def _fetch_overseas_price(*, symbol: str, exchange: str, http_client: Any | None = None) -> dict[str, Any]:
    reasons: list[str] = []
    if os.getenv(KIS_ENV_ENV, "").strip().lower() != "paper":
        reasons.append("KIS_ENV_PAPER_REQUIRED")
    app_key = os.getenv(KIS_APP_KEY_ENV, "").strip()
    app_secret = os.getenv(KIS_APP_SECRET_ENV, "").strip()
    access_token = os.getenv(KIS_ACCESS_TOKEN_ENV, "").strip()
    if not KisTokenManager.is_configured_value(app_key):
        reasons.append("KIS_APP_KEY_MISSING")
    if not KisTokenManager.is_configured_value(app_secret):
        reasons.append("KIS_APP_SECRET_MISSING")
    if not KisTokenManager.is_configured_value(access_token):
        reasons.append("KIS_ACCESS_TOKEN_MISSING")
    base_url = os.getenv(KIS_PAPER_BASE_URL_ENV, DEFAULT_KIS_PAPER_BASE_URL).strip() or DEFAULT_KIS_PAPER_BASE_URL
    if "openapi.koreainvestment.com" in base_url and "openapivts.koreainvestment.com" not in base_url:
        reasons.append("KIS_LIVE_BASE_URL_BLOCKED")
    if reasons:
        return {
            "ok": False,
            "status": "price_lookup_blocked",
            "reason": reasons[0],
            "reason_codes": reasons,
            "network_call_performed": False,
            "secrets_redacted": True,
        }
    client = KisHttpClient(http_client=http_client, max_retries=0)
    result = client.request(
        "GET",
        f"{base_url.rstrip('/')}{KIS_OVERSEAS_PRICE_PATH}",
        headers={
            "authorization": f"Bearer {access_token}",
            "appkey": app_key,
            "appsecret": app_secret,
            "tr_id": KIS_OVERSEAS_PRICE_TR_ID,
            "custtype": "P",
        },
        params={"AUTH": "", "EXCD": _overseas_price_exchange_code(exchange), "SYMB": symbol.strip().upper()},
        operation="kis_overseas_price",
        tr_id=KIS_OVERSEAS_PRICE_TR_ID,
        correlation_prefix="kis-paper-us-price",
    )
    if not result.ok:
        return {
            "ok": False,
            "status": "price_lookup_failed",
            "reason": result.reason or "KIS_OVERSEAS_PRICE_REQUEST_FAILED",
            "reason_codes": [result.reason or "KIS_OVERSEAS_PRICE_REQUEST_FAILED"],
            "trace": result.trace,
            "network_call_performed": bool(result.trace.get("network_call_performed", False)),
            "secrets_redacted": True,
        }
    body = result.body
    if str(body.get("rt_cd", "0")) != "0":
        return {
            "ok": False,
            "status": "price_lookup_failed",
            "reason": str(body.get("msg_cd") or "KIS_OVERSEAS_PRICE_RESPONSE_ERROR"),
            "reason_codes": [str(body.get("msg_cd") or "KIS_OVERSEAS_PRICE_RESPONSE_ERROR")],
            "msg_cd": str(body.get("msg_cd") or ""),
            "msg1": str(body.get("msg1") or "").strip(),
            "trace": result.trace,
            "network_call_performed": True,
            "secrets_redacted": True,
        }
    last_price = _extract_last_price(body)
    return {
        "ok": True,
        "status": "price_ok",
        "status_code": result.status_code,
        "reason": None,
        "reason_codes": [],
        "trace": result.trace,
        "last_price_available": last_price is not None,
        "last_price": last_price,
        "network_call_performed": True,
        "secrets_redacted": True,
    }


def _extract_last_price(body: Mapping[str, Any]) -> float | None:
    output = body.get("output")
    row = output if isinstance(output, Mapping) else output[0] if isinstance(output, list) and output and isinstance(output[0], Mapping) else {}
    for key in ("last", "LAST", "tlast", "TMLAST", "price", "PRPR", "prpr", "base", "ovrs_nmix_prpr"):
        value = row.get(key)
        parsed = _to_float(value)
        if parsed is not None and parsed > 0:
            return parsed
    return None


def _derive_limit_price(last_price: float, *, premium_bps: int) -> float:
    premium = max(0, int(premium_bps)) / 10000
    return round(float(last_price) * (1 + premium), 2)


def _overseas_price_exchange_code(exchange: str) -> str:
    normalized = str(exchange or "").strip().upper()
    return KIS_OVERSEAS_PRICE_EXCHANGE_CODES.get(normalized, normalized or "NAS")


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _load_env_file(
    path: Path,
    *,
    override: bool = False,
    target: MutableMapping[str, str] | None = None,
) -> dict[str, Any]:
    """Load allowlisted env keys from a local env file without returning raw values."""
    env_target = os.environ if target is None else target
    resolved = path if path.is_absolute() else PROJECT_ROOT / path
    if not resolved.exists():
        return {
            "ok": False,
            "status": "env_file_missing",
            "reason": "ENV_FILE_MISSING",
            "reason_codes": ["ENV_FILE_MISSING"],
            "path": _record_path(resolved),
            "network_call_performed": False,
            "raw_secret_printed": False,
        }
    loaded: list[str] = []
    skipped_existing: list[str] = []
    ignored: list[str] = []
    try:
        for raw_line in resolved.read_text(encoding="utf-8").splitlines():
            parsed = _parse_env_line(raw_line)
            if parsed is None:
                continue
            key, value = parsed
            if key not in PHASE21_ENV_FILE_KEYS:
                ignored.append(key)
                continue
            if not override and str(env_target.get(key, "")).strip():
                skipped_existing.append(key)
                continue
            env_target[key] = value
            loaded.append(key)
    except OSError:
        return {
            "ok": False,
            "status": "env_file_read_failed",
            "reason": "ENV_FILE_READ_FAILED",
            "reason_codes": ["ENV_FILE_READ_FAILED"],
            "path": _record_path(resolved),
            "network_call_performed": False,
            "raw_secret_printed": False,
        }
    return {
        "ok": True,
        "status": "env_file_loaded",
        "path": _record_path(resolved),
        "override": override,
        "loaded_keys": _public_env_key_names(loaded),
        "skipped_existing_keys": _public_env_key_names(skipped_existing),
        "ignored_keys": _public_env_key_names(set(ignored)),
        "loaded_count": len(loaded),
        "skipped_existing_count": len(skipped_existing),
        "ignored_count": len(set(ignored)),
        "secret_like_key_names_redacted": True,
        "loaded_secret_like_key_count": _secret_like_env_key_count(loaded),
        "skipped_secret_like_key_count": _secret_like_env_key_count(skipped_existing),
        "ignored_secret_like_key_count": _secret_like_env_key_count(set(ignored)),
        "network_call_performed": False,
        "raw_secret_printed": False,
        "secrets_redacted": True,
    }


def _parse_env_line(raw_line: str) -> tuple[str, str] | None:
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None
    if line.lower().startswith("export "):
        line = line[7:].strip()
    if "=" not in line:
        return None
    key, value = line.split("=", 1)
    key = key.strip()
    if not key:
        return None
    return key, _strip_env_value(value.strip())


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _record_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _public_env_key_names(keys: Sequence[str]) -> list[str]:
    return sorted(key for key in keys if not _is_secret_like_env_key_name(key))


def _secret_like_env_key_count(keys: Sequence[str]) -> int:
    return sum(1 for key in keys if _is_secret_like_env_key_name(key))


def _is_secret_like_env_key_name(key: str) -> bool:
    normalized = key.upper()
    return any(part in normalized for part in SECRET_LIKE_ENV_NAME_PARTS)


if __name__ == "__main__":
    sys.exit(main())
