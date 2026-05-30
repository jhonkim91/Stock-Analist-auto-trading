from __future__ import annotations

from typing import Any

from backend.app.brokers.kis_paper import (
    CANCEL_CONFIRMATION_REQUIRED,
    CONFIRMATION_REQUIRED,
    SYNC_CONFIRMATION_REQUIRED,
    KisPaperBrokerAdapter as BaseKisPaperBrokerAdapter,
)


class KisPaperBrokerAdapter(BaseKisPaperBrokerAdapter):
    """KIS 모의투자 adapter를 서비스 계층의 paper-only 경계로 노출한다."""

    def status(self) -> dict[str, Any]:
        status = super().status()
        status["adapter_boundary"] = "paper_only_service"
        status["live_fallback_enabled"] = False
        status["capabilities"] = {
            "account_summary": True,
            "cash_available": True,
            "positions": True,
            "submit_order": True,
            "cancel_order": True,
            "order_status": True,
        }
        return status


__all__ = [
    "CANCEL_CONFIRMATION_REQUIRED",
    "CONFIRMATION_REQUIRED",
    "SYNC_CONFIRMATION_REQUIRED",
    "KisPaperBrokerAdapter",
]
