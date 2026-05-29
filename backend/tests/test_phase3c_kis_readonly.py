from __future__ import annotations

import json
import os
import subprocess
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.main import app
from backend.app.models.tables import (
    BacktestRun,
    DailyOhlcv,
    DataQualityCheck,
    FundamentalsPti,
    ImportRun,
    IndexOhlcv,
    IndicatorSnapshot,
    Order,
    Report,
    ScreenResult,
    SectorOhlcv,
    SymbolMaster,
)
from backend.app.services.data_providers import ExternalDailyRequest, MockKisMarketDataProvider
from backend.app.services.market_data_import_service import DataSourceService

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
}

MARKET_TABLES = {
    "symbol_master": SymbolMaster,
    "daily_ohlcv": DailyOhlcv,
    "index_ohlcv": IndexOhlcv,
    "sector_ohlcv": SectorOhlcv,
    "fundamentals_pti": FundamentalsPti,
    "indicator_snapshot": IndicatorSnapshot,
    "screen_results": ScreenResult,
    "reports": Report,
    "backtest_runs": BacktestRun,
    "orders": Order,
}


def _market_counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            name: int(db.scalar(select(func.count()).select_from(table)) or 0)
            for name, table in MARKET_TABLES.items()
        }


def _quality_codes(run_id: str) -> set[str]:
    with SessionLocal() as db:
        return set(db.scalars(select(DataQualityCheck.check_code).where(DataQualityCheck.run_id == run_id)).all())


def _enable_kis_market_data(monkeypatch) -> None:
    original = DataSourceService.list_sources

    def patched(self: DataSourceService) -> list[dict[str, object]]:
        sources = original(self)
        return [
            {
                **source,
                "enabled": True,
                "read_only_enabled": True,
                "network_enabled": False,
            }
            if source["source_id"] == "kis_market_data"
            else source
            for source in sources
        ]

    monkeypatch.setattr(DataSourceService, "list_sources", patched)


def _preview_kis(client):
    return client.post(
        "/api/data/external/preview-daily-ohlcv",
        json={
            "source_id": "kis_market_data",
            "symbol": "005930",
            "start_date": "2026-05-19",
            "end_date": "2026-05-21",
        },
    )


def test_kis_market_data_source_defaults_disabled_and_has_no_secret_fields(client):
    sources = client.get("/api/data/sources")
    providers = client.get("/api/data/external/providers")

    assert sources.status_code == 200
    assert providers.status_code == 200
    by_id = {source["source_id"]: source for source in sources.json()}
    provider_by_id = {source["source_id"]: source for source in providers.json()}
    kis = by_id["kis_market_data"]
    assert kis["provider_type"] == "external_market_data"
    assert kis["provider_name"] == "kis"
    assert kis["enabled"] is False
    assert kis["network_enabled"] is False
    assert kis["read_only_enabled"] is False
    assert kis["manual_preview_only"] is True
    assert kis["max_rows"] == 100
    assert kis["max_date_range_days"] == 100
    assert "kis_market_data" in provider_by_id
    assert SENSITIVE_FIELD_NAMES.isdisjoint(kis)


def test_kis_status_config_settings_and_sentinel_secret_are_redacted(client, monkeypatch):
    sentinel = "PHASE3C_" + "SENTINEL_" + "SECRET_VALUE"
    monkeypatch.setenv("KIS_APP_KEY", sentinel)
    monkeypatch.setenv("KIS_APP_SECRET", sentinel)

    responses = [
        client.get("/api/kis/status"),
        client.get("/api/kis/config"),
        client.post("/api/kis/config/validate"),
        client.get("/api/settings"),
    ]

    for response in responses:
        assert response.status_code == 200
        serialized = json.dumps(response.json(), ensure_ascii=False)
        assert sentinel not in serialized

    status = responses[0].json()
    assert status["source_id"] == "kis_market_data"
    assert status["app_key_configured"] is True
    assert status["app_secret_configured"] is True
    assert status["token_cache_enabled"] is False
    assert status["broker_enabled"] is False
    assert status["websocket_enabled"] is False
    assert status["disabled_reason"] == "Phase 3C read-only foundation only"

    config = responses[1].json()
    assert SENSITIVE_FIELD_NAMES.isdisjoint(config["source_config"])

    tracked_files = subprocess.run(["git", "ls-files"], check=True, capture_output=True, text=True).stdout.splitlines()
    for tracked_file in tracked_files:
        path = Path(tracked_file)
        if path.suffix.lower() in {".db", ".png", ".jpg", ".jpeg", ".gif", ".ico"}:
            continue
        if path.exists():
            assert sentinel not in path.read_text(encoding="utf-8", errors="ignore")


def test_kis_disabled_source_blocks_fetch_and_creates_no_token_cache(client):
    client.post("/api/data/seed")
    before = _market_counts()
    before_runs = 0
    with SessionLocal() as db:
        before_runs = int(db.scalar(select(func.count()).select_from(ImportRun)) or 0)

    response = _preview_kis(client)

    assert response.status_code == 400
    assert "비활성화된 data source" in response.json()["detail"]
    assert _market_counts() == before
    with SessionLocal() as db:
        after_runs = int(db.scalar(select(func.count()).select_from(ImportRun)) or 0)
    assert after_runs == before_runs
    assert not Path(".cache/kis/token.json").exists()


def test_mock_kis_market_data_provider_normalizes_itemchart_fixture():
    provider = MockKisMarketDataProvider()
    request = ExternalDailyRequest(
        source_id="kis_market_data",
        provider_name="kis",
        provider_symbol="005930",
        internal_symbol="005930",
        start_date=date(2026, 5, 19),
        end_date=date(2026, 5, 21),
        source={"market": "KR", "venue": "KRX", "provider_type": "external_market_data"},
    )

    raw = provider.fetch_daily_ohlcv(request)
    assert raw.provider_name == "kis"
    assert {"stck_bsop_date", "stck_oprc", "stck_hgpr", "stck_lwpr", "stck_clpr", "acml_vol"}.issubset(raw.rows[0])
    assert provider.validate_raw_response(raw, request) == []
    frame = provider.normalize_ohlcv(raw, request)

    assert list(frame.columns) == [
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
    assert len(frame) == len(pd.bdate_range("2026-05-19", "2026-05-21"))
    assert set(frame["symbol"]) == {"005930"}
    assert set(frame["provider"]) == {"external_market_data"}


def test_mock_kis_preview_confirm_flow_and_orders_invariant(client, monkeypatch):
    _enable_kis_market_data(monkeypatch)
    client.post("/api/data/seed")
    before = _market_counts()

    preview = _preview_kis(client)

    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["source_id"] == "kis_market_data"
    assert preview_payload["provider_type"] == "external_market_data"
    assert preview_payload["status"] == "validated"
    assert preview_payload["can_confirm"] is True
    assert preview_payload["provider_metadata"]["provider_name"] == "kis"
    assert preview_payload["provider_metadata"]["provider_mode"] == "mock"
    assert preview_payload["provider_metadata"]["data_origin"] == "deterministic_kis_mock"
    assert _market_counts() == before
    assert "UNKNOWN_SYMBOL" in _quality_codes(preview_payload["run_id"])

    confirmed = client.post("/api/data/external/confirm-import", json={"run_id": preview_payload["run_id"]})

    assert confirmed.status_code == 200
    confirmed_payload = confirmed.json()
    assert confirmed_payload["status"] == "confirmed"
    after = _market_counts()
    assert after["daily_ohlcv"] == before["daily_ohlcv"] + preview_payload["valid_rows"]
    assert after["orders"] == before["orders"] == 0


def test_kis_order_routes_are_registered_but_disabled_and_websocket_routes_are_not_registered(client):
    route_paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/kis/orders" in route_paths
    assert "/api/kis/orders/preview" in route_paths
    assert not any(path.startswith("/api/kis/broker") for path in route_paths)
    assert not any(path.startswith("/api/kis/websocket") for path in route_paths)
    orders = client.get("/api/kis/orders")
    preview = client.post("/api/kis/orders/preview", json={"symbol": "005930"})
    assert orders.status_code == 200
    assert preview.status_code == 200
    assert orders.json()["network_call_performed"] is False
    assert preview.json()["live_order_created"] is False
    assert client.get("/api/kis/websocket/status").status_code == 404


def test_existing_yfinance_and_csv_flows_still_work(client):
    client.post("/api/data/seed")

    yfinance_preview = client.post(
        "/api/data/external/preview-daily-ohlcv",
        json={
            "source_id": "external_yfinance",
            "symbol": "005930",
            "start_date": "2026-05-19",
            "end_date": "2026-05-21",
        },
    )
    assert yfinance_preview.status_code == 200
    assert yfinance_preview.json()["provider_metadata"]["provider_name"] == "yfinance"

    csv_preview = client.post(
        "/api/data/validate-csv",
        data={"source_id": "csv_krx"},
        files={
            "file": (
                "phase3c-regression.csv",
                b"trade_date,symbol,open,high,low,close,volume\n2026-05-20,CSV3C,1,2,1,2,100\n",
                "text/csv",
            )
        },
    )
    assert csv_preview.status_code == 200
    csv_confirm = client.post("/api/data/import-csv-confirmed", json={"run_id": csv_preview.json()["run_id"]})
    assert csv_confirm.status_code == 200
    assert csv_confirm.json()["status"] == "confirmed"
