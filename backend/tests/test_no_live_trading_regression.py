from __future__ import annotations

import json
from pathlib import Path

from backend.app.brokers.base import BrokerOrderRequest
from backend.app.brokers.kis_live import LIVE_DISABLED_REASON, KisLiveBrokerAdapter
from backend.app.main import app

ROOT = Path(__file__).resolve().parents[2]


def test_live_adapter_methods_are_unreachable():
    adapter = KisLiveBrokerAdapter()
    order = BrokerOrderRequest(symbol="005930", side="buy", qty=1)

    assert adapter.status()["enabled"] is False
    assert adapter.status()["live_trading_enabled"] is False
    for payload in (
        adapter.preview_order(order),
        adapter.submit_order(order),
        adapter.cancel_order(broker_order_id="live-1", confirm=True),
        adapter.list_orders(status="open"),
        adapter.sync(scope="all"),
    ):
        assert payload["ok"] is False
        assert payload["status"] == "live_disabled"
        assert payload["live_order_created"] is False
        assert payload["network_call_performed"] is False
        assert payload["endpoint_called"] is False
        assert payload["reason"] == LIVE_DISABLED_REASON


def test_kis_execution_routes_remain_unregistered_after_adapter_contract(client):
    route_paths = {getattr(route, "path", "") for route in app.routes}

    assert not any(path.startswith("/api/kis/orders") for path in route_paths)
    assert not any(path.startswith("/api/kis/broker") for path in route_paths)
    assert not any(path.startswith("/api/kis/websocket") for path in route_paths)
    assert client.post("/api/kis/orders/submit", json={"symbol": "005930"}).status_code == 404
    assert client.post("/api/kis/orders/cancel", json={"symbol": "005930"}).status_code == 404
    assert client.get("/api/kis/broker/status").status_code == 404
    assert client.get("/api/kis/websocket/status").status_code == 404


def test_broker_and_paper_status_do_not_enable_live_or_leak_secret(client, monkeypatch):
    sentinel = "PHASE2_SENTINEL_SECRET_VALUE"
    monkeypatch.setenv("KIS_APP_KEY", sentinel)
    monkeypatch.setenv("KIS_APP_SECRET", sentinel)

    broker = client.get("/api/broker/status")
    paper = client.get("/api/paper/status")

    assert broker.status_code == 200
    assert paper.status_code == 200
    broker_payload = broker.json()
    paper_payload = paper.json()
    assert broker_payload["live_trading_enabled"] is False
    assert broker_payload["paper_trading_enabled"] is False
    assert broker_payload["adapters"]["kis_live"]["enabled"] is False
    assert broker_payload["adapters"]["kis_paper"]["enabled"] is False
    assert paper_payload["broker_adapter"]["live_trading_enabled"] is False
    assert paper_payload["broker_adapter"]["paper_trading_enabled"] is False
    assert sentinel not in json.dumps({"broker": broker_payload, "paper": paper_payload}, ensure_ascii=False)
    assert not Path(".cache/kis/token.json").exists()


def test_paper_submit_cancel_endpoints_remain_local_fail_closed(client):
    submit = client.post(
        "/api/paper/orders/submit",
        json={
            "symbol": "KR009",
            "side": "buy",
            "qty": 1,
            "confirm": True,
            "idempotency_key": "no-live-regression-submit",
        },
    )
    cancel = client.post(
        "/api/paper/orders/cancel",
        json={
            "paper_order_id": "paper-missing",
            "confirm": True,
            "idempotency_key": "no-live-regression-cancel",
        },
    )

    assert submit.status_code == 200
    submit_payload = submit.json()
    assert submit_payload["ok"] is False
    assert submit_payload["paper_order_created"] is False
    assert submit_payload["live_order_created"] is False
    assert submit_payload["broker_order_created"] is False
    assert submit_payload["network_call_performed"] is False
    assert "KILL_SWITCH_ACTIVE" in submit_payload["reason_codes"]

    assert cancel.status_code == 200
    cancel_payload = cancel.json()
    assert cancel_payload["status"] == "cancel_disabled"
    assert cancel_payload["order_cancelled"] is False
    assert cancel_payload["live_order_created"] is False
    assert cancel_payload["broker_order_created"] is False
    assert cancel_payload["network_call_performed"] is False


def test_paper_sync_endpoint_remains_noop_without_network_or_live_path(client):
    response = client.post("/api/paper/sync", json={"scope": "all"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "sync_disabled"
    assert payload["sync_performed"] is False
    assert payload["live_order_created"] is False
    assert payload["broker_order_created"] is False
    assert payload["network_call_performed"] is False
    assert payload["synthetic_positions_touched"] is False


def test_paper_bot_endpoint_does_not_auto_submit_or_start_live_path(client):
    response = client.post("/api/paper/bot/run", json={"auto_submit": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["paper_order_submitted"] is False
    assert payload["auto_submit_allowed"] is False
    assert payload["live_order_created"] is False
    assert payload["broker_order_created"] is False
    assert payload["network_call_performed"] is False


def test_frontend_paper_controls_do_not_reference_live_execution_routes():
    frontend_files = [
        ROOT / "frontend" / "app" / "paper" / "page.tsx",
        ROOT / "frontend" / "app" / "portfolio" / "page.tsx",
        ROOT / "frontend" / "app" / "reports" / "page.tsx",
        ROOT / "frontend" / "app" / "settings" / "page.tsx",
        ROOT / "frontend" / "components" / "paper-mode-banner.tsx",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in frontend_files)

    assert "실거래 아님" in combined
    assert "paper only" in combined
    assert "/api/kis/orders" not in combined
    assert "/api/kis/broker" not in combined
    assert "/api/kis/websocket" not in combined
    assert "live trading ready" not in combined.lower()
