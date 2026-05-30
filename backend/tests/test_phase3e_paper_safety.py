from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.main import app
from backend.app.models.tables import Order, PaperAuditEvent, PaperFill, PaperOrder, PaperPosition

SENSITIVE_FIELD_NAMES = {
    "app_key",
    "app_secret",
    "token",
    "access_token",
    "refresh_token",
    "approval_key",
    "account",
    "account_no",
    "cano",
    "hts_id",
    "password",
    "authorization",
    "headers",
    "raw_credentials",
}


def _row_counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "orders": int(db.scalar(select(func.count()).select_from(Order)) or 0),
            "paper_orders": int(db.scalar(select(func.count()).select_from(PaperOrder)) or 0),
            "paper_fills": int(db.scalar(select(func.count()).select_from(PaperFill)) or 0),
            "paper_positions": int(db.scalar(select(func.count()).select_from(PaperPosition)) or 0),
            "paper_audit_events": int(db.scalar(select(func.count()).select_from(PaperAuditEvent)) or 0),
        }


def _assert_paper_safety_flags(payload: dict[str, object]) -> None:
    assert payload["enabled"] is True
    assert payload["can_create"] is False
    assert payload["can_simulate_fills"] is False
    assert payload["preview_only"] is False
    assert payload["paper_order_supported"] is False
    assert payload["fill_simulator_supported"] is False
    assert payload["paper_order_created"] is False
    assert payload["live_order_created"] is False
    assert payload["broker_order_created"] is False
    assert payload["fill_created"] is False
    assert payload["position_changed"] is False
    assert payload["token_issued"] is False
    assert payload["token_cache_enabled"] is False
    assert payload["network_call_performed"] is False
    assert payload["adapter_order_call_performed"] is False
    assert payload["adapter_network_call_performed"] is False
    assert payload["audit_persistence_enabled"] is False
    assert payload["paper_tables_write_enabled"] is False
    assert payload["kill_switch"]["blocking"] is False
    assert payload["risk_gate"]["decision"] == "deny"


def test_paper_status_is_enabled_but_blocks_without_network_credentials(client, monkeypatch):
    sentinel = "PHASE3E_SENTINEL_SECRET_VALUE"
    monkeypatch.setenv("KIS_APP_KEY", sentinel)
    monkeypatch.setenv("KIS_APP_SECRET", sentinel)

    status = client.get("/api/paper/status")
    settings = client.get("/api/settings")

    assert status.status_code == 200
    assert settings.status_code == 200
    payload = status.json()
    _assert_paper_safety_flags(payload)
    assert payload["mode"] == "paper"
    assert payload["configured_enabled"] is True
    assert payload["counts"]["orders_count"] == 0
    assert payload["counts"]["paper_orders_count"] == 0
    assert payload["counts"]["paper_fills_count"] == 0
    assert payload["counts"]["paper_positions_count"] == 0
    assert payload["counts"]["paper_audit_events_count"] == 0
    reason_codes = set(payload["risk_gate"]["reason_codes"])
    assert "KIS_ACCESS_TOKEN_REQUIRED_FOR_NETWORK" in reason_codes
    assert "paper" in settings.json()

    serialized = json.dumps({"status": payload, "settings": settings.json()}, ensure_ascii=False)
    assert sentinel not in serialized
    allowed_redacted_field_names = {"access_token", "refresh_token"}
    assert (SENSITIVE_FIELD_NAMES - allowed_redacted_field_names).isdisjoint(serialized.lower().split('"'))


def test_paper_preview_denies_without_kis_network_credentials(client, monkeypatch):
    sentinel = "PHASE3E_SENTINEL_SECRET_VALUE"
    monkeypatch.setenv("KIS_APP_KEY", sentinel)
    monkeypatch.setenv("KIS_APP_SECRET", sentinel)
    before = _row_counts()

    response = client.post(
        "/api/paper/orders/preview",
        json={"symbol": "KR009", "side": "buy", "qty": 10, "limit_price": 100.0, "stop_price": 90.0},
    )

    assert response.status_code == 200
    payload = response.json()
    _assert_paper_safety_flags(payload)
    assert payload["symbol"] == "KR009"
    assert payload["side"] == "buy"
    assert payload["qty"] == 10
    reason_codes = set(payload["risk_gate"]["reason_codes"])
    assert "KIS_ACCESS_TOKEN_REQUIRED_FOR_NETWORK" in reason_codes
    assert _row_counts() == before == {
        "orders": 0,
        "paper_orders": 0,
        "paper_fills": 0,
        "paper_positions": 0,
        "paper_audit_events": 0,
    }
    assert not Path(".cache/kis/token.json").exists()
    assert sentinel not in json.dumps(payload, ensure_ascii=False)


def test_paper_sell_preview_does_not_create_short_or_position_rows(client):
    before = _row_counts()

    response = client.post("/api/paper/orders/preview", json={"symbol": "KR009", "side": "sell", "qty": 1})

    assert response.status_code == 200
    payload = response.json()
    _assert_paper_safety_flags(payload)
    reason_codes = set(payload["risk_gate"]["reason_codes"])
    assert {"PAPER_POSITION_NOT_FOUND", "SHORT_SELL_UNSUPPORTED"}.issubset(reason_codes)
    assert _row_counts() == before


def test_paper_create_fill_and_kis_order_routes_remain_disabled(client):
    route_paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/paper/orders" in route_paths
    assert "/api/paper/fill-simulator/run" in route_paths
    assert "/api/kis/orders/status" in route_paths
    assert "/api/kis/orders/preview" in route_paths
    assert "/api/kis/orders/submit" in route_paths
    assert not any(path.startswith("/api/kis/broker") for path in route_paths)
    assert not any(path.startswith("/api/kis/websocket") for path in route_paths)

    submit = client.post("/api/paper/orders", json={"symbol": "KR009", "side": "buy", "qty": 1})
    assert submit.status_code == 200
    assert submit.json()["paper_order_created"] is False
    assert submit.json()["network_call_performed"] is False
    assert client.post("/api/paper/fill-simulator/run", json={}).status_code == 422
    live_status = client.get("/api/kis/orders/status")
    preview = client.post("/api/kis/orders/preview", json={"symbol": "005930"})
    live_submit = client.post("/api/kis/orders/submit", json={"symbol": "005930"})
    assert live_status.status_code == 200
    assert preview.status_code == 200
    assert live_submit.status_code == 200
    assert live_status.json()["can_submit"] is False
    assert preview.json()["network_call_performed"] is False
    assert preview.json()["live_order_created"] is False
    assert live_submit.json()["network_call_performed"] is False
    assert live_submit.json()["live_order_created"] is False
    assert client.get("/api/kis/broker/status").status_code == 404
    assert client.get("/api/kis/websocket/status").status_code == 404
