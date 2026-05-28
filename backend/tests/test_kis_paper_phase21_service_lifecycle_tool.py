from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from backend.app.models.tables import PaperOrder
from backend.app.repositories.paper_repository import PaperRepository
from tools.kis_paper_phase12c_dry_run import CONFIRMATION_TOKEN, TRADING_WINDOW_CONFIRMATION_TOKEN
from tools.kis_paper_phase21_followup_sync import run_phase21_followup_sync
from tools.kis_paper_phase21_service_lifecycle import run_phase21_service_lifecycle


US_EASTERN = ZoneInfo("America/New_York")


class _RecordingSubmitAdapter:
    broker_order_id = "OVRS|900001|1|145.25|00|NASD|AAPL"

    def __init__(self) -> None:
        self.submits = []
        self.cancels = []

    def submit_order(self, request) -> dict[str, object]:
        self.submits.append(request)
        return {
            "ok": True,
            "status": "submitted",
            "broker_order_id": self.broker_order_id,
            "broker_order_status": "submitted",
            "network_call_performed": True,
            "broker_trace": {
                "endpoint_path": "/uapi/overseas-stock/v1/trading/order",
                "tr_id": "VTTT1002U",
                "secrets_redacted": True,
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

    def cancel_order(self, *, broker_order_id: str, confirm: bool = False) -> dict[str, object]:
        self.cancels.append({"broker_order_id": broker_order_id, "confirm": confirm})
        return {
            "ok": True,
            "status": "cancelled",
            "broker_order_status": "cancelled",
            "network_call_performed": True,
            "broker_trace": {
                "endpoint_path": "/uapi/overseas-stock/v1/trading/order-rvsecncl",
                "tr_id": "VTTT1004U",
                "secrets_redacted": True,
            },
        }


class _FilledLifecycleSyncAdapter:
    def sync(self, *, scope: str = "all") -> dict[str, object]:
        broker_order_id = _RecordingSubmitAdapter.broker_order_id
        return {
            "ok": True,
            "status": "sync_ok",
            "scope": scope,
            "sync_performed": True,
            "network_call_performed": True,
            "synthetic_positions_touched": False,
            "orders": [
                {
                    "broker_order_id": broker_order_id,
                    "symbol": "AAPL",
                    "side": "buy",
                    "qty": 1,
                    "filled_qty": 1,
                    "remaining_qty": 0,
                    "limit_price": 145.25,
                    "status": "filled",
                    "broker_order_status": "filled",
                }
            ],
            "fills": [
                {
                    "broker_fill_id": f"{broker_order_id}|fill|1",
                    "broker_order_id": broker_order_id,
                    "symbol": "AAPL",
                    "side": "buy",
                    "qty": 1,
                    "price": 145.25,
                }
            ],
            "positions": [
                {
                    "symbol": "AAPL",
                    "qty": 1,
                    "avg_price": 145.25,
                    "last_price": 146.0,
                    "market_value": 146.0,
                    "unrealized_pnl": 0.75,
                    "broker_position_key": "kis_paper_us|AAPL",
                }
            ],
            "portfolio": {
                "snapshot_id": "phase21-service-lifecycle",
                "cash_balance": 1000.0,
                "buying_power": 854.75,
                "market_value": 146.0,
                "total_equity": 1000.75,
                "unrealized_pnl": 0.75,
                "realized_pnl": 0.0,
                "status": "synced",
            },
            "broker_trace": {
                "operation": "sync",
                "endpoint_path": "/uapi/overseas-stock/v1/trading/inquire-ccnl",
                "tr_id": "VTTS3035R",
                "secrets_redacted": True,
            },
        }


class _EmptyLifecycleSyncAdapter:
    def sync(self, *, scope: str = "all") -> dict[str, object]:
        return {
            "ok": True,
            "status": "sync_ok",
            "scope": scope,
            "sync_performed": True,
            "network_call_performed": True,
            "synthetic_positions_touched": False,
            "orders": [],
            "fills": [],
            "positions": [],
            "portfolio": None,
            "broker_trace": {
                "operation": "sync",
                "endpoint_path": "/uapi/overseas-stock/v1/trading/inquire-ccnl",
                "tr_id": "VTTS3035R",
                "secrets_redacted": True,
            },
        }


def _enable_network_runtime(monkeypatch) -> None:
    monkeypatch.setenv("KIS_ENV", "paper")
    monkeypatch.setenv("BROKER_MODE", "paper_kis")
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRADING_CAN_CREATE", "true")
    monkeypatch.setenv("PAPER_TRADING_NETWORK_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRADING_KILL_SWITCH", "false")
    monkeypatch.setenv("PAPER_ORDER_SUBMIT_ENABLED", "true")
    monkeypatch.setenv("PAPER_BOT_CONFIRM", "true")
    monkeypatch.setenv("ENABLE_REAL_ORDER", "false")


def _run_regular_lifecycle(db_session, tmp_path, monkeypatch, *, submit_adapter, sync_adapter) -> dict[str, object]:
    _enable_network_runtime(monkeypatch)
    return run_phase21_service_lifecycle(
        symbol="AAPL",
        qty=1,
        limit_price=145.25,
        exchange="NASD",
        currency="USD",
        confirm_submit=CONFIRMATION_TOKEN,
        confirm_sync=CONFIRMATION_TOKEN,
        confirm_cancel=CONFIRMATION_TOKEN,
        confirm_trading_window=TRADING_WINDOW_CONFIRMATION_TOKEN,
        as_of=datetime(2026, 5, 28, 10, 0, tzinfo=US_EASTERN),
        session_factory=lambda: db_session,
        config_dir=tmp_path,
        submit_adapter=submit_adapter,
        sync_adapter=sync_adapter,
    )


def test_phase21_service_lifecycle_blocks_us_premarket_before_submit(db_session, tmp_path, monkeypatch) -> None:
    _enable_network_runtime(monkeypatch)
    submit_adapter = _RecordingSubmitAdapter()

    result = run_phase21_service_lifecycle(
        symbol="AAPL",
        qty=1,
        limit_price=145.25,
        exchange="NASD",
        currency="USD",
        confirm_submit=CONFIRMATION_TOKEN,
        confirm_sync=CONFIRMATION_TOKEN,
        confirm_cancel=CONFIRMATION_TOKEN,
        confirm_trading_window=TRADING_WINDOW_CONFIRMATION_TOKEN,
        as_of=datetime(2026, 5, 28, 8, 0, tzinfo=US_EASTERN),
        session_factory=lambda: db_session,
        config_dir=tmp_path,
        submit_adapter=submit_adapter,
        sync_adapter=_FilledLifecycleSyncAdapter(),
    )

    assert result["status"] == "trading_window_closed"
    assert result["network_call_performed"] is False
    assert result["completion_audit"]["complete"] is False
    assert "network_call_performed" in result["completion_audit"]["missing_requirements"]
    assert "paper_order_created" in result["completion_audit"]["missing_requirements"]
    assert result["reason_codes"] == ["US_REGULAR_SESSION_REQUIRED"]
    assert submit_adapter.submits == []
    assert PaperRepository(db_session).counts()["orders_count"] == 0


def test_phase21_service_lifecycle_persists_order_fill_and_position(
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    submit_adapter = _RecordingSubmitAdapter()

    result = _run_regular_lifecycle(
        db_session,
        tmp_path,
        monkeypatch,
        submit_adapter=submit_adapter,
        sync_adapter=_FilledLifecycleSyncAdapter(),
    )
    repository = PaperRepository(db_session)
    order = db_session.scalar(select(PaperOrder).where(PaperOrder.symbol == "AAPL"))
    serialized = json.dumps(result, ensure_ascii=False, sort_keys=True, default=str)

    assert result["status"] == "completed"
    assert result["network_call_performed"] is True
    assert result["lifecycle_evidence"]["paper_order_created"] is True
    assert result["lifecycle_evidence"]["broker_order_created"] is True
    assert result["lifecycle_evidence"]["paper_fill_created"] is True
    assert result["lifecycle_evidence"]["paper_position_changed"] is True
    assert result["lifecycle_evidence"]["orders_count_delta"] == 0
    assert result["completion_audit"]["complete"] is True
    assert result["completion_audit"]["requirements"]["paper_order_created"] is True
    assert result["completion_audit"]["requirements"]["paper_position_changed"] is True
    assert result["cancel_skipped"] is True
    assert submit_adapter.cancels == []
    assert order is not None
    assert order.status == "filled"
    assert repository.counts()["orders_count"] == 0
    assert "OVRS|900001" not in serialized


def test_phase21_service_lifecycle_cancels_when_sync_has_no_fill_or_position(
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    submit_adapter = _RecordingSubmitAdapter()

    result = _run_regular_lifecycle(
        db_session,
        tmp_path,
        monkeypatch,
        submit_adapter=submit_adapter,
        sync_adapter=_EmptyLifecycleSyncAdapter(),
    )
    order = db_session.scalar(select(PaperOrder).where(PaperOrder.symbol == "AAPL"))

    assert result["status"] == "submitted_sync_without_fill_or_position"
    assert result["reason_codes"] == ["FILL_OR_POSITION_NOT_OBSERVED"]
    assert result["cancel_attempted"] is True
    assert submit_adapter.cancels == [{"broker_order_id": _RecordingSubmitAdapter.broker_order_id, "confirm": True}]
    assert order is not None
    assert order.status == "cancelled"
    assert result["lifecycle_evidence"]["paper_fill_created"] is False
    assert result["lifecycle_evidence"]["paper_position_changed"] is False
    assert result["completion_audit"]["complete"] is False
    assert "paper_fill_created" in result["completion_audit"]["missing_requirements"]
    assert "paper_position_changed" in result["completion_audit"]["missing_requirements"]
    assert PaperRepository(db_session).counts()["orders_count"] == 0


def test_phase21_followup_sync_is_read_only_and_detects_fill_position(
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    _enable_network_runtime(monkeypatch)

    result = run_phase21_followup_sync(
        symbol="AAPL",
        exchange="NASD",
        currency="USD",
        confirm_sync=CONFIRMATION_TOKEN,
        session_factory=lambda: db_session,
        config_dir=tmp_path,
        sync_adapter=_FilledLifecycleSyncAdapter(),
    )
    repository = PaperRepository(db_session)

    assert result["status"] == "completed"
    assert result["submit_performed"] is False
    assert result["cancel_performed"] is False
    assert result["network_call_performed"] is True
    assert result["followup_evidence"]["paper_fill_present"] is True
    assert result["followup_evidence"]["paper_position_present"] is True
    assert result["completion_audit"]["complete"] is True
    assert result["completion_audit"]["requirements"]["submit_not_performed"] is True
    assert repository.counts()["orders_count"] == 0


def test_phase21_followup_sync_requires_confirmation(
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    _enable_network_runtime(monkeypatch)

    result = run_phase21_followup_sync(
        symbol="AAPL",
        exchange="NASD",
        currency="USD",
        session_factory=lambda: db_session,
        config_dir=tmp_path,
        sync_adapter=_FilledLifecycleSyncAdapter(),
    )

    assert result["status"] == "confirmation_required"
    assert result["network_call_performed"] is False
    assert result["completion_audit"]["complete"] is False
    assert "sync_completed" in result["completion_audit"]["missing_requirements"]
    assert PaperRepository(db_session).counts()["orders_count"] == 0
