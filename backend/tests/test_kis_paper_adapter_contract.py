from __future__ import annotations

import pytest

from backend.app.models.schemas import BrokerAdapterStatus
from backend.app.services.broker_adapter import BrokerAdapter, BrokerCapabilityError, BrokerOrderRequest
from backend.app.services.kis_paper_broker_adapter import (
    CANCEL_CONFIRMATION_REQUIRED,
    CONFIRMATION_REQUIRED,
    SYNC_CONFIRMATION_REQUIRED,
    KisPaperBrokerAdapter,
)
from backend.app.services.paper_trading_service import PaperTradingService


def test_service_kis_paper_adapter_contract_is_fail_closed():
    adapter = KisPaperBrokerAdapter()
    request = BrokerOrderRequest(symbol="005930", side="buy", qty=1, limit_price=70000)

    assert isinstance(adapter, BrokerAdapter)
    status = adapter.status()
    parsed = BrokerAdapterStatus(**status)
    assert parsed.name == "kis_paper"
    assert parsed.mode == "paper"
    assert parsed.enabled is False
    assert parsed.live_trading_enabled is False
    assert parsed.network_enabled is False
    assert parsed.can_submit is False
    assert parsed.can_cancel is False
    assert parsed.can_sync is False
    assert parsed.adapter_boundary == "paper_only_service"
    assert parsed.live_fallback_enabled is False
    assert status["official_endpoint_confirmed"] is False
    assert status["reason"] == CONFIRMATION_REQUIRED

    with pytest.raises(BrokerCapabilityError, match=CONFIRMATION_REQUIRED):
        adapter.preview_order(request)
    with pytest.raises(BrokerCapabilityError, match=CONFIRMATION_REQUIRED):
        adapter.submit_order(request)
    with pytest.raises(BrokerCapabilityError, match=CANCEL_CONFIRMATION_REQUIRED):
        adapter.cancel_order(broker_order_id="paper-1", confirm=True)
    with pytest.raises(BrokerCapabilityError, match=CONFIRMATION_REQUIRED):
        adapter.list_orders(status="open")
    with pytest.raises(BrokerCapabilityError, match=SYNC_CONFIRMATION_REQUIRED):
        adapter.sync(scope="all")


def test_paper_trading_service_uses_service_adapter_boundary():
    service = PaperTradingService()
    status = service.status()["broker_adapter"]

    assert status["name"] == "kis_paper"
    assert status["adapter_boundary"] == "paper_only_service"
    assert status["live_fallback_enabled"] is False
    assert status["can_submit"] is False
    assert status["network_enabled"] is False
