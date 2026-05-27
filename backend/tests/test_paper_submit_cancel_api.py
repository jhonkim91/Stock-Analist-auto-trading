from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.models.tables import Order, PaperOrder
from backend.app.services.paper_order_service import CANCEL_DISABLED_REASON, PaperOrderService


class _FakePaperAdapter:
    def __init__(self) -> None:
        self.cancelled: list[str] = []

    def submit_order(self, request):
        return {
            "ok": True,
            "status": "submitted",
            "broker_order_created": True,
            "network_call_performed": True,
            "live_order_created": False,
            "broker_order_id": "001|000001|1|100|00|KRX",
            "broker_order_status": "submitted",
            "order": {
                "symbol": request.symbol,
                "side": request.side,
                "qty": request.qty,
                "filled_qty": 0,
                "remaining_qty": request.qty,
                "status": "submitted",
            },
            "broker_trace": {
                "operation": "submit",
                "endpoint_path": "/uapi/domestic-stock/v1/trading/order-cash",
                "tr_id": "VTTC0012U",
                "secrets_redacted": True,
            },
        }

    def cancel_order(self, *, broker_order_id: str, confirm: bool = False):
        self.cancelled.append(broker_order_id)
        return {
            "ok": True,
            "status": "cancelled",
            "cancel_supported": True,
            "order_cancelled": True,
            "network_call_performed": True,
            "live_order_created": False,
            "broker_order_created": False,
            "broker_order_id": broker_order_id,
            "broker_order_status": "cancelled",
            "broker_trace": {
                "operation": "cancel",
                "endpoint_path": "/uapi/domestic-stock/v1/trading/order-rvsecncl",
                "tr_id": "VTTC0013U",
                "secrets_redacted": True,
            },
        }


def _counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "orders": int(db.scalar(select(func.count()).select_from(Order)) or 0),
            "paper_orders": int(db.scalar(select(func.count()).select_from(PaperOrder)) or 0),
        }


def _write_network_paper_config(tmp_path) -> None:
    tmp_path.joinpath("paper.yaml").write_text(
        dedent(
            """
            paper:
              mode: "paper"
              enabled: true
              can_create: true
              can_simulate_fills: false
              preview_only: false
              kill_switch_enabled: false
              network_enabled: true
              live_order_enabled: false
              broker_order_enabled: false
            risk_gate:
              allow_buy_preview: true
              allow_sell_preview: true
              allow_short_sell: false
              max_order_qty: 1000000
              max_order_notional: 100000000
            audit:
              persistence_enabled: false
              sanitize_enabled: true
            simulator:
              enabled: false
              auto_fill_on_create: false
            broker_adapter:
              name: "kis_paper"
              enabled: true
              official_endpoint_confirmed: true
              official_balance_endpoint_confirmed: true
              balance_inquiry_enabled: true
              live_fallback_enabled: false
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _enable_network_runtime(monkeypatch) -> None:
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRADING_CAN_CREATE", "true")
    monkeypatch.setenv("PAPER_TRADING_NETWORK_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRADING_KILL_SWITCH", "false")
    monkeypatch.setenv("ENABLE_REAL_ORDER", "false")


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


def test_paper_order_service_uses_network_adapter_only_after_all_gates(db_session, tmp_path, monkeypatch):
    _enable_network_runtime(monkeypatch)
    _write_network_paper_config(tmp_path)
    adapter = _FakePaperAdapter()
    service = PaperOrderService(db_session, config_dir=tmp_path, adapter=adapter)

    submitted = service.submit_order(
        symbol="KR009",
        side="buy",
        qty=1,
        limit_price=100.0,
        confirm=True,
        idempotency_key="phase12b-network-submit",
    )
    cancelled = service.cancel_order(
        paper_order_id=submitted["order"]["paper_order_id"],
        confirm=True,
        idempotency_key="phase12b-network-cancel",
    )
    order = db_session.get(PaperOrder, submitted["order"]["paper_order_id"])

    assert submitted["ok"] is True
    assert submitted["broker_order_created"] is True
    assert submitted["network_call_performed"] is True
    assert submitted["broker_trace"]["tr_id"] == "VTTC0012U"
    assert cancelled["ok"] is True
    assert cancelled["order_cancelled"] is True
    assert cancelled["network_call_performed"] is True
    assert adapter.cancelled == ["001|000001|1|100|00|KRX"]
    assert order is not None
    assert order.status == "cancelled"
    assert order.live_order_created is False
    assert order.network_call_performed is True
    assert _counts()["orders"] == 0
