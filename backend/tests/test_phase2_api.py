from __future__ import annotations

from pathlib import Path

from backend.app.services.settings_service import SettingsService


def _prepare_full_flow(client) -> None:
    assert client.post("/api/data/seed").status_code == 200
    assert client.post("/api/indicators/recompute").status_code == 200
    assert client.post("/api/screener/run", json={}).status_code == 200
    assert client.post("/api/reports/daily").status_code == 200
    assert client.post("/api/backtest/run", json={"strategy_name": "trend_breakout"}).status_code == 200


def test_data_status_api_and_broker_preview_keep_orders_empty(client):
    _prepare_full_flow(client)

    before = client.get("/api/data/status")
    assert before.status_code == 200
    payload = before.json()
    for key in (
        "symbol_count",
        "daily_ohlcv_count",
        "index_ohlcv_count",
        "sector_ohlcv_count",
        "fundamentals_count",
        "indicator_snapshot_count",
        "screen_results_count",
        "reports_count",
        "backtest_runs_count",
        "orders_count",
        "latest_trade_date",
        "latest_indicator_date",
        "latest_screen_date",
    ):
        assert key in payload
    assert payload["orders_count"] == 0

    preview = client.post("/api/broker/orders/preview", json={"symbol": "KR009", "side": "buy", "qty": 10})
    assert preview.status_code == 200
    assert preview.json()["preview_only"] is True
    assert preview.json()["order_created"] is False
    assert preview.json()["can_submit"] is False
    assert preview.json()["token_issued"] is False
    assert preview.json()["network_call_performed"] is False

    after = client.get("/api/data/status")
    assert after.status_code == 200
    assert after.json()["orders_count"] == 0


def test_screener_results_filtering_sorting_and_limit(client):
    _prepare_full_flow(client)

    limited = client.get("/api/screener/results?limit=2")
    assert limited.status_code == 200
    assert len(limited.json()) == 2
    first = limited.json()[0]
    for key in (
        "trade_date",
        "symbol",
        "name",
        "strategy_name",
        "passed",
        "grade",
        "total_score",
        "entry_price",
        "stop_price",
        "target_price",
        "reward_risk_ratio",
        "position_size",
        "reason_summary",
        "pass_flags_json",
        "failed_conditions_json",
        "score_details_json",
        "risk_details_json",
        "triggered_conditions",
        "score_breakdown",
        "risk_flags",
        "data_quality_flags",
        "explanation",
        "rationale",
    ):
        assert key in first

    strategy = client.get("/api/screener/results?strategy_name=trend_breakout&limit=100")
    assert strategy.status_code == 200
    assert strategy.json()
    assert {row["strategy_name"] for row in strategy.json()} == {"trend_breakout"}

    passed = client.get("/api/screener/results?passed=true&limit=100")
    assert passed.status_code == 200
    assert all(row["passed"] is True for row in passed.json())

    grade = first["grade"]
    graded = client.get(f"/api/screener/results?grade={grade}&limit=100")
    assert graded.status_code == 200
    assert all(row["grade"] == grade for row in graded.json())

    searched = client.get("/api/screener/results?q=KR009&limit=100")
    assert searched.status_code == 200
    assert searched.json()
    assert all("KR009" in row["symbol"] or "KR009" in row["name"] for row in searched.json())

    asc = client.get("/api/screener/results?sort_by=total_score&sort_dir=asc&limit=5")
    assert asc.status_code == 200
    scores = [row["total_score"] for row in asc.json()]
    assert scores == sorted(scores)

    rr_desc = client.get("/api/screener/results?sort_by=reward_risk_ratio&sort_dir=desc&limit=5")
    assert rr_desc.status_code == 200
    rr_values = [row["reward_risk_ratio"] for row in rr_desc.json()]
    assert rr_values == sorted(rr_values, reverse=True)


def test_reports_list_detail_and_markdown_api(client):
    _prepare_full_flow(client)

    reports = client.get("/api/reports?limit=20")
    assert reports.status_code == 200
    assert reports.json()
    report = reports.json()[0]
    for key in (
        "id",
        "report_date",
        "report_type",
        "title",
        "model_version",
        "strategy_version",
        "data_timestamp",
        "created_at",
    ):
        assert key in report

    detail = client.get(f"/api/reports/{report['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == report["id"]
    assert detail.json()["markdown"].startswith("# Daily Market Report")

    markdown = client.get(f"/api/reports/{report['id']}/markdown")
    assert markdown.status_code == 200
    assert markdown.headers["content-type"].startswith("text/markdown")
    assert "charset=utf-8" in markdown.headers["content-type"].lower()
    assert f'report-{report["id"]}.md' in markdown.headers["content-disposition"]
    assert "# Daily Market Report" in markdown.text


def test_backtest_runs_list_and_detail_api(client):
    _prepare_full_flow(client)

    runs = client.get("/api/backtest/runs?limit=20")
    assert runs.status_code == 200
    assert runs.json()
    run = runs.json()[0]
    for metric in (
        "total_return",
        "cagr",
        "max_drawdown",
        "win_rate",
        "avg_win",
        "avg_loss",
        "profit_factor",
        "expectancy",
        "average_holding_days",
        "trade_count",
        "exposure",
    ):
        assert metric in run["metrics"]

    detail = client.get(f"/api/backtest/runs/{run['run_id']}")
    assert detail.status_code == 200
    assert detail.json()["run_id"] == run["run_id"]
    assert detail.json()["metrics"]["trade_count"] == run["metrics"]["trade_count"]


def test_settings_read_api_and_secret_key_redaction(client, tmp_path):
    response = client.get("/api/settings")
    assert response.status_code == 200
    assert {"strategies", "risk", "backtest", "app"}.issubset(response.json())

    for name in ("strategies", "risk", "backtest", "app"):
        (tmp_path / f"{name}.yaml").write_text("safe: 1\napi_key: abc\nnested:\n  token_value: xyz\n", encoding="utf-8")
    data = SettingsService(config_dir=Path(tmp_path)).read_settings()
    assert data["app"]["api_key"] == "***REDACTED***"
    assert data["risk"]["nested"]["token_value"] == "***REDACTED***"
