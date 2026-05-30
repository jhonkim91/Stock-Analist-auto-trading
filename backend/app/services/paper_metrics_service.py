from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.tables import PaperAccountSnapshot, PaperAuditEvent, PaperBotDecision


class PaperOperationalMetricsService:
    """paper bot 운영 지표를 DB와 worker 상태에서 secret 없이 집계한다."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def summary(self) -> dict[str, Any]:
        """token/realtime/order/risk/sync 대표 지표를 반환한다."""
        latencies = self._order_submit_latencies()
        latest_snapshot = self.db.scalar(
            select(PaperAccountSnapshot).order_by(
                PaperAccountSnapshot.snapshot_ts.desc(),
                PaperAccountSnapshot.created_at.desc(),
            )
        )
        return {
            "token_refresh_count": self._audit_count("kis_token_refresh"),
            "websocket_reconnect_count": self._audit_count("paper_realtime_reconnect"),
            "order_submit_latency_ms": self._latency_summary(latencies),
            "reject_count": int(
                self.db.scalar(
                    select(func.count()).select_from(PaperBotDecision).where(PaperBotDecision.action == "rejected")
                )
                or 0
            ),
            "sync_lag_seconds": self._sync_lag_seconds(latest_snapshot),
            "logging_supported": True,
        }

    def _audit_count(self, event_type: str) -> int:
        return int(
            self.db.scalar(
                select(func.count()).select_from(PaperAuditEvent).where(PaperAuditEvent.event_type == event_type)
            )
            or 0
        )

    def _order_submit_latencies(self) -> list[float]:
        rows = self.db.scalars(
            select(PaperAuditEvent.payload_json).where(PaperAuditEvent.event_type == "paper_order_submit")
        ).all()
        latencies: list[float] = []
        for raw in rows:
            try:
                payload = json.loads(raw or "{}")
            except json.JSONDecodeError:
                continue
            value = payload.get("submit_latency_ms") if isinstance(payload, dict) else None
            if isinstance(value, (int, float)):
                latencies.append(float(value))
        return latencies

    @staticmethod
    def _latency_summary(values: list[float]) -> dict[str, Any]:
        if not values:
            return {"count": 0, "avg": None, "max": None}
        return {
            "count": len(values),
            "avg": round(sum(values) / len(values), 3),
            "max": round(max(values), 3),
        }

    @staticmethod
    def _sync_lag_seconds(snapshot: PaperAccountSnapshot | None) -> float | None:
        if snapshot is None or snapshot.snapshot_ts is None:
            return None
        snapshot_ts = snapshot.snapshot_ts
        if snapshot_ts.tzinfo is None:
            snapshot_ts = snapshot_ts.replace(tzinfo=UTC)
        return round((datetime.now(UTC) - snapshot_ts).total_seconds(), 3)
