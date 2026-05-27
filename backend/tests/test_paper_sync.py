from __future__ import annotations

from sqlalchemy import func, select

from backend.app.brokers.kis_paper import CONFIRMATION_REQUIRED, SYNC_CONFIRMATION_REQUIRED, KisPaperBrokerAdapter
from backend.app.models.tables import PaperFill, PaperOrder, PaperPortfolioSnapshot, PaperPosition, Position, utc_now
from backend.app.services.paper_sync_service import PaperSyncService


def _counts(db_session) -> dict[str, int]:
    return {
        "paper_orders": int(db_session.scalar(select(func.count()).select_from(PaperOrder)) or 0),
        "paper_fills": int(db_session.scalar(select(func.count()).select_from(PaperFill)) or 0),
        "paper_positions": int(db_session.scalar(select(func.count()).select_from(PaperPosition)) or 0),
        "paper_portfolio_snapshots": int(
            db_session.scalar(select(func.count()).select_from(PaperPortfolioSnapshot)) or 0
        ),
        "synthetic_positions": int(db_session.scalar(select(func.count()).select_from(Position)) or 0),
    }


def _seed_paper_and_synthetic_state(db_session) -> None:
    now = utc_now()
    db_session.add_all(
        [
            PaperOrder(
                paper_order_id="paper-phase5-order",
                symbol="KR009",
                side="buy",
                qty=3,
                filled_qty=3,
                remaining_qty=0,
                status="filled",
                idempotency_key="phase5-order",
                request_hash="phase5-hash",
                submitted_at=now,
            ),
            PaperFill(
                paper_fill_id="paper-phase5-fill",
                paper_order_id="paper-phase5-order",
                symbol="KR009",
                side="buy",
                qty=3,
                price=100.0,
                fill_ts=now,
                fill_source="kis_paper_mirror",
                broker_fill_id="paper-fill-1",
                broker_order_id="paper-order-1",
            ),
            PaperPosition(
                symbol="KR009",
                strategy_tag="phase5",
                qty=3,
                avg_price=100.0,
                last_price=110.0,
                market_value=330.0,
                unrealized_pnl=30.0,
                account_alias="paper-demo",
                broker_position_key="paper-position-1",
                broker_synced_at=now,
            ),
            PaperPortfolioSnapshot(
                snapshot_id="paper-phase5-snapshot",
                snapshot_ts=now,
                account_alias="paper-demo",
                cash_balance=1000.0,
                buying_power=900.0,
                market_value=330.0,
                total_equity=1330.0,
                unrealized_pnl=30.0,
                realized_pnl=0.0,
                metadata_json='{"raw_account_marker":"PHASE5_ACCOUNT_SHOULD_NOT_LEAK"}',
            ),
            Position(
                symbol="SYN001",
                entry_ts=now,
                avg_price=50.0,
                qty=99,
                stop_price=45.0,
                strategy_tag="synthetic-only",
            ),
        ]
    )
    db_session.commit()


def test_paper_sync_is_idempotent_disabled_noop_and_does_not_touch_synthetic_positions(db_session):
    _seed_paper_and_synthetic_state(db_session)
    service = PaperSyncService(db_session)
    before = _counts(db_session)

    first = service.sync(scope="all")
    second = service.sync(scope="all")
    positions = service.list_positions()
    portfolio = service.portfolio()

    assert first["status"] == "sync_disabled"
    assert first["reason"] == SYNC_CONFIRMATION_REQUIRED
    assert first["synced_scopes"] == ["orders", "fills", "positions", "portfolio"]
    assert first["dedupe"]["idempotent"] is True
    assert first["dedupe"]["fills_inserted"] == 0
    assert first["network_call_performed"] is False
    assert first["synthetic_positions_touched"] is False
    assert second["counts"] == first["counts"]
    assert _counts(db_session) == before
    assert positions["source"] == "paper_positions"
    assert positions["positions"][0]["symbol"] == "KR009"
    assert positions["synthetic_positions_included"] is False
    assert portfolio["separation_contract"]["mixed"] is False


def test_paper_sync_rejects_unknown_scope_without_mutation(db_session):
    _seed_paper_and_synthetic_state(db_session)
    service = PaperSyncService(db_session)
    before = _counts(db_session)

    result = service.sync(scope="unknown")

    assert result["status"] == "invalid_scope"
    assert result["sync_performed"] is False
    assert result["network_call_performed"] is False
    assert _counts(db_session) == before


def test_kis_paper_adapter_sync_and_cancel_remain_confirmation_required():
    adapter = KisPaperBrokerAdapter()

    listed = adapter.list_orders(status="open")
    cancelled = adapter.cancel_order(broker_order_id="paper-1", confirm=True)
    synced = adapter.sync(scope="all")

    assert listed["status"] == "query_blocked"
    assert CONFIRMATION_REQUIRED in listed["reason_codes"]
    assert listed["network_call_performed"] is False
    assert cancelled["status"] == "cancel_blocked"
    assert cancelled["network_call_performed"] is False
    assert synced["status"] == "sync_blocked"
    assert synced["sync_performed"] is False
    assert SYNC_CONFIRMATION_REQUIRED in synced["reason_codes"]
