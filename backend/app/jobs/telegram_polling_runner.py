from __future__ import annotations

import argparse
import json
import time

from backend.app.core.database import SessionLocal
from backend.app.services.telegram_polling_service import TelegramPollingService


def build_parser() -> argparse.ArgumentParser:
    """Telegram getUpdates polling CLI parser를 생성한다."""
    parser = argparse.ArgumentParser(description="Safe Telegram getUpdates polling runner")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--once", action="store_true", help="run one getUpdates polling cycle after confirmation")
    mode.add_argument("--loop", action="store_true", help="run bounded polling loop only when env gates allow it")
    parser.add_argument("--offset", type=int, default=None)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=0)
    parser.add_argument("--max-iterations", type=int, default=1)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--dry-run", action="store_true", default=None)
    parser.add_argument("--no-dry-run", action="store_false", dest="dry_run")
    parser.add_argument("--send-replies", action="store_true", default=None)
    parser.add_argument("--no-send-replies", action="store_false", dest="send_replies")
    return parser


def main(argv: list[str] | None = None) -> int:
    """기본은 status-only이며 --once/--loop에서만 polling을 실행한다."""
    parser = build_parser()
    args = parser.parse_args(argv)
    with SessionLocal() as db:
        service = TelegramPollingService(db)
        if args.once:
            result = service.run_once(
                offset=args.offset,
                limit=args.limit,
                timeout_seconds=args.timeout_seconds,
                dry_run=args.dry_run,
                send_replies=args.send_replies,
                confirm=True,
            )
            print(json.dumps(result, sort_keys=True, default=str))
            return 0 if result.get("ok") else 2
        if args.loop:
            result = _run_loop(service, args)
            print(json.dumps(result, sort_keys=True, default=str))
            return 0 if result.get("ok") else 2
        payload = service.status()
        payload["execute_required"] = True
        print(json.dumps(payload, sort_keys=True, default=str))
        return 0


def _run_loop(service: TelegramPollingService, args: argparse.Namespace) -> dict[str, object]:
    offset = args.offset
    iterations = []
    for index in range(max(1, int(args.max_iterations))):
        result = service.run_once(
            offset=offset,
            limit=args.limit,
            timeout_seconds=args.timeout_seconds,
            dry_run=args.dry_run,
            send_replies=args.send_replies,
            confirm=True,
        )
        iterations.append(result)
        offset = result.get("next_offset") if isinstance(result.get("next_offset"), int) else offset
        if index < max(1, int(args.max_iterations)) - 1:
            time.sleep(max(0.0, float(args.sleep_seconds)))
    return {
        "ok": all(item.get("ok") for item in iterations),
        "status": "loop_completed",
        "iterations": iterations,
        "iteration_count": len(iterations),
        "next_offset": offset,
        "network_call_performed": any(bool(item.get("network_call_performed")) for item in iterations),
        "live_order_created": False,
        "secrets_redacted": True,
    }


if __name__ == "__main__":
    raise SystemExit(main())
