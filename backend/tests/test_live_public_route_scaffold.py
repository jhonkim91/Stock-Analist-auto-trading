from __future__ import annotations

import json


def test_live_status_route_is_public_but_gated_off_and_redacted(client, monkeypatch):
    sentinel = "LIVE_ROUTE_SENTINEL_SECRET"
    monkeypatch.setenv("KIS_APP_KEY", sentinel)
    monkeypatch.setenv("KIS_APP_SECRET", sentinel)
    monkeypatch.setenv("KIS_REFRESH_TOKEN", sentinel)

    response = client.get("/api/live/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "/api/live/status"
    # 기본 환경: 토글이 꺼져 있고 라이브 자격증명이 불완전하므로 제출 불가.
    assert payload["can_submit"] is False
    assert payload["reason_codes"]
    assert payload["credentials_present"] is False
    assert payload["secrets_redacted"] is True
    assert sentinel not in json.dumps(payload, ensure_ascii=False)


def test_kis_live_order_routes_are_gated_off_without_network(client):
    responses = {
        "status": client.get("/api/kis/orders/status"),
        "preview": client.post(
            "/api/kis/orders/preview",
            json={"symbol": "005930", "side": "buy", "qty": 1, "limit_price": 70000},
        ),
        "submit": client.post(
            "/api/kis/orders/submit",
            json={"symbol": "005930", "side": "buy", "qty": 1, "limit_price": 70000, "confirm": True},
        ),
        "cancel": client.post("/api/kis/orders/cancel", json={"broker_order_id": "live-1", "confirm": True}),
    }

    for response in responses.values():
        assert response.status_code == 200

    assert responses["status"].json()["can_submit"] is False
    assert responses["preview"].json()["network_call_performed"] is False
    assert responses["preview"].json()["live_order_created"] is False
    assert responses["submit"].json()["status"] == "submit_blocked"
    assert responses["submit"].json()["network_call_performed"] is False
    assert responses["submit"].json()["live_order_created"] is False
    assert responses["cancel"].json()["status"] == "cancel_blocked"
    assert responses["cancel"].json()["network_call_performed"] is False


def test_kis_live_broker_and_websocket_routes_stay_unregistered(client):
    assert client.get("/api/kis/broker/status").status_code == 404
    assert client.get("/api/kis/websocket/status").status_code == 404
