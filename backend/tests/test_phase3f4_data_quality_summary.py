from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.main import app
from backend.app.models.tables import (
    DailyOhlcv,
    DataQualityCheck,
    ImportRun,
    Order,
    PaperAuditEvent,
    PaperFill,
    PaperOrder,
    PaperPosition,
    SymbolMaster,
    TradingCalendar,
)
from backend.app.services.data_quality_summary_service import DataQualitySummaryService

EXPECTED_SUMMARY_FIELDS = {
    "market",
    "venue",
    "latest_trade_date",
    "row_counts",
    "source_freshness",
    "missing_rows",
    "duplicate_summary",
    "quality_counts",
    "safety_counts",
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


def _row_counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "daily_ohlcv": int(db.scalar(select(func.count()).select_from(DailyOhlcv)) or 0),
            "symbol_master": int(db.scalar(select(func.count()).select_from(SymbolMaster)) or 0),
            "trading_calendar": int(db.scalar(select(func.count()).select_from(TradingCalendar)) or 0),
            "import_runs": int(db.scalar(select(func.count()).select_from(ImportRun)) or 0),
            "data_quality_checks": int(db.scalar(select(func.count()).select_from(DataQualityCheck)) or 0),
            "orders": int(db.scalar(select(func.count()).select_from(Order)) or 0),
            "paper_orders": int(db.scalar(select(func.count()).select_from(PaperOrder)) or 0),
            "paper_fills": int(db.scalar(select(func.count()).select_from(PaperFill)) or 0),
            "paper_positions": int(db.scalar(select(func.count()).select_from(PaperPosition)) or 0),
            "paper_audit_events": int(db.scalar(select(func.count()).select_from(PaperAuditEvent)) or 0),
        }


def test_quality_summary_contract_seeded_db_and_safety_counts(client):
    client.post("/api/data/seed")
    before = _row_counts()

    response = client.get("/api/data/quality-summary")

    assert response.status_code == 200
    assert _row_counts() == before
    payload = response.json()
    assert set(payload) == EXPECTED_SUMMARY_FIELDS
    assert payload["market"] == "KR"
    assert payload["venue"] == "KRX"
    assert payload["latest_trade_date"] == "2026-05-20"
    assert payload["row_counts"] == {
        "daily_ohlcv": 4800,
        "symbol_master": 15,
        "active_symbols": 15,
        "trading_calendar": 0,
        "import_runs": 0,
        "confirmed_import_runs": 0,
        "data_quality_checks": 0,
    }
    assert payload["missing_rows"]["basis"] == "observed_daily_ohlcv"
    assert payload["missing_rows"]["date_count"] == 30
    assert payload["missing_rows"]["expected_rows"] == 450
    assert payload["missing_rows"]["actual_rows"] == 450
    assert payload["missing_rows"]["missing_rows_estimate"] == 0
    assert payload["missing_rows"]["missing_symbol_sample"] == []

    freshness_by_id = {item["source_id"]: item for item in payload["source_freshness"]}
    assert freshness_by_id["csv_krx"]["freshness_status"] == "NO_CONFIRMED_RUN"
    assert freshness_by_id["external_yfinance"]["freshness_status"] == "NO_CONFIRMED_RUN"
    assert freshness_by_id["kis_market_data"]["freshness_status"] == "DISABLED"
    assert freshness_by_id["krx_symbol_master"]["freshness_status"] == "DISABLED"

    assert payload["duplicate_summary"]["physical_duplicate_groups"] == 0
    assert payload["duplicate_summary"]["physical_duplicate_rows"] == 0
    assert payload["duplicate_summary"]["quality_duplicate_code_counts"] == {
        "DUPLICATE_IN_BATCH": 0,
        "DUPLICATE_IN_DATABASE": 0,
    }
    assert payload["quality_counts"] == {
        "total": 0,
        "by_severity": {"error": 0, "warning": 0, "info": 0},
        "top_check_codes": [],
    }
    assert payload["safety_counts"] == {
        "orders_count": 0,
        "paper_orders_count": 0,
        "paper_fills_count": 0,
        "paper_positions_count": 0,
        "paper_audit_events_count": 0,
        "token_issued": False,
        "token_cache_enabled": False,
        "network_call_performed": False,
        "adapter_order_call_performed": False,
        "adapter_network_call_performed": False,
    }


def test_quality_summary_uses_trading_calendar_open_dates_when_available(client):
    client.post("/api/data/seed")
    with SessionLocal() as db:
        db.add_all(
            [
                TradingCalendar(market="KR", calendar_date=date(2026, 5, 18), is_open=True, source_id="test"),
                TradingCalendar(market="KR", calendar_date=date(2026, 5, 19), is_open=True, source_id="test"),
                TradingCalendar(market="KR", calendar_date=date(2026, 5, 20), is_open=True, source_id="test"),
                TradingCalendar(market="KR", calendar_date=date(2026, 5, 21), is_open=False, source_id="test"),
            ]
        )
        db.commit()

    before = _row_counts()
    response = client.get("/api/data/quality-summary?lookback_trading_dates=3")

    assert response.status_code == 200
    assert _row_counts() == before
    missing_rows = response.json()["missing_rows"]
    assert missing_rows["basis"] == "trading_calendar"
    assert missing_rows["date_count"] == 3
    assert missing_rows["expected_rows"] == 45
    assert missing_rows["actual_rows"] == 45
    assert missing_rows["missing_rows_estimate"] == 0
    assert missing_rows["coverage_ratio"] == 1.0


def test_quality_summary_duplicate_quality_code_counts_are_separate_from_physical_duplicates(client):
    client.post("/api/data/seed")
    with SessionLocal() as db:
        db.add_all(
            [
                DataQualityCheck(
                    run_id="phase3f4-dup",
                    row_number=2,
                    symbol="KR001",
                    trade_date=date(2026, 5, 20),
                    field="symbol",
                    check_code="DUPLICATE_IN_BATCH",
                    severity="error",
                    message="duplicate in batch",
                ),
                DataQualityCheck(
                    run_id="phase3f4-dup",
                    row_number=3,
                    symbol="KR001",
                    trade_date=date(2026, 5, 20),
                    field="symbol",
                    check_code="DUPLICATE_IN_DATABASE",
                    severity="info",
                    message="duplicate in database",
                ),
                DataQualityCheck(
                    run_id="phase3f4-dup",
                    row_number=4,
                    symbol="KR002",
                    trade_date=date(2026, 5, 20),
                    field="volume",
                    check_code="ZERO_VOLUME",
                    severity="warning",
                    message="zero volume",
                ),
            ]
        )
        db.commit()
    before = _row_counts()

    response = client.get("/api/data/quality-summary")

    assert response.status_code == 200
    assert _row_counts() == before
    payload = response.json()
    assert payload["duplicate_summary"]["physical_duplicate_groups"] == 0
    assert payload["duplicate_summary"]["quality_duplicate_code_counts"] == {
        "DUPLICATE_IN_BATCH": 1,
        "DUPLICATE_IN_DATABASE": 1,
    }
    assert payload["quality_counts"]["total"] == 3
    assert payload["quality_counts"]["by_severity"] == {"error": 1, "warning": 1, "info": 1}
    top_codes = {item["check_code"]: item["count"] for item in payload["quality_counts"]["top_check_codes"]}
    assert top_codes["DUPLICATE_IN_BATCH"] == 1
    assert top_codes["DUPLICATE_IN_DATABASE"] == 1
    assert top_codes["ZERO_VOLUME"] == 1


def test_enabled_read_only_reference_without_confirmed_run_is_not_applicable(db_session, monkeypatch):
    service = DataQualitySummaryService(db_session)
    monkeypatch.setattr(
        service.source_service,
        "list_sources",
        lambda: [
            {
                "source_id": "krx_symbol_master_enabled",
                "provider_type": "krx_symbol_master",
                "provider_name": "krx",
                "enabled": True,
                "read_only_enabled": True,
                "network_enabled": False,
                "read_only_capable": True,
                "asset_scope": ["symbol_master"],
            }
        ],
    )

    payload = service.summary()

    assert payload["source_freshness"][0]["freshness_status"] == "NOT_APPLICABLE"
    assert payload["source_freshness"][0]["reason_code"] == "REFERENCE_SOURCE_NO_CONFIRMED_RUN_REQUIRED"


def test_quality_summary_keeps_execution_routes_closed_and_provider_contract_unchanged(client):
    client.post("/api/data/seed")

    providers_response = client.get("/api/data/read-only/providers")
    summary_response = client.get("/api/data/quality-summary")

    assert providers_response.status_code == 200
    assert summary_response.status_code == 200
    for provider in providers_response.json():
        assert set(provider) == EXPECTED_PROVIDER_FIELDS
        assert provider["network_call_performed"] is False
        assert provider["token_issued"] is False
        assert provider["token_cache_enabled"] is False
        assert provider["adapter_order_call_performed"] is False
        assert provider["adapter_network_call_performed"] is False
        assert provider["credential_fields_exposed"] is False

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


def test_quality_summary_service_is_select_only():
    source = Path("backend/app/services/data_quality_summary_service.py").read_text(encoding="utf-8")

    for forbidden in (".add(", ".delete(", ".commit(", ".rollback(", "fetch_daily_ohlcv", "build_external_daily_provider"):
        assert forbidden not in source
