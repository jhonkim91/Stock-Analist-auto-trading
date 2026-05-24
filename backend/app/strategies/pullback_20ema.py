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
            "volume_ratio_50_max": self._lte(indicator.volume_ratio_50, self.config["max_pullback_volume_ratio"]),
            "atr20_pct_max": self._lte(indicator.atr20_pct, self.config["max_atr20_pct"]),
        }
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
                data_quality_flags=self._data_quality_flags(indicator),
            ),
        )

    def _low_touches_ema20(self, low: float | None, ema20: float | None) -> bool:
        buffer = float(self.config["pullback_touch_buffer"])
        return low is not None and ema20 is not None and low <= ema20 * buffer

    @staticmethod
    def _data_quality_flags(indicator: IndicatorSnapshot) -> dict[str, bool]:
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
        }
