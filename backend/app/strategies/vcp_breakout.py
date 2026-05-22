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
        optional_conditions = []
        if bool(self.config.get("pivot_distance_limit_enabled", False)):
            pivot_high = float(indicator.pivot_high_20_prev or 0)
            pivot_distance_pct = ((float(indicator.close) - pivot_high) / pivot_high) if pivot_high > 0 else None
            flags["pivot_distance_limit"] = self._lte(pivot_distance_pct, self.config["max_pivot_distance_pct"])
            optional_conditions.append("pivot_distance_limit")
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
                    "atr20_pct_ma60_available": indicator.atr20_pct_ma60 is not None,
                    "pivot_high_20_prev_available": indicator.pivot_high_20_prev is not None,
                },
                optional_conditions=optional_conditions,
            ),
        )
