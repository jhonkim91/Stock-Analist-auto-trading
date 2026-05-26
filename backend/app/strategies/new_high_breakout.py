from __future__ import annotations

from backend.app.models.tables import FundamentalsPti, IndicatorSnapshot
from backend.app.strategies.base import BaseStrategy, StrategyResult


class NewHighBreakoutStrategy(BaseStrategy):
    """52주 신고가 또는 신고가 근접 돌파 후보를 평가한다."""

    name = "new_high_breakout"

    def evaluate(
        self,
        indicator: IndicatorSnapshot,
        fundamentals: FundamentalsPti | None,
        market_regime: str,
    ) -> StrategyResult:
        """기존 indicator_snapshot 필드만 사용해 pass/fail 결과를 반환한다."""
        flags = {
            "high_52w_available": indicator.high_52w is not None,
            "new_high_threshold": self._near_new_high(indicator.close, indicator.high_52w),
            "breakout_buffer": self._breakout_buffer_confirmed(indicator.close, indicator.high_52w),
            "breakout": bool(indicator.breakout),
            "volume_surge": self._volume_surge(indicator.volume, indicator.volume_ma50),
            "rs_percentile_min": self._gte(indicator.rs_percentile, self.config["rs_percentile_min"]),
            "market_regime_not_bear": market_regime != "bear",
            "close_gt_sma50": self._gt(indicator.close, indicator.sma50),
            "sma50_gt_sma150": self._gt(indicator.sma50, indicator.sma150),
            "sma150_gt_sma200": self._gt(indicator.sma150, indicator.sma200),
            "sma200_slope_positive": self._gt(indicator.sma200_slope, 0),
        }
        if bool(self.config.get("require_breakout_day_volume_ratio", False)):
            flags["breakout_day_volume_ratio"] = self._breakout_day_volume_ratio(indicator)
        optional_conditions = []
        if self._sector_rs_filter_enabled():
            flags["sector_rs_score_min"] = self._gte(
                getattr(indicator, "sector_rs_score", None),
                self.config["sector_rs_score_min"],
            )
            optional_conditions.append("sector_rs_score_min")
        if self._atr_risk_filter_enabled():
            flags["atr20_pct_max"] = self._lte(getattr(indicator, "atr20_pct", None), self._max_atr20_pct())
            optional_conditions.append("atr20_pct_max")
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
        distance_from_52w_high = self._distance_from_52w_high(indicator)
        risk_flags = self._entry_chase_risk_flags(indicator)
        risk_metadata = self._risk_metadata(indicator, entry_chase_reference=indicator.high_52w)
        metadata = self._metadata(
            flags,
            failed,
            summary,
            risk_flags=risk_flags,
            data_quality_flags={
                "close_available": indicator.close is not None,
                "high_52w_available": indicator.high_52w is not None,
                "distance_from_52w_high_available": distance_from_52w_high is not None,
                "volume_available": indicator.volume is not None,
                "volume_ma50_available": indicator.volume_ma50 is not None,
                "volume_ratio_50_available": indicator.volume_ratio_50 is not None,
                "breakout_day_volume_ratio_available": indicator.volume_ratio_50 is not None,
                "rs_percentile_available": indicator.rs_percentile is not None,
                "sma50_available": indicator.sma50 is not None,
                "sma150_available": indicator.sma150 is not None,
                "sma200_available": indicator.sma200 is not None,
                "sma200_slope_available": indicator.sma200_slope is not None,
                "sector_rs_score_available": getattr(indicator, "sector_rs_score", None) is not None,
                "atr20_pct_available": getattr(indicator, "atr20_pct", None) is not None,
                **self._hardening_data_quality_flags(indicator, fundamentals, market_regime, risk_metadata),
            },
            optional_conditions=optional_conditions,
            risk_metadata=risk_metadata,
        )
        metadata.update(
            {
                "distance_from_52w_high": self._round_optional(distance_from_52w_high),
                "breakout_buffer_pct": float(self.config.get("breakout_buffer_pct", 0.0)),
                "breakout_buffer_price": self._round_optional(self._breakout_buffer_price(indicator.high_52w)),
                "breakout_day_volume_ratio": self._round_optional(indicator.volume_ratio_50),
                "breakout_day_volume_ratio_min": self._breakout_day_volume_ratio_min(),
                "breakout_context": {
                    "buffer_confirmed": flags["breakout_buffer"],
                    "volume_quality_required": bool(self.config.get("require_breakout_day_volume_ratio", False)),
                    "volume_quality_confirmed": flags.get("breakout_day_volume_ratio"),
                },
                "chase_warning": risk_flags["chase_warning"],
                "suggested_stop_basis": "pivot_low_or_atr_required",
                "risk_per_share_available": False,
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

    def _near_new_high(self, close: float | None, high_52w: float | None) -> bool:
        threshold = float(self.config["new_high_threshold"])
        return close is not None and high_52w is not None and high_52w > 0 and close >= high_52w * threshold

    def _breakout_buffer_confirmed(self, close: float | None, high_52w: float | None) -> bool:
        buffer_price = self._breakout_buffer_price(high_52w)
        return close is not None and buffer_price is not None and close >= buffer_price

    def _breakout_buffer_price(self, high_52w: float | None) -> float | None:
        high_value = self._as_float(high_52w)
        if high_value is None or high_value <= 0:
            return None
        return high_value * (1 + float(self.config.get("breakout_buffer_pct", 0.0)))

    def _volume_surge(self, volume: float | None, volume_ma50: float | None) -> bool:
        multiple = float(self.config["volume_surge_multiple"])
        return volume is not None and volume_ma50 is not None and volume_ma50 > 0 and volume >= volume_ma50 * multiple

    def _breakout_day_volume_ratio(self, indicator: IndicatorSnapshot) -> bool:
        ratio = self._as_float(getattr(indicator, "volume_ratio_50", None))
        threshold = self._breakout_day_volume_ratio_min()
        return ratio is not None and ratio >= threshold

    def _breakout_day_volume_ratio_min(self) -> float:
        return float(self.config.get("breakout_day_volume_ratio_min", self.config.get("volume_ratio_50_min", 1.0)))

    def _sector_rs_filter_enabled(self) -> bool:
        return bool(self.config.get("sector_rs_filter_enabled", False)) or bool(
            self.config.get("sector_rs_score_min_enabled", False)
        )

    def _atr_risk_filter_enabled(self) -> bool:
        return bool(self.config.get("atr_risk_filter_enabled", False)) or bool(
            self.config.get("atr20_pct_max_enabled", False)
        )

    def _max_atr20_pct(self) -> float | None:
        return self.config.get("max_atr20_pct", self.config.get("atr20_pct_max"))

    def _entry_chase_risk_flags(self, indicator: IndicatorSnapshot) -> dict[str, bool]:
        close = self._as_float(getattr(indicator, "close", None))
        high_52w = self._as_float(getattr(indicator, "high_52w", None))
        threshold = float(
            self.config.get(
                "chase_warning_pct_above_52w_high",
                self.config.get("entry_chase_warning_threshold_pct", 0.05),
            )
        )
        extended_above_high = (
            close is not None
            and high_52w is not None
            and high_52w > 0
            and close > high_52w * (1 + threshold)
        )
        return {
            "chase_warning": extended_above_high,
            "entry_chase_warning": extended_above_high,
            "close_extended_above_52w_high": extended_above_high,
        }

    def _distance_from_52w_high(self, indicator: IndicatorSnapshot) -> float | None:
        distance = self._as_float(getattr(indicator, "distance_from_52w_high", None))
        if distance is not None:
            return distance
        close = self._as_float(getattr(indicator, "close", None))
        high_52w = self._as_float(getattr(indicator, "high_52w", None))
        if close is None or high_52w is None or high_52w <= 0:
            return None
        return (close / high_52w) - 1

    @staticmethod
    def _round_optional(value: float | None) -> float | None:
        return round(value, 6) if value is not None else None
