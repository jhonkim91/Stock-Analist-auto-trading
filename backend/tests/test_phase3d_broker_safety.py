from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.main import app
from backend.app.models.tables import Order, Position
from backend.app.services.broker_service import BrokerAuditService, BrokerService

SENSITIVE_FIELD_NAMES = {
    "app_key",
    "app_secret",
    "token",
    "access_token",
    "refresh_token",
    "approval_key",
    "account",
    "account_no",
    "cano",
    "hts_id",
    "password",
    "authorization",
    "headers",
    "raw_credentials",
}


def _orders_count() -> int:
    with SessionLocal() as db:
        return int(db.scalar(select(func.count()).select_from(Order)) or 0)


def _assert_safety_flags(payload: dict[str, object]) -> None:
    assert payload["mode"] == "paper"
    assert payload["preview_only"] is False
    assert payload["network_call_performed"] is False
    assert payload["adapter_selected"] is True
    assert payload["adapter_name"] == "kis_openapi"
    assert payload["adapter_capability_checked"] is True
    assert payload["adapter_order_call_performed"] is False
    assert payload["adapter_network_call_performed"] is False
    assert payload["audit_persistence_enabled"] is False
    assert "adapter_call_performed" not in payload


def test_broker_status_is_paper_only_and_settings_do_not_expose_secrets(client, monkeypatch):
    sentinel = "PHASE3D_SENTINEL_SECRET_VALUE"
    monkeypatch.setenv("KIS_APP_KEY", sentinel)
    monkeypatch.setenv("KIS_APP_SECRET", sentinel)

    status = client.get("/api/broker/status")
    settings = client.get("/api/settings")

    assert status.status_code == 200
    assert settings.status_code == 200
    status_payload = status.json()
    _assert_safety_flags(status_payload)
    assert status_payload["can_submit"] is False
    assert status_payload["broker_mode"] == "paper_kis"
    assert status_payload["paper_trading_enabled"] is True
    assert status_payload["live_trading_enabled"] is False
    assert status_payload["kill_switch"]["blocking"] is False
    assert "broker" in settings.json()

    serialized = json.dumps({"status": status_payload, "settings": settings.json()}, ensure_ascii=False)
    assert sentinel not in serialized


def test_broker_preview_guarantees_no_order_network_or_adapter_execution(client, monkeypatch):
    sentinel = "PHASE3D_SENTINEL_SECRET_VALUE"
    monkeypatch.setenv("KIS_APP_KEY", sentinel)
    monkeypatch.setenv("KIS_APP_SECRET", sentinel)
    before_orders = _orders_count()

    response = client.post(
        "/api/broker/orders/preview",
        json={"symbol": "KR009", "side": "buy", "qty": 10, "limit_price": 100.0, "stop_price": 90.0},
    )

    assert response.status_code == 200
    payload = response.json()
    _assert_safety_flags(payload)
    assert payload["can_submit"] is True
    assert payload["order_created"] is False
    assert payload["side"] == "buy"
    assert payload["risk_gate"]["decision"] == "allow"
    reason_codes = set(payload["risk_gate"]["reason_codes"])
    assert reason_codes == set()
    assert _orders_count() == before_orders == 0
    assert not Path(".cache/kis/token.json").exists()
    assert sentinel not in json.dumps(payload, ensure_ascii=False)


def test_broker_sell_preview_only_checks_existing_long_position(client):
    no_position = client.post("/api/broker/orders/preview", json={"symbol": "KR009", "side": "sell", "qty": 1})
    assert no_position.status_code == 200
    no_position_reasons = set(no_position.json()["risk_gate"]["reason_codes"])
    assert {"SELL_POSITION_NOT_FOUND", "SHORT_SELL_UNSUPPORTED"}.issubset(no_position_reasons)

    with SessionLocal() as db:
        db.add(
            Position(
                symbol="KR009",
                entry_ts=datetime.now(UTC),
                avg_price=100.0,
                qty=5,
                stop_price=90.0,
                strategy_tag="phase3d_test",
            )
        )
        db.commit()

    over_qty = client.post("/api/broker/orders/preview", json={"symbol": "KR009", "side": "sell", "qty": 6})
    assert over_qty.status_code == 200
    over_qty_reasons = set(over_qty.json()["risk_gate"]["reason_codes"])
    assert {"SELL_QTY_EXCEEDS_POSITION", "SHORT_SELL_UNSUPPORTED"}.issubset(over_qty_reasons)

    within_qty = client.post("/api/broker/orders/preview", json={"symbol": "KR009", "side": "sell", "qty": 3})
    assert within_qty.status_code == 200
    within_qty_reasons = set(within_qty.json()["risk_gate"]["reason_codes"])
    assert "SELL_POSITION_NOT_FOUND" not in within_qty_reasons
    assert "SELL_QTY_EXCEEDS_POSITION" not in within_qty_reasons
    assert "SHORT_SELL_UNSUPPORTED" not in within_qty_reasons
    assert within_qty_reasons == set()
    assert _orders_count() == 0


def test_kis_execution_routes_remain_unregistered_404(client):
    route_paths = {getattr(route, "path", "") for route in app.routes}
    assert not any(path.startswith("/api/kis/orders") for path in route_paths)
    assert not any(path.startswith("/api/kis/broker") for path in route_paths)
    assert not any(path.startswith("/api/kis/websocket") for path in route_paths)
    assert client.get("/api/kis/orders").status_code == 404
    assert client.post("/api/kis/orders/preview", json={"symbol": "005930"}).status_code == 404
    assert client.get("/api/kis/broker/status").status_code == 404
    assert client.get("/api/kis/websocket/status").status_code == 404


def test_broker_config_fail_closed_modes_and_source_mismatch(tmp_path):
    missing = BrokerService(config_dir=tmp_path).preview_order(symbol="KR009", side="buy", qty=1)
    assert "CONFIG_LOAD_FAILED" in missing["risk_gate"]["reason_codes"]
    assert missing["can_submit"] is False

    (tmp_path / "broker.yaml").write_text("broker: [not-a-dict]\n", encoding="utf-8")
    malformed = BrokerService(config_dir=tmp_path).preview_order(symbol="KR009", side="buy", qty=1)
    assert "CONFIG_PARSE_FAILED" in malformed["risk_gate"]["reason_codes"]
    assert malformed["can_submit"] is False

    (tmp_path / "broker.yaml").write_text(
        "broker:\n  mode: live\n  source_id: kis_openapi\nrisk_gate: {}\naudit: {}\n",
        encoding="utf-8",
    )
    unknown_mode = BrokerService(config_dir=tmp_path).preview_order(symbol="KR009", side="buy", qty=1)
    assert unknown_mode["mode"] == "disabled"
    assert "UNKNOWN_BROKER_MODE" in unknown_mode["risk_gate"]["reason_codes"]

    class MismatchedSourceService:
        def list_sources(self) -> list[dict[str, object]]:
            return [
                {
                    "source_id": "kis_openapi",
                    "provider_type": "external_market_data",
                    "provider_name": "yfinance",
                    "enabled": True,
                    "network_enabled": True,
                    "paper_trading_enabled": True,
                    "live_trading_enabled": False,
                }
            ]

    mismatched = BrokerService(source_service=MismatchedSourceService()).preview_order(symbol="KR009", side="buy", qty=1)
    assert mismatched["adapter_selected"] is False
    assert "PROVIDER_SOURCE_MISMATCH" in mismatched["risk_gate"]["reason_codes"]


def test_broker_audit_sanitize_removes_sensitive_values():
    sentinel = "PHASE3D_SENTINEL_SECRET_VALUE"
    sanitized = BrokerAuditService().sanitize(
        {
            "headers": {"Authorization": sentinel},
            "account_no": sentinel,
            "raw_credentials": sentinel,
            "safe_field": "ok",
        }
    )
    serialized = json.dumps(sanitized, ensure_ascii=False)
    assert sentinel not in serialized
    assert sanitized["safe_field"] == "ok"
    assert SENSITIVE_FIELD_NAMES.isdisjoint(serialized.lower().split('"'))
