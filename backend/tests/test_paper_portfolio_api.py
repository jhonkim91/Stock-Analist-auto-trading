from __future__ import annotations

import json

from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.models.tables import PaperFill, PaperPortfolioSnapshot, PaperPosition, Position, utc_now


def _seed_state() -> None:
    now = utc_now()
    with SessionLocal() as db:
        db.add_all(
            [
                PaperFill(
                    paper_fill_id="paper-api-fill",
                    paper_order_id="paper-api-order",
                    symbol="KR009",
                    side="buy",
                    qty=2,
                    price=100.0,
                    fill_ts=now,
                    fill_source="kis_paper_mirror",
                ),
                PaperPosition(
                    symbol="KR009",
                    strategy_tag="phase5-api",
                    qty=2,
                    avg_price=100.0,
                    last_price=120.0,
                    market_value=240.0,
                    unrealized_pnl=40.0,
                    account_alias="paper-demo",
                ),
                PaperPortfolioSnapshot(
                    snapshot_id="paper-api-snapshot",
                    snapshot_ts=now,
                    account_alias="paper-demo",
                    cash_balance=1000.0,
                    buying_power=900.0,
                    market_value=240.0,
                    total_equity=1240.0,
                    unrealized_pnl=40.0,
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
        db.commit()


def _position_count() -> int:
    with SessionLocal() as db:
        return int(db.scalar(select(func.count()).select_from(Position)) or 0)


def test_paper_fill_position_and_portfolio_apis_use_paper_tables_only(client):
    _seed_state()
    synthetic_count = _position_count()

    fills = client.get("/api/paper/fills")
    positions = client.get("/api/paper/positions")
    portfolio = client.get("/api/paper/portfolio")

    assert fills.status_code == 200
    assert fills.json()["source"] == "paper_fills"
    assert fills.json()["fills"][0]["symbol"] == "KR009"
    assert fills.json()["fills"][0]["network_call_performed"] is False

    assert positions.status_code == 200
    positions_payload = positions.json()
    assert positions_payload["source"] == "paper_positions"
    assert positions_payload["synthetic_positions_included"] is False
    assert [position["symbol"] for position in positions_payload["positions"]] == ["KR009"]

    assert portfolio.status_code == 200
    portfolio_payload = portfolio.json()
    assert portfolio_payload["snapshot"]["snapshot_id"] == "paper-api-snapshot"
    assert portfolio_payload["positions_summary"]["source"] == "paper_positions"
    assert portfolio_payload["positions_summary"]["count"] == 1
    assert portfolio_payload["positions_summary"]["market_value"] == 240.0
    assert portfolio_payload["separation_contract"]["synthetic_positions_table"] == "positions"
    assert portfolio_payload["separation_contract"]["paper_positions_table"] == "paper_positions"
    assert portfolio_payload["separation_contract"]["mixed"] is False
    assert "SYN001" not in json.dumps({"positions": positions_payload, "portfolio": portfolio_payload}, ensure_ascii=False)
    assert "PHASE5_ACCOUNT_SHOULD_NOT_LEAK" not in json.dumps(portfolio_payload, ensure_ascii=False)
    assert _position_count() == synthetic_count


def test_paper_sync_endpoint_is_fail_closed_idempotent_and_no_network(client):
    _seed_state()
    before = _position_count()

    first = client.post("/api/paper/sync", json={"scope": "all"})
    second = client.post("/api/paper/sync", json={"scope": "all"})
    fills_scope = client.post("/api/paper/sync", json={"scope": "fills"})

    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["status"] == "sync_blocked"
    assert first_payload["reason"] == "KIS_PAPER_CREDENTIALS_MISSING"
    assert first_payload["sync_performed"] is False
    assert first_payload["network_call_performed"] is False
    assert first_payload["live_order_created"] is False
    assert first_payload["broker_order_created"] is False
    assert first_payload["synthetic_positions_touched"] is False
    assert second.json()["counts"] == first_payload["counts"]
    assert fills_scope.json()["synced_scopes"] == ["fills"]
    assert _position_count() == before


def test_empty_paper_portfolio_is_explicit_without_synthetic_fallback(client):
    response = client.get("/api/paper/portfolio")

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot"] is None
    assert payload["positions_summary"]["source"] == "paper_positions"
    assert payload["positions_summary"]["count"] == 0
    assert payload["reason"] == "PAPER_PORTFOLIO_SNAPSHOT_NOT_FOUND"
