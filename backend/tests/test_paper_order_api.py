from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.models.tables import Order, PaperAuditEvent, PaperOrder

def _row_counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "orders": int(db.scalar(select(func.count()).select_from(Order)) or 0),
            "paper_orders": int(db.scalar(select(func.count()).select_from(PaperOrder)) or 0),
            "paper_audit_events": int(db.scalar(select(func.count()).select_from(PaperAuditEvent)) or 0),
        }


def test_submit_endpoint_requires_confirm_idempotency_and_blocks_without_fresh_quote(client, monkeypatch):
    sentinel = "PHASE4_SENTINEL_SECRET_VALUE"
    monkeypatch.setenv("KIS_APP_KEY", sentinel)
    monkeypatch.setenv("KIS_APP_SECRET", sentinel)
    before = _row_counts()

    no_confirm = client.post(
        "/api/paper/orders/submit",
        json={
            "symbol": "KR009",
            "side": "buy",
            "qty": 10,
            "limit_price": 100.0,
            "idempotency_key": "phase4-api-no-confirm",
        },
    )
    no_key = client.post(
        "/api/paper/orders/submit",
        json={"symbol": "KR009", "side": "buy", "qty": 10, "limit_price": 100.0, "confirm": True},
    )
    blocked = client.post(
        "/api/paper/orders/submit",
        json={
            "symbol": "KR009",
            "side": "buy",
            "qty": 10,
            "limit_price": 100.0,
            "confirm": True,
            "idempotency_key": "phase4-api-blocked",
        },
    )

    assert no_confirm.status_code == 200
    assert no_confirm.json()["status"] == "confirm_required"
    assert no_key.status_code == 200
    assert no_key.json()["status"] == "idempotency_required"
    assert blocked.status_code == 200
    blocked_payload = blocked.json()
    assert blocked_payload["status"] == "blocked"
    assert blocked_payload["paper_order_created"] is False
    assert blocked_payload["live_order_created"] is False
    assert blocked_payload["broker_order_created"] is False
    assert blocked_payload["network_call_performed"] is False
    assert {"PAPER_REALTIME_QUOTE_MISSING", "PAPER_REALTIME_STALE_QUOTE"}.issubset(
        set(blocked_payload["reason_codes"])
    )
    assert _row_counts() == before == {"orders": 0, "paper_orders": 0, "paper_audit_events": 0}
    assert sentinel not in json.dumps([no_confirm.json(), no_key.json(), blocked_payload], ensure_ascii=False)
    assert not Path(".cache/kis/token.json").exists()


def test_list_and_cancel_routes_are_registered_but_cancel_is_safely_disabled(client):
    before = _row_counts()

    listed = client.get("/api/paper/orders")
    no_confirm = client.post(
        "/api/paper/orders/cancel",
        json={"paper_order_id": "paper-missing", "idempotency_key": "phase4-cancel-api"},
    )
    no_key = client.post(
        "/api/paper/orders/cancel",
        json={"paper_order_id": "paper-missing", "confirm": True},
    )
    disabled = client.post(
        "/api/paper/orders/cancel",
        json={"paper_order_id": "paper-missing", "confirm": True, "idempotency_key": "phase4-cancel-api"},
    )

    assert listed.status_code == 200
    assert listed.json()["orders"] == []
    assert no_confirm.status_code == 200
    assert no_confirm.json()["status"] == "confirm_required"
    assert no_key.status_code == 200
    assert no_key.json()["status"] == "idempotency_required"
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "cancel_blocked"
    assert disabled.json()["reason"] == "PAPER_ORDER_NOT_FOUND"
    assert disabled.json()["order_cancelled"] is False
    assert disabled.json()["live_order_created"] is False
    assert disabled.json()["broker_order_created"] is False
    assert disabled.json()["network_call_performed"] is False
    assert _row_counts() == before
