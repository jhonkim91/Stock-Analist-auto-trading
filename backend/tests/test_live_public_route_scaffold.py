from __future__ import annotations

import json


def _assert_disabled_live_route(payload: dict[str, object]) -> None:
    assert payload["status"] == "live_disabled"
    assert payload["public_route_scaffold"] is True
    assert payload["route_registered"] is True
    assert payload["route_network_enabled"] is False
    assert payload["live_submit_blocked"] is True
    assert payload["live_cancel_blocked"] is True
    assert payload["live_order_created"] is False
    assert payload["network_call_performed"] is False
    assert payload["adapter_network_call_performed"] is False
    assert payload["endpoint_called"] is False
    assert payload["secrets_redacted"] is True


def test_live_status_route_is_public_but_disabled_and_redacted(client, monkeypatch):
    sentinel = "LIVE_ROUTE_SENTINEL_SECRET"
    monkeypatch.setenv("KIS_APP_KEY", sentinel)
    monkeypatch.setenv("KIS_APP_SECRET", sentinel)
    monkeypatch.setenv("KIS_REFRESH_TOKEN", sentinel)

    response = client.get("/api/live/status")

    assert response.status_code == 200
    payload = response.json()
    _assert_disabled_live_route(payload)
    assert payload["operation"] == "live_route_status"
    assert payload["adapter"]["enabled"] is False
    assert payload["adapter"]["can_submit"] is False
    assert payload["adapter"]["network_enabled"] is False
    assert payload["live_order_safety"]["network_call_performed"] is False
    assert sentinel not in json.dumps(payload, ensure_ascii=False)


def test_kis_live_order_routes_return_disabled_payloads_without_network(client):
    responses = [
        client.get("/api/kis/orders"),
        client.get("/api/kis/orders/status"),
        client.post(
            "/api/kis/orders/preview",
            json={
                "symbol": "005930",
                "side": "buy",
                "qty": 1,
                "limit_price": 70000,
                "idempotency_key": "live-route-preview",
            },
        ),
        client.post(
            "/api/kis/orders/submit",
            json={
                "symbol": "005930",
                "side": "buy",
                "qty": 1,
                "limit_price": 70000,
                "idempotency_key": "live-route-submit",
            },
        ),
        client.post("/api/kis/orders/cancel", json={"broker_order_id": "live-1", "confirm": True}),
    ]

    for response in responses:
        assert response.status_code == 200
        _assert_disabled_live_route(response.json())

    assert responses[2].json()["live_order_safety"]["decision"] == "deny"
    assert responses[3].json()["live_order_safety"]["decision"] == "deny"
    assert responses[4].json()["live_cancel_safety"]["decision"] == "deny"


def test_kis_live_broker_and_websocket_routes_stay_unregistered(client):
    assert client.get("/api/kis/broker/status").status_code == 404
    assert client.get("/api/kis/websocket/status").status_code == 404
