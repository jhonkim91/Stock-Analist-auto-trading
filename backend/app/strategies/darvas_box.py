from __future__ import annotations

from backend.app.models.tables import FundamentalsPti, IndicatorSnapshot
from backend.app.strategies.base import BaseStrategy, StrategyResult


class DarvasBoxStrategy(BaseStrategy):
    """Evaluate an approximate Darvas Box breakout from indicator snapshots."""

    name = "darvas_box"

    def evaluate(
        self,
        indicator: IndicatorSnapshot,
        fundamentals: FundamentalsPti | None,
        market_regime: str,
    ) -> StrategyResult:
        """Return a pass/fail result using pivot fields already stored in indicator_snapshot."""
        box_top = indicator.pivot_high_20_prev
        box_bottom = indicator.pivot_low_20_prev
        box_height_pct = self._box_height_pct(box_top, box_bottom)
        box_age_days = int(getattr(indicator, "box_age_days", 0) or 0)
        box_age_days_available = self._availability(indicator, "box_age_days_available")
        box_redefinition_count = int(getattr(indicator, "box_redefinition_count", 0) or 0)
        box_redefinition_count_available = self._availability(indicator, "box_redefinition_count_available")
        risk_per_share = self._risk_per_share(indicator.close, box_bottom)
        risk_metadata = self._box_risk_metadata(indicator.close, box_top, box_bottom, risk_per_share)
        flags = {
            "pivot_high_20_prev_available": box_top is not None,
            "pivot_low_20_prev_available": box_bottom is not None,
            "valid_box_range": box_height_pct is not None,
            "box_height_pct_max": self._lte(box_height_pct, self.config["max_box_height_pct"]),
            "box_age_days_available": box_age_days_available,
            "box_age_days_min": (
                box_age_days_available
                and box_age_days >= int(self.config.get("min_box_age_days", 5))
            ),
            "close_gt_box_top": self._gt(indicator.close, box_top),
            "box_bottom_lt_close": self._gt(indicator.close, box_bottom),
            "risk_per_share_positive": self._gt(risk_per_share, 0),
            "breakout": bool(indicator.breakout),
            "volume_surge": self._volume_surge(indicator.volume, indicator.volume_ma50),
            "rs_percentile_min": self._gte(indicator.rs_percentile, self.config["rs_percentile_min"]),
            "close_gt_sma50": self._gt(indicator.close, indicator.sma50),
            "sma50_gt_sma150": self._gt(indicator.sma50, indicator.sma150),
            "market_regime_not_bear": market_regime != "bear",
        }
        if bool(self.config.get("require_rising_box", True)):
            flags["box_redefinition_count_available"] = box_redefinition_count_available
            flags["rising_box_sequence"] = box_redefinition_count_available and box_redefinition_count > 0
        if bool(self.config.get("long_trend_filter_enabled", True)):
            flags.update(
                {
                    "sma150_gt_sma200": self._gt(indicator.sma150, indicator.sma200),
                    "sma200_slope_positive": self._gt(indicator.sma200_slope, 0),
                }
            )
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
        metadata = self._metadata(
            flags,
            failed,
            summary,
            data_quality_flags={
                "pivot_high_20_prev_available": box_top is not None,
                "pivot_low_20_prev_available": box_bottom is not None,
                "box_height_pct_available": box_height_pct is not None,
                "box_age_days_available": box_age_days_available,
                "box_redefinition_count_available": box_redefinition_count_available,
                "volume_ma50_available": indicator.volume_ma50 is not None,
                "rs_percentile_available": indicator.rs_percentile is not None,
                "sma50_available": indicator.sma50 is not None,
                "sma150_available": indicator.sma150 is not None,
                "sma200_available": indicator.sma200 is not None,
                "sma200_slope_available": indicator.sma200_slope is not None,
                **self._hardening_data_quality_flags(indicator, fundamentals, market_regime, risk_metadata),
            },
            optional_conditions=optional_conditions,
            risk_metadata=risk_metadata,
        )
        box_details = self._box_details(box_top, box_bottom, box_height_pct)
        metadata.update(
            {
                **box_details,
                "box_age_days": box_age_days if box_age_days_available else None,
                "box_redefinition_count": (
                    box_redefinition_count if box_redefinition_count_available else None
                ),
                "rising_box_sequence": box_redefinition_count_available and box_redefinition_count > 0,
                "suggested_stop_price": risk_metadata.get("suggested_stop_price"),
                "risk_per_share": risk_metadata.get("risk_per_share"),
                "risk_basis": risk_metadata.get("risk_basis"),
            }
        )
        metadata["score_breakdown"].update(box_details)
        metadata["score_breakdown"].update(
            {
                "box_age_days": box_age_days if box_age_days_available else None,
                "box_redefinition_count": (
                    box_redefinition_count if box_redefinition_count_available else None
                ),
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

    @staticmethod
    def _box_height_pct(box_top: float | None, box_bottom: float | None) -> float | None:
        if box_top is None or box_bottom is None or box_bottom <= 0 or box_top <= box_bottom:
            return None
        return (box_top - box_bottom) / box_bottom

    @staticmethod
    def _box_details(
        box_top: float | None,
        box_bottom: float | None,
        box_height_pct: float | None,
    ) -> dict[str, float | None]:
        return {
            "box_top": round(float(box_top), 4) if box_top is not None else None,
            "box_bottom": round(float(box_bottom), 4) if box_bottom is not None else None,
            "box_height_pct": round(float(box_height_pct), 6) if box_height_pct is not None else None,
        }

    def _risk_per_share(self, close: float | None, box_bottom: float | None) -> float | None:
        close_value = self._as_float(close)
        box_bottom_value = self._as_float(box_bottom)
        if close_value is None or box_bottom_value is None:
            return None
        return close_value - box_bottom_value

    def _box_risk_metadata(
        self,
        close: float | None,
        box_top: float | None,
        box_bottom: float | None,
        risk_per_share: float | None,
    ) -> dict[str, float | str | bool | None]:
        box_top_value = self._as_float(box_top)
        metadata = self._risk_metadata_from_stop(
            close,
            box_bottom,
            "darvas_box_bottom",
            entry_chase_reference=box_top_value,
            fallback_policy="fail_closed_missing_or_invalid_box_bottom_fallback_to_common_risk",
        )
        if metadata.get("suggested_stop_price") is not None and risk_per_share is not None:
            metadata["risk_per_share"] = round(risk_per_share, 4)
        return metadata

    def _sector_rs_filter_enabled(self) -> bool:
        return bool(self.config.get("sector_rs_filter_enabled", False)) or bool(
            self.config.get("sector_rs_score_min_enabled", False)
        )

    def _atr_risk_filter_enabled(self) -> bool:
        return bool(self.config.get("atr_risk_filter_enabled", False)) or bool(
            self.config.get("atr20_pct_max_enabled", False)
        )

    def _max_atr20_pct(self) -> float | None:
        return self._as_float(self.config.get("max_atr20_pct", self.config.get("atr20_pct_max")))

    def _volume_surge(self, volume: float | None, volume_ma50: float | None) -> bool:
        multiple = float(self.config["volume_surge_multiple"])
        return volume is not None and volume_ma50 is not None and volume_ma50 > 0 and volume >= volume_ma50 * multiple

    @staticmethod
    def _availability(indicator: IndicatorSnapshot, field_name: str) -> bool:
        return bool(getattr(indicator, field_name, False))
