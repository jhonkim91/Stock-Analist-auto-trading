from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.tables import IndicatorSnapshot
from backend.app.repositories.market_repository import MarketRepository
from backend.app.services.indicator_service import IndicatorService


class RegimeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = MarketRepository(db)

    def detect_market_regime(self, benchmark: str = "KOSPI_SAMPLE", as_of: date | None = None) -> dict[str, object]:
        """Detect an index-led regime and downgrade bull regimes when breadth is weak."""
        index_df = self.repo.index_df(benchmark)
        if index_df.empty:
            raise ValueError("index_ohlcv data is not available.")
        df = index_df.sort_values("trade_date").copy()
        if as_of is not None:
            df = df[pd.to_datetime(df["trade_date"]).dt.date <= as_of]
        if df.empty:
            raise ValueError("index_ohlcv data is not available.")

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

        index_bull = (
            close_vs_200 is not None
            and sma50_vs_200 is not None
            and weekly_sma30 is not None
            and weekly_slope is not None
            and close_vs_200 > 1
            and sma50_vs_200 > 1
            and weekly_close > weekly_sma30
            and weekly_slope > 0
        )
        index_bear = close_vs_200 is not None and sma50_vs_200 is not None and close_vs_200 < 1 and sma50_vs_200 < 1
        index_regime = "bull" if index_bull else ("bear" if index_bear else "neutral")
        breadth = self._breadth_metrics(pd.Timestamp(latest["trade_date"]).date())
        regime = self._combine_index_and_breadth(index_regime, str(breadth["breadth_regime"]))
        market_score = 1.0 if regime == "bull" else (0.0 if regime == "bear" else 0.5)

        return {
            "benchmark": benchmark,
            "trade_date": latest["trade_date"],
            "regime": regime,
            "index_regime": index_regime,
            "market_score": market_score,
            "close_vs_200dma": close_vs_200,
            "sma50_vs_200dma": sma50_vs_200,
            "weekly_close": weekly_close,
            "weekly_sma30": weekly_sma30,
            "weekly_sma30_slope": weekly_slope,
            **breadth,
        }

    def _breadth_metrics(self, as_of: date) -> dict[str, object]:
        snapshot_metrics = self._breadth_metrics_from_snapshot(as_of)
        if snapshot_metrics["breadth_score_available"]:
            return snapshot_metrics

        daily = self.repo.daily_df(end_date=as_of)
        if daily.empty:
            return snapshot_metrics
        breadth_frame = IndicatorService.breadth_frame_from_daily(daily)
        if breadth_frame.empty:
            return snapshot_metrics
        available_frame = breadth_frame[pd.to_datetime(breadth_frame["trade_date"]).dt.date <= as_of]
        if available_frame.empty:
            return snapshot_metrics
        return self._normalize_breadth_payload(available_frame.iloc[-1].to_dict())

    def _breadth_metrics_from_snapshot(self, as_of: date) -> dict[str, object]:
        row = self.db.scalar(
            select(IndicatorSnapshot)
            .where(
                IndicatorSnapshot.trade_date <= as_of,
                IndicatorSnapshot.breadth_score_available.is_(True),
            )
            .order_by(IndicatorSnapshot.trade_date.desc())
            .limit(1)
        )
        if row is None:
            return self._not_available_breadth_payload()
        return self._normalize_breadth_payload(
            {
                "trade_date": row.trade_date,
                "breadth_advance_decline_ratio": row.breadth_advance_decline_ratio,
                "breadth_advance_decline_available": row.breadth_advance_decline_available,
                "breadth_52w_high_low_ratio": row.breadth_52w_high_low_ratio,
                "breadth_52w_high_low_available": row.breadth_52w_high_low_available,
                "breadth_ma50_participation": row.breadth_ma50_participation,
                "breadth_ma50_participation_available": row.breadth_ma50_participation_available,
                "breadth_score": row.breadth_score,
                "breadth_score_available": row.breadth_score_available,
            }
        )

    @classmethod
    def _normalize_breadth_payload(cls, payload: dict[str, object]) -> dict[str, object]:
        breadth_score = cls._nullable_float(payload.get("breadth_score"))
        breadth_score_available = bool(payload.get("breadth_score_available", False)) and breadth_score is not None
        breadth_regime = cls._breadth_regime(breadth_score) if breadth_score_available else "not_available"
        return {
            "breadth_trade_date": payload.get("trade_date"),
            "breadth_regime": breadth_regime,
            "breadth_score": breadth_score,
            "breadth_score_available": breadth_score_available,
            "breadth_advance_decline_ratio": cls._nullable_float(payload.get("breadth_advance_decline_ratio")),
            "breadth_advance_decline_available": bool(payload.get("breadth_advance_decline_available", False)),
            "breadth_52w_high_low_ratio": cls._nullable_float(payload.get("breadth_52w_high_low_ratio")),
            "breadth_52w_high_low_available": bool(payload.get("breadth_52w_high_low_available", False)),
            "breadth_ma50_participation": cls._nullable_float(payload.get("breadth_ma50_participation")),
            "breadth_ma50_participation_available": bool(payload.get("breadth_ma50_participation_available", False)),
        }

    @classmethod
    def _not_available_breadth_payload(cls) -> dict[str, object]:
        return cls._normalize_breadth_payload(
            {
                "trade_date": None,
                "breadth_score": None,
                "breadth_score_available": False,
                "breadth_advance_decline_ratio": None,
                "breadth_advance_decline_available": False,
                "breadth_52w_high_low_ratio": None,
                "breadth_52w_high_low_available": False,
                "breadth_ma50_participation": None,
                "breadth_ma50_participation_available": False,
            }
        )

    @staticmethod
    def _combine_index_and_breadth(index_regime: str, breadth_regime: str) -> str:
        if index_regime == "bull" and breadth_regime == "weak":
            return "neutral"
        return index_regime

    @staticmethod
    def _breadth_regime(breadth_score: float | None) -> str:
        if breadth_score is None:
            return "not_available"
        if breadth_score >= 0.60:
            return "strong"
        if breadth_score < 0.40:
            return "weak"
        return "neutral"

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
