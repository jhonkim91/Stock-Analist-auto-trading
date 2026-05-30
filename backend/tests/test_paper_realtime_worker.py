from __future__ import annotations

from datetime import UTC, datetime, timedelta
from textwrap import dedent

from backend.app.services.paper_order_service import PaperOrderService
from backend.app.services.paper_trading_service import PaperTradingService
from backend.app.workers.realtime_market_worker import realtime_market_worker


def _write_realtime_paper_config(tmp_path) -> None:
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
              network_enabled: false
              live_order_enabled: false
              broker_order_enabled: false
            risk_gate:
              allow_buy_preview: true
              allow_sell_preview: true
              allow_short_sell: false
              max_order_qty: 1000000
              max_order_notional: 100000000
            audit:
              persistence_enabled: true
              sanitize_enabled: true
            simulator:
              enabled: false
              auto_fill_on_create: false
            broker_adapter:
              name: "kis_paper"
              enabled: false
              official_endpoint_confirmed: false
              official_balance_endpoint_confirmed: false
              balance_inquiry_enabled: false
              live_fallback_enabled: false
            realtime:
              enabled: true
              mode: "polling"
              require_fresh_quote_for_orders: true
              stale_quote_threshold_seconds: 5
              heartbeat_timeout_seconds: 60
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _enable_runtime(monkeypatch) -> None:
    monkeypatch.setenv("KIS_ENV", "paper")
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRADING_CAN_CREATE", "true")
    monkeypatch.setenv("PAPER_TRADING_KILL_SWITCH", "false")
    monkeypatch.setenv("PAPER_BOT_CONFIRM", "true")
    monkeypatch.setenv("PAPER_REALTIME_ENABLED", "true")
    monkeypatch.setenv("PAPER_REALTIME_REQUIRE_FRESH_QUOTES", "true")
    monkeypatch.setenv("ENABLE_REAL_ORDER", "false")


def test_realtime_stale_quote_blocks_new_order(db_session, tmp_path, monkeypatch) -> None:
    _enable_runtime(monkeypatch)
    _write_realtime_paper_config(tmp_path)
    symbol = "RT001"
    service = PaperOrderService(db_session, config_dir=tmp_path)

    missing_quote = service.submit_order(
        symbol=symbol,
        side="buy",
        qty=1,
        limit_price=100.0,
        confirm=True,
        idempotency_key="rt-missing-quote",
    )
    realtime_market_worker.quote_cache.update_quote(
        symbol=symbol,
        price=100.0,
        quote_ts=datetime.now(UTC) - timedelta(seconds=30),
        source="test",
    )
    stale_quote = service.submit_order(
        symbol=symbol,
        side="buy",
        qty=1,
        limit_price=100.0,
        confirm=True,
        idempotency_key="rt-stale-quote",
    )
    realtime_market_worker.quote_cache.update_quote(symbol=symbol, price=100.0, source="test")
    fresh_quote = service.submit_order(
        symbol=symbol,
        side="buy",
        qty=1,
        limit_price=100.0,
        confirm=True,
        idempotency_key="rt-fresh-quote",
    )

    assert "PAPER_REALTIME_STALE_QUOTE" in missing_quote["reason_codes"]
    assert "PAPER_REALTIME_STALE_QUOTE" in stale_quote["reason_codes"]
    assert fresh_quote["ok"] is True
    assert fresh_quote["paper_order_created"] is True


def test_realtime_status_and_account_api_are_registered(client) -> None:
    realtime = client.get("/api/paper/realtime/status")
    account = client.get("/api/paper/account")
    blocked_alias = client.post(
        "/api/paper/orders",
        json={"symbol": "RT002", "side": "buy", "qty": 1, "confirm": True, "idempotency_key": "rt-api-blocked"},
    )
    cancel_alias = client.post(
        "/api/paper/orders/paper-missing/cancel",
        json={"confirm": True, "idempotency_key": "rt-api-cancel"},
    )

    assert realtime.status_code == 200
    assert "quote_cache" in realtime.json()
    assert account.status_code == 200
    assert "account_snapshot" in account.json()
    assert blocked_alias.status_code == 200
    assert blocked_alias.json()["paper_order_created"] is False
    assert cancel_alias.status_code == 200
    assert cancel_alias.json()["order_cancelled"] is False
