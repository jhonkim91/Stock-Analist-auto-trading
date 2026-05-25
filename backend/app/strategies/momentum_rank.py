from __future__ import annotations

from backend.app.models.tables import FundamentalsPti, IndicatorSnapshot
from backend.app.strategies.base import BaseStrategy, StrategyResult


class MomentumRankStrategy(BaseStrategy):
    """Evaluate high relative-strength momentum candidates from indicator snapshots."""

    name = "momentum_rank"

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
            "trend_score_min": self._gte(indicator.trend_score, self.config["trend_score_min"]),
            "sector_rs_score_min": self._gte(indicator.sector_rs_score, self.config["sector_rs_score_min"]),
            "market_score_min": self._gte(indicator.market_score, self.config["market_score_min"]),
            "close_gt_sma50": self._gt(indicator.close, indicator.sma50),
            "sma50_gt_sma150": self._gt(indicator.sma50, indicator.sma150),
            "sma150_gt_sma200": self._gt(indicator.sma150, indicator.sma200),
            "sma200_slope_positive": self._gt(indicator.sma200_slope, 0),
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
        risk_metadata = self._risk_metadata(indicator, entry_chase_reference=indicator.sma50)
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
                    "rs_percentile_available": indicator.rs_percentile is not None,
                    "relative_strength_score_available": indicator.relative_strength_score is not None,
                    "trend_score_available": indicator.trend_score is not None,
                    "sector_rs_score_available": indicator.sector_rs_score is not None,
                    "market_score_available": indicator.market_score is not None,
                    **self._hardening_data_quality_flags(indicator, fundamentals, market_regime, risk_metadata),
                },
                optional_conditions=optional_conditions,
                risk_metadata=risk_metadata,
            ),
        )
