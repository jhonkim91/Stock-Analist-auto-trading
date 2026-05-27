from __future__ import annotations

from typing import Any

from backend.app.services.discord_notifier import DiscordNotifier


class DiscordWebhookNotifier(DiscordNotifier):
    """Discord incoming webhook 전송 adapter 이름을 명시하는 호환 wrapper."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config=config)
