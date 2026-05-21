from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.models.tables import Order


def test_full_backend_api_smoke_flow_asserts_core_fields(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["ok"] is True
    assert health.json()["service"] == "backend"

    seed = client.post("/api/data/seed")
    assert seed.status_code == 200
    seed_payload = seed.json()
    assert seed_payload["symbols"] >= 15
    assert seed_payload["daily_rows"] > 0
    assert seed_payload["fundamental_rows"] >= 30

    indicators = client.post("/api/indicators/recompute")
    assert indicators.status_code == 200
    indicator_payload = indicators.json()
    assert indicator_payload["rows"] > 0
    assert indicator_payload["start_date"]
    assert indicator_payload["end_date"]

    regime = client.get("/api/market/regime")
    assert regime.status_code == 200
    regime_payload = regime.json()
    assert regime_payload["regime"] in {"bull", "neutral", "bear"}
    assert regime_payload["market_score"] in {0.0, 0.5, 1.0}
    assert "weekly_sma30" in regime_payload

    instruments = client.get("/api/instruments")
    assert instruments.status_code == 200
    assert len(instruments.json()) >= 15
    assert {"symbol", "name", "market", "sector"}.issubset(instruments.json()[0])

    screen = client.post("/api/screener/run", json={})
    assert screen.status_code == 200
    screen_payload = screen.json()
    assert screen_payload["rows"] >= 45
    assert screen_payload["passed"] > 0

    results = client.get("/api/screener/results")
    assert results.status_code == 200
    result_payload = results.json()
    assert result_payload
    first_result = result_payload[0]
    assert isinstance(first_result["pass_flags"], dict)
    assert isinstance(first_result["failed_conditions"], list)
    assert first_result["reason_summary"]
    assert "total_score" in first_result
    assert "reward_risk_ratio" in first_result

    report = client.post("/api/reports/daily")
    assert report.status_code == 200
    report_path = Path(report.json()["path"])
    content = report_path.read_text(encoding="utf-8")
    for section in (
        "## Market Regime",
        "## Sector Rotation",
        "## Triggered Candidates",
        "## Rejected But Close",
        "## Portfolio Risk",
        "## Mock Orders For Review",
        "## Audit Trail",
        "data_timestamp",
        "model_version",
        "strategy_version",
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
        assert section in content

    backtest = client.post("/api/backtest/run", json={"strategy_name": "trend_breakout"})
    assert backtest.status_code == 200
    metrics = backtest.json()["metrics"]
    for metric in (
        "trade_count",
        "total_return",
        "cagr",
        "max_drawdown",
        "win_rate",
        "profit_factor",
        "expectancy",
        "average_holding_days",
        "total_estimated_cost",
    ):
        assert metric in metrics

    broker_status = client.get("/api/broker/status")
    assert broker_status.status_code == 200
    broker_payload = broker_status.json()
    assert broker_payload["mode"] in {"disabled", "safety_scaffold"}
    assert broker_payload["live_trading_enabled"] is False
    assert broker_payload["can_submit"] is False
    assert broker_payload["token_issued"] is False
    assert broker_payload["network_call_performed"] is False
    assert broker_payload["adapter_order_call_performed"] is False
    assert broker_payload["adapter_network_call_performed"] is False

    with SessionLocal() as db:
        before_orders = db.scalar(select(func.count()).select_from(Order))
    preview = client.post("/api/broker/orders/preview", json={"symbol": "KR009", "side": "buy", "qty": 10})
    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["preview_only"] is True
    assert preview_payload["order_created"] is False
    assert preview_payload["can_submit"] is False
    assert preview_payload["token_issued"] is False
    assert preview_payload["network_call_performed"] is False
    assert preview_payload["adapter_order_call_performed"] is False
    assert preview_payload["adapter_network_call_performed"] is False
    with SessionLocal() as db:
        after_orders = db.scalar(select(func.count()).select_from(Order))
    assert after_orders == before_orders


def test_cors_allows_local_frontend_origin(client):
    response = client.options(
        "/api/data/status",
        headers={
            "Origin": "http://127.0.0.1:3001",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3001"

    smoke_response = client.options(
        "/api/data/sources",
        headers={
            "Origin": "http://127.0.0.1:3010",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert smoke_response.status_code == 200
    assert smoke_response.headers["access-control-allow-origin"] == "http://127.0.0.1:3010"
