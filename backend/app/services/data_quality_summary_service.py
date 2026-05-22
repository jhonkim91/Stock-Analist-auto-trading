from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

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
from backend.app.services.market_data_import_service import DataSourceService

DAILY_SOURCE_PROVIDER_TYPES = {"csv", "external", "external_market_data"}
REFERENCE_PROVIDER_TYPES = {"krx_market_reference", "krx_symbol_master", "krx_trading_calendar", "krx_corporate_actions"}
DUPLICATE_CHECK_CODES = ("DUPLICATE_IN_BATCH", "DUPLICATE_IN_DATABASE")


class DataQualitySummaryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.source_service = DataSourceService()

    def summary(self, *, market: str = "KR", venue: str = "KRX", lookback_trading_dates: int = 30) -> dict[str, object]:
        """데이터 freshness/quality/safety 상태를 SELECT 기반으로 요약한다."""
        normalized_market = market.strip() or "KR"
        normalized_venue = venue.strip() or "KRX"
        bounded_lookback = max(1, min(int(lookback_trading_dates), 252))
        latest_trade_date = self._latest_trade_date(normalized_venue)
        row_counts = self._row_counts(normalized_market, normalized_venue)
        return {
            "market": normalized_market,
            "venue": normalized_venue,
            "latest_trade_date": latest_trade_date.isoformat() if latest_trade_date else None,
            "row_counts": row_counts,
            "source_freshness": self._source_freshness(latest_trade_date=latest_trade_date),
            "missing_rows": self._missing_rows(
                market=normalized_market,
                venue=normalized_venue,
                latest_trade_date=latest_trade_date,
                lookback_trading_dates=bounded_lookback,
            ),
            "duplicate_summary": self._duplicate_summary(normalized_venue),
            "quality_counts": self._quality_counts(),
            "safety_counts": self._safety_counts(),
        }

    def _latest_trade_date(self, venue: str) -> date | None:
        return self.db.scalar(select(func.max(DailyOhlcv.trade_date)).where(DailyOhlcv.venue == venue))

    def _row_counts(self, market: str, venue: str) -> dict[str, int]:
        return {
            "daily_ohlcv": self._count(select(func.count()).select_from(DailyOhlcv).where(DailyOhlcv.venue == venue)),
            "symbol_master": self._count(
                select(func.count())
                .select_from(SymbolMaster)
                .where(SymbolMaster.market == market, SymbolMaster.exchange == venue)
            ),
            "active_symbols": self._count(
                select(func.count())
                .select_from(SymbolMaster)
                .where(SymbolMaster.market == market, SymbolMaster.exchange == venue, SymbolMaster.is_active.is_(True))
            ),
            "trading_calendar": self._count(
                select(func.count()).select_from(TradingCalendar).where(TradingCalendar.market == market)
            ),
            "import_runs": self._count(select(func.count()).select_from(ImportRun)),
            "confirmed_import_runs": self._count(
                select(func.count()).select_from(ImportRun).where(ImportRun.status == "confirmed")
            ),
            "data_quality_checks": self._count(select(func.count()).select_from(DataQualityCheck)),
        }

    def _source_freshness(self, *, latest_trade_date: date | None) -> list[dict[str, object]]:
        summaries: list[dict[str, object]] = []
        for source in self._summary_sources():
            source_id = str(source["source_id"])
            provider_type = str(source["provider_type"])
            asset_scope = list(source.get("asset_scope") or [])
            enabled = bool(source.get("enabled"))
            read_only_capable = bool(source.get("read_only_capable"))
            daily_source = self._is_daily_source(provider_type, asset_scope)
            reference_source = read_only_capable and not daily_source
            latest_run = self._latest_confirmed_run(source_id)
            latest_confirmed_trade_date = self._confirmed_trade_date(latest_run)

            freshness_status = "UNKNOWN"
            reason_code = "UNKNOWN"
            trading_date_lag: int | None = None
            if not enabled:
                freshness_status = "DISABLED"
                reason_code = "SOURCE_DISABLED"
            elif reference_source and latest_run is None:
                freshness_status = "NOT_APPLICABLE"
                reason_code = "REFERENCE_SOURCE_NO_CONFIRMED_RUN_REQUIRED"
            elif daily_source and latest_run is None:
                freshness_status = "NO_CONFIRMED_RUN"
                reason_code = "NO_CONFIRMED_RUN"
            elif latest_trade_date is None or latest_confirmed_trade_date is None:
                freshness_status = "UNKNOWN"
                reason_code = "TRADE_DATE_UNKNOWN"
            else:
                trading_date_lag = max((latest_trade_date - latest_confirmed_trade_date).days, 0)
                freshness_status = "CURRENT" if trading_date_lag == 0 else "STALE"
                reason_code = "LATEST_TRADE_DATE_MATCH" if trading_date_lag == 0 else "LATEST_CONFIRMED_RUN_BEHIND"

            summaries.append(
                {
                    "source_id": source_id,
                    "provider_type": provider_type,
                    "provider_name": source["provider_name"],
                    "source_kind": self._source_kind(provider_type, asset_scope, read_only_capable),
                    "enabled": enabled,
                    "read_only_enabled": bool(source.get("read_only_enabled")),
                    "network_enabled": bool(source.get("network_enabled")),
                    "asset_scope": asset_scope,
                    "status": "enabled" if enabled else "disabled",
                    "freshness_status": freshness_status,
                    "reason_code": reason_code,
                    "latest_confirmed_at": latest_run.confirmed_at.isoformat() if latest_run and latest_run.confirmed_at else None,
                    "latest_confirmed_trade_date": latest_confirmed_trade_date.isoformat()
                    if latest_confirmed_trade_date
                    else None,
                    "trading_date_lag": trading_date_lag,
                }
            )
        return summaries

    def _summary_sources(self) -> list[dict[str, object]]:
        sources = self.source_service.list_sources()
        return [
            source
            for source in sources
            if str(source["provider_type"]) in DAILY_SOURCE_PROVIDER_TYPES
            or bool(source.get("read_only_capable"))
            or str(source["provider_type"]) in REFERENCE_PROVIDER_TYPES
        ]

    @staticmethod
    def _is_daily_source(provider_type: str, asset_scope: list[object]) -> bool:
        return provider_type in DAILY_SOURCE_PROVIDER_TYPES or "daily_ohlcv" in {str(item) for item in asset_scope}

    @staticmethod
    def _source_kind(provider_type: str, asset_scope: list[object], read_only_capable: bool) -> str:
        if provider_type == "csv":
            return "csv_daily_ohlcv"
        if provider_type in {"external", "external_market_data"}:
            return "external_daily_ohlcv"
        if read_only_capable and "daily_ohlcv" in {str(item) for item in asset_scope}:
            return "read_only_daily_ohlcv"
        if read_only_capable:
            return "read_only_reference"
        return provider_type

    def _latest_confirmed_run(self, source_id: str) -> ImportRun | None:
        return self.db.scalar(
            select(ImportRun)
            .where(ImportRun.source_id == source_id, ImportRun.status == "confirmed")
            .order_by(desc(ImportRun.confirmed_at), desc(ImportRun.created_at))
            .limit(1)
        )

    def _confirmed_trade_date(self, run: ImportRun | None) -> date | None:
        if run is None:
            return None
        dates: list[date] = []
        for row in self._loads_list(run.staged_rows_json):
            raw_date = row.get("trade_date") if isinstance(row, dict) else None
            parsed = self._parse_date(raw_date)
            if parsed is not None:
                dates.append(parsed)
        if dates:
            return max(dates)
        metadata = self._loads_dict(run.provider_metadata_json)
        return self._parse_date(metadata.get("end_date"))

    def _missing_rows(
        self,
        *,
        market: str,
        venue: str,
        latest_trade_date: date | None,
        lookback_trading_dates: int,
    ) -> dict[str, object]:
        date_basis, trading_dates = self._date_universe(market, venue, lookback_trading_dates)
        active_symbols = self._active_symbols(market, venue)
        actual_keys = self._actual_daily_keys(venue, trading_dates, active_symbols)
        expected_rows = len(trading_dates) * len(active_symbols)
        actual_rows = len(actual_keys)
        missing_rows_estimate = max(expected_rows - actual_rows, 0)
        latest_missing_sample = self._latest_missing_symbol_sample(
            venue=venue,
            latest_trade_date=latest_trade_date,
            active_symbols=active_symbols,
        )
        return {
            "basis": date_basis,
            "lookback_trading_dates": lookback_trading_dates,
            "date_count": len(trading_dates),
            "active_symbol_count": len(active_symbols),
            "expected_rows": expected_rows,
            "actual_rows": actual_rows,
            "missing_rows_estimate": missing_rows_estimate,
            "coverage_ratio": round(actual_rows / expected_rows, 6) if expected_rows else None,
            "latest_trade_date_missing_symbol_count": len(latest_missing_sample["all_missing_symbols"]),
            "missing_symbol_sample": latest_missing_sample["sample"],
        }

    def _date_universe(self, market: str, venue: str, lookback_trading_dates: int) -> tuple[str, list[date]]:
        calendar_dates = list(
            self.db.scalars(
                select(TradingCalendar.calendar_date)
                .where(TradingCalendar.market == market, TradingCalendar.is_open.is_(True))
                .order_by(desc(TradingCalendar.calendar_date))
                .limit(lookback_trading_dates)
            ).all()
        )
        if calendar_dates:
            return "trading_calendar", sorted(calendar_dates)
        observed_dates = list(
            self.db.scalars(
                select(DailyOhlcv.trade_date)
                .where(DailyOhlcv.venue == venue)
                .group_by(DailyOhlcv.trade_date)
                .order_by(desc(DailyOhlcv.trade_date))
                .limit(lookback_trading_dates)
            ).all()
        )
        return "observed_daily_ohlcv", sorted(observed_dates)

    def _active_symbols(self, market: str, venue: str) -> list[str]:
        return list(
            self.db.scalars(
                select(SymbolMaster.symbol)
                .where(SymbolMaster.market == market, SymbolMaster.exchange == venue, SymbolMaster.is_active.is_(True))
                .order_by(SymbolMaster.symbol)
            ).all()
        )

    def _actual_daily_keys(self, venue: str, trading_dates: list[date], active_symbols: list[str]) -> set[tuple[date, str]]:
        if not trading_dates or not active_symbols:
            return set()
        rows = self.db.execute(
            select(DailyOhlcv.trade_date, DailyOhlcv.symbol)
            .where(
                DailyOhlcv.venue == venue,
                DailyOhlcv.trade_date.in_(trading_dates),
                DailyOhlcv.symbol.in_(active_symbols),
            )
            .group_by(DailyOhlcv.trade_date, DailyOhlcv.symbol)
        ).all()
        return {(row.trade_date, row.symbol) for row in rows}

    def _latest_missing_symbol_sample(
        self,
        *,
        venue: str,
        latest_trade_date: date | None,
        active_symbols: list[str],
    ) -> dict[str, object]:
        if latest_trade_date is None or not active_symbols:
            return {"all_missing_symbols": [], "sample": []}
        present_symbols = set(
            self.db.scalars(
                select(DailyOhlcv.symbol).where(DailyOhlcv.venue == venue, DailyOhlcv.trade_date == latest_trade_date)
            ).all()
        )
        missing_symbols = [symbol for symbol in active_symbols if symbol not in present_symbols]
        return {"all_missing_symbols": missing_symbols, "sample": missing_symbols[:20]}

    def _duplicate_summary(self, venue: str) -> dict[str, object]:
        grouped_rows = self.db.execute(
            select(
                DailyOhlcv.trade_date,
                DailyOhlcv.symbol,
                DailyOhlcv.venue,
                func.count(DailyOhlcv.id).label("row_count"),
            )
            .where(DailyOhlcv.venue == venue)
            .group_by(DailyOhlcv.trade_date, DailyOhlcv.symbol, DailyOhlcv.venue)
            .having(func.count(DailyOhlcv.id) > 1)
            .order_by(desc(func.count(DailyOhlcv.id)), desc(DailyOhlcv.trade_date), DailyOhlcv.symbol)
        ).all()
        duplicate_rows = sum(int(row.row_count) - 1 for row in grouped_rows)
        quality_code_counts = {
            code: self._count(
                select(func.count()).select_from(DataQualityCheck).where(DataQualityCheck.check_code == code)
            )
            for code in DUPLICATE_CHECK_CODES
        }
        return {
            "physical_duplicate_groups": len(grouped_rows),
            "physical_duplicate_rows": duplicate_rows,
            "physical_duplicate_sample": [
                {
                    "trade_date": row.trade_date.isoformat(),
                    "symbol": row.symbol,
                    "venue": row.venue,
                    "row_count": int(row.row_count),
                }
                for row in grouped_rows[:20]
            ],
            "quality_duplicate_code_counts": quality_code_counts,
        }

    def _quality_counts(self) -> dict[str, object]:
        severity_counts = {"error": 0, "warning": 0, "info": 0}
        for severity, count in self.db.execute(
            select(DataQualityCheck.severity, func.count(DataQualityCheck.id)).group_by(DataQualityCheck.severity)
        ).all():
            severity_counts[str(severity)] = int(count)
        check_count = func.count(DataQualityCheck.id).label("check_count")
        top_codes = [
            {"check_code": check_code, "count": int(count)}
            for check_code, count in self.db.execute(
                select(DataQualityCheck.check_code, check_count)
                .group_by(DataQualityCheck.check_code)
                .order_by(desc(check_count), DataQualityCheck.check_code)
                .limit(10)
            ).all()
        ]
        return {
            "total": sum(severity_counts.values()),
            "by_severity": severity_counts,
            "top_check_codes": top_codes,
        }

    def _safety_counts(self) -> dict[str, object]:
        return {
            "orders_count": self._count(select(func.count()).select_from(Order)),
            "paper_orders_count": self._count(select(func.count()).select_from(PaperOrder)),
            "paper_fills_count": self._count(select(func.count()).select_from(PaperFill)),
            "paper_positions_count": self._count(select(func.count()).select_from(PaperPosition)),
            "paper_audit_events_count": self._count(select(func.count()).select_from(PaperAuditEvent)),
            "token_issued": False,
            "token_cache_enabled": False,
            "network_call_performed": False,
            "adapter_order_call_performed": False,
            "adapter_network_call_performed": False,
        }

    def _count(self, stmt: Any) -> int:
        return int(self.db.scalar(stmt) or 0)

    @staticmethod
    def _loads_list(payload: str) -> list[object]:
        try:
            loaded = json.loads(payload or "[]")
        except json.JSONDecodeError:
            return []
        return loaded if isinstance(loaded, list) else []

    @staticmethod
    def _loads_dict(payload: str) -> dict[str, object]:
        try:
            loaded = json.loads(payload or "{}")
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}

    @staticmethod
    def _parse_date(value: object) -> date | None:
        if isinstance(value, date):
            return value
        if not isinstance(value, str) or not value:
            return None
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
