from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time

from backend.app.core.database import SessionLocal
from backend.app.services.paper_bot_service import PaperBotService

DEFAULT_MAX_ITERATIONS = 1
DEFAULT_MAX_ITERATIONS_CAP = 25


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safe paper bot runner")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="run one safe paper bot cycle")
    mode.add_argument("--loop", action="store_true", help="run loop mode only when scheduler is explicitly enabled")
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=_env_int("PAPER_BOT_MAX_ITERATIONS", DEFAULT_MAX_ITERATIONS),
        help="maximum loop iterations; bounded by PAPER_BOT_MAX_ITERATIONS_CAP",
    )
    parser.add_argument(
        "--stop-file",
        default=os.getenv("PAPER_BOT_STOP_FILE", ""),
        help="optional stop marker file; when present the loop exits before the next iteration",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    with SessionLocal() as db:
        service = PaperBotService(db)
        if args.once:
            print(json.dumps(service.run_once(), sort_keys=True))
            return 0
        loop = service.loop_status()
        if not loop["loop_allowed"]:
            print(json.dumps(loop, sort_keys=True))
            return 0
        requested_iterations = max(1, int(args.max_iterations))
        iteration_cap = max(1, _env_int("PAPER_BOT_MAX_ITERATIONS_CAP", DEFAULT_MAX_ITERATIONS_CAP))
        iterations = min(requested_iterations, iteration_cap)
        stop_file = Path(str(args.stop_file)).expanduser() if str(args.stop_file).strip() else None
        results = []
        stop_reason = ""
        for index in range(iterations):
            loop = service.loop_status()
            if not loop["loop_allowed"]:
                stop_reason = "loop_gate_closed"
                break
            if stop_file is not None and stop_file.exists():
                stop_reason = "stop_file_detected"
                break
            results.append(service.run_once())
            if index < iterations - 1:
                time.sleep(float(loop["interval_seconds"]))
        print(
            json.dumps(
                {
                    "status": "loop_completed" if not stop_reason else "loop_stopped",
                    "auto_start": False,
                    "bounded_loop": True,
                    "iterations_requested": requested_iterations,
                    "iterations_cap": iteration_cap,
                    "iterations_planned": iterations,
                    "iterations_run": len(results),
                    "stop_reason": stop_reason,
                    "live_order_created": False,
                    "broker_order_created": False,
                    "network_call_performed": False,
                    "results": results,
                },
                sort_keys=True,
            )
        )
        return 0


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


if __name__ == "__main__":
    raise SystemExit(main())
