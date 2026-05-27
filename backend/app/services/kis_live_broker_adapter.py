from __future__ import annotations

from typing import Any

from backend.app.brokers.kis_live import (
    LIVE_DISABLED_REASON,
    KisLiveBrokerAdapter as BaseKisLiveBrokerAdapter,
)


class KisLiveBrokerAdapter(BaseKisLiveBrokerAdapter):
    """KIS 실전 adapter를 항상 disabled placeholder로 고정한다."""

    def status(self) -> dict[str, Any]:
        status = super().status()
        status["adapter_boundary"] = "live_disabled_placeholder"
        status["live_fallback_enabled"] = False
        return status


__all__ = ["LIVE_DISABLED_REASON", "KisLiveBrokerAdapter"]
