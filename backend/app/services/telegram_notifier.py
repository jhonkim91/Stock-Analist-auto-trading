from __future__ import annotations

import json
from typing import Any
from urllib import request

TELEGRAM_MESSAGE_LIMIT = 4096


class TelegramNotifier:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def build_payload(self, *, chat_id: str, message: str) -> dict[str, Any]:
        """Telegram payload를 기본 plain text로 만들고 unsafe MarkdownV2 기본값을 피한다."""
        safe_message = self._safe_message(message)
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": safe_message,
            "disable_web_page_preview": True,
        }
        parse_mode = self.config.get("parse_mode")
        if parse_mode and parse_mode != "MarkdownV2":
            payload["parse_mode"] = str(parse_mode)
        return payload

    def send(self, *, bot_token: str, chat_id: str, message: str, timeout_seconds: float = 5.0) -> dict[str, Any]:
        """Telegram sendMessage를 호출하되 token 포함 URL은 반환하지 않는다."""
        api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = json.dumps(self.build_payload(chat_id=chat_id, message=message)).encode("utf-8")
        timeout = self._timeout_seconds(timeout_seconds)
        req = request.Request(
            api_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=timeout) as response:
            return {"status_code": response.status, "delivered": 200 <= response.status < 300}

    @staticmethod
    def _safe_message(message: str) -> str:
        text = str(message).strip() or "notification"
        return text[:TELEGRAM_MESSAGE_LIMIT]

    def _timeout_seconds(self, default: float) -> float:
        try:
            timeout = float(self.config.get("timeout_seconds", default))
        except (TypeError, ValueError):
            return default
        return timeout if timeout > 0 else default
