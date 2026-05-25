from __future__ import annotations

import pytest
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


def _post_validate(client, csv_text: str, source_id: str = "csv_krx", filename: str = "sample.csv"):
    return client.post(
        "/api/data/validate-csv",
        data={"source_id": source_id},
        files={"file": (filename, csv_text.encode(), "text/csv")},
    )


def _market_counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            name: int(db.scalar(select(func.count()).select_from(table)) or 0)
            for name, table in MARKET_TABLES.items()
        }


def _run_counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "import_runs": int(db.scalar(select(func.count()).select_from(ImportRun)) or 0),
            "data_quality_checks": int(db.scalar(select(func.count()).select_from(DataQualityCheck)) or 0),
        }


def _quality_codes(run_id: str) -> set[str]:
    with SessionLocal() as db:
        return set(db.scalars(select(DataQualityCheck.check_code).where(DataQualityCheck.run_id == run_id)).all())


def test_validate_csv_success_records_run_and_quality_without_market_writes(full_flow_client):
    client = full_flow_client
    market_before = _market_counts()
    run_before = _run_counts()

    response = _post_validate(
        client,
        "trade_date,symbol,open,high,low,close,volume\n"
        "2026-05-20,QA001,100,110,95,105,10000\n",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "validated"
    assert payload["can_confirm"] is True
    assert payload["total_rows"] == 1
    assert payload["valid_rows"] == 1
    assert payload["error_count"] == 0
    assert payload["warning_count"] >= 3
    assert len(payload["preview_rows"]) == 1
    assert _market_counts() == market_before
    run_after = _run_counts()
    assert run_after["import_runs"] == run_before["import_runs"] + 1
    assert run_after["data_quality_checks"] > run_before["data_quality_checks"]
    assert {"UNKNOWN_SYMBOL", "MISSING_ADJ_CLOSE", "MISSING_TURNOVER_VALUE"}.issubset(_quality_codes(payload["run_id"]))


@pytest.mark.parametrize(
    ("csv_text", "expected_code"),
    [
        (
            "trade_date,symbol,open,high,low,close\n2026-05-20,BAD,1,2,1,2\n",
            "MISSING_REQUIRED_COLUMN",
        ),
        (
            "trade_date,symbol,open,high,low,close,volume\n2026-05-20,BAD,10,9,11,10,100\n",
            "HIGH_LT_LOW",
        ),
        (
            "trade_date,symbol,open,high,low,close,volume\n2026-05-20,BAD,10,9,8,10,100\n",
            "HIGH_LT_OPEN_OR_CLOSE",
        ),
        (
            "trade_date,symbol,open,high,low,close,volume\n2026-05-20,BAD,10,11,10.5,10,100\n",
            "LOW_GT_OPEN_OR_CLOSE",
        ),
        (
            "trade_date,symbol,open,high,low,close,volume\n2026-05-20,BAD,-1,2,1,2,100\n",
            "NEGATIVE_PRICE",
        ),
        (
            "trade_date,symbol,open,high,low,close,volume\n2026-05-20,BAD,1,2,1,2,-100\n",
            "NEGATIVE_VOLUME",
        ),
        (
            "trade_date,symbol,open,high,low,close,volume\n2026-05-20,BAD,,2,1,2,100\n",
            "MISSING_REQUIRED_VALUE",
        ),
        (
            "trade_date,symbol,open,high,low,close,volume\nbad-date,BAD,1,2,1,2,100\n",
            "DATE_PARSE_FAILED",
        ),
    ],
)
def test_validate_csv_error_taxonomy(client, csv_text, expected_code):
    response = _post_validate(client, csv_text)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["can_confirm"] is False
    assert payload["error_count"] > 0
    assert expected_code in _quality_codes(payload["run_id"])


def test_validate_csv_zero_volume_unknown_symbol_adjusted_close_and_turnover_warnings(client):
    response = _post_validate(
        client,
        "trade_date,symbol,open,high,low,close,volume\n"
        "2026-05-20,ZVOL,1,2,1,2,0\n",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "validated"
    assert payload["can_confirm"] is True
    codes = _quality_codes(payload["run_id"])
    assert {"ZERO_VOLUME", "UNKNOWN_SYMBOL", "MISSING_ADJ_CLOSE", "MISSING_TURNOVER_VALUE"}.issubset(codes)


def test_validate_csv_batch_duplicate_provider_mismatch_and_weekend_errors(client):
    duplicate = _post_validate(
        client,
        "trade_date,symbol,open,high,low,close,volume\n"
        "2026-05-20,DUP1,1,2,1,2,100\n"
        "2026-05-20,DUP1,1,2,1,2,100\n",
    )
    assert duplicate.status_code == 200
    assert "DUPLICATE_IN_BATCH" in _quality_codes(duplicate.json()["run_id"])

    mismatch = _post_validate(
        client,
        "trade_date,symbol,open,high,low,close,volume,provider\n"
        "2026-05-20,PMM,1,2,1,2,100,vendor\n",
    )
    assert mismatch.status_code == 200
    assert "PROVIDER_MISMATCH" in _quality_codes(mismatch.json()["run_id"])

    weekend = _post_validate(
        client,
        "trade_date,symbol,open,high,low,close,volume\n"
        "2026-05-23,WEEKEND,1,2,1,2,100\n",
    )
    assert weekend.status_code == 200
    assert "WEEKEND_DATE" in _quality_codes(weekend.json()["run_id"])


def test_validate_csv_requires_existing_source_id(client):
    response = _post_validate(
        client,
        "trade_date,symbol,open,high,low,close,volume\n2026-05-20,BAD,1,2,1,2,100\n",
        source_id="missing_source",
    )

    assert response.status_code == 400
    assert "존재하지 않는 source_id" in response.json()["detail"]


def test_confirm_import_state_transitions_and_write_timing(full_flow_client):
    client = full_flow_client
    before = _market_counts()
    response = _post_validate(
        client,
        "trade_date,symbol,open,high,low,close,volume,adj_close,turnover_value\n"
        "2026-05-20,KR001,999,1005,990,1000,123456,1000,123456000\n"
        "2026-05-20,NEWCONFIRM,10,12,9,11,1000,11,11000\n",
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]
    assert _market_counts() == before

    confirmed = client.post("/api/data/import-csv-confirmed", json={"run_id": run_id})
    assert confirmed.status_code == 200
    payload = confirmed.json()
    assert payload["status"] == "confirmed"
    assert payload["inserted_count"] == 1
    assert payload["updated_count"] == 1
    after = _market_counts()
    assert after["daily_ohlcv"] == before["daily_ohlcv"] + 1
    assert after["symbol_master"] == before["symbol_master"] + 1
    assert after["orders"] == before["orders"] == 0

    duplicate_confirm = client.post("/api/data/import-csv-confirmed", json={"run_id": run_id})
    assert duplicate_confirm.status_code == 409


def test_confirm_rejects_failed_and_missing_runs(client):
    failed = _post_validate(
        client,
        "trade_date,symbol,open,high,low,close,volume\n"
        "2026-05-20,BADCONFIRM,10,9,11,10,100\n",
    )
    assert failed.status_code == 200
    failed_confirm = client.post("/api/data/import-csv-confirmed", json={"run_id": failed.json()["run_id"]})
    assert failed_confirm.status_code == 400

    missing = client.post("/api/data/import-csv-confirmed", json={"run_id": "imp-does-not-exist"})
    assert missing.status_code == 404


def test_data_sources_import_runs_and_quality_apis(client):
    sources = client.get("/api/data/sources")
    assert sources.status_code == 200
    assert {"sample_krx", "csv_krx", "external_placeholder_disabled"}.issubset(
        {source["source_id"] for source in sources.json()}
    )

    response = _post_validate(
        client,
        "trade_date,symbol,open,high,low,close,volume\n2026-05-20,API001,1,2,1,2,100\n",
    )
    run_id = response.json()["run_id"]

    runs = client.get("/api/data/import-runs?limit=10")
    assert runs.status_code == 200
    assert any(run["run_id"] == run_id for run in runs.json())

    detail = client.get(f"/api/data/import-runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["run_id"] == run_id
    assert "staged_rows" in detail.json()

    quality = client.get(f"/api/data/quality?run_id={run_id}&severity=warning")
    assert quality.status_code == 200
    assert quality.json()
    assert all(check["severity"] == "warning" for check in quality.json())

    quality_by_run = client.get(f"/api/data/quality/{run_id}")
    assert quality_by_run.status_code == 200
    assert quality_by_run.json()


def test_legacy_direct_import_endpoint_remains_compatible(client):
    csv_text = (
        "trade_date,symbol,open,high,low,close,volume,turnover_value,market,provider,adj_close\n"
        "2026-05-20,LEGACY1,10,12,9,11,1000,11000,KOSDAQ,vendor,11\n"
    )
    imported = client.post(
        "/api/data/import/daily-ohlcv",
        files={"file": ("legacy.csv", csv_text.encode(), "text/csv")},
    )
    assert imported.status_code == 200
    assert imported.json()["inserted_count"] == 1

    duplicate = client.post(
        "/api/data/import/daily-ohlcv",
        files={"file": ("legacy.csv", csv_text.encode(), "text/csv")},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["updated_count"] == 1

    with SessionLocal() as db:
        row = db.scalar(select(DailyOhlcv).where(DailyOhlcv.symbol == "LEGACY1"))
        assert row is not None
        assert row.venue == "KOSDAQ"
