from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from io import BytesIO
from typing import Protocol

import pandas as pd


@dataclass(frozen=True)
class ProviderBatch:
    source_id: str
    provider_type: str
    frame: pd.DataFrame


class DataProvider(Protocol):
    source_id: str
    provider_type: str

    def load_daily_ohlcv(self, content: bytes | None = None) -> ProviderBatch:
        """daily OHLCV 원천 데이터를 표준 DataFrame으로 읽는다."""


class SampleDataProvider:
    source_id = "sample_krx"
    provider_type = "sample"

    def load_daily_ohlcv(self, content: bytes | None = None) -> ProviderBatch:
        """샘플 데이터는 기존 seed service가 생성하므로 provider batch는 비워 둔다."""
        return ProviderBatch(self.source_id, self.provider_type, pd.DataFrame())


class CsvDataProvider:
    def __init__(self, source_id: str = "csv_krx") -> None:
        self.source_id = source_id
        self.provider_type = "csv"

    def load_daily_ohlcv(self, content: bytes | None = None) -> ProviderBatch:
        """CSV bytes를 DataFrame으로 읽어 provider batch를 만든다."""
        if content is None:
            raise ValueError("CSV content가 필요합니다.")
        return ProviderBatch(self.source_id, self.provider_type, pd.read_csv(BytesIO(content)))


class ExternalDataProvider:
    source_id = "external_placeholder_disabled"
    provider_type = "external"

    def load_daily_ohlcv(self, content: bytes | None = None) -> ProviderBatch:
        """Phase 3A 호환 placeholder. Phase 3B external flow는 BaseExternalDataProvider를 사용한다."""
        raise RuntimeError("ExternalDataProvider는 비활성화된 placeholder입니다.")


@dataclass(frozen=True)
class ExternalDailyRequest:
    source_id: str
    provider_name: str
    provider_symbol: str
    internal_symbol: str
    start_date: date
    end_date: date
    source: dict[str, object]


@dataclass(frozen=True)
class RawProviderResponse:
    provider_name: str
    provider_symbol: str
    rows: list[dict[str, object]]
    fetched_at: datetime


@dataclass(frozen=True)
class ProviderRateLimitState:
    allowed: bool
    reason: str = ""


class ExternalProviderError(RuntimeError):
    """외부 provider fetch/normalize 실패를 quality check로 변환하기 위한 기본 예외."""


class ExternalProviderTimeoutError(ExternalProviderError):
    """provider timeout을 명시적으로 표현한다."""


class ExternalProviderPartialResponseError(ExternalProviderError):
    """provider가 부분 응답만 반환했을 때 사용한다."""


class ExternalProviderRateLimitError(ExternalProviderError):
    """provider rate limit 초과를 표현한다."""


class BaseExternalDataProvider(Protocol):
    provider_name: str

    def check_rate_limit(self, request: ExternalDailyRequest) -> ProviderRateLimitState:
        """요청 전 rate limit 상태를 점검한다."""

    def fetch_daily_ohlcv(self, request: ExternalDailyRequest) -> RawProviderResponse:
        """provider 원천 daily OHLCV 응답을 가져온다."""

    def validate_raw_response(self, raw: RawProviderResponse, request: ExternalDailyRequest) -> list[dict[str, object]]:
        """원천 응답 구조를 provider 중립 check dict 목록으로 검증한다."""

    def normalize_ohlcv(self, raw: RawProviderResponse, request: ExternalDailyRequest) -> pd.DataFrame:
        """원천 응답을 Phase 3A validate flow가 받는 표준 DataFrame으로 변환한다."""


class ReadOnlyDataProvider(Protocol):
    provider_name: str

    def status(self, source: dict[str, object]) -> dict[str, object]:
        """실행 없이 provider capability와 차단 상태만 반환한다."""


class MockExternalDailyProvider:
    def __init__(self, provider_name: str = "mock") -> None:
        self.provider_name = provider_name

    def check_rate_limit(self, request: ExternalDailyRequest) -> ProviderRateLimitState:
        """테스트 fixture provider는 rate limit을 항상 통과시킨다."""
        return ProviderRateLimitState(allowed=True)

    def fetch_daily_ohlcv(self, request: ExternalDailyRequest) -> RawProviderResponse:
        """네트워크 호출 없이 business day 기준 deterministic OHLCV row를 만든다."""
        dates = pd.bdate_range(start=request.start_date, end=request.end_date)
        rows: list[dict[str, object]] = []
        seed = sum(ord(char) for char in request.internal_symbol)
        base = 40000 + seed
        for offset, trade_date in enumerate(dates):
            close = float(base + offset * 125)
            rows.append(
                {
                    "Date": trade_date.date().isoformat(),
                    "Open": close - 40,
                    "High": close + 120,
                    "Low": close - 160,
                    "Close": close,
                    "Adj Close": close,
                    "Volume": 100000 + offset * 1000,
                }
            )
        return RawProviderResponse(
            provider_name=self.provider_name,
            provider_symbol=request.provider_symbol,
            rows=rows,
            fetched_at=datetime.now(UTC),
        )

    def validate_raw_response(self, raw: RawProviderResponse, request: ExternalDailyRequest) -> list[dict[str, object]]:
        """mock 응답의 최소 컬럼 존재 여부를 검증한다."""
        if not raw.rows:
            return [
                {
                    "field": "provider_response",
                    "check_code": "PROVIDER_PARTIAL_RESPONSE",
                    "severity": "error",
                    "message": "provider 응답 row가 비어 있습니다.",
                }
            ]
        required = {"Date", "Open", "High", "Low", "Close", "Volume"}
        missing = sorted(required - set(raw.rows[0]))
        if not missing:
            return []
        return [
            {
                "field": "provider_response",
                "check_code": "PROVIDER_RESPONSE_SCHEMA_MISMATCH",
                "severity": "error",
                "message": f"provider 응답 필수 필드 누락: {', '.join(missing)}",
            }
        ]

    def normalize_ohlcv(self, raw: RawProviderResponse, request: ExternalDailyRequest) -> pd.DataFrame:
        """mock/yfinance-style row를 표준 daily OHLCV DataFrame으로 변환한다."""
        rows: list[dict[str, object]] = []
        source = request.source
        for row in raw.rows:
            close = float(row["Close"])
            adj_close = row.get("Adj Close", close)
            volume = int(float(row["Volume"]))
            rows.append(
                {
                    "trade_date": row["Date"],
                    "symbol": request.internal_symbol,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": close,
                    "adj_close": float(adj_close),
                    "volume": volume,
                    "turnover_value": close * volume,
                    "market": str(source.get("market") or "KR"),
                    "venue": str(source.get("venue") or "KRX"),
                    "provider": str(source.get("provider_type") or "external_market_data"),
                }
            )
        return pd.DataFrame(rows)


class YFinanceDailyProvider(MockExternalDailyProvider):
    def __init__(self) -> None:
        super().__init__(provider_name="yfinance")

    def fetch_daily_ohlcv(self, request: ExternalDailyRequest) -> RawProviderResponse:
        """network_enabled=true일 때만 yfinance에서 daily OHLCV를 조회한다."""
        if not bool(request.source.get("network_enabled")):
            raise ExternalProviderError("network_enabled=false 상태에서는 yfinance 네트워크 호출을 차단합니다.")
        try:
            import yfinance as yf  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            raise ExternalProviderError("yfinance 패키지가 설치되어 있지 않습니다.") from exc
        try:
            frame = yf.download(
                request.provider_symbol,
                start=request.start_date.isoformat(),
                end=request.end_date.isoformat(),
                progress=False,
                auto_adjust=False,
                threads=False,
            )
        except TimeoutError as exc:
            raise ExternalProviderTimeoutError("yfinance 요청이 timeout되었습니다.") from exc
        except Exception as exc:  # noqa: BLE001
            raise ExternalProviderError(f"yfinance 요청 실패: {exc}") from exc
        if frame is None or frame.empty:
            raise ExternalProviderPartialResponseError("yfinance 응답 row가 비어 있습니다.")
        normalized = frame.reset_index()
        rows = normalized.to_dict("records")
        return RawProviderResponse(
            provider_name=self.provider_name,
            provider_symbol=request.provider_symbol,
            rows=rows,
            fetched_at=datetime.now(UTC),
        )


KIS_DAILY_ITEMCHART_RESPONSE_FIELDS = frozenset({"rt_cd", "msg_cd", "msg1", "output2"})
KIS_DAILY_ITEMCHART_REQUIRED_ROW_FIELDS = frozenset(
    {"stck_bsop_date", "stck_oprc", "stck_hgpr", "stck_lwpr", "stck_clpr", "acml_vol"}
)
KIS_DAILY_ITEMCHART_OPTIONAL_ROW_FIELDS = frozenset({"acml_tr_pbmn"})
KIS_DAILY_ITEMCHART_ROW_FIELDS = KIS_DAILY_ITEMCHART_REQUIRED_ROW_FIELDS | KIS_DAILY_ITEMCHART_OPTIONAL_ROW_FIELDS


def _kis_schema_issue(message: str) -> dict[str, object]:
    return {
        "field": "provider_response",
        "check_code": "PROVIDER_RESPONSE_SCHEMA_MISMATCH",
        "severity": "error",
        "message": message,
    }


def validate_kis_daily_itemchart_fixture(payload: object) -> list[dict[str, object]]:
    """KIS itemchart fixture response shape을 canonical schema 기준으로 검증한다."""
    if not isinstance(payload, dict):
        return [_kis_schema_issue("KIS provider response는 object여야 합니다.")]

    issues: list[dict[str, object]] = []
    fields = set(payload)
    missing_top_level = sorted(KIS_DAILY_ITEMCHART_RESPONSE_FIELDS - fields)
    extra_top_level = sorted(fields - KIS_DAILY_ITEMCHART_RESPONSE_FIELDS)
    if missing_top_level:
        issues.append(_kis_schema_issue(f"KIS response 필수 필드 누락: {', '.join(missing_top_level)}"))
    if extra_top_level:
        issues.append(_kis_schema_issue(f"KIS response 허용되지 않은 필드: {', '.join(extra_top_level)}"))

    output_rows = payload.get("output2")
    if not isinstance(output_rows, list):
        issues.append(_kis_schema_issue("KIS response output2는 list여야 합니다."))
        return issues
    if not output_rows:
        return [
            {
                "field": "provider_response",
                "check_code": "PROVIDER_PARTIAL_RESPONSE",
                "severity": "error",
                "message": "KIS provider 응답 row가 비어 있습니다.",
            }
        ]

    for index, row in enumerate(output_rows, start=1):
        if not isinstance(row, dict):
            issues.append(_kis_schema_issue(f"KIS output2 row {index}는 object여야 합니다."))
            continue
        row_fields = set(row)
        missing_row_fields = sorted(KIS_DAILY_ITEMCHART_REQUIRED_ROW_FIELDS - row_fields)
        extra_row_fields = sorted(row_fields - KIS_DAILY_ITEMCHART_ROW_FIELDS)
        if missing_row_fields:
            issues.append(_kis_schema_issue(f"KIS output2 row {index} 필수 필드 누락: {', '.join(missing_row_fields)}"))
        if extra_row_fields:
            issues.append(_kis_schema_issue(f"KIS output2 row {index} 허용되지 않은 필드: {', '.join(extra_row_fields)}"))
    return issues


def build_kis_daily_itemchart_fixture_response(request: ExternalDailyRequest) -> dict[str, object]:
    """network call 없이 KIS itemchart canonical schema의 deterministic fixture를 만든다."""
    dates = pd.bdate_range(start=request.start_date, end=request.end_date)
    rows: list[dict[str, object]] = []
    seed = sum(ord(char) for char in request.internal_symbol)
    base = 50000 + seed
    for offset, trade_date in enumerate(dates):
        close = base + offset * 110
        volume = 120000 + offset * 1200
        rows.append(
            {
                "stck_bsop_date": trade_date.strftime("%Y%m%d"),
                "stck_oprc": str(close - 50),
                "stck_hgpr": str(close + 150),
                "stck_lwpr": str(close - 180),
                "stck_clpr": str(close),
                "acml_vol": str(volume),
                "acml_tr_pbmn": str(close * volume),
            }
        )
    return {
        "rt_cd": "0",
        "msg_cd": "MCA00000",
        "msg1": "OK",
        "output2": rows,
    }


def normalize_kis_daily_itemchart_rows(raw: RawProviderResponse, request: ExternalDailyRequest) -> pd.DataFrame:
    """KIS itemchart raw rows를 daily OHLCV preview schema로 변환한다."""
    rows: list[dict[str, object]] = []
    source = request.source
    for row in raw.rows:
        close = float(row["stck_clpr"])
        volume = int(float(row["acml_vol"]))
        turnover_value = row.get("acml_tr_pbmn")
        trade_date = pd.to_datetime(str(row["stck_bsop_date"]), format="%Y%m%d", errors="raise").date()
        rows.append(
            {
                "trade_date": trade_date.isoformat(),
                "symbol": request.internal_symbol,
                "open": float(row["stck_oprc"]),
                "high": float(row["stck_hgpr"]),
                "low": float(row["stck_lwpr"]),
                "close": close,
                "adj_close": close,
                "volume": volume,
                "turnover_value": float(turnover_value) if turnover_value is not None else close * volume,
                "market": str(source.get("market") or "KR"),
                "venue": str(source.get("venue") or "KRX"),
                "provider": str(source.get("provider_type") or "external_market_data"),
            }
        )
    return pd.DataFrame(rows)


class MockKisMarketDataProvider:
    provider_name = "kis"

    def check_rate_limit(self, request: ExternalDailyRequest) -> ProviderRateLimitState:
        """KIS fixture provider는 네트워크 없이 항상 rate limit을 통과시킨다."""
        return ProviderRateLimitState(allowed=True)

    def fetch_daily_ohlcv(self, request: ExternalDailyRequest) -> RawProviderResponse:
        """KIS itemchart canonical schema 기반 deterministic fixture row를 만든다."""
        response = build_kis_daily_itemchart_fixture_response(request)
        issues = validate_kis_daily_itemchart_fixture(response)
        if issues:
            raise ExternalProviderError("KIS fixture schema validation failed.")
        output_rows = response["output2"]
        if not isinstance(output_rows, list):
            raise ExternalProviderError("KIS fixture output2 must be a list.")
        rows = [dict(row) for row in output_rows if isinstance(row, dict)]
        return RawProviderResponse(
            provider_name=self.provider_name,
            provider_symbol=request.provider_symbol,
            rows=rows,
            fetched_at=datetime.now(UTC),
        )

    def validate_raw_response(self, raw: RawProviderResponse, request: ExternalDailyRequest) -> list[dict[str, object]]:
        """KIS 기간별시세 fixture의 필수 필드 존재 여부를 검증한다."""
        payload = {"rt_cd": "0", "msg_cd": "MCA00000", "msg1": "OK", "output2": raw.rows}
        return validate_kis_daily_itemchart_fixture(payload)

    def normalize_ohlcv(self, raw: RawProviderResponse, request: ExternalDailyRequest) -> pd.DataFrame:
        """KIS 기간별시세 raw row를 표준 daily OHLCV DataFrame으로 변환한다."""
        return normalize_kis_daily_itemchart_rows(raw, request)


class KisMarketDataProvider(MockKisMarketDataProvider):
    def fetch_daily_ohlcv(self, request: ExternalDailyRequest) -> RawProviderResponse:
        """Phase 3F-2에서는 실제 KIS 네트워크 호출을 수행하지 않는다."""
        raise ExternalProviderError("Phase 3F-2에서는 KIS 실제 API 호출을 금지합니다.")


def build_external_daily_provider(source: dict[str, object]) -> BaseExternalDataProvider:
    """source 설정에 맞는 provider-neutral daily provider 구현체를 반환한다."""
    provider_name = str(source.get("provider_name") or "").strip().lower()
    if provider_name == "kis" and bool(source.get("network_enabled")):
        return KisMarketDataProvider()
    if provider_name == "kis":
        return MockKisMarketDataProvider()
    if provider_name == "yfinance" and bool(source.get("network_enabled")):
        return YFinanceDailyProvider()
    if provider_name == "yfinance":
        return MockExternalDailyProvider(provider_name="yfinance")
    return MockExternalDailyProvider(provider_name=provider_name or "mock")
