from __future__ import annotations

import csv
from datetime import date
from io import StringIO

from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.models.tables import BacktestTradeLedger, Order, PaperAccountSnapshot, PaperPosition, utc_now


def _seed_paper_account_state() -> None:
    now = utc_now()
    with SessionLocal() as db:
        db.add_all(
            [
                PaperAccountSnapshot(
                    snapshot_id="phase1-account-snapshot",
                    snapshot_ts=now,
                    account_alias="paper-demo",
                    cash_balance=1000000.0,
                    buying_power=900000.0,
                    market_value=250000.0,
                    total_equity=1250000.0,
                    realized_pnl=12000.0,
                    unrealized_pnl=30000.0,
                    source="local_test",
                ),
                PaperPosition(
                    symbol="KR009",
                    strategy_tag="phase1-read-report",
                    qty=10,
                    avg_price=10000.0,
                    last_price=12500.0,
                    market_value=125000.0,
                    realized_pnl=1000.0,
                    unrealized_pnl=25000.0,
                    account_alias="paper-demo",
                    updated_at=now,
                ),
            ]
        )
        db.commit()


def _seed_backtest_journal_state() -> None:
    with SessionLocal() as db:
        db.add(
            BacktestTradeLedger(
                run_id="phase1-journal-run",
                trade_index=1,
                strategy_name="trend_breakout",
                symbol="KR009",
                side="long",
                status="closed",
                signal_date=date(2026, 5, 18),
                entry_date=date(2026, 5, 19),
                exit_date=date(2026, 5, 20),
                qty=3,
                raw_entry_price=10000.0,
                entry_price=10000.0,
                raw_exit_price=11000.0,
                exit_price=11000.0,
                pnl=3000.0,
                return_pct=0.1,
                estimated_cost=10.0,
                cost_bps=5.0,
                holding_days=1,
                exit_reason="target",
            )
        )
        db.commit()


def _orders_count() -> int:
    with SessionLocal() as db:
        return int(db.scalar(select(func.count()).select_from(Order)) or 0)


def test_market_realtime_search_detail_chart_and_rankings_are_read_only(full_flow_client):
    before_orders = _orders_count()

    search = full_flow_client.get("/api/market-realtime/search?q=KR009&limit=5")
    detail = full_flow_client.get("/api/market-realtime/symbols/KR009")
    chart = full_flow_client.get("/api/market-realtime/symbols/KR009/chart?limit=30")
    rankings = full_flow_client.get("/api/market-realtime/rankings?metric=total_score&limit=10")

    assert search.status_code == 200
    assert search.json()["network_call_performed"] is False
    assert search.json()["results"][0]["symbol"] == "KR009"

    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["symbol"]["symbol"] == "KR009"
    assert detail_payload["quote"]["available"] is True
    assert detail_payload["network_call_performed"] is False
    if detail_payload["fundamentals"] is not None:
        assert detail_payload["fundamentals"]["effective_date"] <= detail_payload["quote"]["trade_date"]

    assert chart.status_code == 200
    chart_payload = chart.json()
    assert chart_payload["symbol"] == "KR009"
    assert len(chart_payload["bars"]) == 30
    assert chart_payload["network_call_performed"] is False

    assert rankings.status_code == 200
    ranking_payload = rankings.json()
    assert ranking_payload["source"] == "screen_results"
    assert ranking_payload["items"]
    assert ranking_payload["items"][0]["rank"] == 1
    assert _orders_count() == before_orders


def test_account_report_and_holdings_use_paper_tables_without_network(full_flow_client):
    _seed_paper_account_state()
    before_orders = _orders_count()

    summary = full_flow_client.get("/api/account/summary")
    holdings = full_flow_client.get("/api/account/holdings")
    report = full_flow_client.get("/api/account/report")

    assert summary.status_code == 200
    assert summary.json()["source"] == "paper_account_snapshots"
    assert summary.json()["network_call_performed"] is False

    assert holdings.status_code == 200
    holdings_payload = holdings.json()
    assert holdings_payload["source"] == "paper_positions"
    assert holdings_payload["holdings"][0]["symbol"] == "KR009"
    assert holdings_payload["network_call_performed"] is False

    assert report.status_code == 200
    report_payload = report.json()
    assert report_payload["report_type"] == "account_portfolio"
    assert report_payload["separation_contract"]["mixed"] is False
    assert report_payload["live_order_created"] is False
    assert report_payload["network_call_performed"] is False
    assert _orders_count() == before_orders


def test_trade_journal_entries_and_csv_export_use_existing_ledgers(full_flow_client):
    _seed_backtest_journal_state()
    before_orders = _orders_count()

    entries = full_flow_client.get("/api/trade-journal/entries?source=backtest&limit=100")
    csv_response = full_flow_client.get("/api/trade-journal/csv?source=backtest&limit=100")

    assert entries.status_code == 200
    entries_payload = entries.json()
    assert entries_payload["source"] == "backtest"
    assert entries_payload["count"] > 0
    assert entries_payload["network_call_performed"] is False

    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    text = csv_response.content.decode("utf-8-sig")
    rows = list(csv.DictReader(StringIO(text)))
    assert rows
    assert rows[0]["source"] == "backtest"
    assert rows[0]["run_id"]
    assert _orders_count() == before_orders
