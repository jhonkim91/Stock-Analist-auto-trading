from __future__ import annotations

import argparse
import json
from datetime import date

from backend.app.core.database import SessionLocal
from backend.app.services.telegram_report_scheduler_service import SUPPORTED_TELEGRAM_REPORT_SLOTS, TelegramReportSchedulerService


def build_parser() -> argparse.ArgumentParser:
    """Telegram report scheduler CLI parser를 생성한다."""
    parser = argparse.ArgumentParser(description="Manual Telegram report scheduler runner")
    parser.add_argument("--execute", action="store_true", help="run selected slot after explicit confirmation")
    parser.add_argument("--slot", choices=sorted(SUPPORTED_TELEGRAM_REPORT_SLOTS), default="manual")
    parser.add_argument("--report-type", action="append", choices=["daily", "weekly"])
    parser.add_argument("--report-date", default=None, help="optional YYYY-MM-DD report date")
    parser.add_argument("--channel-alias", default="telegram_main")
    parser.add_argument("--dry-run", action="store_true", default=None)
    parser.add_argument("--no-dry-run", action="store_false", dest="dry_run")
    return parser


def main(argv: list[str] | None = None) -> int:
    """상태 조회 또는 confirm된 Telegram report run-once를 수행한다."""
    parser = build_parser()
    args = parser.parse_args(argv)
    report_date = _parse_date(args.report_date, parser)
    with SessionLocal() as db:
        service = TelegramReportSchedulerService(db)
        if not args.execute:
            payload = service.status()
            payload["execute_required"] = True
            print(json.dumps(payload, sort_keys=True, default=str))
            return 0
        result = service.run_once(
            slot=args.slot,
            report_types=args.report_type,
            report_date=report_date,
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
