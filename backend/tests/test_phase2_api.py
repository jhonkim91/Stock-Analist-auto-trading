from __future__ import annotations

import json
import os
from pathlib import Path

from backend.app.services.settings_service import SettingsService


def test_data_status_api_and_broker_preview_keep_orders_empty(full_flow_client):
    client = full_flow_client

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
    broker_status = client.get("/api/broker/status")
    assert broker_status.status_code == 200
    assert preview.json()["preview_only"] is broker_status.json()["preview_only"]
    assert preview.json()["order_created"] is False
    assert isinstance(preview.json()["can_submit"], bool)
    assert preview.json()["token_issued"] is False
    assert preview.json()["network_call_performed"] is False

    after = client.get("/api/data/status")
    assert after.status_code == 200
    assert after.json()["orders_count"] == 0


def test_screener_results_filtering_sorting_and_limit(full_flow_client):
    client = full_flow_client

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
        "metadata",
        "risk_metadata",
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


def test_screener_results_return_execution_time_strategy_metadata(seeded_client):
    client = seeded_client

    run = client.post("/api/screener/run", json={"strategies": ["canslim_lite"]})
    assert run.status_code == 200
    assert run.json()["strategies"] == ["canslim_lite"]

    response = client.get("/api/screener/results?strategy_name=canslim_lite&q=KR009&limit=20")
    assert response.status_code == 200
    rows = response.json()
    assert rows
    first = next(row for row in rows if row["symbol"] == "KR009")

    assert first["metadata"]["fundamentals_available_asof"] is True
    assert first["metadata"]["data_quality_flags"]["fundamentals_available"] is True
    assert first["data_quality_flags"] == first["metadata"]["data_quality_flags"]
    assert first["score_breakdown"] == first["metadata"]["score_breakdown"]
    assert first["explanation"] == first["metadata"]["explanation"]


def test_reports_list_detail_and_markdown_api(full_flow_client):
    client = full_flow_client

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


def test_reports_api_supports_weekly_generation_filtering_and_markdown(client):
    assert client.post("/api/data/seed").status_code == 200
    assert client.post("/api/indicators/recompute").status_code == 200
    assert client.post("/api/screener/run", json={}).status_code == 200

    daily = client.post("/api/reports/daily")
    weekly = client.post("/api/reports/weekly")

    assert daily.status_code == 200
    assert weekly.status_code == 200
    daily_id = daily.json()["report_id"]
    weekly_payload = weekly.json()
    weekly_id = weekly_payload["report_id"]
    assert daily.json()["report_type"] == "daily"
    assert weekly.json()["report_type"] == "weekly"

    daily_reports = client.get("/api/reports?report_type=daily&limit=20")
    weekly_reports = client.get("/api/reports?report_type=weekly&limit=20")

    assert daily_reports.status_code == 200
    assert weekly_reports.status_code == 200
    assert {report["report_type"] for report in daily_reports.json()} == {"daily"}
    assert {report["report_type"] for report in weekly_reports.json()} == {"weekly"}
    assert daily_id in {report["id"] for report in daily_reports.json()}
    assert weekly_id in {report["id"] for report in weekly_reports.json()}

    daily_markdown = client.get(f"/api/reports/{daily_id}/markdown")
    weekly_markdown = client.get(f"/api/reports/{weekly_id}/markdown")

    assert daily_markdown.status_code == 200
    assert weekly_markdown.status_code == 200
    assert daily_markdown.text.startswith("# Daily Market Report")
    assert weekly_markdown.text.startswith("# Weekly Strategy Review")
    assert f'report-{daily_id}.md' in daily_markdown.headers["content-disposition"]
    assert f'report-{weekly_id}.md' in weekly_markdown.headers["content-disposition"]
    assert "- win_rate: not_available_in_current_mvp" in weekly_markdown.text
    assert "- realized_pnl: 0" not in weekly_markdown.text
    assert "## Factor/Filter Attribution" in weekly_markdown.text
    assert "- attribution_status: partial" in weekly_markdown.text
    assert "- attribution_reason: trade_ledger_unavailable" in weekly_markdown.text
    assert "realized_factor_pnl_attribution" not in weekly_markdown.text
    assert "realized_filter_pnl_attribution" not in weekly_markdown.text
    assert "| attribution_type | dimension | value | trade_count | pnl | win_rate | avg_return | joined_trade_count | unavailable_count | status |" in weekly_markdown.text
    assert "| screen_filter_failure |" in weekly_markdown.text
    assert "## Parameter Drift Check" in weekly_markdown.text
    assert "- parameter_snapshot_status: not_available_in_current_mvp" in weekly_markdown.text
    assert "- unavailable_reason: strategy_parameter_snapshot_not_found" in weekly_markdown.text
    assert "- parameter_snapshot_diff: not_available_in_current_mvp" not in weekly_markdown.text
    assert "- changed_keys: not_available_in_current_mvp" in weekly_markdown.text
    assert "- snapshot_dates: not_available_in_current_mvp" in weekly_markdown.text
    assert "- config_hash_diff: changed:0, unchanged:0, unavailable:" in weekly_markdown.text

    weekly_detail = client.get(f"/api/reports/{weekly_id}")
    assert weekly_detail.status_code == 200
    generated_drift = weekly_payload["metadata"]["parameter_drift"]
    detail_drift = weekly_detail.json()["metadata"]["parameter_drift"]
    assert detail_drift["parameter_snapshot_status"] == "not_available_in_current_mvp"
    assert detail_drift["unavailable_reason"] == "strategy_parameter_snapshot_not_found"
    assert detail_drift["changed_keys"] == "not_available_in_current_mvp"
    assert detail_drift["snapshot_dates"] == "not_available_in_current_mvp"
    assert detail_drift["config_hash_diff"] == generated_drift["config_hash_diff"]


def test_backtest_runs_list_and_detail_api(full_flow_client):
    client = full_flow_client

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
    assert detail.json()["trade_ledger_count"] == run["metrics"]["trade_count"]
    assert detail.json()["trade_ledger"]["table"] == "backtest_trade_ledger"

    trades = client.get(f"/api/backtest/runs/{run['run_id']}/trades")
    assert trades.status_code == 200
    assert len(trades.json()) == run["metrics"]["trade_count"]
    if trades.json():
        first_trade = trades.json()[0]
        assert {"run_id", "strategy_name", "symbol", "entry_date", "exit_date", "pnl", "return_pct"}.issubset(first_trade)


def test_strategy_summary_endpoint_shape_and_unspecified_baseline(full_flow_client):
    client = full_flow_client

    response = client.get("/api/backtest/strategy-summary?lookback_days=252")

    assert response.status_code == 200
    payload = response.json()
    assert payload["lookback_days"] == 252
    assert payload["baseline"]["status"] == "unspecified"
    assert payload["baseline"]["snapshot_supplied"] is False
    assert payload["window"]["available_trading_days"] <= 252
    assert payload["screener_window"]["available_trading_days"] <= 252
    assert payload["report"]["filename"] == "strategy_validation_252d.json"
    assert payload["report"]["kind"] == "strategy_validation_summary"
    assert Path(payload["report"]["path"]).exists()
    assert payload["validation_documentation_format"]["docs_file"] == "docs/VALIDATION.md"
    assert "unavailable_metrics" in payload["validation_documentation_format"]["required_fields"]
    assert payload["validation_framework"]["walk_forward"]["status"] == "calculated"
    assert payload["validation_framework"]["walk_forward"]["metric"] == "out_of_sample_summary"
    assert payload["validation_framework"]["walk_forward"]["calculated"] is True
    assert payload["validation_framework"]["walk_forward"]["calculated_strategy_count"] > 0
    pbo = payload["validation_framework"]["overfitting"]["pbo"]
    assert pbo["method"] == "walk_forward_leave_one_window_cscv_lite"
    assert pbo["input_shape"]["candidate_source"] == "strategy_validation.walk_forward.windows"
    if pbo["calculated"]:
        assert 0 <= pbo["value"] <= 1
    else:
        assert pbo["value"] == "not_available_in_current_mvp"
        assert pbo["reason"]
    dsr = payload["validation_framework"]["overfitting"]["deflated_sharpe_ratio"]
    assert dsr["method"] == "bailey_lopez_de_prado_deflated_sharpe_lite"
    assert dsr["input_shape"]["multiple_testing"]["candidate_source"] == "available_strategy_registry"
    assert dsr["input_shape"]["non_normal_adjustment"]["return_series_source"] == "walk_forward_window_total_return"
    if dsr["calculated"]:
        assert 0 <= dsr["value"] <= 1
    else:
        assert dsr["value"] == "not_available_in_current_mvp"
        assert dsr["reason"]
    attribution = payload["validation_framework"]["attribution"]
    assert attribution["value"] == "calculated"
    assert attribution["status"] in {"calculated", "partial"}
    assert attribution["basis"]["join_keys"]
    assert attribution["realized_pnl_attribution"]["rows"]
    assert attribution["screen_filter_failure_counts"]["rows"]
    assert attribution["unjoined_trade_count"] >= 0
    assert "orders" in payload["validation_framework"]["trade_ledger_schema"]["not_connected_to"]

    rows = payload["strategies"]
    assert rows
    first = rows[0]
    assert {"strategy_name", "screener", "backtest", "delta", "validation"}.issubset(first)
    assert {
        "evaluated_count",
        "pass_count",
        "pass_rate",
        "evaluated_trading_days",
        "window_trading_days",
    }.issubset(first["screener"])
    assert {"trade_count", "win_rate", "total_return", "max_drawdown"}.issubset(first["backtest"])
    assert first["delta"]["baseline"] == "unspecified"
    assert first["delta"]["trade_count_delta"] is None
    assert first["delta"]["win_rate_delta"] is None
    assert first["delta"]["total_return_delta"] is None
    assert first["delta"]["max_drawdown_delta"] is None
    assert first["backtest"]["pbo"] == "not_available_in_current_mvp"
    assert first["backtest"]["deflated_sharpe_ratio"] == "not_available_in_current_mvp"
    assert first["validation"]["walk_forward"]["metric"] == "out_of_sample_summary"
    assert first["validation"]["walk_forward"]["calculated"] is True
    assert first["validation"]["walk_forward"]["summary"]["oos_window_count"] >= 1
    assert first["validation"]["walk_forward"]["summary"]["oos_total_return"] is not None
    assert first["validation"]["overfitting"]["pbo"]["input_shape"]["performance_metric"] == "total_return"
    assert (
        "multiple_testing"
        in first["validation"]["overfitting"]["deflated_sharpe_ratio"]["input_shape"]
    )
    assert first["validation"]["attribution"]["realized_pnl_attribution"]["rows"]
    assert first["validation"]["attribution"]["screen_filter_failure_counts"]["rows"]

    artifact = json.loads(Path(payload["report"]["path"]).read_text(encoding="utf-8"))
    assert artifact["validation_framework"]["walk_forward"]["metric"] == "out_of_sample_summary"
    assert "overfitting" in artifact["validation_framework"]
    assert artifact["validation_framework"]["attribution"]["realized_pnl_attribution"]["rows"]
    assert artifact["strategies"][0]["validation"]["walk_forward"]["summary"]["oos_window_count"] >= 1

    status = client.get("/api/data/status")
    assert status.status_code == 200
    assert status.json()["orders_count"] == 0


def test_settings_read_api_and_secret_key_redaction(client, tmp_path):
    response = client.get("/api/settings")
    assert response.status_code == 200
    assert {"strategies", "risk", "backtest", "app"}.issubset(response.json())

    for name in ("strategies", "risk", "backtest", "app"):
        (tmp_path / f"{name}.yaml").write_text("safe: 1\napi_key: abc\nnested:\n  token_value: xyz\n", encoding="utf-8")
    data = SettingsService(config_dir=Path(tmp_path)).read_settings()
    assert data["app"]["redacted_field_0"] == "***REDACTED***"
    assert data["risk"]["nested"]["redacted_field_0"] == "***REDACTED***"
    assert "api_key" not in data["app"]
    assert "token_value" not in data["risk"]["nested"]


def test_runtime_env_toggle_is_process_only_and_allowlisted(client, monkeypatch):
    monkeypatch.delenv("PAPER_TRADING_ENABLED", raising=False)

    status = client.get("/api/settings/runtime-env")
    assert status.status_code == 200
    payload = status.json()
    assert payload["scope"] == "process"
    assert payload["persistence"] == "process_only"
    assert payload["file_write_performed"] is False
    assert payload["secrets_redacted"] is True
    names = {item["name"] for item in payload["toggles"]}
    assert "PAPER_TRADING_ENABLED" in names
    assert "KIS_APP_KEY" not in names

    blocked = client.post(
        "/api/settings/runtime-env/toggle",
        json={"name": "PAPER_TRADING_ENABLED", "enabled": True, "confirm": False},
    )
    assert blocked.status_code == 200
    assert blocked.json()["ok"] is False
    assert blocked.json()["reason_codes"] == ["ENV_TOGGLE_CONFIRM_REQUIRED"]
    assert "PAPER_TRADING_ENABLED" not in os.environ

    updated = client.post(
        "/api/settings/runtime-env/toggle",
        json={"name": "PAPER_TRADING_ENABLED", "enabled": True, "confirm": True},
    )
    assert updated.status_code == 200
    updated_payload = updated.json()
    assert updated_payload["ok"] is True
    assert updated_payload["enabled"] is True
    assert updated_payload["network_call_performed"] is False
    assert updated_payload["file_write_performed"] is False
    assert os.environ["PAPER_TRADING_ENABLED"] == "true"


def test_runtime_env_toggle_keeps_live_order_locked_false(client, monkeypatch):
    monkeypatch.setenv("ENABLE_REAL_ORDER", "false")

    status = client.get("/api/settings/runtime-env")
    live_toggle = next(item for item in status.json()["toggles"] if item["name"] == "ENABLE_REAL_ORDER")
    assert live_toggle["can_toggle"] is True
    assert "false로만 강제 적용" in live_toggle["description"]

    enabled = client.post(
        "/api/settings/runtime-env/toggle",
        json={"name": "ENABLE_REAL_ORDER", "enabled": True, "confirm": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["ok"] is True
    assert enabled.json()["status"] == "locked_false_applied"
    assert enabled.json()["enabled"] is False
    assert enabled.json()["reason_codes"] == ["LIVE_ENV_FORCED_FALSE"]
    assert os.environ["ENABLE_REAL_ORDER"] == "false"

    disabled = client.post(
        "/api/settings/runtime-env/toggle",
        json={"name": "ENABLE_REAL_ORDER", "enabled": False, "confirm": True},
    )
    assert disabled.status_code == 200
    assert disabled.json()["ok"] is True
    assert os.environ["ENABLE_REAL_ORDER"] == "false"


def test_runtime_env_preset_enables_paper_kis_gates_without_live_order(client, monkeypatch):
    for name in (
        "EXECUTION_MODE",
        "BROKER_MODE",
        "KIS_ENV",
        "ENABLE_REAL_ORDER",
        "PAPER_TRADING_ENABLED",
        "PAPER_TRADING_CAN_CREATE",
        "PAPER_TRADING_NETWORK_ENABLED",
        "PAPER_TRADING_KILL_SWITCH",
        "PAPER_ORDER_SUBMIT_ENABLED",
        "PAPER_SYNC_WORKER_ENABLED",
        "PAPER_SYNC_WORKER_MAX_ITERATIONS",
        "PAPER_SYNC_WORKER_MAX_ITERATIONS_CAP",
        "PAPER_BOT_CONFIRM",
        "PAPER_BOT_ENABLED",
        "PAPER_BOT_AUTO_SUBMIT",
        "PAPER_BOT_SCHEDULER_ENABLED",
        "PAPER_BOT_KILL_SWITCH",
    ):
        monkeypatch.delenv(name, raising=False)

    status = client.get("/api/settings/runtime-env")
    assert status.status_code == 200
    presets = {item["name"]: item for item in status.json()["presets"]}
    assert "paper_kis_ready" in presets
    assert "자동매매 ON" == presets["paper_bot_auto_on"]["label"]

    blocked = client.post(
        "/api/settings/runtime-env/preset",
        json={"name": "paper_bot_auto_on", "confirm": False},
    )
    assert blocked.status_code == 200
    assert blocked.json()["ok"] is False
    assert "ENV_PRESET_CONFIRM_REQUIRED" in blocked.json()["reason_codes"]

    applied = client.post(
        "/api/settings/runtime-env/preset",
        json={"name": "paper_bot_auto_on", "confirm": True},
    )
    payload = applied.json()

    assert applied.status_code == 200
    assert payload["ok"] is True
    assert payload["network_call_performed"] is False
    assert payload["live_order_created"] is False
    assert os.environ["EXECUTION_MODE"] == "paper_kis"
    assert os.environ["BROKER_MODE"] == "paper_kis"
    assert os.environ["KIS_ENV"] == "paper"
    assert os.environ["ENABLE_REAL_ORDER"] == "false"
    assert os.environ["PAPER_TRADING_ENABLED"] == "true"
    assert os.environ["PAPER_TRADING_CAN_CREATE"] == "true"
    assert os.environ["PAPER_TRADING_NETWORK_ENABLED"] == "true"
    assert os.environ["PAPER_TRADING_KILL_SWITCH"] == "false"
    assert os.environ["PAPER_ORDER_SUBMIT_ENABLED"] == "true"
    assert os.environ["PAPER_SYNC_WORKER_ENABLED"] == "true"
    assert os.environ["PAPER_SYNC_WORKER_MAX_ITERATIONS"] == "1"
    assert os.environ["PAPER_SYNC_WORKER_MAX_ITERATIONS_CAP"] == "10"
    assert os.environ["PAPER_BOT_CONFIRM"] == "true"
    assert os.environ["PAPER_BOT_ENABLED"] == "true"
    assert os.environ["PAPER_BOT_AUTO_SUBMIT"] == "true"
    assert os.environ["PAPER_BOT_SCHEDULER_ENABLED"] == "true"
    assert os.environ["PAPER_BOT_KILL_SWITCH"] == "false"
