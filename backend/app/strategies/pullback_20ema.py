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
        pullback_context = self._pullback_context(indicator)
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
            "pullback_count_available": bool(pullback_context["available"]),
            "pullback_count_within_limit": bool(pullback_context["within_limit"]),
        }
        if bool(self.config.get("require_volume_dry_up_vs_ma20", False)):
            flags["volume_dry_up_vs_ma20"] = self._volume_dry_up_vs_ma20(indicator)
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
        risk_metadata = self._pullback_risk_metadata(indicator)
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
                "pullback_count": pullback_context["count"],
                "max_pullback_count": pullback_context["max_count"],
                "pullback_context": {
                    "count": pullback_context["count"],
                    "max_count": pullback_context["max_count"],
                    "first_or_second_pullback": bool(pullback_context["within_limit"]),
                    "volume_dry_up_vs_ma20_required": bool(self.config.get("require_volume_dry_up_vs_ma20", False)),
                    "volume_dry_up_vs_ma20": flags.get("volume_dry_up_vs_ma20"),
                },
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

    def _pullback_context(self, indicator: IndicatorSnapshot) -> dict[str, int | bool | None]:
        count = getattr(indicator, "pullback_count", None)
        available = getattr(indicator, "pullback_count_available", None)
        if count is None:
            count = getattr(indicator, "contraction_count", None)
        if available is None:
            available = getattr(indicator, "contraction_count_available", count is not None)
        count_value = int(count) if count is not None else None
        max_count = int(self.config.get("max_pullback_count", 2))
        return {
            "count": count_value,
            "max_count": max_count,
            "available": bool(available) and count_value is not None,
            "within_limit": bool(available) and count_value is not None and 1 <= count_value <= max_count,
        }

    def _volume_dry_up_vs_ma20(self, indicator: IndicatorSnapshot) -> bool:
        volume = self._as_float(getattr(indicator, "volume", None))
        volume_ma20 = self._as_float(getattr(indicator, "volume_ma20", None))
        threshold = float(self.config.get("volume_dry_up_vs_ma20_ratio", 1.0))
        return volume is not None and volume_ma20 is not None and volume_ma20 > 0 and volume <= volume_ma20 * threshold

    def _ema20_distance_pct(self, price: float | None, ema20: float | None) -> float | None:
        price_value = self._as_float(price)
        ema20_value = self._as_float(ema20)
        if price_value is None or ema20_value is None or ema20_value <= 0:
            return None
        return (price_value / ema20_value) - 1

    def _pullback_risk_metadata(self, indicator: IndicatorSnapshot) -> dict[str, object]:
        close = self._as_float(getattr(indicator, "close", None))
        swing_low = self._as_float(getattr(indicator, "pivot_low_20_prev", None))
        ema20 = self._as_float(getattr(indicator, "ema20", None))
        if close is not None and swing_low is not None and 0 < swing_low < close:
            return self._risk_metadata_from_stop(
                close,
                swing_low,
                "swing_low",
                entry_chase_reference=ema20,
            )
        if close is not None and ema20 is not None and 0 < ema20 < close:
            return self._risk_metadata_from_stop(
                close,
                ema20,
                "ema20_failure",
                entry_chase_reference=ema20,
            )
        return self._risk_metadata_from_stop(
            close,
            None,
            "unavailable",
            entry_chase_reference=ema20,
            fallback_policy="fail_closed_missing_swing_low_and_ema20_fallback_to_common_risk",
        )

    @staticmethod
    def _round_optional(value: float | None) -> float | None:
        return round(value, 6) if value is not None else None

    def _pullback_quality(
        self,
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
        if not flags["pullback_count_available"]:
            return "pullback_count_missing"
        if not flags["pullback_count_within_limit"]:
            return "too_late_pullback"
        if bool(self.config.get("require_volume_dry_up_vs_ma20", False)) and not flags["volume_dry_up_vs_ma20"]:
            return "volume_not_dry_vs_ma20"
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
            "volume_available": getattr(indicator, "volume", None) is not None,
            "volume_ma20_available": getattr(indicator, "volume_ma20", None) is not None,
            "volume_ratio_50_available": indicator.volume_ratio_50 is not None,
            "atr20_pct_available": indicator.atr20_pct is not None,
            "high_52w_available": getattr(indicator, "high_52w", None) is not None,
            "pullback_count_available": bool(
                getattr(indicator, "pullback_count_available", getattr(indicator, "contraction_count_available", False))
            ),
            "swing_low_available": getattr(indicator, "pivot_low_20_prev", None) is not None,
            "ema_failure_stop_available": indicator.ema20 is not None,
            "sector_rs_score_available": getattr(indicator, "sector_rs_score", None) is not None,
            "fundamentals_available": fundamentals is not None,
            "roe_available": fundamentals is not None and getattr(fundamentals, "roe", None) is not None,
        }
