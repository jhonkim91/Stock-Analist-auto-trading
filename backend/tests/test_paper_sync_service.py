from __future__ import annotations

import json
from textwrap import dedent

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
from backend.app.services.paper_order_service import PaperOrderService
from backend.app.services.paper_sync_service import SYNC_CONFIRMATION_REQUIRED, PaperSyncService


class _FakeSyncAdapter:
    def sync(self, *, scope: str = "all") -> dict[str, object]:
        return {
            "ok": True,
            "status": "sync_ok",
            "scope": scope,
            "sync_performed": True,
            "network_call_performed": True,
            "synthetic_positions_touched": False,
            "orders": [
                {
                    "broker_order_id": "001|000001|2|70000|00|KRX",
                    "symbol": "005930",
                    "side": "buy",
                    "qty": 2,
                    "filled_qty": 1,
                    "remaining_qty": 1,
                    "limit_price": 70000.0,
                    "status": "submitted",
                    "broker_order_status": "submitted",
                }
            ],
            "fills": [
                {
                    "broker_fill_id": "001|000001|fill",
                    "broker_order_id": "001|000001|2|70000|00|KRX",
                    "symbol": "005930",
                    "side": "buy",
                    "qty": 1,
                    "price": 70000.0,
                }
            ],
            "positions": [
                {
                    "symbol": "005930",
                    "qty": 2,
                    "avg_price": 70000.0,
                    "last_price": 71000.0,
                    "market_value": 142000.0,
                    "unrealized_pnl": 2000.0,
                    "broker_position_key": "kis_paper|005930",
                }
            ],
            "portfolio": {
                "snapshot_id": "kis-paper-sync-test",
                "cash_balance": 100000.0,
                "buying_power": 100000.0,
                "market_value": 142000.0,
                "total_equity": 242000.0,
                "unrealized_pnl": 2000.0,
                "realized_pnl": 0.0,
                "status": "synced",
            },
            "broker_trace": {
                "operation": "sync",
                "endpoint_path": "/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
                "tr_id": "VTTC0081R",
                "secrets_redacted": True,
            },
        }


class _BrokerLifecycleSubmitAdapter:
    broker_order_id = "OVRS|900001|1|145.25|00|NASD|AAPL"

    def submit_order(self, request) -> dict[str, object]:
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


class _BrokerLifecycleSyncAdapter:
    def sync(self, *, scope: str = "all") -> dict[str, object]:
        broker_order_id = _BrokerLifecycleSubmitAdapter.broker_order_id
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
                "snapshot_id": "kis-paper-us-lifecycle-sync",
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
    monkeypatch.setenv("KIS_ENV", "paper")
    monkeypatch.setenv("BROKER_MODE", "paper_kis")
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRADING_CAN_CREATE", "true")
    monkeypatch.setenv("PAPER_TRADING_NETWORK_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRADING_KILL_SWITCH", "false")
    monkeypatch.setenv("PAPER_ORDER_SUBMIT_ENABLED", "true")
    monkeypatch.setenv("PAPER_BOT_CONFIRM", "true")
    monkeypatch.setenv("ENABLE_REAL_ORDER", "false")
    monkeypatch.setenv("PAPER_TRADING_MARKET", "US")
    monkeypatch.setenv("KIS_OVERSEAS_EXCHANGE_CODE", "NASD")
    monkeypatch.setenv("KIS_OVERSEAS_CURRENCY", "USD")


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


def test_paper_sync_service_persists_mock_adapter_payload_to_paper_tables(
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    _enable_network_runtime(monkeypatch)
    _write_network_paper_config(tmp_path)
    service = PaperSyncService(db_session, config_dir=tmp_path, adapter=_FakeSyncAdapter())

    result = service.sync(scope="all")
    counts = PaperRepository(db_session).counts()
    fills = service.list_fills(symbol="005930")
    positions = service.list_positions(symbol="005930")
    portfolio = service.portfolio()
    serialized = json.dumps({"result": result, "fills": fills, "positions": positions, "portfolio": portfolio}, ensure_ascii=False)

    assert result["status"] == "sync_ok"
    assert result["sync_performed"] is True
    assert result["network_call_performed"] is True
    assert result["synthetic_positions_touched"] is False
    assert result["dedupe"]["orders_inserted"] == 1
    assert result["dedupe"]["fills_inserted"] == 1
    assert result["dedupe"]["positions_upserted"] == 1
    assert result["dedupe"]["portfolio_snapshots_inserted"] == 1
    assert counts["orders_count"] == 0
    assert counts["synthetic_positions_count"] == 0
    assert fills["fills"][0]["broker_order_id"] == "001|000001|2|70000|00|KRX"
    assert positions["positions"][0]["broker_position_key"] == "kis_paper|005930"
    assert portfolio["snapshot"]["snapshot_id"] == "kis-paper-sync-test"
    assert "KIS_APP_SECRET" not in serialized
    assert "KIS_ACCESS_TOKEN" not in serialized


def test_broker_submit_then_sync_attaches_fill_to_existing_paper_order(
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    _enable_network_runtime(monkeypatch)
    _write_network_paper_config(tmp_path)
    order_service = PaperOrderService(
        db_session,
        config_dir=tmp_path,
        adapter=_BrokerLifecycleSubmitAdapter(),
    )

    submitted = order_service.submit_order(
        symbol="AAPL",
        side="buy",
        qty=1,
        limit_price=145.25,
        strategy_tag="phase21-us",
        confirm=True,
        idempotency_key="phase21-us-lifecycle",
    )
    sync_service = PaperSyncService(db_session, config_dir=tmp_path, adapter=_BrokerLifecycleSyncAdapter())
    synced = sync_service.sync(scope="all")
    repository = PaperRepository(db_session)
    order = db_session.get(PaperOrder, submitted["order"]["paper_order_id"])
    fill = repository.list_fills(symbol="AAPL")[0]
    position = repository.list_positions(symbol="AAPL")[0]

    assert submitted["ok"] is True
    assert submitted["broker_order_created"] is True
    assert submitted["network_call_performed"] is True
    assert synced["ok"] is True
    assert synced["dedupe"]["orders_inserted"] == 0
    assert synced["dedupe"]["fills_inserted"] == 1
    assert synced["dedupe"]["positions_upserted"] == 1
    assert order is not None
    assert order.broker_order_id == _BrokerLifecycleSubmitAdapter.broker_order_id
    assert order.status == "filled"
    assert order.filled_qty == 1
    assert order.remaining_qty == 0
    assert fill.paper_order_id == submitted["order"]["paper_order_id"]
    assert fill.broker_order_id == _BrokerLifecycleSubmitAdapter.broker_order_id
    assert position.broker_position_key == "kis_paper_us|AAPL"
    assert repository.counts()["orders_count"] == 0
