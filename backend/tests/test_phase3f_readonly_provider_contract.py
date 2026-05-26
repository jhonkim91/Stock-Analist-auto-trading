from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.main import app
from backend.app.models.tables import Order, PaperAuditEvent, PaperFill, PaperOrder, PaperPosition

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


def _execution_counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "orders": int(db.scalar(select(func.count()).select_from(Order)) or 0),
            "paper_orders": int(db.scalar(select(func.count()).select_from(PaperOrder)) or 0),
            "paper_fills": int(db.scalar(select(func.count()).select_from(PaperFill)) or 0),
            "paper_positions": int(db.scalar(select(func.count()).select_from(PaperPosition)) or 0),
            "paper_audit_events": int(db.scalar(select(func.count()).select_from(PaperAuditEvent)) or 0),
        }


def test_read_only_providers_expose_capabilities_fail_closed_and_redacted(client, monkeypatch):
    sentinel = "PHASE3F_SENTINEL_SECRET_VALUE"
    monkeypatch.setenv("KIS_APP_KEY", sentinel)
    monkeypatch.setenv("KIS_APP_SECRET", sentinel)

    response = client.get("/api/data/read-only/providers")

    assert response.status_code == 200
    providers = response.json()
    by_id = {provider["source_id"]: provider for provider in providers}
    assert {
        "external_yfinance",
        "kis_market_data",
        "krx_index_sector",
        "krx_symbol_master",
        "krx_trading_calendar",
        "krx_corporate_actions",
    }.issubset(by_id)

    kis = by_id["kis_market_data"]
    assert kis["provider_name"] == "kis"
    assert kis["asset_scope"] == ["daily_ohlcv"]
    assert "daily_ohlcv_preview" in kis["capabilities"]
    assert "daily_ohlcv_network_candidate" in kis["capabilities"]
    assert kis["enabled"] is False
    assert kis["network_enabled"] is False
    assert kis["read_only_enabled"] is False
    assert kis["status"] == "disabled"
    assert {"SOURCE_DISABLED", "READ_ONLY_DISABLED", "NETWORK_DISABLED_FAIL_CLOSED"}.issubset(kis["reason_codes"])

    krx_index = by_id["krx_index_sector"]
    assert krx_index["provider_name"] == "krx"
    assert krx_index["asset_scope"] == ["index_ohlcv", "sector_ohlcv"]
    assert {"index_daily_ohlcv_status", "sector_daily_ohlcv_status"}.issubset(set(krx_index["capabilities"]))

    for provider in providers:
        assert provider["network_call_performed"] is False
        assert provider["token_issued"] is False
        assert provider["token_cache_enabled"] is False
        assert provider["adapter_order_call_performed"] is False
        assert provider["adapter_network_call_performed"] is False
        assert provider["credential_fields_exposed"] is False
        assert SENSITIVE_FIELD_NAMES.isdisjoint(provider)

    serialized = json.dumps(providers, ensure_ascii=False)
    assert sentinel not in serialized
    assert "raw_credentials" not in serialized
    assert not Path(".cache/kis/token.json").exists()


def test_read_only_provider_contract_does_not_mutate_execution_tables_or_routes(client):
    client.post("/api/data/seed")
    before = _execution_counts()

    response = client.get("/api/data/read-only/providers")
    external = client.get("/api/data/external/providers")

    assert response.status_code == 200
    assert external.status_code == 200
    assert _execution_counts() == before == {
        "orders": 0,
        "paper_orders": 0,
        "paper_fills": 0,
        "paper_positions": 0,
        "paper_audit_events": 0,
    }

    external_source_ids = {provider["source_id"] for provider in external.json()}
    assert {"external_yfinance", "kis_market_data"}.issubset(external_source_ids)
    assert "krx_index_sector" not in external_source_ids
    assert "krx_symbol_master" not in external_source_ids

    route_paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/paper/orders" in route_paths
    assert "/api/paper/fill-simulator/run" not in route_paths
    assert client.post("/api/paper/orders", json={"symbol": "KR009"}).status_code == 405
    assert client.post("/api/paper/fill-simulator/run", json={}).status_code == 404
