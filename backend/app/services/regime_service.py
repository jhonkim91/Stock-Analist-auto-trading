from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from backend.app.repositories.market_repository import MarketRepository


class RegimeService:
    def __init__(self, db: Session) -> None:
        self.repo = MarketRepository(db)

    def detect_market_regime(self, benchmark: str = "KOSPI_SAMPLE") -> dict[str, object]:
        """일봉 index 데이터를 주봉으로 resample해 시장 국면을 판정한다."""
        index_df = self.repo.index_df(benchmark)
        if index_df.empty:
            raise ValueError("index_ohlcv 데이터가 없습니다.")
        df = index_df.sort_values("trade_date").copy()
        df["sma50"] = df["close"].rolling(50, min_periods=50).mean()
        df["sma200"] = df["close"].rolling(200, min_periods=200).mean()

        weekly = df.set_index(pd.to_datetime(df["trade_date"])).resample("W-FRI").agg({"close": "last"}).dropna()
        weekly["weekly_sma30"] = weekly["close"].rolling(30, min_periods=30).mean()
        weekly["weekly_sma30_slope"] = weekly["weekly_sma30"] - weekly["weekly_sma30"].shift(4)

        latest = df.iloc[-1]
        weekly_latest = weekly.iloc[-1]
        close_vs_200 = self._ratio(latest["close"], latest["sma200"])
        sma50_vs_200 = self._ratio(latest["sma50"], latest["sma200"])
        weekly_close = float(weekly_latest["close"])
        weekly_sma30 = self._nullable_float(weekly_latest["weekly_sma30"])
        weekly_slope = self._nullable_float(weekly_latest["weekly_sma30_slope"])

        bull = (
            close_vs_200 is not None
            and sma50_vs_200 is not None
            and weekly_sma30 is not None
            and weekly_slope is not None
            and close_vs_200 > 1
            and sma50_vs_200 > 1
            and weekly_close > weekly_sma30
            and weekly_slope > 0
        )
        bear = close_vs_200 is not None and sma50_vs_200 is not None and close_vs_200 < 1 and sma50_vs_200 < 1
        regime = "bull" if bull else ("bear" if bear else "neutral")
        market_score = 1.0 if regime == "bull" else (0.0 if regime == "bear" else 0.5)

        return {
            "benchmark": benchmark,
            "trade_date": latest["trade_date"],
            "regime": regime,
            "market_score": market_score,
            "close_vs_200dma": close_vs_200,
            "sma50_vs_200dma": sma50_vs_200,
            "weekly_close": weekly_close,
            "weekly_sma30": weekly_sma30,
            "weekly_sma30_slope": weekly_slope,
        }

    @staticmethod
    def _ratio(numerator: object, denominator: object) -> float | None:
        if pd.isna(numerator) or pd.isna(denominator) or float(denominator) == 0:
            return None
        return float(numerator) / float(denominator)

    @staticmethod
    def _nullable_float(value: object) -> float | None:
        if value is None or pd.isna(value):
            return None
        return float(value)
