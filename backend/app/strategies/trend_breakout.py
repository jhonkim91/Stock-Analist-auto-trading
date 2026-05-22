from __future__ import annotations

from backend.app.models.tables import FundamentalsPti, IndicatorSnapshot
from backend.app.strategies.base import BaseStrategy, StrategyResult


class TrendBreakoutStrategy(BaseStrategy):
    name = "trend_breakout"

    def evaluate(
        self,
        indicator: IndicatorSnapshot,
        fundamentals: FundamentalsPti | None,
        market_regime: str,
    ) -> StrategyResult:
        flags = {
            "close_gt_sma50": self._gt(indicator.close, indicator.sma50),
            "sma50_gt_sma150": self._gt(indicator.sma50, indicator.sma150),
            "sma150_gt_sma200": self._gt(indicator.sma150, indicator.sma200),
            "sma200_slope_positive": self._gt(indicator.sma200_slope, 0),
            "rs_percentile_min": self._gte(indicator.rs_percentile, self.config["rs_percentile_min"]),
            "near_52w_high": self._gte(indicator.close, (indicator.high_52w or 0) * self.config["high_52w_threshold"]),
            "volume_surge": self._gte(indicator.volume, (indicator.volume_ma50 or 0) * self.config["volume_surge_multiple"]),
        }
        optional_conditions = []
        if bool(self.config.get("atr_risk_filter_enabled", False)):
            flags["atr20_pct_max"] = self._lte(indicator.atr20_pct, self.config["max_atr20_pct"])
            optional_conditions.append("atr20_pct_max")
        failed = self._failed(flags)
        passed = self._all_flags(flags)
        summary = self._summary(self.name, passed, failed)
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
                    "atr20_pct_available": indicator.atr20_pct is not None,
                    "rs_percentile_available": indicator.rs_percentile is not None,
                    "volume_ma50_available": indicator.volume_ma50 is not None,
                },
                optional_conditions=optional_conditions,
            ),
        )
