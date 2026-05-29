from __future__ import annotations

from typing import Any

from backend.app.brokers.base import BrokerOrderRequest
from backend.app.brokers.kis_live import (
    LIVE_DISABLED_REASON,
    KisLiveBrokerAdapter as BaseKisLiveBrokerAdapter,
)
from backend.app.services.live_order_safety_service import LiveOrderAuditService, LiveOrderSafetyService


class KisLiveBrokerAdapter(BaseKisLiveBrokerAdapter):
    """KIS 실전 adapter의 안전 preflight 경계를 제공하되 실행은 항상 차단한다."""

    def __init__(self, safety_service: LiveOrderSafetyService | None = None) -> None:
        self.safety_service = safety_service or LiveOrderSafetyService()
        self.audit_service = LiveOrderAuditService()

    def status(self) -> dict[str, Any]:
        status = super().status()
        status["adapter_boundary"] = "live_disabled_placeholder"
        status["live_fallback_enabled"] = False
        status["submit_implementation_present"] = True
        status["cancel_implementation_present"] = True
        status["list_implementation_present"] = True
        status["submit_network_enabled"] = False
        status["cancel_network_enabled"] = False
        status["safety_preflight_required"] = True
        return status

    def preview_order(self, request: BrokerOrderRequest) -> dict[str, Any]:
        """live 주문 후보를 안전장치로 평가하지만 network/order 생성은 하지 않는다."""
        payload = super().preview_order(request)
        return self._with_order_safety(payload, request=request)

    def submit_order(self, request: BrokerOrderRequest) -> dict[str, Any]:
        """live submit 후보를 안전장치로 평가한 뒤 disabled payload로 차단한다."""
        payload = super().submit_order(request)
        return self._with_order_safety(payload, request=request)

    def cancel_order(self, *, broker_order_id: str, confirm: bool = False) -> dict[str, Any]:
        """live cancel 후보를 안전장치로 평가한 뒤 disabled payload로 차단한다."""
        payload = super().cancel_order(broker_order_id=broker_order_id, confirm=confirm)
        reason_codes = list(payload.get("reason_codes") or [])
        if not broker_order_id.strip():
            reason_codes.append("LIVE_CANCEL_BROKER_ORDER_ID_REQUIRED")
        if not confirm:
            reason_codes.append("LIVE_CANCEL_CONFIRM_REQUIRED")
        safety_preflight = self.safety_service.preflight()
        reason_codes.extend(list(safety_preflight["blockers"]))
        audit_event = self.audit_service.build_event(
            event_type="live_cancel_safety_evaluated",
            decision="deny",
            reason_codes=reason_codes,
            payload={
                "broker_order_id_present": bool(broker_order_id.strip()),
                "confirm_received": bool(confirm),
            },
        )
        payload.update(
            {
                "reason_codes": _merge_reason_codes(reason_codes),
                "live_cancel_safety": {
                    "decision": "deny",
                    "passed": False,
                    "preflight": safety_preflight,
                    "request_blockers": [
                        code
                        for code in ("LIVE_CANCEL_BROKER_ORDER_ID_REQUIRED", "LIVE_CANCEL_CONFIRM_REQUIRED")
                        if code in reason_codes
                    ],
                    "audit": audit_event,
                    "live_order_created": False,
                    "network_call_performed": False,
                },
            }
        )
        return payload

    def _with_order_safety(self, payload: dict[str, Any], *, request: BrokerOrderRequest) -> dict[str, Any]:
        safety = self.safety_service.evaluate_order_request(
            symbol=request.symbol,
            side=request.side,
            qty=request.qty,
            limit_price=request.limit_price,
            idempotency_key=request.idempotency_key,
        )
        payload.update(
            {
                "reason_codes": _merge_reason_codes(list(payload.get("reason_codes") or []) + safety["blockers"]),
                "live_order_safety": safety,
            }
        )
        return payload


__all__ = ["LIVE_DISABLED_REASON", "KisLiveBrokerAdapter"]


def _merge_reason_codes(codes: list[str]) -> list[str]:
    merged: list[str] = []
    for code in codes:
        if code not in merged:
            merged.append(code)
    return merged
