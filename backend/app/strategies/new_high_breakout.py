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
            "breakout": bool(indicator.breakout),
            "volume_surge": self._volume_surge(indicator.volume, indicator.volume_ma50),
            "rs_percentile_min": self._gte(indicator.rs_percentile, self.config["rs_percentile_min"]),
            "close_gt_sma50": self._gt(indicator.close, indicator.sma50),
            "sma50_gt_sma150": self._gt(indicator.sma50, indicator.sma150),
            "sma150_gt_sma200": self._gt(indicator.sma150, indicator.sma200),
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
                data_quality_flags={
                    "close_available": indicator.close is not None,
                    "high_52w_available": indicator.high_52w is not None,
                    "distance_from_52w_high_available": indicator.distance_from_52w_high is not None,
                    "volume_available": indicator.volume is not None,
                    "volume_ma50_available": indicator.volume_ma50 is not None,
                    "volume_ratio_50_available": indicator.volume_ratio_50 is not None,
                    "rs_percentile_available": indicator.rs_percentile is not None,
                    "sma50_available": indicator.sma50 is not None,
                    "sma150_available": indicator.sma150 is not None,
                    "sma200_available": indicator.sma200 is not None,
                },
            ),
        )

    def _near_new_high(self, close: float | None, high_52w: float | None) -> bool:
        threshold = float(self.config["new_high_threshold"])
        return close is not None and high_52w is not None and high_52w > 0 and close >= high_52w * threshold

    def _volume_surge(self, volume: float | None, volume_ma50: float | None) -> bool:
        multiple = float(self.config["volume_surge_multiple"])
        return volume is not None and volume_ma50 is not None and volume_ma50 > 0 and volume >= volume_ma50 * multiple
