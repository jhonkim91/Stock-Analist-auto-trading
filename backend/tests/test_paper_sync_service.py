from __future__ import annotations

import json

from backend.app.models.tables import (
    BrokerAuditEvent,
    KisTokenStatusMetadata,
    PaperFill,
    PaperOrder,
    PaperPortfolioSnapshot,
    PaperPosition,
    Position,
    utc_now,
)
from backend.app.repositories.paper_repository import PaperRepository
from backend.app.services.paper_sync_service import SYNC_CONFIRMATION_REQUIRED, PaperSyncService


def _seed_phase5_state(db_session) -> None:
    now = utc_now()
    db_session.add_all(
        [
            PaperOrder(
                paper_order_id="paper-phase5-service-order",
                symbol="KR009",
                side="buy",
                qty=3,
                filled_qty=3,
                remaining_qty=0,
                status="filled",
                idempotency_key="phase5-service-order",
                request_hash="phase5-service-hash",
                submitted_at=now,
                broker_order_status="filled",
                account_alias="paper-demo",
                broker_status_json='{"status":"filled"}',
            ),
            PaperFill(
                paper_fill_id="paper-phase5-service-fill",
                paper_order_id="paper-phase5-service-order",
                symbol="KR009",
                side="buy",
                qty=3,
                price=100.0,
                fill_ts=now,
                fill_source="kis_paper_mirror",
                broker_fill_id="paper-fill-1",
                broker_order_id="paper-order-1",
                broker_status_json='{"status":"filled"}',
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
                broker_status_json='{"status":"synced"}',
            ),
            PaperPortfolioSnapshot(
                snapshot_id="paper-phase5-service-snapshot",
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
            BrokerAuditEvent(
                event_type="paper_sync",
                broker_name="kis_paper",
                broker_mode="paper",
                account_alias="paper-demo",
                paper_order_id="paper-phase5-service-order",
                decision="deny",
                reason_codes_json='["KIS_PAPER_SYNC_CONFIRMATION_REQUIRED"]',
                sanitized_payload_json='{"paper_order_id":"paper-phase5-service-order"}',
            ),
            KisTokenStatusMetadata(
                state="ISSUED_METADATA",
                app_key_configured=True,
                app_secret_configured=True,
                token_issued=True,
                token_cache_enabled=False,
                token_file_persistence_enabled=False,
                token_db_persistence_enabled=False,
                status_json='{"token_fingerprint":"fingerprint-only"}',
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


def test_paper_repository_lists_paper_state_and_counts_phase5_tables(db_session) -> None:
    _seed_phase5_state(db_session)
    repository = PaperRepository(db_session)

    counts = repository.counts()

    assert counts["paper_orders_count"] == 1
    assert counts["paper_fills_count"] == 1
    assert counts["paper_positions_count"] == 1
    assert counts["paper_portfolio_snapshots_count"] == 1
    assert counts["broker_audit_events_count"] == 1
    assert counts["kis_token_status_metadata_count"] == 1
    assert counts["orders_count"] == 0
    assert counts["synthetic_positions_count"] == 1
    assert repository.list_orders(status="filled")[0].paper_order_id == "paper-phase5-service-order"
    assert repository.list_fills(symbol="KR009")[0].paper_fill_id == "paper-phase5-service-fill"
    assert repository.list_positions(symbol="KR009")[0].symbol == "KR009"
    assert repository.list_positions(symbol="SYN001") == []
    assert repository.latest_portfolio_snapshot().snapshot_id == "paper-phase5-service-snapshot"


def test_paper_sync_service_payloads_are_consistent_and_secret_free(db_session) -> None:
    _seed_phase5_state(db_session)
    service = PaperSyncService(db_session)

    fills = service.list_fills(symbol="KR009")
    positions = service.list_positions(symbol="KR009")
    portfolio = service.portfolio()
    payload_text = json.dumps({"fills": fills, "positions": positions, "portfolio": portfolio}, ensure_ascii=False)

    assert fills["source"] == "paper_fills"
    assert fills["fills"][0]["paper_fill_id"] == "paper-phase5-service-fill"
    assert positions["source"] == "paper_positions"
    assert positions["positions"][0]["symbol"] == "KR009"
    assert positions["synthetic_positions_included"] is False
    assert portfolio["source"] == "paper_portfolio_snapshots"
    assert portfolio["snapshot"]["snapshot_id"] == "paper-phase5-service-snapshot"
    assert portfolio["positions_summary"]["count"] == 1
    assert portfolio["positions_summary"]["market_value"] == 330.0
    assert portfolio["counts"]["broker_audit_events_count"] == 1
    assert portfolio["counts"]["kis_token_status_metadata_count"] == 1
    assert portfolio["separation_contract"]["mixed"] is False
    assert portfolio["kis_balance"]["secrets_redacted"] is True
    assert "SYN001" not in payload_text
    assert "PHASE5_ACCOUNT_SHOULD_NOT_LEAK" not in payload_text
    assert "raw_account_marker" not in payload_text


def test_paper_sync_service_is_idempotent_disabled_noop(db_session) -> None:
    _seed_phase5_state(db_session)
    service = PaperSyncService(db_session)
    before = PaperRepository(db_session).counts()

    first = service.sync(scope="all")
    second = service.sync(scope="fills")
    invalid = service.sync(scope="unknown")
    after = PaperRepository(db_session).counts()

    assert first["status"] == "sync_disabled"
    assert first["reason"] == SYNC_CONFIRMATION_REQUIRED
    assert first["sync_performed"] is False
    assert first["network_call_performed"] is False
    assert first["live_order_created"] is False
    assert first["broker_order_created"] is False
    assert first["synthetic_positions_touched"] is False
    assert first["synced_scopes"] == ["orders", "fills", "positions", "portfolio"]
    assert second["synced_scopes"] == ["fills"]
    assert invalid["status"] == "invalid_scope"
    assert invalid["sync_performed"] is False
    assert after == before
