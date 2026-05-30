from __future__ import annotations

import json
from typing import Any
from urllib import request


class DiscordNotifier:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def build_payload(self, message: str) -> dict[str, Any]:
        """Discord message payload를 mention-safe 형태로 만든다."""
        return {
            "content": message,
            "allowed_mentions": {
                "parse": [],
            },
        }

    def send(self, *, webhook_url: str, message: str, timeout_seconds: float = 5.0) -> dict[str, Any]:
        """Discord webhook으로 메시지를 전송하되 호출 URL은 반환하지 않는다."""
        payload = json.dumps(self.build_payload(message)).encode("utf-8")
        req = request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=timeout_seconds) as response:
            return {"status_code": response.status, "delivered": 200 <= response.status < 300}
