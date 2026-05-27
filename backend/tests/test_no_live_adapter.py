from __future__ import annotations

import json

import pytest

from backend.app.main import app
from backend.app.services.broker_adapter import BrokerDisabledError, BrokerOrderRequest
from backend.app.services.broker_service import BrokerService
from backend.app.services.kis_live_broker_adapter import LIVE_DISABLED_REASON, KisLiveBrokerAdapter


def test_service_live_adapter_is_hard_disabled():
    adapter = KisLiveBrokerAdapter()
    request = BrokerOrderRequest(symbol="005930", side="buy", qty=1)
    status = adapter.status()

    assert status["name"] == "kis_live"
    assert status["mode"] == "live"
    assert status["enabled"] is False
    assert status["live_trading_enabled"] is False
    assert status["network_enabled"] is False
    assert status["can_submit"] is False
    assert status["adapter_boundary"] == "live_disabled_placeholder"
    assert status["live_fallback_enabled"] is False

    with pytest.raises(BrokerDisabledError, match=LIVE_DISABLED_REASON):
        adapter.preview_order(request)
    with pytest.raises(BrokerDisabledError, match=LIVE_DISABLED_REASON):
        adapter.submit_order(request)
    with pytest.raises(BrokerDisabledError, match=LIVE_DISABLED_REASON):
        adapter.cancel_order(broker_order_id="live-1", confirm=True)
    with pytest.raises(BrokerDisabledError, match=LIVE_DISABLED_REASON):
        adapter.list_orders(status="open")
    with pytest.raises(BrokerDisabledError, match=LIVE_DISABLED_REASON):
        adapter.sync(scope="all")


def test_broker_service_reports_disabled_live_adapter_without_secrets(monkeypatch):
    sentinel = "PHASE2_SERVICE_SENTINEL_SECRET"
    monkeypatch.setenv("KIS_APP_KEY", sentinel)
    monkeypatch.setenv("KIS_APP_SECRET", sentinel)

    payload = BrokerService().status()
    live = payload["adapters"]["kis_live"]
    paper = payload["adapters"]["kis_paper"]

    assert live["enabled"] is False
    assert live["live_trading_enabled"] is False
    assert live["adapter_boundary"] == "live_disabled_placeholder"
    assert paper["adapter_boundary"] == "paper_only_service"
    assert paper["live_fallback_enabled"] is False
    assert sentinel not in json.dumps(payload, ensure_ascii=False)


def test_live_execution_routes_remain_unregistered():
    route_paths = {getattr(route, "path", "") for route in app.routes}

    assert not any(path.startswith("/api/kis/orders") for path in route_paths)
    assert not any(path.startswith("/api/kis/broker") for path in route_paths)
    assert not any(path.startswith("/api/kis/websocket") for path in route_paths)
