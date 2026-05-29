from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.main import app
from backend.app.models.tables import DailyOhlcv, Order, PaperAuditEvent, PaperFill, PaperOrder, PaperPosition
from backend.app.services.data_providers import (
    ExternalDailyRequest,
    ExternalProviderError,
    KIS_DAILY_ITEMCHART_RESPONSE_FIELDS,
    KIS_DAILY_ITEMCHART_ROW_FIELDS,
    KisMarketDataProvider,
    MockKisMarketDataProvider,
    RawProviderResponse,
    build_external_daily_provider,
    validate_kis_daily_itemchart_fixture,
)
from backend.app.services.market_data_import_service import DataSourceService


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "kis_daily_itemchartprice_response.json"
NORMALIZED_COLUMNS = [
    "trade_date",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "turnover_value",
    "market",
    "venue",
    "provider",
]
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


def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


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


def _kis_request(network_enabled: bool = False) -> ExternalDailyRequest:
    return ExternalDailyRequest(
        source_id="kis_market_data",
        provider_name="kis",
        provider_symbol="KR001",
        internal_symbol="KR001",
        start_date=date(2026, 5, 19),
        end_date=date(2026, 5, 21),
        source={
            "source_id": "kis_market_data",
            "provider_type": "external_market_data",
            "provider_name": "kis",
            "market": "KR",
            "venue": "KRX",
            "network_enabled": network_enabled,
        },
    )


def _daily_count() -> int:
    with SessionLocal() as db:
        return int(db.scalar(select(func.count()).select_from(DailyOhlcv)) or 0)


def _execution_counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "orders": int(db.scalar(select(func.count()).select_from(Order)) or 0),
            "paper_orders": int(db.scalar(select(func.count()).select_from(PaperOrder)) or 0),
            "paper_fills": int(db.scalar(select(func.count()).select_from(PaperFill)) or 0),
            "paper_positions": int(db.scalar(select(func.count()).select_from(PaperPosition)) or 0),
            "paper_audit_events": int(db.scalar(select(func.count()).select_from(PaperAuditEvent)) or 0),
        }


def _enable_kis_market_data(monkeypatch: pytest.MonkeyPatch) -> None:
    original = DataSourceService.list_sources

    def patched(self: DataSourceService) -> list[dict[str, object]]:
        return [
            {**source, "enabled": True, "read_only_enabled": True, "network_enabled": False}
            if source["source_id"] == "kis_market_data"
            else source
            for source in original(self)
        ]

    monkeypatch.setattr(DataSourceService, "list_sources", patched)


def _preview_kis(client):
    return client.post(
        "/api/data/external/preview-daily-ohlcv",
        json={
            "source_id": "kis_market_data",
            "symbol": "KR001",
            "start_date": "2026-05-19",
            "end_date": "2026-05-21",
        },
    )


def test_kis_daily_itemchart_fixture_schema_is_canonical_and_redacted():
    payload = _load_fixture()

    assert set(payload) == KIS_DAILY_ITEMCHART_RESPONSE_FIELDS
    assert validate_kis_daily_itemchart_fixture(payload) == []
    assert SENSITIVE_FIELD_NAMES.isdisjoint(_walk_keys(payload))

    rows = payload["output2"]
    assert len(rows) == 3
    for row in rows:
        assert set(row) == KIS_DAILY_ITEMCHART_ROW_FIELDS


def test_kis_raw_itemchart_response_normalizes_to_daily_ohlcv_columns():
    payload = _load_fixture()
    request = _kis_request()
    raw = RawProviderResponse(
        provider_name="kis",
        provider_symbol=request.provider_symbol,
        rows=payload["output2"],
        fetched_at=datetime.now(UTC),
    )

    provider = MockKisMarketDataProvider()
    assert provider.validate_raw_response(raw, request) == []
    frame = provider.normalize_ohlcv(raw, request)

    assert list(frame.columns) == NORMALIZED_COLUMNS
    assert frame.to_dict("records")[0] == {
        "trade_date": "2026-05-19",
        "symbol": "KR001",
        "open": 50252.0,
        "high": 50452.0,
        "low": 50122.0,
        "close": 50302.0,
        "adj_close": 50302.0,
        "volume": 120000,
        "turnover_value": 6036240000.0,
        "market": "KR",
        "venue": "KRX",
        "provider": "external_market_data",
    }


def test_kis_provider_selection_uses_mock_only_when_network_disabled():
    network_disabled_source = dict(_kis_request(network_enabled=False).source)
    network_enabled_source = dict(_kis_request(network_enabled=True).source)

    disabled_provider = build_external_daily_provider(network_disabled_source)
    enabled_provider = build_external_daily_provider(network_enabled_source)

    assert isinstance(disabled_provider, MockKisMarketDataProvider)
    assert isinstance(enabled_provider, KisMarketDataProvider)
    with pytest.raises(ExternalProviderError):
        enabled_provider.fetch_daily_ohlcv(_kis_request(network_enabled=True))


def test_kis_mock_preview_writes_no_daily_rows_until_confirm_then_upserts(client, monkeypatch):
    _enable_kis_market_data(monkeypatch)
    client.post("/api/data/seed")
    before_daily = _daily_count()
    before_execution = _execution_counts()

    preview = _preview_kis(client)

    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["source_id"] == "kis_market_data"
    assert preview_payload["provider_type"] == "external_market_data"
    assert preview_payload["status"] == "validated"
    assert preview_payload["can_confirm"] is True
    assert preview_payload["total_rows"] == 3
    assert preview_payload["valid_rows"] == 3
    assert preview_payload["provider_metadata"]["provider_name"] == "kis"
    assert preview_payload["provider_metadata"]["provider_mode"] == "mock"
    assert preview_payload["provider_metadata"]["data_origin"] == "deterministic_kis_mock"
    assert preview_payload["provider_metadata"]["network_enabled"] is False
    assert _daily_count() == before_daily
    assert _execution_counts() == before_execution == {
        "orders": 0,
        "paper_orders": 0,
        "paper_fills": 0,
        "paper_positions": 0,
        "paper_audit_events": 0,
    }

    confirmed = client.post("/api/data/external/confirm-import", json={"run_id": preview_payload["run_id"]})

    assert confirmed.status_code == 200
    confirmed_payload = confirmed.json()
    assert confirmed_payload["status"] == "confirmed"
    assert confirmed_payload["inserted_count"] == 1
    assert confirmed_payload["updated_count"] == 2
    assert _daily_count() == before_daily + 1
    assert _execution_counts() == before_execution

    duplicate_confirm = client.post("/api/data/external/confirm-import", json={"run_id": preview_payload["run_id"]})
    assert duplicate_confirm.status_code == 409


def test_kis_read_only_provider_contract_safety_and_execution_routes_remain_blocked(client, monkeypatch):
    sentinel = "PHASE3F2_SENTINEL_SECRET_VALUE"
    monkeypatch.setenv("KIS_APP_KEY", sentinel)
    monkeypatch.setenv("KIS_APP_SECRET", sentinel)
    before_execution = _execution_counts()

    sources = client.get("/api/data/sources")
    providers = client.get("/api/data/read-only/providers")
    kis_status = client.get("/api/kis/status")
    kis_config = client.get("/api/kis/config")
    kis_validate = client.post("/api/kis/config/validate")

    assert sources.status_code == 200
    assert providers.status_code == 200
    assert kis_status.status_code == 200
    assert kis_config.status_code == 200
    assert kis_validate.status_code == 200

    sources_by_id = {source["source_id"]: source for source in sources.json()}
    kis_source = sources_by_id["kis_market_data"]
    assert kis_source["enabled"] is False
    assert kis_source["network_enabled"] is False
    assert kis_source["read_only_enabled"] is False

    providers_by_id = {provider["source_id"]: provider for provider in providers.json()}
    kis_provider = providers_by_id["kis_market_data"]
    assert kis_provider["status"] == "disabled"
    assert {"SOURCE_DISABLED", "READ_ONLY_DISABLED", "NETWORK_DISABLED_FAIL_CLOSED"}.issubset(
        set(kis_provider["reason_codes"])
    )

    for provider in providers.json():
        assert provider["network_call_performed"] is False
        assert provider["token_issued"] is False
        assert provider["token_cache_enabled"] is False
        assert provider["adapter_order_call_performed"] is False
        assert provider["adapter_network_call_performed"] is False
        assert provider["credential_fields_exposed"] is False

    serialized = json.dumps(
        {
            "sources": sources.json(),
            "providers": providers.json(),
            "kis_status": kis_status.json(),
            "kis_config": kis_config.json(),
            "kis_validate": kis_validate.json(),
        },
        ensure_ascii=False,
    )
    assert sentinel not in serialized
    assert not Path(".cache/kis/token.json").exists()
    assert _execution_counts() == before_execution == {
        "orders": 0,
        "paper_orders": 0,
        "paper_fills": 0,
        "paper_positions": 0,
        "paper_audit_events": 0,
    }

    route_paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/kis/orders" in route_paths
    assert "/api/kis/orders/preview" in route_paths
    assert not any(path.startswith("/api/kis/broker") for path in route_paths)
    assert not any(path.startswith("/api/kis/websocket") for path in route_paths)
    orders = client.get("/api/kis/orders")
    preview = client.post("/api/kis/orders/preview", json={"symbol": "KR001"})
    assert orders.status_code == 200
    assert preview.status_code == 200
    assert orders.json()["network_call_performed"] is False
    assert preview.json()["live_order_created"] is False
    assert client.get("/api/kis/broker/account").status_code == 404
    assert client.get("/api/kis/websocket/status").status_code == 404
    assert client.post("/api/paper/orders", json={"symbol": "KR001"}).status_code == 422
    assert client.post("/api/paper/fill-simulator/run", json={}).status_code == 422
