from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy import select

from backend.app.core.database import SessionLocal
from backend.app.models.tables import (
    PaperAccountSnapshot,
    PaperBotDecision,
    PaperFill,
    PaperOrder,
    PaperPosition,
    utc_now,
)
from backend.app.services.report_service import ReportService
from backend.app.services.screener_service import ScreenerService


def _seed_dashboard_rows() -> None:
    with SessionLocal() as db:
        now = utc_now()
        db.add(
            PaperAccountSnapshot(
                snapshot_id="acct-phase6",
                snapshot_ts=now,
                account_alias="kis_paper",
                cash_balance=900000.0,
                buying_power=850000.0,
                market_value=100000.0,
                total_equity=1000000.0,
                realized_pnl=1200.0,
                unrealized_pnl=3400.0,
                source="kis_paper",
                status="snapshot",
                metadata_json="{}",
            )
        )
        db.add(
            PaperPosition(
                symbol="KR009",
                strategy_tag="trend_breakout",
                qty=10,
                avg_price=100.0,
                last_price=110.0,
                market_value=1100.0,
                realized_pnl=1200.0,
                unrealized_pnl=100.0,
                updated_at=now,
            )
        )
        db.add(
            PaperOrder(
                paper_order_id="paper-phase6-open",
                created_ts=now,
                updated_ts=now,
                symbol="KR009",
                side="buy",
                qty=10,
                filled_qty=2,
                remaining_qty=8,
                order_type="limit",
                limit_price=100.0,
                stop_price=94.0,
                status="submitted",
                idempotency_key="phase6-open",
                request_hash="hash",
                strategy_tag="trend_breakout",
                reason_codes_json="[]",
                risk_gate_json="{}",
            )
        )
        db.add(
            PaperFill(
                paper_fill_id="fill-phase6",
                paper_order_id="paper-phase6-open",
                symbol="KR009",
                side="buy",
                qty=2,
                price=100.0,
                fill_ts=now,
            )
        )
        db.add(
            PaperBotDecision(
                run_id="run-phase6",
                symbol="KR009",
                strategy_tag="trend_breakout",
                action="rejected",
                total_score=90.0,
                qty=10,
                limit_price=100.0,
                stop_price=94.0,
                target_price=118.0,
                risk_passed=False,
                reason_codes_json='["PAPER_REALTIME_STALE_QUOTE"]',
                paper_order_id=None,
            )
        )
        db.commit()


def test_paper_dashboard_api_contains_required_phase6_sections(client) -> None:
    _seed_dashboard_rows()

    response = client.get("/api/paper/dashboard")

    payload = response.json()
    assert response.status_code == 200
    assert {"account", "positions", "open_orders", "fills", "pnl", "risk", "worker_status", "metrics"}.issubset(
        payload
    )
    assert payload["account"]["available"] is True
    assert payload["positions"][0]["symbol"] == "KR009"
    assert payload["open_orders"][0]["paper_order_id"] == "paper-phase6-open"
    assert payload["fills"][0]["paper_fill_id"] == "fill-phase6"
    assert payload["pnl"]["realized_pnl"] == 1200.0
    assert payload["risk"]["reject_reason_counts"]["PAPER_REALTIME_STALE_QUOTE"] == 1
    assert payload["metrics"]["reject_count"] == 1
    assert "websocket_reconnect_count" in payload["worker_status"]["metrics"]


def test_daily_and_weekly_reports_include_paper_trading_section(seeded_db) -> None:
    ScreenerService(seeded_db).run()
    latest_screen_date = seeded_db.scalar(select(PaperOrder.created_ts).limit(1))
    assert latest_screen_date is None
    now = utc_now()
    seeded_db.add(
        PaperBotDecision(
            run_id="report-phase6",
            symbol="KR009",
            strategy_tag="trend_breakout",
            action="rejected",
            total_score=90.0,
            qty=10,
            limit_price=100.0,
            stop_price=94.0,
            target_price=118.0,
            risk_passed=False,
            reason_codes_json='["PAPER_REALTIME_STALE_QUOTE"]',
            created_at=now,
        )
    )
    seeded_db.commit()

    daily = ReportService(seeded_db).generate_daily_report()
    weekly = ReportService(seeded_db).generate_weekly_report()
    daily_content = Path(daily["path"]).read_text(encoding="utf-8")
    weekly_content = Path(weekly["path"]).read_text(encoding="utf-8")

    for content in (daily_content, weekly_content):
        assert "## Paper Trading" in content
        assert "- paper_order_count:" in content
        assert "- paper_fill_count:" in content
        assert "- paper_reject_reason:" in content
        assert "- paper_realized_pnl:" in content
        assert "- paper_unrealized_pnl:" in content
        assert "- paper_stale_data_event_count:" in content
        assert "- paper_risk_gate_block_count:" in content
