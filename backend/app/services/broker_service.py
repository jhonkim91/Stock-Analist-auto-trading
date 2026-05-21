from __future__ import annotations

from uuid import uuid4


class BrokerService:
    def status(self) -> dict[str, object]:
        """Phase 1에서는 mock preview만 가능하다는 상태를 반환한다."""
        return {
            "mode": "mock",
            "broker_mode": "mock",
            "can_submit": False,
            "live_trading_enabled": False,
            "paper_trading_enabled": False,
            "reason": "preview_only",
            "live_order_supported": False,
            "paper_order_supported": False,
        }

    def preview_order(
        self,
        symbol: str,
        side: str,
        qty: int,
        limit_price: float | None = None,
        stop_price: float | None = None,
        strategy_tag: str | None = None,
    ) -> dict[str, object]:
        """실제 주문 없이 검토용 주문 preview를 만든다."""
        return {
            "preview_id": f"mock-{uuid4().hex[:12]}",
            "mode": "mock",
            "broker_mode": "mock",
            "can_submit": False,
            "preview_only": True,
            "order_created": False,
            "live_trading_enabled": False,
            "reason": "preview_only",
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "limit_price": limit_price,
            "stop_price": stop_price,
            "strategy_tag": strategy_tag,
        }
