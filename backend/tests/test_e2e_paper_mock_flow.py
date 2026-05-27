from __future__ import annotations

import json
from datetime import date
from textwrap import dedent

from sqlalchemy import func, select

from backend.app.api import paper as paper_api
from backend.app.core.database import SessionLocal
from backend.app.models.tables import (
    NotificationDeliveryLog,
    NotificationEvent,
    Order,
    PaperFill,
    PaperOrder,
    PaperPortfolioSnapshot,
    PaperPosition,
    Report,
    utc_now,
)
from backend.app.services.notification_outbox_service import NotificationOutboxService
from backend.app.services.notification_service import NotificationService
from backend.app.services.paper_trading_service import PaperTradingService
from backend.app.services import report_service as report_service_module


def _write_paper_config(tmp_path) -> None:
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
              balance_inquiry_enabled: false
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
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _write_notification_config(tmp_path) -> None:
    tmp_path.joinpath("notifications.yaml").write_text(
        dedent(
            """
            notifications:
              enabled: true
              default_dry_run: false
              channels:
                telegram_main:
                  type: telegram
                  enabled: true
                  mode: mock
                  bot_token_env: TELEGRAM_BOT_TOKEN
                  chat_id_env: TELEGRAM_CHAT_ID
                  dry_run: false
                  parse_mode: null
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _patch_paper_api_config(monkeypatch, tmp_path) -> None:
    class ConfiguredPaperTradingService(PaperTradingService):
        def __init__(self, db=None, **kwargs):
            super().__init__(db, config_dir=tmp_path, **kwargs)

    monkeypatch.setattr(paper_api, "PaperTradingService", ConfiguredPaperTradingService)


def _seed_fill_position_snapshot(paper_order_id: str) -> None:
    now = utc_now()
    with SessionLocal() as db:
        order = db.scalar(select(PaperOrder).where(PaperOrder.paper_order_id == paper_order_id))
        assert order is not None
        order.status = "filled"
        order.filled_qty = order.qty
        order.remaining_qty = 0
        order.updated_ts = now
        db.add_all(
            [
                order,
                PaperFill(
                    paper_fill_id="phase11-fill-1",
                    paper_order_id=paper_order_id,
                    symbol=order.symbol,
                    side=order.side,
                    qty=order.qty,
                    price=order.limit_price or 100.0,
                    fill_ts=now,
                    fill_source="mock_poll",
                    commission=0.0,
                    slippage_bps=0.0,
                    live_order_created=False,
                    broker_order_created=False,
                    network_call_performed=False,
                ),
                PaperPosition(
                    symbol=order.symbol,
                    strategy_tag=order.strategy_tag,
                    qty=order.qty,
                    avg_price=order.limit_price or 100.0,
                    realized_pnl=0.0,
                    last_price=110.0,
                    market_value=order.qty * 110.0,
                    unrealized_pnl=order.qty * 10.0,
                    account_alias="paper-demo",
                    broker_synced_at=now,
                ),
                PaperPortfolioSnapshot(
                    snapshot_id="phase11-portfolio-snapshot",
                    snapshot_ts=now,
                    account_alias="paper-demo",
                    cash_balance=1000.0,
                    buying_power=900.0,
                    market_value=order.qty * 110.0,
                    total_equity=1000.0 + order.qty * 110.0,
                    unrealized_pnl=order.qty * 10.0,
                    realized_pnl=0.0,
                    metadata_json=json.dumps({"source": "phase11_mock"}, sort_keys=True),
                ),
            ]
        )
        db.commit()


def _create_report(tmp_path) -> str:
    report_id = "phase11-mock-report"
    path = tmp_path / f"{report_id}.md"
    path.write_text("# Daily Market Report\n\n- paper mock flow complete\n", encoding="utf-8")
    with SessionLocal() as db:
        db.add(
            Report(
                report_id=report_id,
                report_date=date(2026, 5, 27),
                report_type="daily",
                version="phase11",
                path=str(path),
            )
        )
        db.commit()
    return report_id


def _count(model) -> int:
    with SessionLocal() as db:
        return int(db.scalar(select(func.count()).select_from(model)) or 0)


def test_e2e_paper_mock_flow_is_local_non_live_and_report_notified(client, tmp_path, monkeypatch):
    for name in (
        "KIS_APP_KEY",
        "KIS_APP_SECRET",
        "KIS_ACCESS_TOKEN",
        "KIS_REFRESH_TOKEN",
        "KIS_ACCOUNT_NO",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "DISCORD_OPS_WEBHOOK_URL",
        "PAPER_TRADING_NETWORK_ENABLED",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRADING_CAN_CREATE", "true")
    monkeypatch.setenv("PAPER_TRADING_KILL_SWITCH", "false")
    _write_paper_config(tmp_path)
    _write_notification_config(tmp_path)
    _patch_paper_api_config(monkeypatch, tmp_path)
    monkeypatch.setattr(report_service_module, "REPORT_DIR", tmp_path)

    request_payload = {
        "symbol": "KR009",
        "side": "buy",
        "qty": 3,
        "limit_price": 100.0,
        "stop_price": 90.0,
        "strategy_tag": "phase11_e2e",
    }
    preview = client.post("/api/paper/orders/preview", json=request_payload)
    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["paper_order_created"] is False
    assert preview_payload["live_order_created"] is False
    assert preview_payload["broker_order_created"] is False
    assert preview_payload["network_call_performed"] is False
    assert _count(PaperOrder) == 0

    submit = client.post(
        "/api/paper/orders/submit",
        json={**request_payload, "confirm": True, "idempotency_key": "phase11-submit-1"},
    )
    assert submit.status_code == 200
    submit_payload = submit.json()
    assert submit_payload["ok"] is True
    assert submit_payload["status"] == "submitted"
    assert submit_payload["paper_only"] is True
    assert submit_payload["paper_order_created"] is True
    assert submit_payload["live_order_created"] is False
    assert submit_payload["broker_order_created"] is False
    assert submit_payload["network_call_performed"] is False

    paper_order_id = submit_payload["order"]["paper_order_id"]
    orders = client.get("/api/paper/orders")
    assert orders.status_code == 200
    assert orders.json()["orders"][0]["paper_order_id"] == paper_order_id

    _seed_fill_position_snapshot(paper_order_id)
    sync = client.post("/api/paper/sync", json={"scope": "all"})
    assert sync.status_code == 200
    sync_payload = sync.json()
    assert sync_payload["status"] == "sync_disabled"
    assert sync_payload["sync_performed"] is False
    assert sync_payload["network_call_performed"] is False

    fills = client.get("/api/paper/fills")
    positions = client.get("/api/paper/positions")
    portfolio = client.get("/api/paper/portfolio")
    assert fills.status_code == 200
    assert positions.status_code == 200
    assert portfolio.status_code == 200
    assert fills.json()["fills"][0]["paper_order_id"] == paper_order_id
    assert positions.json()["positions"][0]["symbol"] == "KR009"
    portfolio_payload = portfolio.json()
    assert portfolio_payload["snapshot"]["snapshot_id"] == "phase11-portfolio-snapshot"
    assert portfolio_payload["positions_summary"]["count"] == 1
    assert portfolio_payload["network_call_performed"] is False
    assert portfolio_payload["separation_contract"]["mixed"] is False
    assert portfolio_payload["kis_balance"]["secrets_redacted"] is True
    assert all(isinstance(value, bool) for value in portfolio_payload["kis_balance"]["credential_fields"].values())

    with SessionLocal() as db:
        outbox = NotificationOutboxService(
            db,
            notification_service=NotificationService(config_dir=tmp_path),
        )
        queued = outbox.enqueue_event(
            event_type="paper_order_filled",
            subject=paper_order_id,
            payload_summary={
                "paper_order_id": paper_order_id,
                "symbol": "KR009",
                "portfolio_snapshot": "phase11-portfolio-snapshot",
            },
        )
        dispatched = outbox.dispatch_pending()
    assert queued["status"] == "queued"
    assert dispatched["processed_count"] == 1
    assert dispatched["sent_count"] == 1
    assert dispatched["non_blocking"] is True

    report_id = _create_report(tmp_path)
    notify = client.post(f"/api/reports/{report_id}/notify", json={"mode": "summary", "dry_run": True})
    assert notify.status_code == 200, notify.text
    notify_payload = notify.json()
    assert notify_payload["ok"] is True
    assert notify_payload["report_id"] == report_id
    assert notify_payload["dry_run"] is True
    assert notify_payload["secrets_redacted"] is True
    assert notify_payload["portfolio_snapshot"]["snapshot_id"] == "phase11-portfolio-snapshot"
    assert notify_payload["portfolio_snapshot"]["network_call_performed"] is False

    serialized = json.dumps(
        {
            "submit": submit_payload,
            "fills": fills.json(),
            "positions": positions.json(),
            "portfolio": portfolio_payload,
            "notify": notify_payload,
        },
        ensure_ascii=False,
    )
    assert "KIS_APP_SECRET=" not in serialized
    assert "KIS_ACCESS_TOKEN=" not in serialized
    assert "KIS_REFRESH_TOKEN=" not in serialized
    assert "KIS_ACCOUNT_NO=" not in serialized
    assert _count(Order) == 0
    assert _count(PaperOrder) == 1
    assert _count(PaperFill) == 1
    assert _count(PaperPosition) == 1
    assert _count(PaperPortfolioSnapshot) == 1
    assert _count(NotificationEvent) == 2
    assert _count(NotificationDeliveryLog) == 2
