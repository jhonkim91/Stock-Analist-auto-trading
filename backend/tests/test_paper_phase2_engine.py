from __future__ import annotations

from textwrap import dedent

from sqlalchemy import func, select

from backend.app.models.tables import Order, PaperAuditEvent, PaperFill, PaperOrder, PaperPosition, utc_now
from backend.app.services.paper_fill_simulator_service import PaperFillSimulatorService
from backend.app.services.paper_order_service import PaperOrderService


def _write_phase2_config(tmp_path) -> None:
    tmp_path.joinpath("paper.yaml").write_text(
        dedent(
            """
            paper:
              mode: "paper"
              enabled: true
              can_create: true
              can_simulate_fills: true
              preview_only: false
              kill_switch_enabled: false
              network_enabled: false
              live_order_enabled: false
              broker_order_enabled: false
              require_bot_confirm: true
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
              enabled: true
              auto_fill_on_create: false
            broker_adapter:
              name: "kis_paper"
              enabled: false
              live_fallback_enabled: false
            realtime:
              enabled: false
              require_fresh_quote_for_orders: false
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _enable_phase2_runtime(monkeypatch) -> None:
    monkeypatch.setenv("KIS_ENV", "paper")
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRADING_CAN_CREATE", "true")
    monkeypatch.setenv("PAPER_TRADING_CAN_SIMULATE_FILLS", "true")
    monkeypatch.setenv("PAPER_FILL_SIMULATOR_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRADING_KILL_SWITCH", "false")
    monkeypatch.setenv("PAPER_BOT_CONFIRM", "true")
    monkeypatch.setenv("ENABLE_REAL_ORDER", "false")


def _count(db_session, model) -> int:
    return int(db_session.scalar(select(func.count()).select_from(model)) or 0)


def test_local_paper_cancel_closes_open_order_without_live_side_effects(db_session, tmp_path, monkeypatch) -> None:
    _enable_phase2_runtime(monkeypatch)
    _write_phase2_config(tmp_path)
    order_service = PaperOrderService(db_session, config_dir=tmp_path)
    created = order_service.submit_order(
        symbol="KR009",
        side="buy",
        qty=5,
        limit_price=100.0,
        confirm=True,
        idempotency_key="phase2-cancel-create",
    )

    open_before = order_service.list_open_orders()
    cancelled = order_service.cancel_order(
        paper_order_id=created["order"]["paper_order_id"],
        confirm=True,
        idempotency_key="phase2-cancel-local",
    )
    open_after = order_service.list_open_orders()
    order = db_session.get(PaperOrder, created["order"]["paper_order_id"])

    assert open_before["orders"][0]["paper_order_id"] == created["order"]["paper_order_id"]
    assert cancelled["ok"] is True
    assert cancelled["order_cancelled"] is True
    assert cancelled["network_call_performed"] is False
    assert cancelled["live_order_created"] is False
    assert order is not None
    assert order.status == "cancelled"
    assert open_after["orders"] == []
    assert _count(db_session, Order) == 0


def test_fill_simulator_creates_fill_and_updates_position_idempotently(db_session, tmp_path, monkeypatch) -> None:
    _enable_phase2_runtime(monkeypatch)
    _write_phase2_config(tmp_path)
    order_service = PaperOrderService(db_session, config_dir=tmp_path)
    fill_service = PaperFillSimulatorService(db_session, config_dir=tmp_path)
    created = order_service.submit_order(
        symbol="KR010",
        side="buy",
        qty=4,
        limit_price=50.0,
        strategy_tag="phase2",
        confirm=True,
        idempotency_key="phase2-fill-create",
    )

    filled = fill_service.simulate_fill(
        paper_order_id=created["order"]["paper_order_id"],
        fill_price=50.5,
        qty=4,
        confirm=True,
        idempotency_key="phase2-fill-once",
    )
    replay = fill_service.simulate_fill(
        paper_order_id=created["order"]["paper_order_id"],
        fill_price=50.5,
        qty=4,
        confirm=True,
        idempotency_key="phase2-fill-once",
    )
    order = db_session.get(PaperOrder, created["order"]["paper_order_id"])
    position = db_session.scalar(select(PaperPosition).where(PaperPosition.symbol == "KR010"))

    assert filled["ok"] is True
    assert filled["status"] == "filled"
    assert filled["fill_created"] is True
    assert filled["position_changed"] is True
    assert filled["network_call_performed"] is False
    assert replay["status"] == "idempotent_replay"
    assert replay["fill_created"] is False
    assert order is not None
    assert order.status == "filled"
    assert order.filled_qty == 4
    assert order.remaining_qty == 0
    assert position is not None
    assert position.qty == 4
    assert position.avg_price == 50.5
    assert _count(db_session, PaperFill) == 1
    assert _count(db_session, PaperPosition) == 1
    assert _count(db_session, Order) == 0


def test_stoploss_and_trailing_exit_create_local_sell_fill(db_session, tmp_path, monkeypatch) -> None:
    _enable_phase2_runtime(monkeypatch)
    _write_phase2_config(tmp_path)
    now = utc_now()
    db_session.add(
        PaperPosition(
            symbol="KR011",
            strategy_tag="phase2",
            qty=3,
            avg_price=100.0,
            last_price=110.0,
            market_value=330.0,
            unrealized_pnl=30.0,
            updated_at=now,
        )
    )
    db_session.commit()
    service = PaperFillSimulatorService(db_session, config_dir=tmp_path)

    preview = service.check_risk_exit(
        symbol="KR011",
        strategy_tag="phase2",
        current_price=112.0,
        stop_price=95.0,
        trailing_high_price=120.0,
        trailing_stop_pct=8.0,
        confirm=False,
        idempotency_key=None,
    )
    triggered = service.check_risk_exit(
        symbol="KR011",
        strategy_tag="phase2",
        current_price=109.0,
        stop_price=95.0,
        trailing_high_price=120.0,
        trailing_stop_pct=8.0,
        confirm=True,
        idempotency_key="phase2-trailing-exit",
    )
    position = db_session.scalar(select(PaperPosition).where(PaperPosition.symbol == "KR011"))
    exit_order = db_session.scalar(select(PaperOrder).where(PaperOrder.symbol == "KR011", PaperOrder.side == "sell"))

    assert preview["status"] == "not_triggered"
    assert preview["fill_created"] is False
    assert triggered["ok"] is True
    assert triggered["status"] == "exit_filled"
    assert triggered["trigger"]["trailing_stop_triggered"] is True
    assert triggered["fill"]["fill_source"] == "local_trailing_stop"
    assert position is not None
    assert position.qty == 0
    assert position.realized_pnl == 27.0
    assert exit_order is not None
    assert exit_order.status == "filled"
    assert exit_order.live_order_created is False
    assert exit_order.network_call_performed is False
    assert _count(db_session, PaperFill) == 1
    assert _count(db_session, PaperAuditEvent) == 1
    assert _count(db_session, Order) == 0


def test_ma_cross_exit_creates_local_sell_fill(db_session, tmp_path, monkeypatch) -> None:
    _enable_phase2_runtime(monkeypatch)
    _write_phase2_config(tmp_path)
    db_session.add(
        PaperPosition(
            symbol="KR012",
            strategy_tag="phase2",
            qty=2,
            avg_price=100.0,
            last_price=104.0,
            market_value=208.0,
            unrealized_pnl=8.0,
            updated_at=utc_now(),
        )
    )
    db_session.commit()
    service = PaperFillSimulatorService(db_session, config_dir=tmp_path)

    not_triggered = service.check_risk_exit(
        symbol="KR012",
        strategy_tag="phase2",
        current_price=103.0,
        ma_fast_previous=105.0,
        ma_slow_previous=102.0,
        ma_fast_current=104.0,
        ma_slow_current=103.0,
        confirm=True,
        idempotency_key="phase2-ma-cross-noop",
    )
    triggered = service.check_risk_exit(
        symbol="KR012",
        strategy_tag="phase2",
        current_price=99.0,
        ma_fast_previous=105.0,
        ma_slow_previous=102.0,
        ma_fast_current=98.0,
        ma_slow_current=101.0,
        confirm=True,
        idempotency_key="phase2-ma-cross-exit",
    )
    position = db_session.scalar(select(PaperPosition).where(PaperPosition.symbol == "KR012"))
    exit_order = db_session.scalar(select(PaperOrder).where(PaperOrder.symbol == "KR012", PaperOrder.side == "sell"))

    assert not_triggered["status"] == "not_triggered"
    assert not_triggered["trigger"]["ma_cross_triggered"] is False
    assert triggered["ok"] is True
    assert triggered["status"] == "exit_filled"
    assert triggered["trigger"]["ma_cross_triggered"] is True
    assert triggered["fill"]["fill_source"] == "local_ma_cross_exit"
    assert triggered["exit_order"]["order_type"] == "ma_cross"
    assert position is not None
    assert position.qty == 0
    assert position.realized_pnl == -2.0
    assert exit_order is not None
    assert exit_order.network_call_performed is False
    assert _count(db_session, PaperFill) == 1
    assert _count(db_session, PaperAuditEvent) == 1
    assert _count(db_session, Order) == 0


def test_ma_cross_exit_requires_complete_ma_inputs(db_session, tmp_path, monkeypatch) -> None:
    _enable_phase2_runtime(monkeypatch)
    _write_phase2_config(tmp_path)
    service = PaperFillSimulatorService(db_session, config_dir=tmp_path)

    result = service.check_risk_exit(
        symbol="KR012",
        current_price=99.0,
        ma_fast_current=98.0,
        ma_slow_current=101.0,
        confirm=True,
        idempotency_key="phase2-incomplete-ma-cross",
    )

    assert result["status"] == "blocked"
    assert "INCOMPLETE_MA_CROSS_INPUT" in result["reason_codes"]
    assert result["fill_created"] is False
    assert _count(db_session, PaperFill) == 0
    assert _count(db_session, Order) == 0
