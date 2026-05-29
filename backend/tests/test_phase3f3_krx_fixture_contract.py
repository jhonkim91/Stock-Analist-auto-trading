from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.main import app
from backend.app.models.tables import (
    CorporateAction,
    IndexOhlcv,
    Order,
    PaperAuditEvent,
    PaperFill,
    PaperOrder,
    PaperPosition,
    SectorOhlcv,
    SymbolMaster,
    TradingCalendar,
)
from backend.app.services.data_providers import (
    KRX_CORPORATE_ACTION_FIXTURE_FIELDS,
    KRX_INDEX_SECTOR_FIXTURE_FIELDS,
    KRX_SYMBOL_MASTER_FIXTURE_FIELDS,
    KRX_TRADING_CALENDAR_FIXTURE_FIELDS,
    normalize_krx_corporate_action_rows,
    normalize_krx_index_rows,
    normalize_krx_sector_rows,
    normalize_krx_symbol_master_rows,
    normalize_krx_trading_calendar_rows,
    validate_krx_corporate_action_fixture,
    validate_krx_index_sector_fixture,
    validate_krx_symbol_master_fixture,
    validate_krx_trading_calendar_fixture,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURES = {
    "index_sector": FIXTURE_DIR / "krx_index_sector_reference.json",
    "symbol_master": FIXTURE_DIR / "krx_symbol_master_reference.json",
    "trading_calendar": FIXTURE_DIR / "krx_trading_calendar_reference.json",
    "corporate_actions": FIXTURE_DIR / "krx_corporate_actions_reference.json",
}
SENSITIVE_FIELD_NAMES = {
    "app_key",
    "app_secret",
    "secret",
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
EXPECTED_PROVIDER_FIELDS = {
    "source_id",
    "provider_type",
    "provider_name",
    "asset_scope",
    "capabilities",
    "enabled",
    "network_enabled",
    "read_only_enabled",
    "manual_preview_only",
    "requires_api_key",
    "supported_markets",
    "market",
    "venue",
    "status",
    "blocked_reason",
    "reason_codes",
    "network_call_performed",
    "token_issued",
    "token_cache_enabled",
    "adapter_order_call_performed",
    "adapter_network_call_performed",
    "credential_fields_exposed",
}


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads(FIXTURES[name].read_text(encoding="utf-8"))


def _walk_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(str(key).lower())
            keys.update(_walk_keys(nested))
    elif isinstance(value, list):
        for item in value:
            keys.update(_walk_keys(item))
    return keys


def _row_counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "symbol_master": int(db.scalar(select(func.count()).select_from(SymbolMaster)) or 0),
            "index_ohlcv": int(db.scalar(select(func.count()).select_from(IndexOhlcv)) or 0),
            "sector_ohlcv": int(db.scalar(select(func.count()).select_from(SectorOhlcv)) or 0),
            "trading_calendar": int(db.scalar(select(func.count()).select_from(TradingCalendar)) or 0),
            "corporate_actions": int(db.scalar(select(func.count()).select_from(CorporateAction)) or 0),
            "orders": int(db.scalar(select(func.count()).select_from(Order)) or 0),
            "paper_orders": int(db.scalar(select(func.count()).select_from(PaperOrder)) or 0),
            "paper_fills": int(db.scalar(select(func.count()).select_from(PaperFill)) or 0),
            "paper_positions": int(db.scalar(select(func.count()).select_from(PaperPosition)) or 0),
            "paper_audit_events": int(db.scalar(select(func.count()).select_from(PaperAuditEvent)) or 0),
        }


def test_krx_fixture_top_level_schema_and_sensitive_fields_absent():
    fixtures = {name: _load_fixture(name) for name in FIXTURES}

    assert set(fixtures["index_sector"]) == set(KRX_INDEX_SECTOR_FIXTURE_FIELDS)
    assert set(fixtures["symbol_master"]) == set(KRX_SYMBOL_MASTER_FIXTURE_FIELDS)
    assert set(fixtures["trading_calendar"]) == set(KRX_TRADING_CALENDAR_FIXTURE_FIELDS)
    assert set(fixtures["corporate_actions"]) == set(KRX_CORPORATE_ACTION_FIXTURE_FIELDS)
    assert validate_krx_index_sector_fixture(fixtures["index_sector"]) == []
    assert validate_krx_symbol_master_fixture(fixtures["symbol_master"]) == []
    assert validate_krx_trading_calendar_fixture(fixtures["trading_calendar"]) == []
    assert validate_krx_corporate_action_fixture(fixtures["corporate_actions"]) == []

    for fixture in fixtures.values():
        assert SENSITIVE_FIELD_NAMES.isdisjoint(_walk_keys(fixture))


def test_krx_index_and_sector_normalize_output_matches_existing_models():
    raw = _load_fixture("index_sector")

    index_rows = normalize_krx_index_rows(raw)
    sector_rows = normalize_krx_sector_rows(raw)

    assert index_rows[0] == {
        "trade_date": "2026-05-20",
        "symbol": "KOSPI",
        "open": 2725.10,
        "high": 2744.20,
        "low": 2718.35,
        "close": 2738.42,
        "volume": 483920000,
    }
    assert set(index_rows[0]) == {"trade_date", "symbol", "open", "high", "low", "close", "volume"}
    assert sector_rows[0] == {
        "trade_date": "2026-05-20",
        "sector": "Semiconductors",
        "open": 512.10,
        "high": 520.30,
        "low": 509.20,
        "close": 517.65,
        "volume": 128300000,
    }
    assert set(sector_rows[0]) == {"trade_date", "sector", "open", "high", "low", "close", "volume"}


def test_krx_symbol_master_normalize_output_matches_existing_model():
    rows = normalize_krx_symbol_master_rows(_load_fixture("symbol_master"))

    assert rows[0] == {
        "symbol": "005930",
        "name": "Samsung Electronics",
        "asset_type": "stock",
        "currency": "KRW",
        "market": "KR",
        "exchange": "KRX",
        "sector": "Semiconductors",
        "industry": "Memory",
        "is_active": True,
        "list_date": "1975-06-11",
        "delist_date": None,
    }
    assert set(rows[0]) == {
        "symbol",
        "name",
        "asset_type",
        "currency",
        "market",
        "exchange",
        "sector",
        "industry",
        "is_active",
        "list_date",
        "delist_date",
    }


def test_krx_trading_calendar_normalize_output_matches_existing_model():
    rows = normalize_krx_trading_calendar_rows(_load_fixture("trading_calendar"))

    assert rows[0] == {
        "market": "KR",
        "calendar_date": "2026-05-20",
        "is_open": True,
        "source_id": "krx_trading_calendar",
        "note": "session=regular",
    }
    assert rows[1] == {
        "market": "KR",
        "calendar_date": "2026-05-25",
        "is_open": False,
        "source_id": "krx_trading_calendar",
        "note": "session=closed; holiday=Observed Holiday",
    }
    assert set(rows[0]) == {"market", "calendar_date", "is_open", "source_id", "note"}


def test_krx_corporate_action_normalize_output_matches_existing_model():
    rows = normalize_krx_corporate_action_rows(_load_fixture("corporate_actions"))

    assert rows[0] == {
        "symbol": "005930",
        "action_date": "2026-05-20",
        "action_type": "DIVIDEND",
        "value": 361.0,
        "source_id": "krx_corporate_actions",
        "note": "cash dividend fixture",
    }
    assert set(rows[0]) == {"symbol", "action_date", "action_type", "value", "source_id", "note"}


def test_krx_read_only_provider_contract_and_safety_invariants_remain_closed(client, monkeypatch):
    sentinel = "PHASE3F3_SENTINEL_SECRET_VALUE"
    monkeypatch.setenv("KIS_APP_KEY", sentinel)
    monkeypatch.setenv("KIS_APP_SECRET", sentinel)
    before = _row_counts()

    providers_response = client.get("/api/data/read-only/providers")
    assert providers_response.status_code == 200
    providers = providers_response.json()
    by_id = {provider["source_id"]: provider for provider in providers}

    for provider in providers:
        assert set(provider) == EXPECTED_PROVIDER_FIELDS
        assert provider["network_call_performed"] is False
        assert provider["token_issued"] is False
        assert provider["token_cache_enabled"] is False
        assert provider["adapter_order_call_performed"] is False
        assert provider["adapter_network_call_performed"] is False
        assert provider["credential_fields_exposed"] is False
        assert SENSITIVE_FIELD_NAMES.isdisjoint(provider)

    krx_index = by_id["krx_index_sector"]
    assert krx_index["asset_scope"] == ["index_ohlcv", "sector_ohlcv"]
    assert {
        "index_daily_ohlcv_status",
        "sector_daily_ohlcv_status",
        "index_fixture_schema",
        "sector_fixture_schema",
        "index_normalize_contract",
        "sector_normalize_contract",
    }.issubset(set(krx_index["capabilities"]))

    expected_krx_sources = {
        "krx_index_sector",
        "krx_symbol_master",
        "krx_trading_calendar",
        "krx_corporate_actions",
    }
    for source_id in expected_krx_sources:
        provider = by_id[source_id]
        assert provider["provider_name"] == "krx"
        assert provider["enabled"] is False
        assert provider["network_enabled"] is False
        assert provider["read_only_enabled"] is False
        assert provider["status"] == "disabled"
        assert {"SOURCE_DISABLED", "READ_ONLY_DISABLED", "NETWORK_DISABLED_FAIL_CLOSED"}.issubset(
            set(provider["reason_codes"])
        )

    assert "symbol_master_fixture_schema" in by_id["krx_symbol_master"]["capabilities"]
    assert "symbol_master_normalize_contract" in by_id["krx_symbol_master"]["capabilities"]
    assert "trading_calendar_fixture_schema" in by_id["krx_trading_calendar"]["capabilities"]
    assert "trading_calendar_normalize_contract" in by_id["krx_trading_calendar"]["capabilities"]
    assert "corporate_action_fixture_schema" in by_id["krx_corporate_actions"]["capabilities"]
    assert "corporate_action_normalize_contract" in by_id["krx_corporate_actions"]["capabilities"]

    serialized = json.dumps(providers, ensure_ascii=False)
    assert sentinel not in serialized
    assert not Path(".cache/kis/token.json").exists()
    assert _row_counts() == before

    route_paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/kis/orders" in route_paths
    assert "/api/kis/orders/preview" in route_paths
    assert not any(path.startswith("/api/kis/broker") for path in route_paths)
    assert not any(path.startswith("/api/kis/websocket") for path in route_paths)
    assert "/api/paper/orders" in route_paths
    assert "/api/paper/fill-simulator/run" in route_paths
    orders = client.get("/api/kis/orders")
    preview = client.post("/api/kis/orders/preview", json={"symbol": "005930"})
    assert orders.status_code == 200
    assert preview.status_code == 200
    assert orders.json()["network_call_performed"] is False
    assert preview.json()["live_order_created"] is False
    assert client.get("/api/kis/broker/status").status_code == 404
    assert client.get("/api/kis/websocket/status").status_code == 404
    submit = client.post("/api/paper/orders", json={"symbol": "005930", "side": "buy", "qty": 1})
    assert submit.status_code == 200
    assert submit.json()["paper_order_created"] is False
    assert submit.json()["network_call_performed"] is False
    assert client.post("/api/paper/fill-simulator/run", json={}).status_code == 422
