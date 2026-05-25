from __future__ import annotations

from backend.app.models.tables import FundamentalsPti, IndicatorSnapshot
from backend.app.strategies.base import BaseStrategy, StrategyResult


class RelativeStrengthLeaderStrategy(BaseStrategy):
    """Evaluate market and sector relative-strength leadership candidates."""

    name = "relative_strength_leader"

    def evaluate(
        self,
        indicator: IndicatorSnapshot,
        fundamentals: FundamentalsPti | None,
        market_regime: str,
    ) -> StrategyResult:
        """Return a pass/fail result using only indicator_snapshot fields."""
        flags = {
            "rs_percentile_min": self._gte(indicator.rs_percentile, self.config["rs_percentile_min"]),
            "relative_strength_score_min": self._gte(
                indicator.relative_strength_score,
                self.config["relative_strength_score_min"],
            ),
            "sector_rs_score_min": self._gte(indicator.sector_rs_score, self.config["sector_rs_score_min"]),
            "near_high_52w": self._near_high_52w(indicator.close, indicator.high_52w),
            "close_gt_sma50": self._gt(indicator.close, indicator.sma50),
            "sma50_gt_sma150": self._gt(indicator.sma50, indicator.sma150),
            "sma200_slope_positive": self._gt(indicator.sma200_slope, 0),
            "volume_ratio_50_min": self._gte(indicator.volume_ratio_50, self.config["min_volume_ratio_50"]),
        }
        optional_conditions = []
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
        risk_metadata = self._risk_metadata(indicator, entry_chase_reference=indicator.high_52w)
        return StrategyResult(
            strategy_tag=self.name,
            passed=passed,
            pass_flags=flags,
            failed_conditions=failed,
            reason_summary=summary,
            metadata=self._metadata(
                flags,
                failed,
                summary,
                data_quality_flags={
                    **self._data_quality_flags(indicator),
                    **self._hardening_data_quality_flags(indicator, fundamentals, market_regime, risk_metadata),
                },
                optional_conditions=optional_conditions,
                risk_metadata=risk_metadata,
            ),
        )

    def _near_high_52w(self, close: float | None, high_52w: float | None) -> bool:
        threshold = float(self.config["near_high_52w_threshold"])
        return close is not None and high_52w is not None and high_52w > 0 and close >= high_52w * threshold

    @staticmethod
    def _data_quality_flags(indicator: IndicatorSnapshot) -> dict[str, bool]:
        return {
            "rs_percentile_available": indicator.rs_percentile is not None,
            "relative_strength_score_available": indicator.relative_strength_score is not None,
            "sector_rs_score_available": indicator.sector_rs_score is not None,
            "high_52w_available": indicator.high_52w is not None,
            "volume_ratio_50_available": indicator.volume_ratio_50 is not None,
            "close_available": indicator.close is not None,
            "sma50_available": indicator.sma50 is not None,
            "sma150_available": indicator.sma150 is not None,
            "sma200_slope_available": indicator.sma200_slope is not None,
        }
