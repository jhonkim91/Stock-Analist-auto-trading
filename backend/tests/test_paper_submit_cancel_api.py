from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.models.tables import Order, PaperOrder
from backend.app.services.paper_order_service import CANCEL_DISABLED_REASON


def _counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "orders": int(db.scalar(select(func.count()).select_from(Order)) or 0),
            "paper_orders": int(db.scalar(select(func.count()).select_from(PaperOrder)) or 0),
        }


def test_paper_submit_api_is_paper_only_and_blocked_by_default(client, monkeypatch):
    sentinel = "PHASE4_SUBMIT_SENTINEL_SECRET"
    monkeypatch.setenv("KIS_APP_KEY", sentinel)
    monkeypatch.setenv("KIS_APP_SECRET", sentinel)
    monkeypatch.setenv("PAPER_BOT_ENABLED", "false")
    before = _counts()

    response = client.post(
        "/api/paper/orders/submit",
        json={
            "symbol": "KR009",
            "side": "buy",
            "qty": 1,
            "confirm": True,
            "idempotency_key": "phase4-submit-api-paper-only",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["paper_only"] is True
    assert payload["execution_mode"] == "paper"
    assert payload["live_fallback_enabled"] is False
    assert payload["paper_order_created"] is False
    assert payload["live_order_created"] is False
    assert payload["broker_order_created"] is False
    assert payload["network_call_performed"] is False
    assert payload["broker_trace"]["operation"] == "paper_order_submit"
    assert payload["broker_trace"]["paper_only"] is True
    assert payload["broker_trace"]["live_fallback_enabled"] is False
    assert "KILL_SWITCH_ACTIVE" in payload["reason_codes"]
    assert sentinel not in json.dumps(payload, ensure_ascii=False)
    assert _counts() == before
    assert not Path(".cache/kis/token.json").exists()


def test_paper_cancel_api_is_registered_but_fail_closed(client):
    before = _counts()

    response = client.post(
        "/api/paper/orders/cancel",
        json={
            "paper_order_id": "paper-missing",
            "confirm": True,
            "idempotency_key": "phase4-cancel-api-paper-only",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "cancel_disabled"
    assert payload["reason"] == CANCEL_DISABLED_REASON
    assert payload["paper_only"] is True
    assert payload["execution_mode"] == "paper"
    assert payload["live_fallback_enabled"] is False
    assert payload["order_cancelled"] is False
    assert payload["live_order_created"] is False
    assert payload["broker_order_created"] is False
    assert payload["network_call_performed"] is False
    assert payload["broker_trace"]["operation"] == "paper_order_cancel"
    assert _counts() == before
