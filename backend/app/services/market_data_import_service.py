from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from io import BytesIO
from uuid import uuid4

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.config import get_config
from backend.app.models.tables import DailyOhlcv, DataQualityCheck, ExternalSymbolMapping, ImportRun, SymbolMaster, TradingCalendar
from backend.app.services.data_providers import (
    ExternalDailyRequest,
    ExternalProviderError,
    ExternalProviderPartialResponseError,
    ExternalProviderRateLimitError,
    ExternalProviderTimeoutError,
    build_external_daily_provider,
)

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_ROWS = 10000
PREVIEW_ROW_LIMIT = 100
CONFIRMABLE_STATUSES = {"validated"}
TERMINAL_STATUSES = {"confirmed"}
STATUS_CANDIDATES = {"validated", "confirmed", "failed", "rejected", "expired"}
SEVERITIES = {"error", "warning", "info"}
EXTERNAL_PROVIDER_TYPES = {"external", "external_market_data", "broker_data"}


class ImportRunNotFoundError(ValueError):
    """import run을 찾을 수 없을 때 사용한다."""


class ImportRunConflictError(ValueError):
    """상태 전이 충돌이 있을 때 사용한다."""


class ImportRunBadRequestError(ValueError):
    """요청은 유효하지만 confirm할 수 없는 run일 때 사용한다."""


@dataclass(frozen=True)
class QualityIssue:
    row_number: int | None
    symbol: str | None
    trade_date: date | None
    field: str | None
    check_code: str
    severity: str
    message: str


class DataSourceService:
    def list_sources(self) -> list[dict[str, object]]:
        """backend/config/data_sources.yaml의 source 설정을 반환한다."""
        config = get_config("data_sources")
        sources = config.get("sources", [])
        if not isinstance(sources, list):
            raise ValueError("data_sources.yaml sources 형식이 올바르지 않습니다.")
        return [self._normalize_source(source) for source in sources]

    def get_source(self, source_id: str) -> dict[str, object]:
        """source_id에 해당하는 source 설정을 조회한다."""
        for source in self.list_sources():
            if source["source_id"] == source_id:
                if not bool(source["enabled"]):
                    raise ValueError(f"비활성화된 data source입니다: {source_id}")
                return source
        raise ValueError(f"존재하지 않는 source_id입니다: {source_id}")

    def list_external_sources(self) -> list[dict[str, object]]:
        """external provider 후보 source를 enabled 여부와 무관하게 반환한다."""
        return [source for source in self.list_sources() if str(source["provider_type"]) in EXTERNAL_PROVIDER_TYPES]

    @staticmethod
    def _normalize_source(source: object) -> dict[str, object]:
        if not isinstance(source, dict):
            raise ValueError("data source 항목 형식이 올바르지 않습니다.")
        source_id = str(source.get("source_id", "")).strip()
        provider_type = str(source.get("provider_type", "")).strip()
        if not source_id or not provider_type:
            raise ValueError("data source에는 source_id와 provider_type이 필요합니다.")
        return {
            "source_id": source_id,
            "provider_type": provider_type,
            "provider_name": str(source.get("provider_name") or provider_type).strip() or provider_type,
            "enabled": bool(source.get("enabled", False)),
            "network_enabled": bool(source.get("network_enabled", False)),
            "manual_preview_only": bool(source.get("manual_preview_only", False)),
            "requires_api_key": bool(source.get("requires_api_key", False)),
            "read_only_enabled": bool(source.get("read_only_enabled", False)),
            "paper_trading_enabled": bool(source.get("paper_trading_enabled", False)),
            "live_trading_enabled": bool(source.get("live_trading_enabled", False)),
            "websocket_enabled": bool(source.get("websocket_enabled", False)),
            "supported_markets": list(source.get("supported_markets") or []),
            "market": str(source.get("market") or "KRX").strip() or "KRX",
            "venue": str(source.get("venue") or "KRX").strip() or "KRX",
            "timezone": str(source.get("timezone") or "Asia/Seoul").strip() or "Asia/Seoul",
            "zero_volume_policy": str(source.get("zero_volume_policy") or "warn").strip() or "warn",
            "unknown_symbol_policy": str(source.get("unknown_symbol_policy") or "warn_and_create_on_confirm").strip()
            or "warn_and_create_on_confirm",
            "max_rows": int(source.get("max_rows") or DEFAULT_MAX_ROWS),
            "max_date_range_days": int(source.get("max_date_range_days") or 0),
            "timeout_seconds": int(source.get("timeout_seconds") or 0),
            "retry_count": int(source.get("retry_count") or 0),
        }


class MarketDataImportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.source_service = DataSourceService()

    def list_sources(self) -> list[dict[str, object]]:
        """설정된 data source 목록을 반환한다."""
        return self.source_service.list_sources()

    def list_external_providers(self) -> list[dict[str, object]]:
        """provider-neutral external data source 목록을 반환한다."""
        return self.source_service.list_external_sources()

    def preview_external_daily_ohlcv(
        self,
        *,
        source_id: str,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, object]:
        """외부 daily OHLCV를 fetch/normalize/validate하고 preview run만 기록한다."""
        source = self.source_service.get_source(source_id)
        if str(source["provider_type"]) not in EXTERNAL_PROVIDER_TYPES:
            raise ValueError("external preview에는 external provider source만 사용할 수 있습니다.")
        internal_symbol = symbol.strip()
        if not internal_symbol:
            raise ValueError("symbol 값이 필요합니다.")
        if start_date > end_date:
            raise ValueError("start_date는 end_date보다 늦을 수 없습니다.")

        metadata = self._external_metadata(
            source=source,
            internal_symbol=internal_symbol,
            provider_symbol=None,
            start_date=start_date,
            end_date=end_date,
            raw_row_count=0,
            normalized_row_count=0,
            raw_hash="",
            fetch_started_at=None,
            fetch_finished_at=None,
        )
        max_date_range_days = int(source.get("max_date_range_days") or 0)
        if max_date_range_days and (end_date - start_date).days > max_date_range_days:
            issue = self._issue(
                None,
                internal_symbol,
                None,
                "date_range",
                "DATE_RANGE_TOO_LARGE",
                "error",
                f"외부 fetch date range는 {max_date_range_days}일 이하여야 합니다.",
            )
            return self._create_validation_run(
                run_id=f"ext-{uuid4().hex[:12]}",
                source=source,
                original_filename="external-daily-ohlcv",
                file_hash=hashlib.sha256(b"date-range-error").hexdigest(),
                total_rows=0,
                staged_rows=[],
                issues=[issue],
                provider_metadata=metadata,
            )

        mapping = self.db.scalar(
            select(ExternalSymbolMapping).where(
                ExternalSymbolMapping.source_id == source_id,
                ExternalSymbolMapping.symbol == internal_symbol,
            )
        )
        if mapping is None:
            metadata["raw_hash"] = hashlib.sha256(f"{source_id}:{internal_symbol}:missing-mapping".encode()).hexdigest()
            issue = self._issue(
                None,
                internal_symbol,
                None,
                "symbol",
                "SYMBOL_MAPPING_FAILED",
                "error",
                "external_symbol_mapping에 provider symbol 매핑이 없습니다.",
            )
            return self._create_validation_run(
                run_id=f"ext-{uuid4().hex[:12]}",
                source=source,
                original_filename="external-daily-ohlcv",
                file_hash=str(metadata["raw_hash"]),
                total_rows=0,
                staged_rows=[],
                issues=[issue],
                provider_metadata=metadata,
            )

        provider_symbol = mapping.external_symbol
        fetch_started_at = datetime.now(UTC)
        request = ExternalDailyRequest(
            source_id=source_id,
            provider_name=str(source.get("provider_name") or ""),
            provider_symbol=provider_symbol,
            internal_symbol=internal_symbol,
            start_date=start_date,
            end_date=end_date,
            source=source,
        )
        provider = build_external_daily_provider(source)
        issues: list[QualityIssue] = []
        raw_rows: list[dict[str, object]] = []
        normalized = pd.DataFrame()
        try:
            rate_limit = provider.check_rate_limit(request)
            if not rate_limit.allowed:
                raise ExternalProviderRateLimitError(rate_limit.reason or "provider rate limit을 초과했습니다.")
            raw = provider.fetch_daily_ohlcv(request)
            raw_rows = raw.rows
            for raw_issue in provider.validate_raw_response(raw, request):
                issues.append(self._external_issue(raw_issue, internal_symbol))
            if not any(issue.severity == "error" for issue in issues):
                normalized = provider.normalize_ohlcv(raw, request)
        except ExternalProviderTimeoutError as exc:
            issues.append(self._issue(None, internal_symbol, None, "provider", "PROVIDER_TIMEOUT", "error", str(exc)))
        except ExternalProviderPartialResponseError as exc:
            issues.append(self._issue(None, internal_symbol, None, "provider", "PROVIDER_PARTIAL_RESPONSE", "error", str(exc)))
        except ExternalProviderRateLimitError as exc:
            issues.append(self._issue(None, internal_symbol, None, "provider", "RATE_LIMIT_EXCEEDED", "error", str(exc)))
        except ExternalProviderError as exc:
            issues.append(self._issue(None, internal_symbol, None, "provider", "PROVIDER_RESPONSE_SCHEMA_MISMATCH", "error", str(exc)))

        fetch_finished_at = datetime.now(UTC)
        raw_hash = hashlib.sha256(json.dumps(raw_rows, ensure_ascii=False, default=str).encode()).hexdigest()
        metadata = self._external_metadata(
            source=source,
            internal_symbol=internal_symbol,
            provider_symbol=provider_symbol,
            start_date=start_date,
            end_date=end_date,
            raw_row_count=len(raw_rows),
            normalized_row_count=int(len(normalized)),
            raw_hash=raw_hash,
            fetch_started_at=fetch_started_at,
            fetch_finished_at=fetch_finished_at,
        )
        if raw_rows and len(raw_rows) != int(len(normalized)) and not any(issue.severity == "error" for issue in issues):
            issues.append(
                self._issue(
                    None,
                    internal_symbol,
                    None,
                    "provider_response",
                    "PROVIDER_ROW_COUNT_MISMATCH",
                    "warning",
                    "provider raw row 수와 normalized row 수가 다릅니다.",
                )
            )
        if not normalized.empty and not any(issue.severity == "error" for issue in issues):
            latest_normalized_date = pd.to_datetime(normalized["trade_date"]).max().date()
            if latest_normalized_date < end_date:
                issues.append(
                    self._issue(
                        None,
                        internal_symbol,
                        latest_normalized_date,
                        "trade_date",
                        "STALE_DATA",
                        "warning",
                        "provider 최신 normalized date가 요청 end_date보다 오래되었습니다.",
                    )
                )

        staged_rows: list[dict[str, object]] = []
        total_rows = int(metadata["raw_row_count"])
        if not any(issue.severity == "error" for issue in issues):
            max_rows = int(source.get("max_rows") or DEFAULT_MAX_ROWS)
            if len(normalized) > max_rows:
                issues.append(
                    self._issue(
                        None,
                        internal_symbol,
                        None,
                        "provider_response",
                        "MISSING_REQUIRED_VALUE",
                        "error",
                        f"external normalized row 수는 {max_rows:,}개 이하여야 합니다.",
                    )
                )
            else:
                staged_rows = self._validate_frame(normalized, source, issues, enforce_source_match=True)

        return self._create_validation_run(
            run_id=f"ext-{uuid4().hex[:12]}",
            source=source,
            original_filename="external-daily-ohlcv",
            file_hash=raw_hash,
            total_rows=total_rows,
            staged_rows=staged_rows,
            issues=issues,
            provider_metadata=metadata,
        )

    def validate_csv(
        self,
        *,
        content: bytes,
        original_filename: str,
        source_id: str,
        enforce_source_match: bool = True,
    ) -> dict[str, object]:
        """CSV를 검증하고 import_runs/data_quality_checks에 preview 결과만 저장한다."""
        source = self.source_service.get_source(source_id)
        if str(source["provider_type"]) != "csv":
            raise ValueError("CSV 검증에는 provider_type=csv source만 사용할 수 있습니다.")

        run_id = f"imp-{uuid4().hex[:12]}"
        file_hash = hashlib.sha256(content).hexdigest()
        issues: list[QualityIssue] = []
        staged_rows: list[dict[str, object]] = []
        total_rows = 0

        if len(content) > MAX_FILE_SIZE_BYTES:
            issues.append(
                QualityIssue(
                    row_number=None,
                    symbol=None,
                    trade_date=None,
                    field="file",
                    check_code="MISSING_REQUIRED_VALUE",
                    severity="error",
                    message="CSV 파일 크기는 10MB 이하여야 합니다.",
                )
            )
        else:
            try:
                df = pd.read_csv(BytesIO(content))
            except Exception as exc:  # noqa: BLE001
                issues.append(
                    QualityIssue(
                        row_number=None,
                        symbol=None,
                        trade_date=None,
                        field="file",
                        check_code="MISSING_REQUIRED_VALUE",
                        severity="error",
                        message=f"CSV 파일을 읽을 수 없습니다: {exc}",
                    )
                )
                df = pd.DataFrame()

            total_rows = int(len(df))
            max_rows = int(source.get("max_rows") or DEFAULT_MAX_ROWS)
            if total_rows > max_rows:
                issues.append(
                    QualityIssue(
                        row_number=None,
                        symbol=None,
                        trade_date=None,
                        field="file",
                        check_code="MISSING_REQUIRED_VALUE",
                        severity="error",
                        message=f"CSV row 수는 {max_rows:,}개 이하여야 합니다.",
                    )
                )
            else:
                staged_rows.extend(self._validate_frame(df, source, issues, enforce_source_match))

        return self._create_validation_run(
            run_id=run_id,
            source=source,
            original_filename=original_filename,
            file_hash=file_hash,
            total_rows=total_rows,
            staged_rows=staged_rows,
            issues=issues,
            provider_metadata={},
        )

    def legacy_direct_import_csv(self, content: bytes, original_filename: str = "legacy_daily_ohlcv.csv") -> dict[str, int]:
        """기존 direct import endpoint 호환을 위해 validate 후 즉시 confirm한다."""
        result = self.validate_csv(
            content=content,
            original_filename=original_filename,
            source_id="csv_krx",
            enforce_source_match=False,
        )
        if result["error_count"]:
            checks = self.list_quality_checks(run_id=str(result["run_id"]), severity="error")
            if any(check["check_code"] == "MISSING_REQUIRED_COLUMN" for check in checks):
                missing = ", ".join(str(check["field"]) for check in checks if check["check_code"] == "MISSING_REQUIRED_COLUMN")
                raise ValueError(f"CSV 필수 컬럼 누락: {missing}")
            messages = "; ".join(str(check["message"]) for check in checks)
            raise ValueError(f"CSV import 검증 실패: {messages}")
        confirmed = self.confirm_import(str(result["run_id"]), match_symbol_date_only=True)
        return {
            "inserted_count": int(confirmed["inserted_count"]),
            "updated_count": int(confirmed["updated_count"]),
            "skipped_count": int(confirmed["skipped_count"]),
            "error_count": int(confirmed["error_count"]),
            "inserted": int(confirmed["inserted_count"]),
            "updated": int(confirmed["updated_count"]),
        }

    def confirm_import(self, run_id: str, match_symbol_date_only: bool = False) -> dict[str, object]:
        """검증 완료된 staged rows를 transaction으로 daily_ohlcv에 반영한다."""
        run = self.db.get(ImportRun, run_id)
        if run is None:
            raise ImportRunNotFoundError("import run을 찾을 수 없습니다.")
        if run.status in TERMINAL_STATUSES:
            raise ImportRunConflictError("이미 confirmed 처리된 import run입니다.")
        if run.status not in CONFIRMABLE_STATUSES or not run.can_confirm:
            raise ImportRunBadRequestError("confirm할 수 없는 import run입니다.")

        source = self.source_service.get_source(run.source_id)
        staged_rows = json.loads(run.staged_rows_json or "[]")
        inserted_count = 0
        updated_count = 0
        pending_symbols: set[str] = set()
        try:
            for row in staged_rows:
                symbol = str(row["symbol"])
                venue = str(row["venue"])
                trade_date = date.fromisoformat(str(row["trade_date"]))

                symbol_row = self.db.get(SymbolMaster, symbol)
                if symbol_row is None and symbol not in pending_symbols:
                    self.db.add(
                        SymbolMaster(
                            symbol=symbol,
                            name=symbol,
                            asset_type="stock",
                            currency="KRW",
                            market=str(source.get("market") or "KRX"),
                            exchange=str(source.get("venue") or "KRX"),
                            sector="Unknown",
                            industry="",
                            is_active=True,
                        )
                    )
                    pending_symbols.add(symbol)

                if match_symbol_date_only:
                    existing = self.db.scalar(
                        select(DailyOhlcv)
                        .where(DailyOhlcv.trade_date == trade_date, DailyOhlcv.symbol == symbol)
                        .limit(1)
                    )
                else:
                    existing = self.db.scalar(
                        select(DailyOhlcv)
                        .where(DailyOhlcv.trade_date == trade_date, DailyOhlcv.symbol == symbol, DailyOhlcv.venue == venue)
                        .limit(1)
                    )
                payload = {
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "adj_close": float(row["adj_close"]),
                    "volume": int(row["volume"]),
                    "turnover_value": float(row["turnover_value"]),
                    "venue": venue,
                }
                if existing:
                    for key, value in payload.items():
                        setattr(existing, key, value)
                    updated_count += 1
                else:
                    self.db.add(DailyOhlcv(trade_date=trade_date, symbol=symbol, **payload))
                    inserted_count += 1

            run.status = "confirmed"
            run.can_confirm = False
            run.inserted_count = inserted_count
            run.updated_count = updated_count
            run.skipped_count = 0
            run.confirmed_at = datetime.now(UTC)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get_import_run(run_id)

    def confirm_external_import(self, run_id: str) -> dict[str, object]:
        """external provider preview run만 confirm하도록 제한한다."""
        run = self.db.get(ImportRun, run_id)
        if run is None:
            raise ImportRunNotFoundError("import run을 찾을 수 없습니다.")
        if run.provider_type not in EXTERNAL_PROVIDER_TYPES:
            raise ImportRunBadRequestError("external import run만 confirm할 수 있습니다.")
        return self.confirm_import(run_id)

    def list_import_runs(self, limit: int = 20, provider_types: set[str] | None = None) -> list[dict[str, object]]:
        """최근 import run 목록을 반환한다."""
        stmt = select(ImportRun)
        if provider_types:
            stmt = stmt.where(ImportRun.provider_type.in_(provider_types))
        rows = list(self.db.scalars(stmt.order_by(ImportRun.created_at.desc()).limit(limit)).all())
        return [self._serialize_run(row, include_rows=False) for row in rows]

    def get_import_run(self, run_id: str) -> dict[str, object]:
        """단일 import run 상세를 반환한다."""
        run = self.db.get(ImportRun, run_id)
        if run is None:
            raise ImportRunNotFoundError("import run을 찾을 수 없습니다.")
        return self._serialize_run(run, include_rows=True)

    def list_quality_checks(
        self,
        run_id: str | None = None,
        severity: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, object]]:
        """data quality check 목록을 반환한다."""
        stmt = select(DataQualityCheck)
        if run_id:
            stmt = stmt.where(DataQualityCheck.run_id == run_id)
        if severity:
            stmt = stmt.where(DataQualityCheck.severity == severity)
        rows = list(self.db.scalars(stmt.order_by(DataQualityCheck.id).limit(limit)).all())
        return [self._serialize_check(row) for row in rows]

    def _create_validation_run(
        self,
        *,
        run_id: str,
        source: dict[str, object],
        original_filename: str,
        file_hash: str,
        total_rows: int,
        staged_rows: list[dict[str, object]],
        issues: list[QualityIssue],
        provider_metadata: dict[str, object],
    ) -> dict[str, object]:
        counts = self._issue_counts(issues)
        can_confirm = counts["error_count"] == 0
        status = "validated" if can_confirm else "failed"
        run = ImportRun(
            run_id=run_id,
            source_id=str(source["source_id"]),
            provider_type=str(source["provider_type"]),
            original_filename=original_filename,
            file_hash=file_hash,
            status=status,
            can_confirm=can_confirm,
            total_rows=total_rows,
            valid_rows=len(staged_rows),
            error_count=counts["error_count"],
            warning_count=counts["warning_count"],
            info_count=counts["info_count"],
            inserted_count=0,
            updated_count=0,
            skipped_count=0,
            staged_rows_json=json.dumps(staged_rows, ensure_ascii=False, default=str),
            preview_rows_json=json.dumps(staged_rows[:PREVIEW_ROW_LIMIT], ensure_ascii=False, default=str),
            source_config_snapshot_json=json.dumps(source, ensure_ascii=False, default=str),
            provider_metadata_json=json.dumps(provider_metadata, ensure_ascii=False, default=str),
        )
        self.db.add(run)
        self.db.add_all([self._issue_to_model(run_id, issue) for issue in issues])
        self.db.commit()
        return self.get_import_run(run_id)

    @staticmethod
    def _external_metadata(
        *,
        source: dict[str, object],
        internal_symbol: str,
        provider_symbol: str | None,
        start_date: date,
        end_date: date,
        raw_row_count: int,
        normalized_row_count: int,
        raw_hash: str,
        fetch_started_at: datetime | None,
        fetch_finished_at: datetime | None,
    ) -> dict[str, object]:
        return {
            "provider_name": source.get("provider_name"),
            "source_id": source.get("source_id"),
            "provider_symbol": provider_symbol,
            "internal_symbol": internal_symbol,
            "raw_row_count": raw_row_count,
            "normalized_row_count": normalized_row_count,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "timezone": source.get("timezone"),
            "raw_hash": raw_hash,
            "network_enabled": bool(source.get("network_enabled")),
            "fetch_started_at": fetch_started_at.isoformat() if fetch_started_at else None,
            "fetch_finished_at": fetch_finished_at.isoformat() if fetch_finished_at else None,
        }

    def _external_issue(self, raw_issue: dict[str, object], symbol: str) -> QualityIssue:
        return self._issue(
            None,
            symbol,
            None,
            str(raw_issue.get("field") or "provider_response"),
            str(raw_issue.get("check_code") or "PROVIDER_RESPONSE_SCHEMA_MISMATCH"),
            str(raw_issue.get("severity") or "error"),
            str(raw_issue.get("message") or "provider 응답 검증 실패"),
        )

    def _validate_frame(
        self,
        df: pd.DataFrame,
        source: dict[str, object],
        issues: list[QualityIssue],
        enforce_source_match: bool,
    ) -> list[dict[str, object]]:
        required = {"trade_date", "symbol", "open", "high", "low", "close", "volume"}
        missing = sorted(required - set(df.columns))
        for column in missing:
            issues.append(
                QualityIssue(
                    row_number=None,
                    symbol=None,
                    trade_date=None,
                    field=column,
                    check_code="MISSING_REQUIRED_COLUMN",
                    severity="error",
                    message=f"CSV 필수 컬럼 누락: {column}",
                )
            )
        if missing:
            return []

        staged_rows: list[dict[str, object]] = []
        seen_keys: set[tuple[str, date, str]] = set()
        for index, row in enumerate(df.to_dict("records"), start=2):
            row_issues: list[QualityIssue] = []
            symbol = self._string_value(row.get("symbol"))
            parsed_date: date | None = None
            if not symbol:
                row_issues.append(self._issue(index, None, None, "symbol", "MISSING_REQUIRED_VALUE", "error", "symbol 값이 비어 있습니다."))

            raw_date = row.get("trade_date")
            if self._is_missing(raw_date):
                row_issues.append(self._issue(index, symbol, None, "trade_date", "MISSING_REQUIRED_VALUE", "error", "trade_date 값이 비어 있습니다."))
            else:
                try:
                    parsed_date = pd.Timestamp(raw_date).date()
                except Exception:  # noqa: BLE001
                    row_issues.append(self._issue(index, symbol, None, "trade_date", "DATE_PARSE_FAILED", "error", "trade_date 파싱 실패"))

            market = self._string_value(row.get("market")) or str(source.get("market") or "KRX")
            venue = self._string_value(row.get("venue")) or str(source.get("venue") or "KRX")
            provider = self._string_value(row.get("provider")) or str(source.get("provider_type") or "csv")
            if not enforce_source_match and "venue" not in row and "market" in row and self._string_value(row.get("market")):
                venue = self._string_value(row.get("market")) or venue

            if enforce_source_match:
                source_provider = str(source.get("provider_type") or "csv")
                source_market = str(source.get("market") or "KRX")
                source_venue = str(source.get("venue") or "KRX")
                if provider != source_provider:
                    row_issues.append(self._issue(index, symbol, parsed_date, "provider", "PROVIDER_MISMATCH", "error", "CSV provider가 source 설정과 다릅니다."))
                if market != source_market:
                    row_issues.append(self._issue(index, symbol, parsed_date, "market", "PROVIDER_MISMATCH", "error", "CSV market이 source 설정과 다릅니다."))
                if venue != source_venue:
                    row_issues.append(self._issue(index, symbol, parsed_date, "venue", "PROVIDER_MISMATCH", "error", "CSV venue가 source 설정과 다릅니다."))

            numeric = self._parse_numeric_fields(row, index, symbol, parsed_date, row_issues)
            if parsed_date is not None:
                if parsed_date.weekday() >= 5:
                    row_issues.append(self._issue(index, symbol, parsed_date, "trade_date", "WEEKEND_DATE", "error", "주말 날짜는 daily OHLCV import 대상이 아닙니다."))
                elif not self._calendar_known(market, parsed_date):
                    row_issues.append(self._issue(index, symbol, parsed_date, "trade_date", "CALENDAR_UNKNOWN_DATE", "info", "trading_calendar에 등록되지 않은 평일입니다."))

            if symbol and self.db.get(SymbolMaster, symbol) is None:
                row_issues.append(self._issue(index, symbol, parsed_date, "symbol", "UNKNOWN_SYMBOL", "warning", "symbol_master에 없는 symbol입니다. confirm 시 기본값으로 생성됩니다."))

            if parsed_date is not None and symbol:
                key = (symbol, parsed_date, venue)
                if key in seen_keys:
                    row_issues.append(self._issue(index, symbol, parsed_date, "symbol", "DUPLICATE_IN_BATCH", "error", "CSV 내부에 동일 symbol/trade_date/venue row가 중복되었습니다."))
                seen_keys.add(key)
                existing_count = int(
                    self.db.scalar(
                        select(func.count())
                        .select_from(DailyOhlcv)
                        .where(DailyOhlcv.symbol == symbol, DailyOhlcv.trade_date == parsed_date, DailyOhlcv.venue == venue)
                    )
                    or 0
                )
                if existing_count:
                    row_issues.append(self._issue(index, symbol, parsed_date, "symbol", "DUPLICATE_IN_DATABASE", "info", "기존 daily_ohlcv row가 있어 confirm 시 update됩니다."))

            row_errors = [issue for issue in row_issues if issue.severity == "error"]
            issues.extend(row_issues)
            if not row_errors and parsed_date is not None and symbol and numeric is not None:
                quality_flags = [issue.check_code for issue in row_issues if issue.severity != "error"]
                staged_rows.append(
                    {
                        "row_number": index,
                        "trade_date": parsed_date.isoformat(),
                        "symbol": symbol,
                        "open": numeric["open"],
                        "high": numeric["high"],
                        "low": numeric["low"],
                        "close": numeric["close"],
                        "adj_close": numeric["adj_close"],
                        "volume": numeric["volume"],
                        "turnover_value": numeric["turnover_value"],
                        "market": market,
                        "venue": venue,
                        "provider": provider,
                        "quality_flags": quality_flags,
                    }
                )
        return staged_rows

    def _parse_numeric_fields(
        self,
        row: dict[str, object],
        row_number: int,
        symbol: str | None,
        trade_date: date | None,
        issues: list[QualityIssue],
    ) -> dict[str, float | int] | None:
        values: dict[str, float | int] = {}
        for field in ("open", "high", "low", "close"):
            raw_value = row.get(field)
            if self._is_missing(raw_value):
                issues.append(self._issue(row_number, symbol, trade_date, field, "MISSING_REQUIRED_VALUE", "error", f"{field} 값이 비어 있습니다."))
                continue
            try:
                value = float(raw_value)
            except Exception:  # noqa: BLE001
                issues.append(self._issue(row_number, symbol, trade_date, field, "NUMERIC_PARSE_FAILED", "error", f"{field} 숫자 변환 실패"))
                continue
            if value < 0:
                issues.append(self._issue(row_number, symbol, trade_date, field, "NEGATIVE_PRICE", "error", f"{field} 가격이 음수입니다."))
            elif value == 0:
                issues.append(self._issue(row_number, symbol, trade_date, field, "NON_POSITIVE_PRICE", "error", f"{field} 가격은 0보다 커야 합니다."))
            values[field] = value

        raw_volume = row.get("volume")
        if self._is_missing(raw_volume):
            issues.append(self._issue(row_number, symbol, trade_date, "volume", "MISSING_REQUIRED_VALUE", "error", "volume 값이 비어 있습니다."))
        else:
            try:
                volume = int(float(raw_volume))
                if volume < 0:
                    issues.append(self._issue(row_number, symbol, trade_date, "volume", "NEGATIVE_VOLUME", "error", "volume이 음수입니다."))
                elif volume == 0:
                    issues.append(self._issue(row_number, symbol, trade_date, "volume", "ZERO_VOLUME", "warning", "volume이 0입니다."))
                values["volume"] = volume
            except Exception:  # noqa: BLE001
                issues.append(self._issue(row_number, symbol, trade_date, "volume", "NUMERIC_PARSE_FAILED", "error", "volume 숫자 변환 실패"))

        if not {"open", "high", "low", "close", "volume"}.issubset(values):
            return None
        open_price = float(values["open"])
        high_price = float(values["high"])
        low_price = float(values["low"])
        close_price = float(values["close"])
        if high_price < low_price:
            issues.append(self._issue(row_number, symbol, trade_date, "high", "HIGH_LT_LOW", "error", "high가 low보다 작습니다."))
        if high_price < max(open_price, close_price):
            issues.append(self._issue(row_number, symbol, trade_date, "high", "HIGH_LT_OPEN_OR_CLOSE", "error", "high가 open 또는 close보다 작습니다."))
        if low_price > min(open_price, close_price):
            issues.append(self._issue(row_number, symbol, trade_date, "low", "LOW_GT_OPEN_OR_CLOSE", "error", "low가 open 또는 close보다 큽니다."))

        if "adj_close" in row and not self._is_missing(row.get("adj_close")):
            try:
                values["adj_close"] = float(row.get("adj_close"))
            except Exception:  # noqa: BLE001
                issues.append(self._issue(row_number, symbol, trade_date, "adj_close", "NUMERIC_PARSE_FAILED", "error", "adj_close 숫자 변환 실패"))
        else:
            issues.append(self._issue(row_number, symbol, trade_date, "adj_close", "MISSING_ADJ_CLOSE", "warning", "adj_close 누락으로 close를 사용합니다."))
            values["adj_close"] = close_price

        if "turnover_value" in row and not self._is_missing(row.get("turnover_value")):
            try:
                values["turnover_value"] = float(row.get("turnover_value"))
            except Exception:  # noqa: BLE001
                issues.append(self._issue(row_number, symbol, trade_date, "turnover_value", "NUMERIC_PARSE_FAILED", "error", "turnover_value 숫자 변환 실패"))
        else:
            issues.append(self._issue(row_number, symbol, trade_date, "turnover_value", "MISSING_TURNOVER_VALUE", "warning", "turnover_value 누락으로 close * volume을 사용합니다."))
            values["turnover_value"] = close_price * int(values["volume"])
        return values

    def _calendar_known(self, market: str, target_date: date) -> bool:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(TradingCalendar)
                .where(TradingCalendar.market == market, TradingCalendar.calendar_date == target_date)
            )
            or 0
        ) > 0

    @staticmethod
    def _is_missing(value: object) -> bool:
        if value is None:
            return True
        try:
            if pd.isna(value):
                return True
        except TypeError:
            return False
        return isinstance(value, str) and not value.strip()

    @staticmethod
    def _string_value(value: object) -> str | None:
        if MarketDataImportService._is_missing(value):
            return None
        return str(value).strip()

    @staticmethod
    def _issue(
        row_number: int | None,
        symbol: str | None,
        trade_date: date | None,
        field: str | None,
        check_code: str,
        severity: str,
        message: str,
    ) -> QualityIssue:
        if severity not in SEVERITIES:
            raise ValueError(f"지원하지 않는 severity입니다: {severity}")
        return QualityIssue(row_number, symbol, trade_date, field, check_code, severity, message)

    @staticmethod
    def _issue_counts(issues: list[QualityIssue]) -> dict[str, int]:
        return {
            "error_count": sum(1 for issue in issues if issue.severity == "error"),
            "warning_count": sum(1 for issue in issues if issue.severity == "warning"),
            "info_count": sum(1 for issue in issues if issue.severity == "info"),
        }

    @staticmethod
    def _issue_to_model(run_id: str, issue: QualityIssue) -> DataQualityCheck:
        return DataQualityCheck(
            run_id=run_id,
            row_number=issue.row_number,
            symbol=issue.symbol,
            trade_date=issue.trade_date,
            field=issue.field,
            check_code=issue.check_code,
            severity=issue.severity,
            message=issue.message,
        )

    @staticmethod
    def _serialize_run(run: ImportRun, include_rows: bool) -> dict[str, object]:
        payload: dict[str, object] = {
            "run_id": run.run_id,
            "source_id": run.source_id,
            "provider_type": run.provider_type,
            "original_filename": run.original_filename,
            "file_hash": run.file_hash,
            "status": run.status,
            "can_confirm": run.can_confirm,
            "total_rows": run.total_rows,
            "valid_rows": run.valid_rows,
            "error_count": run.error_count,
            "warning_count": run.warning_count,
            "info_count": run.info_count,
            "inserted_count": run.inserted_count,
            "updated_count": run.updated_count,
            "skipped_count": run.skipped_count,
            "created_at": run.created_at,
            "confirmed_at": run.confirmed_at,
            "preview_rows": json.loads(run.preview_rows_json or "[]"),
            "source_config_snapshot": json.loads(run.source_config_snapshot_json or "{}"),
            "provider_metadata": json.loads(run.provider_metadata_json or "{}"),
        }
        if include_rows:
            payload["staged_rows"] = json.loads(run.staged_rows_json or "[]")
        return payload

    @staticmethod
    def _serialize_check(check: DataQualityCheck) -> dict[str, object]:
        return {
            "id": check.id,
            "run_id": check.run_id,
            "row_number": check.row_number,
            "symbol": check.symbol,
            "trade_date": check.trade_date,
            "field": check.field,
            "check_code": check.check_code,
            "severity": check.severity,
            "message": check.message,
            "created_at": check.created_at,
        }
