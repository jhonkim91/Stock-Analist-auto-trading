from __future__ import annotations

from backend.app.models.tables import FundamentalsPti, IndicatorSnapshot
from backend.app.strategies.base import BaseStrategy, StrategyResult


class VcpBreakoutStrategy(BaseStrategy):
    name = "vcp_breakout"

    def evaluate(
        self,
        indicator: IndicatorSnapshot,
        fundamentals: FundamentalsPti | None,
        market_regime: str,
    ) -> StrategyResult:
        trend_ok = (
            self._gt(indicator.close, indicator.sma50)
            and self._gt(indicator.sma50, indicator.sma150)
            and self._gt(indicator.sma150, indicator.sma200)
            and self._gt(indicator.sma200_slope, 0)
        )
        flags = {
            "trend_ok": trend_ok,
            "atr20_pct_contracting": self._gt(indicator.atr20_pct_ma60, indicator.atr20_pct),
            "std20_lt_std60": self._gt(indicator.std60, indicator.std20),
            "volume_dry_up": bool(indicator.volume_dry_up),
            "pivot_breakout": bool(indicator.breakout),
            "volume_surge": self._gte(indicator.volume, (indicator.volume_ma50 or 0) * self.config["volume_surge_multiple"]),
            "rs_percentile_min": self._gte(indicator.rs_percentile, self.config["rs_percentile_min"]),
        }
        failed = self._failed(flags)
        passed = self._all_flags(flags)
        return StrategyResult(
            strategy_tag=self.name,
            passed=passed,
            pass_flags=flags,
            failed_conditions=failed,
            reason_summary=self._summary(self.name, passed, failed),
        )
