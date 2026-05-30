from __future__ import annotations

from typing import Any

from backend.app.brokers.base import BrokerOrderRequest
from backend.app.services.kis_paper_broker_adapter import KisPaperBrokerAdapter as ServiceKisPaperBrokerAdapter


class KisPaperAdapterDomainError(RuntimeError):
    """KIS paper adapter domain 오류를 secret 없이 표현한다."""


class KisPaperBrokerAdapter(ServiceKisPaperBrokerAdapter):
    """요청 명명 계약에 맞춘 KIS 모의투자 전용 adapter facade다."""

    def account_summary(self) -> dict[str, Any]:
        """KIS paper account summary를 조회한다."""
        result = self.query_balance()
        if not result.get("ok"):
            return self._domain_error_payload(result, operation="account_summary")
        return {
            "ok": True,
            "account": result.get("portfolio"),
            "positions": result.get("positions", []),
            "network_call_performed": bool(result.get("network_call_performed")),
            "paper_only": True,
            "live_order_created": False,
            "broker_trace": result.get("broker_trace"),
        }

    def cash_available(self) -> dict[str, Any]:
        """KIS paper 주문 가능 현금 요약을 반환한다."""
        summary = self.account_summary()
        account = summary.get("account") if isinstance(summary.get("account"), dict) else {}
        return {
            **summary,
            "cash_available": account.get("buying_power") or account.get("cash_balance"),
        }

    def positions(self) -> dict[str, Any]:
        """KIS paper position 목록을 반환한다."""
        summary = self.account_summary()
        return {**summary, "positions": summary.get("positions", [])}

    def order_status(self, *, broker_order_id: str | None = None, status: str | None = None) -> dict[str, Any]:
        """KIS paper 주문 상태 조회를 daily order/fill 조회로 매핑한다."""
        result = self.list_orders(status=status)
        if not result.get("ok"):
            return self._domain_error_payload(result, operation="order_status")
        orders = result.get("orders", [])
        if broker_order_id:
            orders = [order for order in orders if isinstance(order, dict) and order.get("broker_order_id") == broker_order_id]
        return {
            "ok": True,
            "orders": orders,
            "fills": result.get("fills", []),
            "paper_only": True,
            "live_order_created": False,
            "network_call_performed": bool(result.get("network_call_performed")),
            "broker_trace": result.get("broker_trace"),
        }

    def submit_order_request(self, request: BrokerOrderRequest) -> dict[str, Any]:
        """표준 broker request를 KIS paper submit으로 전달한다."""
        result = self.submit_order(request)
        return result if result.get("ok") else self._domain_error_payload(result, operation="submit_order")

    def cancel_order_request(self, *, broker_order_id: str, confirm: bool = False) -> dict[str, Any]:
        """표준 cancel request를 KIS paper cancel로 전달한다."""
        result = self.cancel_order(broker_order_id=broker_order_id, confirm=confirm)
        return result if result.get("ok") else self._domain_error_payload(result, operation="cancel_order")

    @staticmethod
    def _domain_error_payload(result: dict[str, Any], *, operation: str) -> dict[str, Any]:
        reason_codes = list(result.get("reason_codes") or [str(result.get("reason") or "KIS_PAPER_DOMAIN_ERROR")])
        return {
            "ok": False,
            "status": result.get("status") or "domain_error",
            "operation": operation,
            "reason": reason_codes[0],
            "reason_codes": reason_codes,
            "paper_only": True,
            "live_order_created": False,
            "network_call_performed": bool(result.get("network_call_performed", False)),
            "broker_trace": result.get("broker_trace"),
        }
