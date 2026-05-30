from __future__ import annotations

from typing import Any

from backend.app.brokers.base import BrokerAdapter, BrokerOrderRequest

LIVE_DISABLED_REASON = "KIS_LIVE_BROKER_DISABLED_PLACEHOLDER"
LIVE_DISABLED_STATUS = "live_disabled"


class KisLiveBrokerAdapter(BrokerAdapter):
    """KIS live adapter를 실행 불가능한 disabled scaffold로 고정한다."""

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
            "reason_codes": [LIVE_DISABLED_REASON],
            "adapter_boundary": "live_disabled_placeholder",
            "live_fallback_enabled": False,
            "endpoint_configured": False,
            "endpoint_called": False,
            "secrets_redacted": True,
        }

    def preview_order(self, request: BrokerOrderRequest) -> dict[str, Any]:
        """live preview 요청을 네트워크 없이 disabled payload로 반환한다."""
        return self._disabled_payload("preview_order", request=request)

    def submit_order(self, request: BrokerOrderRequest) -> dict[str, Any]:
        """실거래 submit 요청을 네트워크 없이 disabled payload로 반환한다."""
        return self._disabled_payload("submit_order", request=request)

    def cancel_order(self, *, broker_order_id: str, confirm: bool = False) -> dict[str, Any]:
        """실거래 cancel 요청을 네트워크 없이 disabled payload로 반환한다."""
        return self._disabled_payload("cancel_order", broker_order_id=broker_order_id, confirm=confirm)

    def list_orders(self, *, status: str | None = None) -> dict[str, Any]:
        """실거래 주문 조회 요청을 네트워크 없이 disabled payload로 반환한다."""
        return self._disabled_payload("list_orders", status_filter=status)

    def sync(self, *, scope: str = "all") -> dict[str, Any]:
        """실거래 sync 요청을 네트워크 없이 disabled payload로 반환한다."""
        return self._disabled_payload("sync", scope=scope)

    def _disabled_payload(
        self,
        operation: str,
        *,
        request: BrokerOrderRequest | None = None,
        broker_order_id: str | None = None,
        confirm: bool | None = None,
        status_filter: str | None = None,
        scope: str | None = None,
    ) -> dict[str, Any]:
        """live operation이 호출되어도 실행 가능성이 0인 redacted payload를 만든다."""
        payload: dict[str, Any] = {
            "ok": False,
            "status": LIVE_DISABLED_STATUS,
            "operation": operation,
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
            "order_created": False,
            "order_cancelled": False,
            "broker_order_created": False,
            "live_order_created": False,
            "network_call_performed": False,
            "adapter_network_call_performed": False,
            "endpoint_configured": False,
            "endpoint_called": False,
            "adapter_boundary": "live_disabled_placeholder",
            "live_fallback_enabled": False,
            "reason": LIVE_DISABLED_REASON,
            "reason_codes": [LIVE_DISABLED_REASON],
            "secrets_redacted": True,
            "account_redacted": True,
        }
        if request is not None:
            payload["symbol"] = request.symbol
            payload["side"] = request.side
            payload["qty"] = request.qty
            payload["limit_price"] = request.limit_price
            payload["stop_price"] = request.stop_price
            payload["idempotency_key_present"] = bool(request.idempotency_key)
        if broker_order_id is not None:
            payload["broker_order_id_present"] = bool(broker_order_id)
        if confirm is not None:
            payload["confirm_received"] = bool(confirm)
        if status_filter is not None:
            payload["status_filter"] = status_filter
        if scope is not None:
            payload["scope"] = scope
        return payload
