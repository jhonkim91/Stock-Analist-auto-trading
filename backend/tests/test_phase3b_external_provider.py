from __future__ import annotations

import json

from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
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
from backend.app.services import data_providers


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


def _preview_external(client, symbol: str = "005930", source_id: str = "external_yfinance"):
    return client.post(
        "/api/data/external/preview-daily-ohlcv",
        json={
            "source_id": source_id,
            "symbol": symbol,
            "start_date": "2026-05-19",
            "end_date": "2026-05-21",
        },
    )


def _post_validate_csv(client):
    return client.post(
        "/api/data/validate-csv",
        data={"source_id": "csv_krx"},
        files={
            "file": (
                "phase3b-regression.csv",
                b"trade_date,symbol,open,high,low,close,volume\n2026-05-20,CSV3B,1,2,1,2,100\n",
                "text/csv",
            )
        },
    )


def test_external_providers_are_provider_neutral_and_kis_has_no_secret_fields(client):
    response = client.get("/api/data/external/providers")

    assert response.status_code == 200
    providers = response.json()
    by_id = {provider["source_id"]: provider for provider in providers}
    assert by_id["external_yfinance"]["provider_name"] == "yfinance"
    assert by_id["external_yfinance"]["network_enabled"] is False
    assert by_id["external_yfinance"]["unknown_symbol_policy"] == "warn_and_create_on_confirm"
    assert by_id["kis_openapi"]["provider_name"] == "kis"
    assert by_id["kis_openapi"]["enabled"] is False
    assert by_id["kis_openapi"]["unknown_symbol_policy"] == "reject"
    assert by_id["kis_openapi"]["paper_trading_enabled"] is False
    assert by_id["kis_openapi"]["live_trading_enabled"] is False
    assert by_id["kis_openapi"]["websocket_enabled"] is False
    forbidden = {"app_key", "app_secret", "token", "password", "account_no", "hts_id", "access_token", "refresh_token"}
    assert forbidden.isdisjoint(by_id["kis_openapi"])

    settings = client.get("/api/settings")
    assert settings.status_code == 200
    serialized = json.dumps(settings.json()).lower()
    for key in forbidden:
        assert key not in serialized


def test_yfinance_source_preview_uses_mapping_and_does_not_write_market_tables(client, monkeypatch):
    client.post("/api/data/seed")
    before = _market_counts()

    def fail_network(*_args, **_kwargs):
        raise AssertionError("network_enabled=false 상태에서 yfinance network fetch가 호출되었습니다.")

    monkeypatch.setattr(data_providers.YFinanceDailyProvider, "fetch_daily_ohlcv", fail_network)
    response = _preview_external(client)

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_id"] == "external_yfinance"
    assert payload["provider_type"] == "external_market_data"
    assert payload["status"] == "validated"
    assert payload["can_confirm"] is True
    assert payload["total_rows"] == 3
    assert payload["valid_rows"] == 3
    assert payload["provider_metadata"]["provider_name"] == "yfinance"
    assert payload["provider_metadata"]["provider_symbol"] == "005930.KS"
    assert payload["provider_metadata"]["internal_symbol"] == "005930"
    assert payload["provider_metadata"]["network_enabled"] is False
    assert payload["provider_metadata"]["provider_mode"] == "mock"
    assert payload["provider_metadata"]["data_origin"] == "deterministic_mock"
    assert _market_counts() == before
    assert "UNKNOWN_SYMBOL" in _quality_codes(payload["run_id"])


def test_kis_openapi_source_is_disabled_for_phase3b(client):
    client.post("/api/data/seed")

    response = _preview_external(client, symbol="KR001", source_id="kis_openapi")

    assert response.status_code == 400
    assert "비활성화된 data source" in response.json()["detail"]


def test_symbol_mapping_failure_creates_failed_run_without_market_writes(client):
    client.post("/api/data/seed")
    before = _market_counts()
    run_count_before = 0
    with SessionLocal() as db:
        run_count_before = int(db.scalar(select(func.count()).select_from(ImportRun)) or 0)

    response = _preview_external(client, symbol="NO_MAPPING")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["can_confirm"] is False
    assert payload["error_count"] == 1
    assert "SYMBOL_MAPPING_FAILED" in _quality_codes(payload["run_id"])
    assert _market_counts() == before
    with SessionLocal() as db:
        run_count_after = int(db.scalar(select(func.count()).select_from(ImportRun)) or 0)
    assert run_count_after == run_count_before + 1


def test_external_confirm_only_then_updates_daily_ohlcv_and_keeps_orders_zero(client):
    client.post("/api/data/seed")
    preview = _preview_external(client)
    assert preview.status_code == 200
    run_id = preview.json()["run_id"]
    before = _market_counts()

    confirmed = client.post("/api/data/external/confirm-import", json={"run_id": run_id})

    assert confirmed.status_code == 200
    payload = confirmed.json()
    assert payload["status"] == "confirmed"
    assert payload["inserted_count"] == 3
    assert payload["updated_count"] == 0
    assert payload["provider_metadata"]["provider_mode"] == "mock"
    assert payload["provider_metadata"]["data_origin"] == "deterministic_mock"
    after = _market_counts()
    assert after["daily_ohlcv"] == before["daily_ohlcv"] + 3
    assert after["symbol_master"] == before["symbol_master"] + 1
    assert after["orders"] == before["orders"] == 0

    duplicate_confirm = client.post("/api/data/external/confirm-import", json={"run_id": run_id})
    assert duplicate_confirm.status_code == 409


def test_external_confirm_rejects_csv_run_and_existing_csv_flow_still_works(client):
    csv_preview = _post_validate_csv(client)
    assert csv_preview.status_code == 200
    run_id = csv_preview.json()["run_id"]

    external_confirm = client.post("/api/data/external/confirm-import", json={"run_id": run_id})
    assert external_confirm.status_code == 400

    csv_confirm = client.post("/api/data/import-csv-confirmed", json={"run_id": run_id})
    assert csv_confirm.status_code == 200
    assert csv_confirm.json()["status"] == "confirmed"
