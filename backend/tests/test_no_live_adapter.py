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
    assert status["adapter_boundary"] == "live_disabled_placeholder"
    assert status["live_fallback_enabled"] is False

    for operation, payload in {
        "preview_order": adapter.preview_order(request),
        "submit_order": adapter.submit_order(request),
        "cancel_order": adapter.cancel_order(broker_order_id="live-1", confirm=True),
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


def test_live_execution_routes_remain_unregistered():
    route_paths = {getattr(route, "path", "") for route in app.routes}

    assert not any(path.startswith("/api/kis/orders") for path in route_paths)
    assert not any(path.startswith("/api/kis/broker") for path in route_paths)
    assert not any(path.startswith("/api/kis/websocket") for path in route_paths)
