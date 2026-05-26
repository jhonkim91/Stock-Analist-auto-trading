from __future__ import annotations

from typing import Any

from backend.app.brokers.base import BrokerAdapter, BrokerCapabilityError, BrokerOrderRequest

CONFIRMATION_REQUIRED = "KIS_PAPER_OFFICIAL_ENDPOINT_CONFIRMATION_REQUIRED"
CANCEL_CONFIRMATION_REQUIRED = "KIS_PAPER_CANCEL_CONFIRMATION_REQUIRED"


class KisPaperBrokerAdapter(BrokerAdapter):
    name = "kis_paper"
    mode = "paper"

    def status(self) -> dict[str, Any]:
        """KIS paper adapter skeleton 상태를 fail-closed로 반환한다."""
        return {
            "name": self.name,
            "mode": self.mode,
            "enabled": False,
            "paper_trading_enabled": False,
            "live_trading_enabled": False,
            "network_enabled": False,
            "can_preview": False,
            "can_submit": False,
            "can_cancel": False,
            "can_list_orders": False,
            "can_sync": False,
            "token_required": True,
            "token_issued": False,
            "token_persistence_enabled": False,
            "official_endpoint_confirmed": False,
            "reason": CONFIRMATION_REQUIRED,
        }

    def preview_order(self, request: BrokerOrderRequest) -> dict[str, Any]:
        """공식 paper 주문 field 확인 전 adapter preview를 실행하지 않는다."""
        raise BrokerCapabilityError(CONFIRMATION_REQUIRED)

    def submit_order(self, request: BrokerOrderRequest) -> dict[str, Any]:
        """공식 paper 주문 endpoint/TR-ID 확인 전 submit을 실행하지 않는다."""
        raise BrokerCapabilityError(CONFIRMATION_REQUIRED)

    def cancel_order(self, *, broker_order_id: str, confirm: bool = False) -> dict[str, Any]:
        """공식 cancel payload 확인 전 cancel을 실행하지 않는다."""
        raise BrokerCapabilityError(CANCEL_CONFIRMATION_REQUIRED)

    def list_orders(self, *, status: str | None = None) -> dict[str, Any]:
        """공식 주문 조회 field 확인 전 list를 실행하지 않는다."""
        raise BrokerCapabilityError(CONFIRMATION_REQUIRED)

    def sync(self, *, scope: str = "all") -> dict[str, Any]:
        """공식 sync 조회 contract 확인 전 sync를 실행하지 않는다."""
        raise BrokerCapabilityError(CONFIRMATION_REQUIRED)
