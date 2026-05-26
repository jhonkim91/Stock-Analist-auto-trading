from __future__ import annotations

from typing import Any

from backend.app.brokers.base import BrokerAdapter, BrokerDisabledError, BrokerOrderRequest

LIVE_DISABLED_REASON = "KIS_LIVE_BROKER_DISABLED_PLACEHOLDER"


class KisLiveBrokerAdapter(BrokerAdapter):
    name = "kis_live"
    mode = "live"

    def status(self) -> dict[str, Any]:
        """KIS live adapter는 placeholder로만 존재하며 항상 disabled다."""
        return {
            "name": self.name,
            "mode": self.mode,
            "enabled": False,
            "paper_trading_enabled": False,
            "live_trading_enabled": False,
            "websocket_enabled": False,
            "network_enabled": False,
            "can_preview": False,
            "can_submit": False,
            "can_cancel": False,
            "can_list_orders": False,
            "can_sync": False,
            "reason": LIVE_DISABLED_REASON,
        }

    def preview_order(self, request: BrokerOrderRequest) -> dict[str, Any]:
        """live preview도 현재 범위에서는 실행하지 않는다."""
        raise BrokerDisabledError(LIVE_DISABLED_REASON)

    def submit_order(self, request: BrokerOrderRequest) -> dict[str, Any]:
        """실거래 submit은 구현하지 않는다."""
        raise BrokerDisabledError(LIVE_DISABLED_REASON)

    def cancel_order(self, *, broker_order_id: str, confirm: bool = False) -> dict[str, Any]:
        """실거래 cancel은 구현하지 않는다."""
        raise BrokerDisabledError(LIVE_DISABLED_REASON)

    def list_orders(self, *, status: str | None = None) -> dict[str, Any]:
        """실거래 주문 조회는 구현하지 않는다."""
        raise BrokerDisabledError(LIVE_DISABLED_REASON)

    def sync(self, *, scope: str = "all") -> dict[str, Any]:
        """실거래 sync는 구현하지 않는다."""
        raise BrokerDisabledError(LIVE_DISABLED_REASON)
