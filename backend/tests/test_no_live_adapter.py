from __future__ import annotations

import json

from backend.app.main import app
from backend.app.services.broker_adapter import BrokerOrderRequest
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
    assert status["submit_implementation_present"] is True
    assert status["cancel_implementation_present"] is True
    assert status["submit_network_enabled"] is False
    assert status["cancel_network_enabled"] is False
    assert status["adapter_boundary"] == "live_disabled_placeholder"
    assert status["live_fallback_enabled"] is False

    preview_payload = adapter.preview_order(request)
    submit_payload = adapter.submit_order(request)
    cancel_payload = adapter.cancel_order(broker_order_id="live-1", confirm=True)
    for operation, payload in {
        "preview_order": preview_payload,
        "submit_order": submit_payload,
        "cancel_order": cancel_payload,
        "list_orders": adapter.list_orders(status="open"),
        "sync": adapter.sync(scope="all"),
    }.items():
        assert payload["ok"] is False
        assert payload["operation"] == operation
        assert payload["status"] == "live_disabled"
        assert payload["live_order_created"] is False
        assert payload["network_call_performed"] is False
        assert payload["endpoint_called"] is False
        assert payload["reason"] == LIVE_DISABLED_REASON

    assert preview_payload["live_order_safety"]["decision"] == "deny"
    assert submit_payload["live_order_safety"]["decision"] == "deny"
    assert cancel_payload["live_cancel_safety"]["decision"] == "deny"
    assert cancel_payload["live_cancel_safety"]["network_call_performed"] is False


def test_broker_service_reports_disabled_live_adapter_without_secrets(monkeypatch):
    sentinel = "PHASE2_SERVICE_SENTINEL_SECRET"
    monkeypatch.setenv("KIS_APP_KEY", sentinel)
    monkeypatch.setenv("KIS_APP_SECRET", sentinel)

    payload = BrokerService().status()
    live = payload["adapters"]["kis_live"]
    paper = payload["adapters"]["kis_paper"]
    safety = payload["live_order_safety"]

    assert live["enabled"] is False
    assert live["live_trading_enabled"] is False
    assert live["adapter_boundary"] == "live_disabled_placeholder"
    assert live["submit_implementation_present"] is True
    assert live["cancel_implementation_present"] is True
    assert paper["adapter_boundary"] == "paper_only_service"
    assert paper["live_fallback_enabled"] is False
    assert safety["all_required_controls_passed"] is False
    assert "LIVE_TOKEN_REFRESH_NETWORK_DISABLED" in safety["blockers"]
    assert safety["live_order_created"] is False
    assert sentinel not in json.dumps(payload, ensure_ascii=False)


def test_broker_preview_includes_order_specific_live_safety_without_live_route(monkeypatch):
    monkeypatch.setenv("LIVE_MAX_ORDER_NOTIONAL", "100")
    monkeypatch.setenv("LIVE_SYMBOL_BLACKLIST", "KR009")

    payload = BrokerService().preview_order(
        symbol="KR009",
        side="buy",
        qty=2,
        limit_price=80.0,
        idempotency_key=None,
    )
    safety = payload["live_order_safety"]

    assert payload["order_created"] is False
    assert payload["network_call_performed"] is False
    assert safety["decision"] == "deny"
    assert safety["live_order_created"] is False
    assert "LIVE_ORDER_IDEMPOTENCY_KEY_REQUIRED" in safety["request_blockers"]
    assert "LIVE_ORDER_SYMBOL_BLACKLISTED" in safety["request_blockers"]
    assert "LIVE_ORDER_NOTIONAL_EXCEEDS_LIMIT" in safety["request_blockers"]


def test_live_execution_routes_are_registered_but_hard_disabled(client):
    route_paths = {getattr(route, "path", "") for route in app.routes}

    assert "/api/live/status" in route_paths
    assert "/api/kis/orders" in route_paths
    assert "/api/kis/orders/preview" in route_paths
    assert "/api/kis/orders/submit" in route_paths
    assert "/api/kis/orders/cancel" in route_paths
    assert not any(path.startswith("/api/kis/broker") for path in route_paths)
    assert not any(path.startswith("/api/kis/websocket") for path in route_paths)

    for response in (
        client.get("/api/live/status"),
        client.get("/api/kis/orders"),
        client.post("/api/kis/orders/preview", json={"symbol": "005930"}),
        client.post("/api/kis/orders/submit", json={"symbol": "005930"}),
        client.post("/api/kis/orders/cancel", json={"broker_order_id": "live-1", "confirm": True}),
    ):
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "live_disabled"
        assert payload["route_registered"] is True
        assert payload["live_order_created"] is False
        assert payload["network_call_performed"] is False
        assert payload["endpoint_called"] is False

    assert client.get("/api/kis/broker/status").status_code == 404
    assert client.get("/api/kis/websocket/status").status_code == 404
