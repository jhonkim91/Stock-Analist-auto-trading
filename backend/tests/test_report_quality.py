from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from backend.app.models.tables import BacktestTradeLedger, ScreenResult
from backend.app.services.report_service import ReportService
from backend.app.services.screener_service import ScreenerService


def test_daily_report_markdown_contains_required_quality_fields(seeded_db):
    ScreenerService(seeded_db).run()
    result = ReportService(seeded_db).generate_daily_report()
    content = Path(result["path"]).read_text(encoding="utf-8")

    for section in (
        "## Market Regime",
        "## Sector Rotation",
        "## Triggered Candidates",
        "## Rejected But Close",
        "## Portfolio Risk",
        "## Mock Orders For Review",
        "## Audit Trail",
    ):
        assert section in content

    for audit_field in ("data_timestamp", "model_version", "strategy_version"):
        assert audit_field in content

    for candidate_field in (
        "total_score",
        "grade",
        "entry_price",
        "stop_price",
        "target_price",
        "risk_per_share",
        "reward_risk_ratio",
        "position_size",
        "reason_summary",
        "failed_conditions",
    ):
        assert candidate_field in content


def test_weekly_report_marks_trade_ledger_fields_unavailable(seeded_db):
    ScreenerService(seeded_db).run()
    result = ReportService(seeded_db).generate_weekly_report()
    content = Path(result["path"]).read_text(encoding="utf-8")

    assert result["report_type"] == "weekly"
    assert result["report_id"].startswith("weekly-")
    assert content.startswith("# Weekly Strategy Review")
    for section in (
        "## Performance Summary",
        "## Risk Summary",
        "## Hit Rate By Setup",
        "## Regime Diagnostics",
        "## Factor/Filter Attribution",
        "## Failed Trades Review",
        "## Parameter Drift Check",
        "## Audit Trail",
    ):
        assert section in content

    for unavailable_field in (
        "realized_trade_count",
        "realized_pnl",
        "win_rate",
        "regime_segment_return",
        "failed_trade_count",
    ):
        assert f"{unavailable_field}: not_available_in_current_mvp" in content

    assert "| setup | screened | screen_passed | screen_pass_rate | trade_hit_rate |" in content
    assert "| not_available_in_current_mvp |" in content
    assert "### Realized PnL Attribution" in content
    assert "### Screen Filter Failure Counts" in content
    assert (
        "| attribution_type | dimension | value | trade_count | pnl | win_rate | "
        "avg_return | joined_trade_count | unavailable_count | status |"
    ) in content
    assert "- parameter_snapshot_status: not_available_in_current_mvp" in content
    assert "- unavailable_reason: strategy_parameter_snapshot_not_found" in content
    assert "- parameter_snapshot_diff: not_available_in_current_mvp" not in content

    assert "- win_rate: 0" not in content
    assert "- realized_pnl: 0" not in content


def test_weekly_report_uses_trade_ledger_for_realized_metrics(seeded_db):
    ScreenerService(seeded_db).run()
    latest_screen_date = seeded_db.scalar(select(ScreenResult.trade_date).order_by(ScreenResult.trade_date.desc()))
    assert latest_screen_date is not None
    seeded_db.add_all(
        [
            BacktestTradeLedger(
                run_id="bt-weekly-ledger-fixture",
                trade_index=1,
                strategy_name="trend_breakout",
                symbol="KRWIN",
                side="long",
                status="closed",
                signal_date=latest_screen_date,
                entry_date=latest_screen_date,
                exit_date=latest_screen_date,
                qty=10,
                raw_entry_price=100.0,
                entry_price=100.0,
                raw_exit_price=110.0,
                exit_price=110.0,
                pnl=100.0,
                return_pct=0.10,
                estimated_cost=0.0,
                cost_bps=0.0,
                holding_days=3,
                exit_reason="target",
                risk_basis="fixture",
            ),
            BacktestTradeLedger(
                run_id="bt-weekly-ledger-fixture",
                trade_index=2,
                strategy_name="trend_breakout",
                symbol="KRLOSS",
                side="long",
                status="closed",
                signal_date=latest_screen_date,
                entry_date=latest_screen_date,
                exit_date=latest_screen_date,
                qty=10,
                raw_entry_price=100.0,
                entry_price=100.0,
                raw_exit_price=95.0,
                exit_price=95.0,
                pnl=-50.0,
                return_pct=-0.05,
                estimated_cost=0.0,
                cost_bps=0.0,
                holding_days=2,
                exit_reason="stop",
                risk_basis="fixture",
            ),
        ]
    )
    seeded_db.commit()

    result = ReportService(seeded_db).generate_weekly_report()
    content = Path(result["path"]).read_text(encoding="utf-8")

    assert "- realized_trade_count: 2" in content
    assert "- realized_pnl: 50.0" in content
    assert "- realized_return: 0.025" in content
    assert "- win_rate: 0.5" in content
    assert "- average_holding_days: 2.5" in content
    assert "- trade_ledger_source: backtest_trade_ledger" in content
    assert "| trend_breakout |" in content
    assert "- failed_trade_count: 1" in content
    assert "- loss_reason_breakdown: stop:1" in content
    assert "| KRLOSS | trend_breakout |" in content
    assert "### Realized PnL Attribution" in content
    assert (
        "| realized_pnl | strategy_name | trend_breakout | 2 | 50.0 | 0.5 | 0.025 |"
    ) in content
    assert "- parameter_snapshot_status: not_available_in_current_mvp" in content
    assert "- unavailable_reason: strategy_parameter_snapshot_not_found" in content
    assert "- parameter_snapshot_diff: not_available_in_current_mvp" not in content


def test_latest_report_endpoint_payload(client):
    assert client.post("/api/data/seed").status_code == 200
    assert client.post("/api/indicators/recompute").status_code == 200
    assert client.post("/api/screener/run", json={}).status_code == 200
    assert client.post("/api/reports/daily").status_code == 200

    latest = client.get("/api/reports/latest")

    assert latest.status_code == 200
    assert latest.json()["markdown"].startswith("# Daily Market Report")
    assert latest.json()["report_id"].startswith("daily-")
