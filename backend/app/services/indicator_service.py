from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend.app.models.tables import IndicatorSnapshot, SymbolMaster
from backend.app.repositories.market_repository import MarketRepository


class IndicatorService:
    VCP_PATTERN_LOOKBACK_DAYS = 90
    VCP_MIN_PULLBACK_DEPTH = 0.02
    DARVAS_BOX_WINDOW_DAYS = 20
    DARVAS_BOX_SEQUENCE_LOOKBACK_DAYS = 80
    WEEKLY_BREAKOUT_LOOKBACK_WEEKS = 13
    WEEKLY_RS_LOOKBACK_WEEKS = 13
    WEEKLY_VOLUME_LOOKBACK_WEEKS = 30

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
        features = self._attach_weekly_relative_strength(features)
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
        df["ema20"] = close.ewm(span=20, adjust=False, min_periods=20).mean()
        df["sma50"] = close.rolling(50, min_periods=50).mean()
        df["sma150"] = close.rolling(150, min_periods=150).mean()
        df["sma200"] = close.rolling(200, min_periods=200).mean()
        df["sma200_slope"] = df["sma200"] - df["sma200"].shift(20)
        df = IndicatorService._attach_weekly_indicators(df, high, close, volume)
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
        df = IndicatorService._attach_pattern_indicators(df)
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
    def _attach_weekly_indicators(
        df: pd.DataFrame,
        high: pd.Series,
        close: pd.Series,
        volume: pd.Series,
    ) -> pd.DataFrame:
        """각 daily snapshot 시점 기준의 as-of 주봉 지표를 추가한다."""
        trade_dates = pd.to_datetime(df["trade_date"])
        week_ends = trade_dates.dt.to_period("W-FRI").dt.end_time.dt.normalize()
        weekly_closes: list[float] = []
        weekly_highs: list[float] = []
        weekly_volumes: list[float] = []
        weekly_sma30_series: list[float | None] = []
        current_week: pd.Timestamp | None = None
        weekly_close_values: list[float] = []
        weekly_sma30_values: list[float | None] = []
        weekly_sma30_slope_values: list[float | None] = []
        weekly_breakout_values: list[bool] = []
        weekly_breakout_available_values: list[bool] = []
        weekly_volume_ratio_values: list[float] = []
        weekly_volume_ratio_available_values: list[bool] = []
        weekly_return_13_values: list[float | None] = []

        for week_end, high_value, close_value, volume_value in zip(week_ends, high, close, volume):
            high_float = float(high_value)
            close_float = float(close_value)
            volume_float = float(volume_value)
            if current_week is None or week_end != current_week:
                current_week = week_end
                weekly_closes.append(close_float)
                weekly_highs.append(high_float)
                weekly_volumes.append(volume_float)
                weekly_sma30_series.append(None)
            else:
                weekly_closes[-1] = close_float
                weekly_highs[-1] = max(weekly_highs[-1], high_float)
                weekly_volumes[-1] += volume_float

            weekly_sma30 = float(np.mean(weekly_closes[-30:])) if len(weekly_closes) >= 30 else None
            weekly_sma30_series[-1] = weekly_sma30
            shifted_sma30 = weekly_sma30_series[-5] if len(weekly_sma30_series) >= 5 else None
            weekly_sma30_slope = (
                weekly_sma30 - shifted_sma30
                if weekly_sma30 is not None and shifted_sma30 is not None
                else None
            )
            previous_weekly_high = (
                max(weekly_highs[-(IndicatorService.WEEKLY_BREAKOUT_LOOKBACK_WEEKS + 1):-1])
                if len(weekly_highs) > IndicatorService.WEEKLY_BREAKOUT_LOOKBACK_WEEKS
                else None
            )
            weekly_breakout_available = previous_weekly_high is not None
            weekly_breakout = (
                weekly_breakout_available
                and previous_weekly_high is not None
                and close_float > previous_weekly_high
            )
            previous_weekly_volume = (
                float(np.mean(weekly_volumes[-(IndicatorService.WEEKLY_VOLUME_LOOKBACK_WEEKS + 1):-1]))
                if len(weekly_volumes) > IndicatorService.WEEKLY_VOLUME_LOOKBACK_WEEKS
                else None
            )
            weekly_volume_ratio_available = previous_weekly_volume is not None and previous_weekly_volume > 0
            weekly_volume_ratio = (
                weekly_volumes[-1] / previous_weekly_volume
                if weekly_volume_ratio_available and previous_weekly_volume is not None
                else 0.0
            )
            weekly_return_13 = (
                close_float / weekly_closes[-(IndicatorService.WEEKLY_RS_LOOKBACK_WEEKS + 1)] - 1
                if len(weekly_closes) > IndicatorService.WEEKLY_RS_LOOKBACK_WEEKS
                and weekly_closes[-(IndicatorService.WEEKLY_RS_LOOKBACK_WEEKS + 1)] > 0
                else None
            )

            weekly_close_values.append(close_float)
            weekly_sma30_values.append(weekly_sma30)
            weekly_sma30_slope_values.append(weekly_sma30_slope)
            weekly_breakout_values.append(bool(weekly_breakout))
            weekly_breakout_available_values.append(weekly_breakout_available)
            weekly_volume_ratio_values.append(float(weekly_volume_ratio))
            weekly_volume_ratio_available_values.append(weekly_volume_ratio_available)
            weekly_return_13_values.append(weekly_return_13)

        df["weekly_close"] = weekly_close_values
        df["weekly_sma30"] = weekly_sma30_values
        df["weekly_sma30_slope"] = weekly_sma30_slope_values
        df["weekly_breakout"] = weekly_breakout_values
        df["weekly_breakout_available"] = weekly_breakout_available_values
        df["weekly_volume_ratio"] = weekly_volume_ratio_values
        df["weekly_volume_ratio_available"] = weekly_volume_ratio_available_values
        df["weekly_return_13"] = weekly_return_13_values
        return df

    @staticmethod
    def _attach_pattern_indicators(df: pd.DataFrame) -> pd.DataFrame:
        highs = df["high"].astype(float).reset_index(drop=True)
        lows = df["low"].astype(float).reset_index(drop=True)
        trade_dates = pd.to_datetime(df["trade_date"]).reset_index(drop=True)

        contraction_counts: list[int] = []
        contraction_count_available: list[bool] = []
        pullback_depth_last: list[float | None] = []
        pullback_depth_last_available: list[bool] = []
        pullback_depth_prev: list[float | None] = []
        pullback_depth_prev_available: list[bool] = []
        box_age_days: list[int] = []
        box_age_days_available: list[bool] = []
        box_redefinition_counts: list[int] = []
        box_redefinition_count_available: list[bool] = []

        for index in range(len(df)):
            lookback_start = max(0, index - IndicatorService.VCP_PATTERN_LOOKBACK_DAYS + 1)
            depths = IndicatorService._recent_pullback_depths(
                highs.iloc[lookback_start:index + 1].to_numpy(dtype=float),
                lows.iloc[lookback_start:index + 1].to_numpy(dtype=float),
            )
            contraction_available = index - lookback_start + 1 >= IndicatorService.DARVAS_BOX_WINDOW_DAYS
            last_depth = depths[-1] if depths else None
            prev_depth = depths[-2] if len(depths) >= 2 else None

            contraction_counts.append(len(depths) if contraction_available else 0)
            contraction_count_available.append(contraction_available)
            pullback_depth_last.append(last_depth)
            pullback_depth_last_available.append(last_depth is not None)
            pullback_depth_prev.append(prev_depth)
            pullback_depth_prev_available.append(prev_depth is not None)

            age, age_available = IndicatorService._box_age_days(highs, lows, trade_dates, index)
            redefinition_count, redefinition_available = IndicatorService._box_redefinition_count(highs, index)
            box_age_days.append(age)
            box_age_days_available.append(age_available)
            box_redefinition_counts.append(redefinition_count)
            box_redefinition_count_available.append(redefinition_available)

        df["contraction_count"] = contraction_counts
        df["contraction_count_available"] = contraction_count_available
        df["pullback_depth_last"] = pullback_depth_last
        df["pullback_depth_last_available"] = pullback_depth_last_available
        df["pullback_depth_prev"] = pullback_depth_prev
        df["pullback_depth_prev_available"] = pullback_depth_prev_available
        df["box_age_days"] = box_age_days
        df["box_age_days_available"] = box_age_days_available
        df["box_redefinition_count"] = box_redefinition_counts
        df["box_redefinition_count_available"] = box_redefinition_count_available
        return df

    @staticmethod
    def _recent_pullback_depths(highs: np.ndarray, lows: np.ndarray) -> list[float]:
        if len(highs) == 0 or len(lows) == 0:
            return []

        peak = float(highs[0])
        trough = float(lows[0])
        in_pullback = False
        depths: list[float] = []
        for high_value, low_value in zip(highs[1:], lows[1:]):
            high_float = float(high_value)
            low_float = float(low_value)
            if high_float >= peak:
                if in_pullback and peak > 0:
                    depth = (peak - trough) / peak
                    if depth >= IndicatorService.VCP_MIN_PULLBACK_DEPTH:
                        depths.append(float(depth))
                peak = high_float
                trough = low_float
                in_pullback = False
                continue
            in_pullback = True
            trough = min(trough, low_float)

        if in_pullback and peak > 0:
            depth = (peak - trough) / peak
            if depth >= IndicatorService.VCP_MIN_PULLBACK_DEPTH:
                depths.append(float(depth))
        return depths

    @staticmethod
    def _box_age_days(
        highs: pd.Series,
        lows: pd.Series,
        trade_dates: pd.Series,
        index: int,
    ) -> tuple[int, bool]:
        window = IndicatorService.DARVAS_BOX_WINDOW_DAYS
        if index < window:
            return 0, False
        start = index - window
        high_window = highs.iloc[start:index].to_numpy(dtype=float)
        low_window = lows.iloc[start:index].to_numpy(dtype=float)
        if len(high_window) < window or len(low_window) < window:
            return 0, False

        box_top = float(np.max(high_window))
        box_bottom = float(np.min(low_window))
        if box_top <= box_bottom or box_bottom <= 0:
            return 0, False

        high_offsets = np.flatnonzero(np.isclose(high_window, box_top))
        low_offsets = np.flatnonzero(np.isclose(low_window, box_bottom))
        if len(high_offsets) == 0 or len(low_offsets) == 0:
            return 0, False

        boundary_index = start + int(max(high_offsets[-1], low_offsets[-1]))
        age = (trade_dates.iloc[index].date() - trade_dates.iloc[boundary_index].date()).days
        return max(int(age), 0), True

    @staticmethod
    def _box_redefinition_count(highs: pd.Series, index: int) -> tuple[int, bool]:
        window = IndicatorService.DARVAS_BOX_WINDOW_DAYS
        if index < window:
            return 0, False
        start = max(window, index - IndicatorService.DARVAS_BOX_SEQUENCE_LOOKBACK_DAYS + 1)
        previous_top: float | None = None
        count = 0
        for cursor in range(start, index + 1):
            high_window = highs.iloc[cursor - window:cursor].to_numpy(dtype=float)
            if len(high_window) < window:
                continue
            top = float(np.max(high_window))
            if previous_top is not None and top > previous_top:
                count += 1
            previous_top = top
        return count, previous_top is not None

    @staticmethod
    def _attach_relative_strength(features: pd.DataFrame) -> pd.DataFrame:
        features["rs_percentile"] = features.groupby("trade_date")["ret_126"].rank(pct=True) * 100
        features["relative_strength_score"] = (features["rs_percentile"] / 100).fillna(0)
        return features

    @staticmethod
    def _attach_weekly_relative_strength(features: pd.DataFrame) -> pd.DataFrame:
        available = features["weekly_return_13"].notna()
        features["weekly_rs_score"] = 0.0
        if available.any():
            weekly_ranks = features.loc[available].groupby("trade_date")["weekly_return_13"].rank(pct=True)
            features.loc[available, "weekly_rs_score"] = weekly_ranks.astype(float)
        features["weekly_rs_score_available"] = available
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
            low=self._clean(row.get("low")),
            volume=int(row["volume"]),
            turnover_value=float(row["turnover_value"]),
            sma20=self._clean(row.get("sma20")),
            ema20=self._clean(row.get("ema20")),
            sma50=self._clean(row.get("sma50")),
            sma150=self._clean(row.get("sma150")),
            sma200=self._clean(row.get("sma200")),
            sma200_slope=self._clean(row.get("sma200_slope")),
            weekly_close=self._clean(row.get("weekly_close")),
            weekly_sma30=self._clean(row.get("weekly_sma30")),
            weekly_sma30_slope=self._clean(row.get("weekly_sma30_slope")),
            contraction_count=int(row.get("contraction_count") or 0),
            contraction_count_available=bool(row.get("contraction_count_available", False)),
            pullback_depth_last=self._clean(row.get("pullback_depth_last")),
            pullback_depth_last_available=bool(row.get("pullback_depth_last_available", False)),
            pullback_depth_prev=self._clean(row.get("pullback_depth_prev")),
            pullback_depth_prev_available=bool(row.get("pullback_depth_prev_available", False)),
            box_age_days=int(row.get("box_age_days") or 0),
            box_age_days_available=bool(row.get("box_age_days_available", False)),
            box_redefinition_count=int(row.get("box_redefinition_count") or 0),
            box_redefinition_count_available=bool(row.get("box_redefinition_count_available", False)),
            weekly_breakout=bool(row.get("weekly_breakout", False)),
            weekly_breakout_available=bool(row.get("weekly_breakout_available", False)),
            weekly_volume_ratio=float(row.get("weekly_volume_ratio") or 0.0),
            weekly_volume_ratio_available=bool(row.get("weekly_volume_ratio_available", False)),
            weekly_rs_score=float(row.get("weekly_rs_score") or 0.0),
            weekly_rs_score_available=bool(row.get("weekly_rs_score_available", False)),
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
