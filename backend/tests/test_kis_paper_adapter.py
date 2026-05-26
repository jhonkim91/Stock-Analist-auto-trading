from __future__ import annotations

import pytest

from backend.app.brokers.base import BrokerAdapter, BrokerCapabilityError, BrokerOrderRequest
from backend.app.brokers.kis_live import KisLiveBrokerAdapter
from backend.app.brokers.kis_paper import CONFIRMATION_REQUIRED, KisPaperBrokerAdapter


def test_kis_paper_adapter_implements_contract_as_disabled_skeleton():
    adapter = KisPaperBrokerAdapter()

    assert isinstance(adapter, BrokerAdapter)
    status = adapter.status()
    assert status["name"] == "kis_paper"
    assert status["enabled"] is False
    assert status["paper_trading_enabled"] is False
    assert status["live_trading_enabled"] is False
    assert status["network_enabled"] is False
    assert status["can_submit"] is False
    assert status["official_endpoint_confirmed"] is False
    assert status["reason"] == CONFIRMATION_REQUIRED


def test_kis_paper_adapter_blocks_unconfirmed_capabilities():
    adapter = KisPaperBrokerAdapter()
    order = BrokerOrderRequest(symbol="005930", side="buy", qty=1, limit_price=70000)

    with pytest.raises(BrokerCapabilityError, match=CONFIRMATION_REQUIRED):
        adapter.preview_order(order)
    with pytest.raises(BrokerCapabilityError, match=CONFIRMATION_REQUIRED):
        adapter.submit_order(order)
    with pytest.raises(BrokerCapabilityError, match=CONFIRMATION_REQUIRED):
        adapter.cancel_order(broker_order_id="paper-1", confirm=True)
    with pytest.raises(BrokerCapabilityError, match=CONFIRMATION_REQUIRED):
        adapter.list_orders(status="open")
    with pytest.raises(BrokerCapabilityError, match=CONFIRMATION_REQUIRED):
        adapter.sync(scope="all")


def test_kis_live_adapter_is_separate_disabled_placeholder():
    live = KisLiveBrokerAdapter()
    paper = KisPaperBrokerAdapter()

    assert live.name != paper.name
    assert live.status()["enabled"] is False
    assert live.status()["live_trading_enabled"] is False
    assert live.status()["paper_trading_enabled"] is False
