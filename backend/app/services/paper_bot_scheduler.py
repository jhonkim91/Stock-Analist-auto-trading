from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.paths import CONFIG_DIR
from backend.app.services.paper_bot_service import PaperBotService


class PaperBotScheduler:
    """명시적으로 활성화된 경우에만 paper bot loop를 실행하는 얇은 scheduler."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def status(self) -> dict[str, Any]:
        return PaperBotService(self.db, config_dir=CONFIG_DIR).loop_status()

    def run_once(self, *, auto_submit: bool | None = None) -> dict[str, Any]:
        return PaperBotService(self.db, config_dir=CONFIG_DIR).run_once(auto_submit=auto_submit)

    def stop(self) -> dict[str, Any]:
        return PaperBotService(self.db, config_dir=CONFIG_DIR).stop()
