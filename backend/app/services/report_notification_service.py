from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.core.paths import CONFIG_DIR
from backend.app.models.tables import NotificationDeliveryLog, NotificationEvent
from backend.app.repositories.paper_repository import PaperRepository
from backend.app.services.notification_service import NotificationService
from backend.app.services.report_service import ReportService

ReportNotifyMode = Literal["summary", "summary_and_file"]

TELEGRAM_MESSAGE_LIMIT = 4096
DISCORD_MESSAGE_LIMIT = 2000
SAFE_TELEGRAM_CHUNK_LIMIT = 3900
SAFE_DISCORD_CHUNK_LIMIT = 1900
SUMMARY_MAX_CHARS = 7600


class ReportNotificationService:
    def __init__(self, db: Session, *, config_dir: Path = CONFIG_DIR) -> None:
        self.db = db
        self.notification_service = NotificationService(config_dir=config_dir)

    def notify(
        self,
        *,
        report_id: str,
        mode: ReportNotifyMode = "summary",
        channel_alias: str | None = None,
        dry_run: bool | None = None,
    ) -> dict[str, Any]:
        """저장된 report를 channel-safe summary로 전달하고 sanitized delivery log를 남긴다."""
        report = ReportService(self.db).get_report(report_id, include_markdown=True)
        markdown = str(report["markdown"])
        resolved = self.notification_service.resolve_channel(channel_alias)
        channel = resolved.get("channel") or {}
        channel_type = str(channel.get("type") or "disabled")
        limit = self._safe_limit(channel_type)
        summary = self._summary(markdown=markdown, report=report)
        portfolio_snapshot = self._portfolio_snapshot_payload()
        summary = self._append_portfolio_summary(summary, portfolio_snapshot)
        message_chunks = self._split_message(summary, limit)
        attachment = self._attachment_payload(report=report, markdown=markdown, channel_type=channel_type, mode=mode)
        effective_dry_run = bool(dry_run) if dry_run is not None else bool(resolved.get("default_dry_run", True))
        if resolved.get("raw") and isinstance(resolved["raw"], dict):
            effective_dry_run = effective_dry_run or bool(resolved["raw"].get("dry_run", False))

        status = "disabled"
        delivered = False
        attempted = False
        reason_codes = list(resolved.get("reason_codes") or [])
        if not resolved.get("found"):
            status = "channel_not_found"
        elif not channel.get("enabled") or channel.get("mode") == "disabled":
            status = "disabled"
        elif effective_dry_run:
            status = "dry_run"
        elif channel.get("mode") == "mock":
            status = "mock_sent"
            delivered = True
        elif channel.get("can_dispatch"):
            attempted = True
            try:
                for chunk in message_chunks:
                    delivery = self.notification_service.dispatch(resolved["raw"], chunk)
                    delivered = bool(delivery.get("delivered"))
                    if not delivered:
                        raise RuntimeError("delivery_not_confirmed")
                status = "sent"
            except Exception:
                status = "failed"
                delivered = False
                reason_codes = self._merge_reason_codes(reason_codes, ["DELIVERY_FAILED"])
        else:
            status = "blocked"

        event = self._record_delivery(
            report=report,
            mode=mode,
            channel_alias=str(resolved.get("alias") or channel_alias or ""),
            status=status,
            reason_codes=reason_codes,
            message_chunks=message_chunks,
            attachment=attachment,
            portfolio_snapshot=portfolio_snapshot,
            attempted=attempted,
        )
        return {
            "ok": status not in {"failed", "channel_not_found"},
            "status": status,
            "report_id": report_id,
            "mode": mode,
            "channel_alias": event.channel_alias,
            "attempted": attempted,
            "delivered": delivered,
            "dry_run": effective_dry_run,
            "message_count": len(message_chunks),
            "message_lengths": [len(chunk) for chunk in message_chunks],
            "max_message_length": limit,
            "channel_limits": {"telegram": TELEGRAM_MESSAGE_LIMIT, "discord": DISCORD_MESSAGE_LIMIT},
            "payload_shape": self._payload_shape_with_attachment(resolved.get("payload_shape") or {}, attachment),
            "attachment": attachment,
            "portfolio_snapshot": portfolio_snapshot,
            "reason_codes": reason_codes,
            "notification_event_id": event.event_id,
            "secrets_redacted": True,
            "report_preserved": True,
        }

    def _record_delivery(
        self,
        *,
        report: dict[str, Any],
        mode: str,
        channel_alias: str,
        status: str,
        reason_codes: list[str],
        message_chunks: list[str],
        attachment: dict[str, Any],
        portfolio_snapshot: dict[str, Any],
        attempted: bool,
    ) -> NotificationEvent:
        payload_summary = {
            "report_id": report["report_id"],
            "report_type": report["report_type"],
            "mode": mode,
            "message_count": len(message_chunks),
            "message_lengths": [len(chunk) for chunk in message_chunks],
            "attachment": attachment,
            "portfolio_snapshot": portfolio_snapshot,
            "reason_codes": reason_codes,
        }
        payload_hash = hashlib.sha256(json.dumps(payload_summary, sort_keys=True).encode("utf-8")).hexdigest()
        event = NotificationEvent(
            event_id=f"notify-{uuid4().hex[:16]}",
            event_type="report_notify",
            channel_alias=channel_alias,
            status=status,
            subject=f"report:{report['report_id']}",
            payload_hash=payload_hash,
            payload_summary_json=json.dumps(payload_summary, sort_keys=True),
        )
        self.db.add(event)
        self.db.add(
            NotificationDeliveryLog(
                event_id=event.event_id,
                channel_alias=channel_alias,
                status=status,
                attempt_count=1 if attempted else 0,
                last_error_code="DELIVERY_FAILED" if status == "failed" else None,
                delivered_at=datetime.now(UTC) if status in {"sent", "mock_sent"} else None,
            )
        )
        self.db.commit()
        self.db.refresh(event)
        return event

    def _portfolio_snapshot_payload(self) -> dict[str, Any]:
        """KIS 네트워크 없이 local paper portfolio snapshot 요약만 반환한다."""
        repository = PaperRepository(self.db)
        snapshot = repository.latest_portfolio_snapshot()
        positions = repository.list_positions()
        positions_market_value = sum(float(position.market_value or 0.0) for position in positions)
        if snapshot is None:
            return {
                "source": "paper_portfolio_snapshots",
                "snapshot_id": None,
                "snapshot_ts": None,
                "positions_count": len(positions),
                "positions_market_value": positions_market_value,
                "reason": "PAPER_PORTFOLIO_SNAPSHOT_NOT_FOUND",
                "network_call_performed": False,
                "secrets_redacted": True,
            }
        return {
            "source": "paper_portfolio_snapshots",
            "snapshot_id": snapshot.snapshot_id,
            "snapshot_ts": snapshot.snapshot_ts.isoformat() if snapshot.snapshot_ts else None,
            "account_alias": snapshot.account_alias,
            "cash_balance": snapshot.cash_balance,
            "buying_power": snapshot.buying_power,
            "market_value": snapshot.market_value,
            "total_equity": snapshot.total_equity,
            "unrealized_pnl": snapshot.unrealized_pnl,
            "realized_pnl": snapshot.realized_pnl,
            "positions_count": len(positions),
            "positions_market_value": positions_market_value,
            "reason": None,
            "network_call_performed": False,
            "secrets_redacted": True,
        }

    @staticmethod
    def _append_portfolio_summary(summary: str, portfolio_snapshot: dict[str, Any]) -> str:
        lines = [
            "",
            "Portfolio Snapshot",
            f"- source: {portfolio_snapshot['source']}",
            f"- snapshot_id: {portfolio_snapshot.get('snapshot_id') or 'not_available'}",
            f"- total_equity: {portfolio_snapshot.get('total_equity')}",
            f"- positions_count: {portfolio_snapshot.get('positions_count')}",
        ]
        return ReportNotificationService._redact(summary.rstrip() + "\n" + "\n".join(lines))

    @staticmethod
    def _summary(*, markdown: str, report: dict[str, Any]) -> str:
        title = next((line.strip("# ").strip() for line in markdown.splitlines() if line.startswith("# ")), report["report_id"])
        body_lines = [line.strip() for line in markdown.splitlines() if line.strip() and not line.startswith("# ")]
        body = "\n".join(body_lines)
        redacted = ReportNotificationService._redact(f"# {title}\n\n{body}")
        if len(redacted) > SUMMARY_MAX_CHARS:
            return redacted[: SUMMARY_MAX_CHARS - 80].rstrip() + "\n\n[truncated: attach full report if needed]"
        return redacted

    @staticmethod
    def _split_message(message: str, limit: int) -> list[str]:
        if len(message) <= limit:
            return [message]
        chunks: list[str] = []
        current = ""
        for line in message.splitlines():
            candidate = f"{current}\n{line}".strip() if current else line
            if len(candidate) <= limit:
                current = candidate
                continue
            if current:
                chunks.append(current)
            while len(line) > limit:
                chunks.append(line[:limit])
                line = line[limit:]
            current = line
        if current:
            chunks.append(current)
        return chunks or [message[:limit]]

    @staticmethod
    def _attachment_payload(*, report: dict[str, Any], markdown: str, channel_type: str, mode: str) -> dict[str, Any]:
        included = mode == "summary_and_file"
        method = None
        if included:
            method = "document" if channel_type == "telegram" else "file"
        return {
            "included": included,
            "method": method,
            "filename": Path(str(report["path"])).name if included else None,
            "content_length": len(markdown) if included else 0,
            "content_hash": hashlib.sha256(markdown.encode("utf-8")).hexdigest() if included else None,
        }

    @staticmethod
    def _payload_shape_with_attachment(payload_shape: dict[str, Any], attachment: dict[str, Any]) -> dict[str, Any]:
        merged = dict(payload_shape)
        if attachment["included"]:
            merged["attachment_method"] = attachment["method"]
        return merged

    @staticmethod
    def _safe_limit(channel_type: str) -> int:
        if channel_type == "telegram":
            return SAFE_TELEGRAM_CHUNK_LIMIT
        return SAFE_DISCORD_CHUNK_LIMIT

    @staticmethod
    def _redact(text: str) -> str:
        patterns = [
            r"https://discord\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+",
            r"\b[0-9]{8,10}:[A-Za-z0-9_-]{20,}\b",
            r"(?i)(KIS_APP_KEY|KIS_APP_SECRET|ACCESS_TOKEN|REFRESH_TOKEN)\s*[:=]\s*[^ \n]+",
            r"(?i)(account_no|account_number|cano|chat_id)\s*[:=]\s*[^ \n]+",
        ]
        redacted = text
        for pattern in patterns:
            redacted = re.sub(pattern, "[REDACTED]", redacted)
        return redacted

    @staticmethod
    def _merge_reason_codes(*groups: list[str]) -> list[str]:
        merged: list[str] = []
        for group in groups:
            for code in group:
                if code not in merged:
                    merged.append(code)
        return merged
