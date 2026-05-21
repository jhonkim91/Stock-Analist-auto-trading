from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend.app.models.tables import IndicatorSnapshot, SymbolMaster
from backend.app.repositories.market_repository import MarketRepository


class IndicatorService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = MarketRepository(db)

    def recompute(self) -> dict[str, object]:
        """daily_ohlcv 기준 지표 스냅샷을 재계산한다."""
        daily = self.repo.daily_df()
        if daily.empty:
            return {"rows": 0, "start_date": None, "end_date": None}

        symbols = {row.symbol: row.sector for row in self.db.query(SymbolMaster).all()}
        frames = []
        for symbol, group in daily.groupby("symbol", sort=True):
            frames.append(self._compute_symbol_indicators(group.sort_values("trade_date").copy()))
        features = pd.concat(frames, ignore_index=True)
        features = self._attach_relative_strength(features)
        features = self._attach_market_score(features)
        features = self._attach_sector_score(features, symbols)

        self.db.execute(delete(IndicatorSnapshot))
        rows = [self._snapshot_from_row(row) for row in features.to_dict("records")]
        self.db.add_all(rows)
        self.db.commit()

        return {
            "rows": len(rows),
            "start_date": features["trade_date"].min(),
            "end_date": features["trade_date"].max(),
        }

    @staticmethod
    def _compute_symbol_indicators(df: pd.DataFrame) -> pd.DataFrame:
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        close = df["close"].astype(float)
        volume = df["volume"].astype(float)
        prev_close = close.shift(1)
        true_range = pd.concat(
            [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
            axis=1,
        ).max(axis=1)

        df["sma20"] = close.rolling(20, min_periods=20).mean()
        df["sma50"] = close.rolling(50, min_periods=50).mean()
        df["sma150"] = close.rolling(150, min_periods=150).mean()
        df["sma200"] = close.rolling(200, min_periods=200).mean()
        df["sma200_slope"] = df["sma200"] - df["sma200"].shift(20)
        df["volume_ma20"] = volume.rolling(20, min_periods=20).mean()
        df["volume_ma50"] = volume.rolling(50, min_periods=50).mean()
        df["atr14"] = true_range.rolling(14, min_periods=14).mean()
        df["atr20"] = true_range.rolling(20, min_periods=20).mean()
        df["atr20_pct"] = df["atr20"] / close
        df["atr20_pct_ma60"] = df["atr20_pct"].rolling(60, min_periods=30).mean()
        df["std20"] = close.pct_change().rolling(20, min_periods=20).std()
        df["std60"] = close.pct_change().rolling(60, min_periods=30).std()
        df["high_52w"] = high.rolling(252, min_periods=100).max()
        df["distance_from_52w_high"] = (close / df["high_52w"]) - 1
        df["volume_ratio_50"] = volume / df["volume_ma50"]
        df["pivot_high_20_prev"] = high.rolling(20, min_periods=20).max().shift(1)
        df["pivot_low_20_prev"] = low.rolling(20, min_periods=20).min().shift(1)
        prev_volume_ma20 = volume.shift(1).rolling(20, min_periods=20).mean()
        prev_volume_ma50 = volume.shift(1).rolling(50, min_periods=50).mean()
        df["breakout"] = close > df["pivot_high_20_prev"]
        df["volume_dry_up"] = prev_volume_ma20 < prev_volume_ma50 * 0.8
        df["ret_126"] = close / close.shift(126) - 1
        df["trend_score"] = (
            (close > df["sma50"]).astype(float)
            + (df["sma50"] > df["sma150"]).astype(float)
            + (df["sma150"] > df["sma200"]).astype(float)
            + (df["sma200_slope"] > 0).astype(float)
        ) / 4
        df["volume_score"] = np.minimum(df["volume_ratio_50"] / 1.5, 1).fillna(0)
        df["pattern_score"] = df["breakout"].astype(float)
        return df

    @staticmethod
    def _attach_relative_strength(features: pd.DataFrame) -> pd.DataFrame:
        features["rs_percentile"] = features.groupby("trade_date")["ret_126"].rank(pct=True) * 100
        features["relative_strength_score"] = (features["rs_percentile"] / 100).fillna(0)
        return features

    def _attach_market_score(self, features: pd.DataFrame) -> pd.DataFrame:
        index_df = self.repo.index_df()
        if index_df.empty:
            features["market_score"] = 0.0
            return features
        index_df = index_df.sort_values("trade_date")
        index_df["sma50"] = index_df["close"].rolling(50, min_periods=50).mean()
        index_df["sma200"] = index_df["close"].rolling(200, min_periods=200).mean()
        index_df["market_score"] = np.select(
            [
                (index_df["close"] > index_df["sma200"]) & (index_df["sma50"] > index_df["sma200"]),
                index_df["close"] > index_df["sma200"],
            ],
            [1.0, 0.5],
            default=0.0,
        )
        market_scores = index_df.set_index("trade_date")["market_score"].to_dict()
        features["market_score"] = features["trade_date"].map(market_scores).fillna(0.0)
        return features

    def _attach_sector_score(self, features: pd.DataFrame, symbol_sectors: dict[str, str]) -> pd.DataFrame:
        sector_df = self.repo.sector_df()
        if sector_df.empty:
            features["sector_rs_score"] = 0.0
            return features
        sector_df = sector_df.sort_values(["sector", "trade_date"])
        sector_df["sector_return_126"] = sector_df.groupby("sector")["close"].pct_change(126)
        sector_df["sector_rs_score"] = sector_df.groupby("trade_date")["sector_return_126"].rank(pct=True).fillna(0)
        score_map = {
            (row.trade_date, row.sector): row.sector_rs_score for row in sector_df.itertuples(index=False)
        }
        features["sector"] = features["symbol"].map(symbol_sectors)
        features["sector_rs_score"] = [
            float(score_map.get((row.trade_date, row.sector), 0.0)) for row in features.itertuples(index=False)
        ]
        return features

    @staticmethod
    def _clean(value: object) -> float | None:
        if value is None:
            return None
        if isinstance(value, (float, int, np.floating, np.integer)):
            if math.isnan(float(value)):
                return None
            return float(value)
        return value  # type: ignore[return-value]

    def _snapshot_from_row(self, row: dict[str, object]) -> IndicatorSnapshot:
        return IndicatorSnapshot(
            trade_date=pd.Timestamp(row["trade_date"]).date(),
            symbol=str(row["symbol"]),
            close=float(row["close"]),
            volume=int(row["volume"]),
            turnover_value=float(row["turnover_value"]),
            sma20=self._clean(row.get("sma20")),
            sma50=self._clean(row.get("sma50")),
            sma150=self._clean(row.get("sma150")),
            sma200=self._clean(row.get("sma200")),
            sma200_slope=self._clean(row.get("sma200_slope")),
            volume_ma20=self._clean(row.get("volume_ma20")),
            volume_ma50=self._clean(row.get("volume_ma50")),
            atr14=self._clean(row.get("atr14")),
            atr20=self._clean(row.get("atr20")),
            atr20_pct=self._clean(row.get("atr20_pct")),
            atr20_pct_ma60=self._clean(row.get("atr20_pct_ma60")),
            std20=self._clean(row.get("std20")),
            std60=self._clean(row.get("std60")),
            high_52w=self._clean(row.get("high_52w")),
            distance_from_52w_high=self._clean(row.get("distance_from_52w_high")),
            volume_ratio_50=self._clean(row.get("volume_ratio_50")),
            pivot_high_20_prev=self._clean(row.get("pivot_high_20_prev")),
            pivot_low_20_prev=self._clean(row.get("pivot_low_20_prev")),
            breakout=bool(row.get("breakout", False)),
            volume_dry_up=bool(row.get("volume_dry_up", False)),
            rs_percentile=self._clean(row.get("rs_percentile")),
            trend_score=float(row.get("trend_score") or 0.0),
            volume_score=float(row.get("volume_score") or 0.0),
            pattern_score=float(row.get("pattern_score") or 0.0),
            fund_score=float(row.get("fund_score") or 0.0),
            market_score=float(row.get("market_score") or 0.0),
            sector_rs_score=float(row.get("sector_rs_score") or 0.0),
            relative_strength_score=float(row.get("relative_strength_score") or 0.0),
            rr_score=float(row.get("rr_score") or 0.0),
        )
