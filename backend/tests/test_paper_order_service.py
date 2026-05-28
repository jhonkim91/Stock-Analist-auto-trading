from __future__ import annotations

from textwrap import dedent

from sqlalchemy import func, select

from backend.app.models.tables import Order, PaperAuditEvent, PaperOrder
from backend.app.services.paper_order_service import CANCEL_DISABLED_REASON, PaperOrderService


def _write_paper_config(
    tmp_path,
    *,
    enabled: bool = True,
    can_create: bool = True,
    preview_only: bool = False,
    kill_switch_enabled: bool = False,
    network_enabled: bool = False,
    audit_persistence_enabled: bool = True,
) -> None:
    tmp_path.joinpath("paper.yaml").write_text(
        dedent(
            f"""
            paper:
              mode: "safety_scaffold"
              enabled: {str(enabled).lower()}
              can_create: {str(can_create).lower()}
              can_simulate_fills: false
              preview_only: {str(preview_only).lower()}
              kill_switch_enabled: {str(kill_switch_enabled).lower()}
              network_enabled: {str(network_enabled).lower()}
              live_order_enabled: false
              broker_order_enabled: false
            risk_gate:
              allow_buy_preview: true
              allow_sell_preview: true
              allow_short_sell: false
              max_order_qty: 1000000
              max_order_notional: 100000000
            audit:
              persistence_enabled: {str(audit_persistence_enabled).lower()}
              sanitize_enabled: true
            simulator:
              enabled: false
              auto_fill_on_create: false
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _count(db_session, model) -> int:
    return int(db_session.scalar(select(func.count()).select_from(model)) or 0)


def _enable_manual_paper_runtime(monkeypatch) -> None:
    monkeypatch.setenv("KIS_ENV", "paper")
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRADING_CAN_CREATE", "true")
    monkeypatch.setenv("PAPER_TRADING_KILL_SWITCH", "false")
    monkeypatch.setenv("PAPER_BOT_CONFIRM", "true")
    monkeypatch.delenv("PAPER_TRADING_NETWORK_ENABLED", raising=False)


class _RecordingSubmitAdapter:
    def __init__(self) -> None:
        self.requests = []

    def submit_order(self, request):
        self.requests.append(request)
        return {
            "ok": True,
            "broker_order_id": "kis-paper-us|NASD|AAPL|900001",
            "broker_order_status": "submitted",
            "broker_trace": {
                "endpoint_path": "/uapi/overseas-stock/v1/trading/order",
                "tr_id": "VTTT1002U",
                "network_call_performed": True,
            },
            "order": {
                "symbol": request.symbol,
                "side": request.side,
                "qty": request.qty,
                "filled_qty": 0,
                "remaining_qty": request.qty,
                "status": "submitted",
                "market": request.metadata.get("market"),
                "venue": request.metadata.get("venue"),
            },
        }


class _FailingNetworkSubmitAdapter:
    def submit_order(self, request):
        return {
            "ok": False,
            "status": "submit_failed",
            "reason": "KIS_PAPER_RESPONSE_ERROR",
            "reason_codes": ["KIS_PAPER_RESPONSE_ERROR"],
            "broker_trace": {
                "endpoint_path": "/uapi/overseas-stock/v1/trading/order",
                "tr_id": "VTTT1002U",
                "network_call_performed": True,
                "rt_cd": "1",
                "msg_cd": "EGW00123",
                "msg1": "expired token",
            },
        }


def test_submit_requires_confirm_idempotency_and_kill_switch_before_write(db_session, tmp_path, monkeypatch):
    _enable_manual_paper_runtime(monkeypatch)
    _write_paper_config(tmp_path)
    service = PaperOrderService(db_session, config_dir=tmp_path)

    no_confirm = service.submit_order(
        symbol="KR009",
        side="buy",
        qty=10,
        limit_price=100.0,
        confirm=False,
        idempotency_key="phase4-no-confirm",
    )
    no_key = service.submit_order(
        symbol="KR009",
        side="buy",
        qty=10,
        limit_price=100.0,
        confirm=True,
        idempotency_key=None,
    )

    _write_paper_config(tmp_path, kill_switch_enabled=True)
    monkeypatch.setenv("PAPER_TRADING_KILL_SWITCH", "true")
    kill_switch = service.submit_order(
        symbol="KR009",
        side="buy",
        qty=10,
        limit_price=100.0,
        confirm=True,
        idempotency_key="phase4-kill",
    )

    assert no_confirm["status"] == "confirm_required"
    assert no_confirm["paper_order_created"] is False
    assert no_key["status"] == "idempotency_required"
    assert no_key["paper_order_created"] is False
    assert kill_switch["status"] == "blocked"
    assert "KILL_SWITCH_ACTIVE" in kill_switch["reason_codes"]
    assert _count(db_session, PaperOrder) == 0
    assert _count(db_session, PaperAuditEvent) == 0
    assert _count(db_session, Order) == 0


def test_submit_creates_local_paper_order_idempotently_without_live_side_effects(db_session, tmp_path, monkeypatch):
    _enable_manual_paper_runtime(monkeypatch)
    _write_paper_config(tmp_path)
    service = PaperOrderService(db_session, config_dir=tmp_path)

    created = service.submit_order(
        symbol="KR009",
        side="buy",
        qty=10,
        limit_price=100.0,
        stop_price=90.0,
        strategy_tag="phase4",
        confirm=True,
        idempotency_key="phase4-submit-1",
    )
    replay = service.submit_order(
        symbol="KR009",
        side="buy",
        qty=10,
        limit_price=100.0,
        stop_price=90.0,
        strategy_tag="phase4",
        confirm=True,
        idempotency_key="phase4-submit-1",
    )
    conflict = service.submit_order(
        symbol="KR009",
        side="buy",
        qty=11,
        limit_price=100.0,
        stop_price=90.0,
        strategy_tag="phase4",
        confirm=True,
        idempotency_key="phase4-submit-1",
    )
    duplicate = service.submit_order(
        symbol="KR009",
        side="buy",
        qty=10,
        limit_price=100.0,
        stop_price=90.0,
        strategy_tag="phase4",
        confirm=True,
        idempotency_key="phase4-submit-duplicate",
    )
    listed = service.list_orders()

    assert created["ok"] is True
    assert created["status"] == "submitted"
    assert created["paper_order_created"] is True
    assert created["live_order_created"] is False
    assert created["broker_order_created"] is False
    assert created["network_call_performed"] is False
    assert created["order"]["status"] == "submitted"
    assert created["order"]["idempotency_key"] == "phase4-submit-1"
    assert replay["status"] == "idempotent_replay"
    assert replay["paper_order_created"] is False
    assert replay["order"]["paper_order_id"] == created["order"]["paper_order_id"]
    assert conflict["status"] == "idempotency_conflict"
    assert conflict["paper_order_created"] is False
    assert duplicate["status"] == "duplicate_blocked"
    assert "PAPER_DUPLICATE_OPEN_ORDER" in duplicate["reason_codes"]
    assert duplicate["paper_order_created"] is False
    assert listed["orders"][0]["paper_order_id"] == created["order"]["paper_order_id"]
    assert _count(db_session, PaperOrder) == 1
    assert _count(db_session, PaperAuditEvent) == 1
    assert _count(db_session, Order) == 0


def test_network_submit_uses_us_market_metadata_from_runtime_env(db_session, tmp_path, monkeypatch):
    _enable_manual_paper_runtime(monkeypatch)
    monkeypatch.setenv("PAPER_TRADING_NETWORK_ENABLED", "true")
    monkeypatch.setenv("BROKER_MODE", "paper_kis")
    monkeypatch.setenv("PAPER_ORDER_SUBMIT_ENABLED", "true")
    monkeypatch.setenv("ENABLE_REAL_ORDER", "false")
    monkeypatch.setenv("PAPER_TRADING_MARKET", "US")
    monkeypatch.setenv("KIS_OVERSEAS_EXCHANGE_CODE", "NASD")
    monkeypatch.setenv("KIS_OVERSEAS_CURRENCY", "USD")
    monkeypatch.setenv("KIS_OVERSEAS_ORDER_SESSION", "premarket")
    _write_paper_config(tmp_path, network_enabled=True)
    adapter = _RecordingSubmitAdapter()
    service = PaperOrderService(db_session, config_dir=tmp_path, adapter=adapter)

    result = service.submit_order(
        symbol="AAPL",
        side="buy",
        qty=1,
        limit_price=145.25,
        strategy_tag="phase21-us",
        confirm=True,
        idempotency_key="phase21-us-service-submit",
    )

    assert result["ok"] is True
    assert result["broker_order_created"] is True
    assert result["network_call_performed"] is True
    assert adapter.requests[0].metadata == {
        "strategy_tag": "phase21-us",
        "market": "US",
        "venue": "NASD",
        "exchange": "NASD",
        "currency": "USD",
        "order_session": "premarket",
    }
    assert _count(db_session, PaperOrder) == 1
    assert _count(db_session, Order) == 0


def test_network_submit_failure_preserves_network_trace_flag(db_session, tmp_path, monkeypatch):
    _enable_manual_paper_runtime(monkeypatch)
    monkeypatch.setenv("PAPER_TRADING_NETWORK_ENABLED", "true")
    monkeypatch.setenv("BROKER_MODE", "paper_kis")
    monkeypatch.setenv("PAPER_ORDER_SUBMIT_ENABLED", "true")
    monkeypatch.setenv("ENABLE_REAL_ORDER", "false")
    monkeypatch.setenv("PAPER_TRADING_MARKET", "US")
    monkeypatch.setenv("KIS_OVERSEAS_EXCHANGE_CODE", "NASD")
    monkeypatch.setenv("KIS_OVERSEAS_CURRENCY", "USD")
    _write_paper_config(tmp_path, network_enabled=True)
    service = PaperOrderService(db_session, config_dir=tmp_path, adapter=_FailingNetworkSubmitAdapter())

    result = service.submit_order(
        symbol="AAPL",
        side="buy",
        qty=1,
        limit_price=145.25,
        strategy_tag="phase21-us",
        confirm=True,
        idempotency_key="phase21-us-service-submit-failed",
    )

    assert result["ok"] is False
    assert result["status"] == "submit_failed"
    assert result["network_call_performed"] is True
    assert result["broker_trace"]["network_call_performed"] is True
    assert result["broker_trace"]["msg_cd"] == "EGW00123"
    assert _count(db_session, PaperOrder) == 0
    assert _count(db_session, Order) == 0


def test_cancel_stays_disabled_until_official_payload_is_confirmed(db_session, tmp_path, monkeypatch):
    _enable_manual_paper_runtime(monkeypatch)
    _write_paper_config(tmp_path)
    service = PaperOrderService(db_session, config_dir=tmp_path)
    created = service.submit_order(
        symbol="KR009",
        side="buy",
        qty=1,
        limit_price=100.0,
        confirm=True,
        idempotency_key="phase4-cancel-source",
    )

    no_confirm = service.cancel_order(
        paper_order_id=created["order"]["paper_order_id"],
        confirm=False,
        idempotency_key="phase4-cancel-1",
    )
    no_key = service.cancel_order(
        paper_order_id=created["order"]["paper_order_id"],
        confirm=True,
        idempotency_key=None,
    )
    disabled = service.cancel_order(
        paper_order_id=created["order"]["paper_order_id"],
        confirm=True,
        idempotency_key="phase4-cancel-1",
    )
    order = db_session.scalar(select(PaperOrder).where(PaperOrder.paper_order_id == created["order"]["paper_order_id"]))

    assert no_confirm["status"] == "confirm_required"
    assert no_confirm["order_cancelled"] is False
    assert no_key["status"] == "idempotency_required"
    assert no_key["order_cancelled"] is False
    assert disabled["status"] == "cancel_disabled"
    assert disabled["reason"] == CANCEL_DISABLED_REASON
    assert disabled["order_cancelled"] is False
    assert order is not None
    assert order.status == "submitted"
    assert order.canceled_at is None
    assert _count(db_session, PaperOrder) == 1
    assert _count(db_session, Order) == 0
