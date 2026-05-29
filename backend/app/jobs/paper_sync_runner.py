from __future__ import annotations

import argparse
import json

from backend.app.core.database import SessionLocal
from backend.app.services.paper_sync_service import SUPPORTED_SYNC_SCOPES
from backend.app.services.paper_sync_worker_service import PaperSyncWorkerService


def build_parser() -> argparse.ArgumentParser:
    """KIS paper sync worker CLI parser를 생성한다."""
    parser = argparse.ArgumentParser(description="Safe KIS paper sync worker runner")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--once", action="store_true", help="run one sync worker cycle after confirmation")
    mode.add_argument("--loop", action="store_true", help="run bounded loop only when worker is explicitly enabled")
    parser.add_argument("--scope", choices=sorted(SUPPORTED_SYNC_SCOPES), default="all")
    parser.add_argument("--max-iterations", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    """기본은 status-only이며 --once/--loop에서만 worker를 실행한다."""
    parser = build_parser()
    args = parser.parse_args(argv)
    with SessionLocal() as db:
        service = PaperSyncWorkerService(db)
        if args.once:
            result = service.run_once(scope=args.scope, confirm=True)
            print(json.dumps(result, sort_keys=True, default=str))
            return 0 if result.get("ok") else 2
        if args.loop:
            result = service.run_loop(scope=args.scope, max_iterations=args.max_iterations)
            print(json.dumps(result, sort_keys=True, default=str))
            return 0 if result.get("ok") else 2
        payload = service.status()
        payload["execute_required"] = True
        print(json.dumps(payload, sort_keys=True, default=str))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
