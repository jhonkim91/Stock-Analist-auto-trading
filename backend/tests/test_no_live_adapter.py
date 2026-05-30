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
    assert status["authority_contract"]["present"] is True
    assert status["authority_contract"]["submit_authority_present"] is False
    assert status["authority_contract"]["cancel_authority_present"] is False
    assert status["authority_contract"]["network_call_performed"] is False

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
        if operation in {"preview_order", "submit_order", "cancel_order"}:
            assert payload["authority_contract"]["requires_separate_user_approval"] is True
            assert payload["authority_contract"]["live_order_created"] is False

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
    assert live["authority_contract"]["requires_token_refresh_real_call_proof"] is True
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


def test_live_execution_routes_are_registered_and_gated_off_by_default(client):
    """라이브 라우트는 등록되어 있으나 기본 환경에서는 모든 게이트가 꺼져 실주문/네트워크가 없다."""
    route_paths = {getattr(route, "path", "") for route in app.routes}

    assert "/api/live/status" in route_paths
    assert "/api/kis/orders/status" in route_paths
    assert "/api/kis/orders/preview" in route_paths
    assert "/api/kis/orders/submit" in route_paths
    assert "/api/kis/orders/cancel" in route_paths
    assert not any(path.startswith("/api/kis/broker") for path in route_paths)
    assert not any(path.startswith("/api/kis/websocket") for path in route_paths)

    live_status = client.get("/api/live/status")
    kis_status = client.get("/api/kis/orders/status")
    assert live_status.status_code == 200
    assert kis_status.status_code == 200
    assert live_status.json()["can_submit"] is False
    assert kis_status.json()["can_submit"] is False
    assert "LIVE_TRADING_DISABLED" in kis_status.json()["reason_codes"]
    assert "ENABLE_REAL_ORDER_REQUIRED" in kis_status.json()["reason_codes"]

    # confirm=True여도 게이트(토글/자격증명)가 꺼져 있으면 차단되고 네트워크가 발생하지 않는다.
    submit = client.post(
        "/api/kis/orders/submit",
        json={"symbol": "005930", "side": "buy", "qty": 1, "limit_price": 70000, "confirm": True},
    )
    cancel = client.post("/api/kis/orders/cancel", json={"broker_order_id": "live-1", "confirm": True})
    assert submit.status_code == 200
    assert cancel.status_code == 200
    assert submit.json()["status"] == "submit_blocked"
    assert submit.json()["live_order_created"] is False
    assert submit.json()["network_call_performed"] is False
    assert cancel.json()["status"] == "cancel_blocked"
    assert cancel.json()["network_call_performed"] is False

    assert client.get("/api/kis/broker/status").status_code == 404
    assert client.get("/api/kis/websocket/status").status_code == 404
