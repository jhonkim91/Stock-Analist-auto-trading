from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.tables import NotificationDeliveryLog, NotificationEvent
from backend.app.services.credential_redaction import CredentialRedactionService
from backend.app.services.notification_service import NotificationService, SUPPORTED_NOTIFICATION_EVENTS

RETRIABLE_STATUSES = {"pending", "retry"}


class NotificationOutboxService:
    """notification delivery를 trading state commit과 분리하는 outbox service."""

    def __init__(
        self,
        db: Session,
        *,
        notification_service: NotificationService | None = None,
    ) -> None:
        self.db = db
        self.notification_service = notification_service or NotificationService()
        self.redactor = CredentialRedactionService()

    def enqueue_event(
        self,
        *,
        event_type: str,
        payload_summary: dict[str, Any] | None = None,
        channel_alias: str | None = None,
        subject: str | None = None,
    ) -> dict[str, Any]:
        """지원 event를 outbox에 저장하고 delivery는 후속 dispatch로 분리한다."""
        if event_type not in SUPPORTED_NOTIFICATION_EVENTS:
            return {
                "ok": False,
                "status": "unsupported_event",
                "event_type": event_type,
                "persisted": False,
                "reason_codes": ["NOTIFICATION_EVENT_UNSUPPORTED"],
            }

        resolved = self.notification_service.resolve_channel(channel_alias)
        selected_alias = str(resolved.get("alias") or channel_alias or "")
        sanitized_summary = self._sanitize_summary(payload_summary or {})
        payload_hash = hashlib.sha256(
            json.dumps(sanitized_summary, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        event = NotificationEvent(
            event_id=f"event-{uuid4().hex[:16]}",
            event_type=event_type,
            channel_alias=selected_alias,
            status="pending",
            subject=self._safe_text(subject),
            payload_hash=payload_hash,
            payload_summary_json=json.dumps(sanitized_summary, sort_keys=True, default=str),
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return {
            "ok": True,
            "status": "queued",
            "event_id": event.event_id,
            "event_type": event.event_type,
            "channel_alias": event.channel_alias,
            "persisted": True,
            "delivery_attempted": False,
            "secrets_redacted": True,
        }

    def dispatch_pending(self, *, limit: int = 10) -> dict[str, Any]:
        """pending/retry event를 bounded batch로 dispatch하고 실패는 retry 상태로 남긴다."""
        statement = (
            select(NotificationEvent)
            .where(NotificationEvent.status.in_(RETRIABLE_STATUSES))
            .order_by(NotificationEvent.created_at.asc())
            .limit(max(0, limit))
        )
        events = list(self.db.scalars(statement).all())
        results = [self._dispatch_event(event) for event in events]
        return {
            "ok": True,
            "status": "completed",
            "processed_count": len(results),
            "sent_count": sum(1 for result in results if result["status"] in {"sent", "mock_sent"}),
            "retry_count": sum(1 for result in results if result["status"] == "retry"),
            "results": results,
            "non_blocking": True,
        }

    def _dispatch_event(self, event: NotificationEvent) -> dict[str, Any]:
        resolved = self.notification_service.resolve_channel(event.channel_alias or None)
        channel = resolved.get("channel") or {}
        status = "disabled"
        delivered = False
        attempted = False
        last_error_code = None
        reason_codes = list(resolved.get("reason_codes") or [])

        if not resolved.get("found"):
            status = "channel_not_found"
            last_error_code = "CHANNEL_NOT_FOUND"
        elif not channel.get("enabled") or channel.get("mode") == "disabled":
            status = "disabled"
        elif channel.get("dry_run"):
            status = "dry_run"
        elif channel.get("mode") == "mock":
            status = "mock_sent"
            delivered = True
        elif channel.get("can_dispatch"):
            attempted = True
            try:
                delivery = self.notification_service.dispatch(resolved["raw"], self._message_for_event(event))
                delivered = bool(delivery.get("delivered"))
                status = "sent" if delivered else "retry"
                if not delivered:
                    last_error_code = "DELIVERY_NOT_CONFIRMED"
            except Exception:
                status = "retry"
                delivered = False
                last_error_code = "DELIVERY_FAILED"
                reason_codes = self._merge_reason_codes(reason_codes, ["DELIVERY_FAILED"])
        else:
            status = "blocked"
            last_error_code = "CHANNEL_BLOCKED"

        event.status = status
        self.db.add(
            NotificationDeliveryLog(
                event_id=event.event_id,
                channel_alias=event.channel_alias,
                status=status,
                attempt_count=1 if attempted else 0,
                last_error_code=last_error_code,
                delivered_at=datetime.now(UTC) if delivered else None,
            )
        )
        self.db.commit()
        return {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "status": status,
            "attempted": attempted,
            "delivered": delivered,
            "reason_codes": reason_codes,
            "last_error_code": last_error_code,
        }

    def _sanitize_summary(self, payload_summary: dict[str, Any]) -> dict[str, Any]:
        cleaned = self.redactor.remove_sensitive(payload_summary)
        return cleaned if isinstance(cleaned, dict) else {}

    @staticmethod
    def _message_for_event(event: NotificationEvent) -> str:
        return f"{event.event_type}: {event.subject or event.event_id}"

    @staticmethod
    def _safe_text(text: str | None) -> str | None:
        if text is None:
            return None
        redacted = str(text)
        patterns = [
            r"https://discord\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+",
            r"\b[0-9]{8,10}:[A-Za-z0-9_-]{20,}\b",
            r"(?i)(access_token|refresh_token|app_secret|app_key|account_no|account_number|cano|chat_id|webhook_url)\s*[:=]\s*[^ \n]+",
        ]
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
