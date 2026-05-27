from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.database import SessionLocal
from backend.app.services.report_automation_service import SUPPORTED_REPORT_AUTOMATION_TYPES, ReportAutomationService


def build_parser() -> argparse.ArgumentParser:
    """report automation run-once CLI argument parser를 생성한다."""
    parser = argparse.ArgumentParser(description="Disabled-by-default daily/weekly report automation runner")
    parser.add_argument("--execute", action="store_true", help="run automation after config/env gates are enabled")
    parser.add_argument(
        "--report-type",
        action="append",
        choices=SUPPORTED_REPORT_AUTOMATION_TYPES,
        help="report type to run; repeat for daily and weekly",
    )
    parser.add_argument("--report-date", default=None, help="optional YYYY-MM-DD report date")
    parser.add_argument("--notify", action="store_true", help="dispatch queued notification events after generation")
    parser.add_argument("--channel-alias", default=None, help="optional notification channel alias")
    parser.add_argument("--dry-run", action="store_true", default=None, help="force notification dry-run")
    parser.add_argument("--no-dry-run", action="store_false", dest="dry_run", help="allow notification dispatch when channel gates allow it")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI에서 report automation 상태 확인 또는 수동 run-once를 수행한다."""
    parser = build_parser()
    args = parser.parse_args(argv)
    report_date = _parse_date(args.report_date, parser)
    with SessionLocal() as db:
        service = ReportAutomationService(db)
        if not args.execute:
            payload = service.status()
            payload["execute_required"] = True
            print(json.dumps(payload, sort_keys=True, default=str))
            return 0
        result = service.run_once(
            report_types=args.report_type,
            report_date=report_date,
            notify=bool(args.notify),
            channel_alias=args.channel_alias,
            dry_run=args.dry_run,
            confirm=True,
        )
        print(json.dumps(result, sort_keys=True, default=str))
        return 0 if result.get("ok") else 2


def _parse_date(value: str | None, parser: argparse.ArgumentParser) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        parser.error("--report-date must use YYYY-MM-DD")
    return None


if __name__ == "__main__":
    raise SystemExit(main())
