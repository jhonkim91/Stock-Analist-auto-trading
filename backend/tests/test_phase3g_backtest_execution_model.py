from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.main import app
from backend.app.models.tables import Order, PaperAuditEvent, PaperFill, PaperOrder, PaperPosition

EXPECTED_METRIC_KEYS = {
    "trade_count",
    "trades",
    "win_rate",
    "total_return",
    "cagr",
    "max_drawdown",
    "profit_factor",
    "expectancy",
    "avg_win",
    "avg_loss",
    "average_holding_days",
    "exposure",
    "total_estimated_cost",
    "cost_bps",
    "partial_fill_count",
    "no_fill_count",
    "total_unfilled_qty",
    "adjusted_price_trade_count",
    "forced_exit_count",
    "delisted_exit_count",
    "missing_data_exit_count",
}

EXPECTED_TRADE_KEYS = {
    "symbol",
    "signal_date",
    "entry_date",
    "raw_entry_price",
    "entry_price",
    "exit_date",
    "raw_exit_price",
    "exit_price",
    "exit_reason",
    "qty",
    "pnl",
    "estimated_cost",
    "cost_bps",
    "return_pct",
    "holding_days",
    "price_detail",
}

EXPECTED_EXECUTION_DETAIL_KEYS = {
    "entry_assumption",
    "exit_assumption",
    "same_bar_stop_first",
    "stop_touched",
    "target_touched",
    "same_bar_both_touched",
    "gap_stop",
    "gap_target",
    "stop_price",
    "target_price",
    "commission_bps",
    "slippage_bps",
    "forced_exit",
    "delisted_exit",
    "missing_data_exit",
    "delisted_handling_policy",
    "missing_data_policy",
}

EXPECTED_LIQUIDITY_DETAIL_KEYS = {
    "planned_qty",
    "filled_qty",
    "unfilled_qty",
    "requested_notional",
    "liquidity_notional",
    "cap_notional",
    "fill_ratio",
    "max_participation_rate",
    "min_fill_ratio",
    "allow_partial_fill",
    "liquidity_basis",
    "position_size_cap_applied",
}

EXPECTED_PRICE_DETAIL_KEYS = {
    "use_adjusted_price",
    "entry_price_basis",
    "exit_price_basis",
    "entry_adjustment_factor",
    "exit_adjustment_factor",
    "entry_raw_close",
    "entry_adj_close",
    "exit_raw_close",
    "exit_adj_close",
}


def _execution_counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "orders": int(db.scalar(select(func.count()).select_from(Order)) or 0),
            "paper_orders": int(db.scalar(select(func.count()).select_from(PaperOrder)) or 0),
            "paper_fills": int(db.scalar(select(func.count()).select_from(PaperFill)) or 0),
            "paper_positions": int(db.scalar(select(func.count()).select_from(PaperPosition)) or 0),
            "paper_audit_events": int(db.scalar(select(func.count()).select_from(PaperAuditEvent)) or 0),
        }


def test_phase3g_backtest_api_contract_and_metrics_remain_backward_compatible(seeded_client):
    client = seeded_client

    run_response = client.post("/api/backtest/run", json={"strategy_name": "trend_breakout"})

    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert {"run_id", "strategy_name", "metrics", "trades"}.issubset(run_payload)
    assert EXPECTED_METRIC_KEYS.issubset(run_payload["metrics"])
    assert isinstance(run_payload["trades"], list)
    if run_payload["trades"]:
        first_trade = run_payload["trades"][0]
        assert EXPECTED_TRADE_KEYS.issubset(first_trade)
        assert EXPECTED_EXECUTION_DETAIL_KEYS.issubset(first_trade["execution_detail"])
        assert EXPECTED_LIQUIDITY_DETAIL_KEYS.issubset(first_trade["liquidity_detail"])
        assert EXPECTED_PRICE_DETAIL_KEYS.issubset(first_trade["price_detail"])
        assert first_trade["execution_detail"]["entry_assumption"] == "next_open"
        assert first_trade["qty"] == first_trade["liquidity_detail"]["filled_qty"]
        assert first_trade["liquidity_detail"]["planned_qty"] >= first_trade["liquidity_detail"]["filled_qty"]

    runs_response = client.get("/api/backtest/runs?limit=20")
    assert runs_response.status_code == 200
    runs_payload = runs_response.json()
    assert runs_payload
    latest_run = runs_payload[0]
    assert latest_run["run_id"] == run_payload["run_id"]
    assert EXPECTED_METRIC_KEYS.issubset(latest_run["metrics"])

    detail_response = client.get(f"/api/backtest/runs/{run_payload['run_id']}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["run_id"] == run_payload["run_id"]
    assert detail_payload["metrics"]["trade_count"] == run_payload["metrics"]["trade_count"]


def test_phase3g_backtest_keeps_execution_safety_invariants(seeded_client):
    client = seeded_client
    before = _execution_counts()

    response = client.post("/api/backtest/run", json={"strategy_name": "trend_breakout"})

    assert response.status_code == 200
    assert _execution_counts() == before == {
        "orders": 0,
        "paper_orders": 0,
        "paper_fills": 0,
        "paper_positions": 0,
        "paper_audit_events": 0,
    }

    route_paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/kis/orders/status" in route_paths
    assert "/api/kis/orders/preview" in route_paths
    assert "/api/kis/orders/submit" in route_paths
    assert not any(path.startswith("/api/kis/broker") for path in route_paths)
    assert not any(path.startswith("/api/kis/websocket") for path in route_paths)
    assert "/api/paper/orders" in route_paths
    assert "/api/paper/fill-simulator/run" in route_paths
    live_status = client.get("/api/kis/orders/status")
    preview = client.post("/api/kis/orders/preview", json={"symbol": "005930"})
    live_submit = client.post("/api/kis/orders/submit", json={"symbol": "005930"})
    assert live_status.status_code == 200
    assert preview.status_code == 200
    assert live_submit.status_code == 200
    assert live_status.json()["can_submit"] is False
    assert preview.json()["network_call_performed"] is False
    assert preview.json()["live_order_created"] is False
    assert live_submit.json()["network_call_performed"] is False
    assert live_submit.json()["live_order_created"] is False
    assert client.get("/api/kis/broker/status").status_code == 404
    assert client.get("/api/kis/websocket/status").status_code == 404
    submit = client.post("/api/paper/orders", json={"symbol": "005930", "side": "buy", "qty": 1})
    assert submit.status_code == 200
    assert submit.json()["paper_order_created"] is False
    assert submit.json()["network_call_performed"] is False
    assert client.post("/api/paper/fill-simulator/run", json={}).status_code == 422

    providers_response = client.get("/api/data/read-only/providers")
    assert providers_response.status_code == 200
    for provider in providers_response.json():
        assert provider["network_call_performed"] is False
        assert provider["token_issued"] is False
        assert provider["token_cache_enabled"] is False
        assert provider["adapter_order_call_performed"] is False
        assert provider["adapter_network_call_performed"] is False
    assert not Path(".cache/kis/token.json").exists()
