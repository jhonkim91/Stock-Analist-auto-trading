from __future__ import annotations

import json
from typing import Any
from urllib import request


class TelegramNotifier:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def build_payload(self, *, chat_id: str, message: str) -> dict[str, Any]:
        """Telegram payload를 기본 plain text로 만들고 unsafe MarkdownV2 기본값을 피한다."""
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": message,
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
        req = request.Request(
            api_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=timeout_seconds) as response:
            return {"status_code": response.status, "delivered": 200 <= response.status < 300}
