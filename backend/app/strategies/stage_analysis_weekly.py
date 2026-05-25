from __future__ import annotations

from backend.app.models.tables import FundamentalsPti, IndicatorSnapshot
from backend.app.strategies.base import BaseStrategy, StrategyResult


class StageAnalysisWeeklyStrategy(BaseStrategy):
    """Evaluate a weekly Stage 2 approximation from indicator snapshots."""

    name = "stage_analysis_weekly"

    def evaluate(
        self,
        indicator: IndicatorSnapshot,
        fundamentals: FundamentalsPti | None,
        market_regime: str,
    ) -> StrategyResult:
        """Return a pass/fail result for Weinstein-style Stage 2 conditions."""
        weekly_data_available = (
            indicator.weekly_close is not None
            and indicator.weekly_sma30 is not None
            and indicator.weekly_sma30_slope is not None
        )
        flags = {
            "weekly_data_available": weekly_data_available,
            "weekly_close_gt_sma30": self._gt(indicator.weekly_close, indicator.weekly_sma30),
            "weekly_sma30_slope_positive": self._gt(indicator.weekly_sma30_slope, 0),
            "close_gt_sma200": self._gt(indicator.close, indicator.sma200),
            "sma50_gt_sma150": self._gt(indicator.sma50, indicator.sma150),
            "sma150_gt_sma200": self._gt(indicator.sma150, indicator.sma200),
            "rs_percentile_min": self._gte(indicator.rs_percentile, self.config["rs_percentile_min"]),
            "volume_ratio_50_min": self._gte(indicator.volume_ratio_50, self.config["min_volume_ratio_50"]),
            "market_regime_not_bear": market_regime != "bear",
        }
        optional_conditions = []
        self._apply_optional_hardening_flags(
            flags,
            optional_conditions,
            indicator,
            fundamentals,
            market_regime,
        )
        failed = self._failed(flags)
        passed = self._all_flags(flags)
        summary = self._summary(self.name, passed, failed)
        risk_metadata = self._risk_metadata(indicator, entry_chase_reference=indicator.weekly_sma30)
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
                    **self._data_quality_flags(indicator, weekly_data_available),
                    **self._hardening_data_quality_flags(indicator, fundamentals, market_regime, risk_metadata),
                },
                optional_conditions=optional_conditions,
                risk_metadata=risk_metadata,
            ),
        )

    @staticmethod
    def _data_quality_flags(
        indicator: IndicatorSnapshot,
        weekly_data_available: bool,
    ) -> dict[str, bool]:
        return {
            "weekly_data_available": weekly_data_available,
            "weekly_close_available": indicator.weekly_close is not None,
            "weekly_sma30_available": indicator.weekly_sma30 is not None,
            "weekly_sma30_slope_available": indicator.weekly_sma30_slope is not None,
            "sma50_available": indicator.sma50 is not None,
            "sma150_available": indicator.sma150 is not None,
            "sma200_available": indicator.sma200 is not None,
            "rs_percentile_available": indicator.rs_percentile is not None,
            "volume_ratio_50_available": indicator.volume_ratio_50 is not None,
        }
