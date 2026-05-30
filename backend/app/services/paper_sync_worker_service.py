from __future__ import annotations

import json
import os
import time
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.tables import PaperAuditEvent
from backend.app.services.paper_sync_service import SUPPORTED_SYNC_SCOPES, PaperSyncService

PAPER_SYNC_WORKER_ENABLED_ENV = "PAPER_SYNC_WORKER_ENABLED"
PAPER_SYNC_WORKER_INTERVAL_SECONDS_ENV = "PAPER_SYNC_WORKER_INTERVAL_SECONDS"
PAPER_SYNC_WORKER_MAX_ITERATIONS_ENV = "PAPER_SYNC_WORKER_MAX_ITERATIONS"
PAPER_SYNC_WORKER_MAX_ITERATIONS_CAP_ENV = "PAPER_SYNC_WORKER_MAX_ITERATIONS_CAP"


class PaperSyncWorkerService:
    """KIS paper 주문/체결/잔고 sync를 명시적 gate 뒤에서 주기 실행하는 wrapper다."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def status(self) -> dict[str, Any]:
        """paper sync worker 상태를 secret 없이 반환한다."""
        enabled = _env_true(PAPER_SYNC_WORKER_ENABLED_ENV)
        interval_seconds = _env_int(PAPER_SYNC_WORKER_INTERVAL_SECONDS_ENV, default=60)
        max_iterations_cap = _env_int(PAPER_SYNC_WORKER_MAX_ITERATIONS_CAP_ENV, default=10)
        return {
            "enabled": enabled,
            "loop_allowed": enabled,
            "auto_start": False,
            "interval_seconds": interval_seconds,
            "max_iterations_default": _env_int(PAPER_SYNC_WORKER_MAX_ITERATIONS_ENV, default=1),
            "max_iterations_cap": max_iterations_cap,
            "supported_scopes": sorted(SUPPORTED_SYNC_SCOPES),
            "public_surface": {
                "status_route": "GET /api/paper/sync-worker/status",
                "run_once_route": "POST /api/paper/sync-worker/run-once",
                "run_loop_route": "POST /api/paper/sync-worker/run-loop",
                "cli": "backend.app.jobs.paper_sync_runner",
            },
            "network_call_performed": False,
            "live_order_created": False,
            "secrets_redacted": True,
            "reason_codes": [] if enabled else ["PAPER_SYNC_WORKER_DISABLED"],
        }

    def run_once(self, *, scope: str = "all", confirm: bool = False) -> dict[str, Any]:
        """confirm과 worker gate가 모두 열렸을 때 PaperSyncService.sync를 1회 호출한다."""
        normalized_scope = str(scope or "all").strip().lower()
        status = self.status()
        if normalized_scope not in SUPPORTED_SYNC_SCOPES:
            result = self._blocked(
                scope=normalized_scope,
                reason_codes=["PAPER_SYNC_SCOPE_UNSUPPORTED"],
                status=status,
            )
            self._audit(result)
            return result
        if not confirm:
            result = self._blocked(
                scope=normalized_scope,
                reason_codes=["PAPER_SYNC_WORKER_CONFIRMATION_REQUIRED"],
                status=status,
            )
            self._audit(result)
            return result
        if not status["enabled"]:
            result = self._blocked(
                scope=normalized_scope,
                reason_codes=list(status["reason_codes"]),
                status=status,
            )
            self._audit(result)
            return result

        sync_result = PaperSyncService(self.db).sync(scope=normalized_scope)
        result = {
            **sync_result,
            "worker_enabled": True,
            "worker_run_performed": True,
            "worker_interval_seconds": status["interval_seconds"],
            "auto_start": False,
            "live_order_created": False,
            "secrets_redacted": True,
        }
        self._audit(result)
        return result

    def run_loop(self, *, scope: str = "all", max_iterations: int | None = None, confirm: bool = False) -> dict[str, Any]:
        """명시적으로 활성화된 worker만 bounded loop를 수행한다."""
        status = self.status()
        normalized_scope = str(scope or "all").strip().lower()
        if normalized_scope not in SUPPORTED_SYNC_SCOPES:
            result = self._loop_blocked(
                status=status,
                scope=normalized_scope,
                reason_codes=["PAPER_SYNC_SCOPE_UNSUPPORTED"],
            )
            self._audit(result)
            return result
        if not confirm:
            result = self._loop_blocked(
                status=status,
                scope=normalized_scope,
                reason_codes=["PAPER_SYNC_WORKER_LOOP_CONFIRMATION_REQUIRED"],
            )
            self._audit(result)
            return result
        if not status["loop_allowed"]:
            result = self._loop_blocked(
                status=status,
                scope=normalized_scope,
                reason_codes=list(status.get("reason_codes") or ["PAPER_SYNC_WORKER_DISABLED"]),
            )
            self._audit(result)
            return result
        requested_iterations = max(1, int(max_iterations or status["max_iterations_default"]))
        iterations = min(requested_iterations, int(status["max_iterations_cap"]))
        results: list[dict[str, Any]] = []
        for index in range(iterations):
            results.append(self.run_once(scope=normalized_scope, confirm=True))
            if index < iterations - 1:
                time.sleep(float(status["interval_seconds"]))
        return {
            "ok": all(item.get("ok") for item in results),
            "status": "loop_completed",
            "scope": normalized_scope,
            "iterations": results,
            "iteration_count": len(results),
            "requested_iteration_count": requested_iterations,
            "max_iterations_cap": status["max_iterations_cap"],
            "bounded_loop": True,
            "auto_start": False,
            "network_call_performed": any(bool(item.get("network_call_performed")) for item in results),
            "live_order_created": False,
            "secrets_redacted": True,
        }

    def _blocked(self, *, scope: str, reason_codes: list[str], status: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": False,
            "status": "worker_blocked",
            "scope": scope,
            "sync_performed": False,
            "worker_enabled": bool(status.get("enabled")),
            "worker_run_performed": False,
            "supported_scopes": sorted(SUPPORTED_SYNC_SCOPES),
            "reason": reason_codes[0] if reason_codes else "PAPER_SYNC_WORKER_BLOCKED",
            "reason_codes": reason_codes,
            "network_call_performed": False,
            "live_order_created": False,
            "secrets_redacted": True,
        }

    def _loop_blocked(
        self,
        *,
        status: dict[str, Any],
        scope: str,
        reason_codes: list[str],
    ) -> dict[str, Any]:
        return {
            **status,
            "ok": False,
            "status": "loop_blocked",
            "scope": scope,
            "sync_performed": False,
            "worker_run_performed": False,
            "iterations": [],
            "iteration_count": 0,
            "bounded_loop": True,
            "reason": reason_codes[0] if reason_codes else "PAPER_SYNC_WORKER_LOOP_BLOCKED",
            "reason_codes": reason_codes,
            "network_call_performed": False,
            "live_order_created": False,
            "secrets_redacted": True,
        }

    def _audit(self, result: dict[str, Any]) -> None:
        self.db.add(
            PaperAuditEvent(
                event_type="paper_sync_worker",
                decision="allow" if result.get("worker_run_performed") else "deny",
                reason_codes_json=json.dumps(result.get("reason_codes") or [], ensure_ascii=False),
                payload_json=json.dumps(
                    {
                        "scope": result.get("scope"),
                        "status": result.get("status"),
                        "sync_performed": result.get("sync_performed"),
                        "network_call_performed": result.get("network_call_performed"),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
        )
        self.db.commit()


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, *, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default
