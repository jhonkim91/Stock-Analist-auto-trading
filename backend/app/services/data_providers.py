from __future__ import annotations

from dataclasses import dataclass
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
        """Phase 3A에서는 외부 API 호출을 지원하지 않는다."""
        raise RuntimeError("ExternalDataProvider는 Phase 3A에서 비활성화되어 있습니다.")
