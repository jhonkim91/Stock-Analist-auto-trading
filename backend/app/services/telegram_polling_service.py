from __future__ import annotations

import json
import os
import re
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.tables import PaperAuditEvent
from backend.app.services.kis_http_client import KisHttpClient
from backend.app.services.telegram_bot_service import TelegramBotService

TELEGRAM_API_BASE_URL_ENV = "TELEGRAM_API_BASE_URL"
TELEGRAM_BOT_ENABLED_ENV = "TELEGRAM_BOT_ENABLED"
TELEGRAM_POLLING_ENABLED_ENV = "TELEGRAM_POLLING_ENABLED"
TELEGRAM_BOT_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
TELEGRAM_POLLING_DRY_RUN_ENV = "TELEGRAM_POLLING_DRY_RUN"
TELEGRAM_POLLING_SEND_REPLIES_ENV = "TELEGRAM_POLLING_SEND_REPLIES"
DEFAULT_TELEGRAM_API_BASE_URL = "https://api.telegram.org"


class TelegramPollingService:
    """Telegram getUpdates polling을 명시적 gate 뒤에서 1회 실행한다."""

    def __init__(self, db: Session, *, http_client: Any | None = None) -> None:
        self.db = db
        self.http_client = http_client

    def status(self) -> dict[str, Any]:
        """Telegram polling runner 상태를 token 원문 없이 반환한다."""
        bot_enabled = _env_true(TELEGRAM_BOT_ENABLED_ENV)
        polling_enabled = _env_true(TELEGRAM_POLLING_ENABLED_ENV)
        token_configured = _configured(os.getenv(TELEGRAM_BOT_TOKEN_ENV, ""))
        reason_codes: list[str] = []
        if not bot_enabled:
            reason_codes.append("TELEGRAM_BOT_DISABLED")
        if not polling_enabled:
            reason_codes.append("TELEGRAM_POLLING_DISABLED")
        if not token_configured:
            reason_codes.append("TELEGRAM_BOT_TOKEN_MISSING")
        return {
            "enabled": bot_enabled,
            "polling_enabled": polling_enabled,
            "polling_allowed": not reason_codes,
            "token_configured": token_configured,
            "dry_run_default": _env_bool(TELEGRAM_POLLING_DRY_RUN_ENV, default=True),
            "send_replies_default": _env_bool(TELEGRAM_POLLING_SEND_REPLIES_ENV, default=False),
            "auto_start": False,
            "public_surface": {
                "status_route": "GET /api/telegram/polling/status",
                "run_once_route": "POST /api/telegram/polling/run-once",
                "cli": "backend.app.jobs.telegram_polling_runner",
            },
            "network_call_performed": False,
            "live_order_created": False,
            "secrets_redacted": True,
            "reason_codes": reason_codes,
        }

    def run_once(
        self,
        *,
        offset: int | None = None,
        limit: int = 10,
        timeout_seconds: int = 0,
        dry_run: bool | None = None,
        send_replies: bool | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """getUpdates를 1회 조회하고 text command를 dispatcher에 전달한다."""
        status = self.status()
        effective_dry_run = status["dry_run_default"] if dry_run is None else bool(dry_run)
        effective_send_replies = status["send_replies_default"] if send_replies is None else bool(send_replies)
        if not confirm:
            result = self._blocked(
                status=status,
                reason_codes=["TELEGRAM_POLLING_CONFIRMATION_REQUIRED"],
                dry_run=effective_dry_run,
                send_replies=effective_send_replies,
            )
            self._audit(result)
            return result
        if not status["polling_allowed"]:
            result = self._blocked(
                status=status,
                reason_codes=list(status["reason_codes"]),
                dry_run=effective_dry_run,
                send_replies=effective_send_replies,
            )
            self._audit(result)
            return result

        token = os.getenv(TELEGRAM_BOT_TOKEN_ENV, "").strip()
        get_result = self._post_telegram(
            token=token,
            method="getUpdates",
            payload={
                "offset": offset,
                "limit": max(1, min(int(limit), 100)),
                "timeout": max(0, min(int(timeout_seconds), 30)),
                "allowed_updates": ["message", "edited_message", "callback_query"],
            },
        )
        if not get_result["ok"]:
            result = {
                "ok": False,
                "status": "polling_failed",
                "updates_received": 0,
                "commands_dispatched": 0,
                "reply_attempts": 0,
                "dry_run": effective_dry_run,
                "send_replies": effective_send_replies,
                "next_offset": offset,
                "network_call_performed": bool(get_result["network_call_performed"]),
                "live_order_created": False,
                "secrets_redacted": True,
                "reason_codes": list(get_result["reason_codes"]),
                "trace": get_result["trace"],
            }
            self._audit(result)
            return result

        updates = _updates_from_body(get_result["body"])
        dispatches: list[dict[str, Any]] = []
        reply_results: list[dict[str, Any]] = []
        max_update_id = offset - 1 if offset is not None else None
        for update in updates:
            update_id = _int_or_none(update.get("update_id"))
            if update_id is not None:
                max_update_id = update_id if max_update_id is None else max(max_update_id, update_id)
            dispatch = TelegramBotService(self.db).handle_update(update)
            dispatches.append(self._dispatch_summary(dispatch))
            chat_id = _chat_id_from_update(update)
            if effective_send_replies and not effective_dry_run and chat_id and dispatch.get("message"):
                reply_results.append(
                    self._post_telegram(
                        token=token,
                        method="sendMessage",
                        payload={
                            "chat_id": chat_id,
                            "text": str(dispatch["message"])[:3900],
                            "disable_web_page_preview": True,
                        },
                    )
                )

        result = {
            "ok": True,
            "status": "completed",
            "updates_received": len(updates),
            "commands_dispatched": len(dispatches),
            "dispatches": dispatches,
            "reply_attempts": len(reply_results),
            "reply_results": [self._reply_summary(reply) for reply in reply_results],
            "dry_run": effective_dry_run,
            "send_replies": effective_send_replies,
            "next_offset": (max_update_id + 1) if max_update_id is not None else offset,
            "network_call_performed": True,
            "live_order_created": False,
            "secrets_redacted": True,
            "reason_codes": [],
            "trace": get_result["trace"],
        }
        self._audit(result)
        return result

    def _post_telegram(self, *, token: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        client = KisHttpClient(http_client=self.http_client, timeout_seconds=10.0, max_retries=0)
        base_url = os.getenv(TELEGRAM_API_BASE_URL_ENV, DEFAULT_TELEGRAM_API_BASE_URL).strip() or DEFAULT_TELEGRAM_API_BASE_URL
        result = client.request(
            "POST",
            f"{base_url.rstrip('/')}/bot{token}/{method}",
            json_body={key: value for key, value in payload.items() if value is not None},
            retry_enabled=False,
            operation=f"telegram_{method}",
            redact_body=True,
            correlation_prefix="telegram",
        )
        return {
            "ok": result.ok,
            "status_code": result.status_code,
            "body": result.body if isinstance(result.body, dict) else {},
            "reason_codes": [] if result.ok else [str(result.reason or "TELEGRAM_REQUEST_FAILED")],
            "network_call_performed": bool(result.trace.get("network_call_performed")),
            "trace": _sanitize_telegram_trace(result.trace),
        }

    def _blocked(
        self,
        *,
        status: dict[str, Any],
        reason_codes: list[str],
        dry_run: bool,
        send_replies: bool,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "status": "polling_blocked",
            "updates_received": 0,
            "commands_dispatched": 0,
            "reply_attempts": 0,
            "dry_run": dry_run,
            "send_replies": send_replies,
            "next_offset": None,
            "polling_allowed": bool(status.get("polling_allowed")),
            "network_call_performed": False,
            "live_order_created": False,
            "secrets_redacted": True,
            "reason_codes": reason_codes,
        }

    def _audit(self, result: dict[str, Any]) -> None:
        self.db.add(
            PaperAuditEvent(
                event_type="telegram_polling_run",
                decision="allow" if result.get("ok") else "deny",
                reason_codes_json=json.dumps(result.get("reason_codes") or [], ensure_ascii=False),
                payload_json=json.dumps(
                    {
                        "status": result.get("status"),
                        "updates_received": result.get("updates_received"),
                        "commands_dispatched": result.get("commands_dispatched"),
                        "reply_attempts": result.get("reply_attempts"),
                        "dry_run": result.get("dry_run"),
                        "network_call_performed": result.get("network_call_performed"),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
        )
        self.db.commit()

    @staticmethod
    def _dispatch_summary(dispatch: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": bool(dispatch.get("ok")),
            "status": dispatch.get("status"),
            "command": dispatch.get("command"),
            "message_length": len(str(dispatch.get("message") or "")),
            "reason_codes": dispatch.get("reason_codes") or [],
            "network_call_performed": bool(dispatch.get("network_call_performed")),
        }

    @staticmethod
    def _reply_summary(reply: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": bool(reply.get("ok")),
            "status_code": reply.get("status_code"),
            "network_call_performed": bool(reply.get("network_call_performed")),
            "reason_codes": reply.get("reason_codes") or [],
            "trace": reply.get("trace") or {},
        }


def _updates_from_body(body: dict[str, Any]) -> list[dict[str, Any]]:
    result = body.get("result")
    if not isinstance(result, list):
        return []
    return [item for item in result if isinstance(item, dict)]


def _chat_id_from_update(update: dict[str, Any]) -> str | None:
    for key in ("message", "edited_message"):
        message = update.get(key)
        if isinstance(message, dict):
            chat = message.get("chat")
            if isinstance(chat, dict) and chat.get("id") not in {None, ""}:
                return str(chat["id"])
    callback = update.get("callback_query")
    if isinstance(callback, dict) and isinstance(callback.get("message"), dict):
        chat = callback["message"].get("chat")
        if isinstance(chat, dict) and chat.get("id") not in {None, ""}:
            return str(chat["id"])
    return None


def _sanitize_telegram_trace(trace: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(trace)
    for key in ("path", "endpoint_path"):
        if isinstance(sanitized.get(key), str):
            sanitized[key] = re.sub(r"/bot[^/]+/", "/bot[REDACTED]/", sanitized[key])
    return sanitized


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _configured(value: str) -> bool:
    stripped = value.strip()
    return bool(stripped) and "placeholder" not in stripped.lower()


def _int_or_none(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
