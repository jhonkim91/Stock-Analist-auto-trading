from __future__ import annotations

import argparse
import json
import time

from backend.app.core.database import SessionLocal
from backend.app.services.paper_bot_service import PaperBotService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safe paper bot runner")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="run one safe paper bot cycle")
    mode.add_argument("--loop", action="store_true", help="run loop mode only when scheduler is explicitly enabled")
    parser.add_argument("--max-iterations", type=int, default=1, help="maximum loop iterations")
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
        iterations = max(1, int(args.max_iterations))
        results = []
        for _ in range(iterations):
            results.append(service.run_once())
            if iterations > 1:
                time.sleep(float(loop["interval_seconds"]))
        print(json.dumps({"status": "loop_completed", "results": results}, sort_keys=True))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
