from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.models.tables import DailyOhlcv, SymbolMaster


FIXTURE = Path(__file__).parent / "fixtures" / "sample_daily_ohlcv.csv"


def _daily_count() -> int:
    with SessionLocal() as db:
        return int(db.scalar(select(func.count()).select_from(DailyOhlcv)) or 0)


def test_csv_import_success_duplicate_handling_and_indicator_recompute(client):
    seed = client.post("/api/data/seed")
    assert seed.status_code == 200
    before_count = _daily_count()

    with FIXTURE.open("rb") as file:
        imported = client.post(
            "/api/data/import/daily-ohlcv",
            files={"file": ("sample_daily_ohlcv.csv", file, "text/csv")},
    )
    assert imported.status_code == 200
    assert imported.json()["inserted_count"] == 2
    assert imported.json()["updated_count"] == 0
    assert imported.json()["skipped_count"] == 0
    assert imported.json()["error_count"] == 0
    assert _daily_count() == before_count + 2

    with FIXTURE.open("rb") as file:
        duplicate = client.post(
            "/api/data/import/daily-ohlcv",
            files={"file": ("sample_daily_ohlcv.csv", file, "text/csv")},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["inserted_count"] == 0
    assert duplicate.json()["updated_count"] == 2
    assert _daily_count() == before_count + 2

    recompute = client.post("/api/indicators/recompute")
    assert recompute.status_code == 200
    assert recompute.json()["rows"] > 0


def test_csv_import_missing_required_column_returns_error(client):
    csv_content = b"trade_date,symbol,open,high,low,close\n2026-05-20,BAD,1,2,1,2\n"
    response = client.post(
        "/api/data/import/daily-ohlcv",
        files={"file": ("bad.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 400
    assert "CSV 필수 컬럼 누락" in response.json()["detail"]


def test_csv_import_optional_defaults_symbol_upsert_and_update(client):
    csv_content = (
        "trade_date,symbol,open,high,low,close,volume\n"
        "2026-05-20,NEW001,10,12,9,11,1000\n"
    ).encode()
    response = client.post(
        "/api/data/import/daily-ohlcv",
        files={"file": ("minimal.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 200
    assert response.json()["inserted_count"] == 1
    with SessionLocal() as db:
        symbol = db.get(SymbolMaster, "NEW001")
        row = db.scalar(select(DailyOhlcv).where(DailyOhlcv.symbol == "NEW001"))
        assert symbol is not None
        assert symbol.name == "NEW001"
        assert symbol.asset_type == "stock"
        assert symbol.currency == "KRW"
        assert row is not None
        assert row.adj_close == 11
        assert row.turnover_value == 11000
        assert row.venue == "KRX"

    update_content = (
        "trade_date,symbol,open,high,low,close,volume,turnover_value,market,provider,adj_close\n"
        "2026-05-20,NEW001,11,13,10,12,2000,24000,KOSDAQ,vendor,12.5\n"
    ).encode()
    updated = client.post(
        "/api/data/import/daily-ohlcv",
        files={"file": ("update.csv", update_content, "text/csv")},
    )

    assert updated.status_code == 200
    assert updated.json()["inserted_count"] == 0
    assert updated.json()["updated_count"] == 1
    with SessionLocal() as db:
        row = db.scalar(select(DailyOhlcv).where(DailyOhlcv.symbol == "NEW001"))
        assert row is not None
        assert row.close == 12
        assert row.turnover_value == 24000
        assert row.venue == "KOSDAQ"


def test_csv_import_validation_rejects_invalid_rows(client):
    invalid_cases = [
        "trade_date,symbol,open,high,low,close,volume\nbad-date,BAD,1,2,1,2,100\n",
        "trade_date,symbol,open,high,low,close,volume\n2026-05-20,BAD,1,1,2,2,100\n",
        "trade_date,symbol,open,high,low,close,volume\n2026-05-20,BAD,-1,2,1,2,100\n",
    ]
    for index, csv_text in enumerate(invalid_cases):
        response = client.post(
            "/api/data/import/daily-ohlcv",
            files={"file": (f"invalid-{index}.csv", csv_text.encode(), "text/csv")},
        )
        assert response.status_code == 400
        assert "CSV import 검증 실패" in response.json()["detail"]
