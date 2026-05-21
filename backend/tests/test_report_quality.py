from __future__ import annotations

from pathlib import Path

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


def test_latest_report_endpoint_payload(client):
    assert client.post("/api/data/seed").status_code == 200
    assert client.post("/api/indicators/recompute").status_code == 200
    assert client.post("/api/screener/run", json={}).status_code == 200
    assert client.post("/api/reports/daily").status_code == 200

    latest = client.get("/api/reports/latest")

    assert latest.status_code == 200
    assert latest.json()["markdown"].startswith("# Daily Market Report")
    assert latest.json()["report_id"].startswith("daily-")
