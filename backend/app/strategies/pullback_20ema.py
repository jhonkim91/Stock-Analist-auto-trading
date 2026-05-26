from __future__ import annotations

from backend.app.models.tables import FundamentalsPti, IndicatorSnapshot
from backend.app.strategies.base import BaseStrategy, StrategyResult


class Pullback20EmaStrategy(BaseStrategy):
    """Evaluate 20 EMA pullback candidates in an established uptrend."""

    name = "pullback_20ema"

    def evaluate(
        self,
        indicator: IndicatorSnapshot,
        fundamentals: FundamentalsPti | None,
        market_regime: str,
    ) -> StrategyResult:
        """Return a pass/fail result from one indicator snapshot."""
        flags = {
            "close_gt_sma50": self._gt(indicator.close, indicator.sma50),
            "sma50_gt_sma150": self._gt(indicator.sma50, indicator.sma150),
            "sma150_gt_sma200": self._gt(indicator.sma150, indicator.sma200),
            "sma200_slope_positive": self._gt(indicator.sma200_slope, 0),
            "ema20_available": indicator.ema20 is not None,
            "low_available": indicator.low is not None,
            "low_touch_ema20": self._low_touches_ema20(indicator.low, indicator.ema20),
            "close_gte_ema20": self._gte(indicator.close, indicator.ema20),
            "rs_percentile_min": self._gte(indicator.rs_percentile, self.config["rs_percentile_min"]),
            "market_regime_not_bear": market_regime != "bear",
            "volume_ratio_50_max": self._lte(indicator.volume_ratio_50, self.config["max_pullback_volume_ratio"]),
            "atr20_pct_max": self._lte(indicator.atr20_pct, self.config["max_atr20_pct"]),
        }
        optional_conditions = []
        if bool(self.config.get("sector_rs_filter_enabled", False)):
            flags["sector_rs_score_min"] = self._gte(
                getattr(indicator, "sector_rs_score", None),
                self.config["sector_rs_score_min"],
            )
            optional_conditions.append("sector_rs_score_min")
        if bool(self.config.get("near_high_52w_filter_enabled", False)):
            flags["near_high_52w"] = self._near_high_52w(indicator)
            optional_conditions.append("near_high_52w")
        if bool(self.config.get("fundamentals_quality_enabled", False)):
            flags["roe_min"] = self._gte(getattr(fundamentals, "roe", None), self.config["min_roe"])
            optional_conditions.append("roe_min")
        self._apply_optional_hardening_flags(
            flags,
            optional_conditions,
            indicator,
            fundamentals,
            market_regime,
            include_near_high=True,
        )
        failed = self._failed(flags)
        passed = self._all_flags(flags)
        summary = self._summary(self.name, passed, failed)
        risk_metadata = self._risk_metadata(indicator, entry_chase_reference=indicator.ema20)
        low_to_ema20_pct = self._ema20_distance_pct(indicator.low, indicator.ema20)
        close_to_ema20_pct = self._ema20_distance_pct(indicator.close, indicator.ema20)
        metadata = self._metadata(
            flags,
            failed,
            summary,
            data_quality_flags={
                **self._data_quality_flags(indicator, fundamentals),
                **self._hardening_data_quality_flags(indicator, fundamentals, market_regime, risk_metadata),
            },
            optional_conditions=optional_conditions,
            risk_metadata=risk_metadata,
        )
        metadata.update(
            {
                "low_to_ema20_pct": self._round_optional(low_to_ema20_pct),
                "close_to_ema20_pct": self._round_optional(close_to_ema20_pct),
                "volume_ratio_50": self._round_optional(indicator.volume_ratio_50),
                "atr20_pct": self._round_optional(indicator.atr20_pct),
                "pullback_quality": self._pullback_quality(flags, low_to_ema20_pct, close_to_ema20_pct),
            }
        )
        return StrategyResult(
            strategy_tag=self.name,
            passed=passed,
            pass_flags=flags,
            failed_conditions=failed,
            reason_summary=summary,
            metadata=metadata,
        )

    def _low_touches_ema20(self, low: float | None, ema20: float | None) -> bool:
        buffer = float(self.config["pullback_touch_buffer"])
        return low is not None and ema20 is not None and low <= ema20 * buffer

    def _near_high_52w(self, indicator: IndicatorSnapshot) -> bool:
        threshold = float(self.config["near_high_52w_threshold"])
        close = self._as_float(getattr(indicator, "close", None))
        high_52w = self._as_float(getattr(indicator, "high_52w", None))
        return close is not None and high_52w is not None and high_52w > 0 and close >= high_52w * threshold

    def _ema20_distance_pct(self, price: float | None, ema20: float | None) -> float | None:
        price_value = self._as_float(price)
        ema20_value = self._as_float(ema20)
        if price_value is None or ema20_value is None or ema20_value <= 0:
            return None
        return (price_value / ema20_value) - 1

    @staticmethod
    def _round_optional(value: float | None) -> float | None:
        return round(value, 6) if value is not None else None

    @staticmethod
    def _pullback_quality(
        flags: dict[str, bool],
        low_to_ema20_pct: float | None,
        close_to_ema20_pct: float | None,
    ) -> str:
        if (
            low_to_ema20_pct is None
            or close_to_ema20_pct is None
            or not flags["low_touch_ema20"]
            or not flags["close_gte_ema20"]
        ):
            return "too_deep_or_missing"
        if not flags["volume_ratio_50_max"]:
            return "volume_too_high"
        if not flags["atr20_pct_max"]:
            return "atr_too_high"
        return "valid"

    @staticmethod
    def _data_quality_flags(indicator: IndicatorSnapshot, fundamentals: FundamentalsPti | None) -> dict[str, bool]:
        return {
            "close_available": indicator.close is not None,
            "low_available": indicator.low is not None,
            "ema20_available": indicator.ema20 is not None,
            "sma50_available": indicator.sma50 is not None,
            "sma150_available": indicator.sma150 is not None,
            "sma200_available": indicator.sma200 is not None,
            "sma200_slope_available": indicator.sma200_slope is not None,
            "rs_percentile_available": indicator.rs_percentile is not None,
            "volume_ratio_50_available": indicator.volume_ratio_50 is not None,
            "atr20_pct_available": indicator.atr20_pct is not None,
            "high_52w_available": getattr(indicator, "high_52w", None) is not None,
            "sector_rs_score_available": getattr(indicator, "sector_rs_score", None) is not None,
            "fundamentals_available": fundamentals is not None,
            "roe_available": fundamentals is not None and getattr(fundamentals, "roe", None) is not None,
        }
