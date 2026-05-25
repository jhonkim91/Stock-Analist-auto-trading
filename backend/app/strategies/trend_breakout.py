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
        high_52w = getattr(indicator, "high_52w", None)
        flags = {
            "close_gt_sma50": self._gt(indicator.close, indicator.sma50),
            "sma50_gt_sma150": self._gt(indicator.sma50, indicator.sma150),
            "sma150_gt_sma200": self._gt(indicator.sma150, indicator.sma200),
            "sma200_slope_positive": self._gt(indicator.sma200_slope, 0),
            "rs_percentile_min": self._gte(indicator.rs_percentile, self.config["rs_percentile_min"]),
            "near_52w_high": self._gte(
                indicator.close,
                high_52w * self.config["high_52w_threshold"] if high_52w is not None else None,
            ),
            "breakout": bool(getattr(indicator, "breakout", False)),
            "market_regime_not_bear": self._market_regime_allowed(market_regime),
            "volume_surge": self._gte(indicator.volume, (indicator.volume_ma50 or 0) * self.config["volume_surge_multiple"]),
        }
        optional_conditions = []
        if bool(self.config.get("atr_risk_filter_enabled", False)):
            flags["atr20_pct_max"] = self._lte(indicator.atr20_pct, self.config["max_atr20_pct"])
            optional_conditions.append("atr20_pct_max")
        if bool(self.config.get("sector_rs_filter_enabled", False)):
            flags["sector_rs_score_min"] = self._gte(
                getattr(indicator, "sector_rs_score", None),
                self.config["sector_rs_score_min"],
            )
            optional_conditions.append("sector_rs_score_min")
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
        risk_metadata = self._risk_metadata(indicator, entry_chase_reference=high_52w)
        risk_flags = self._entry_chase_risk_flags(indicator)
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
                risk_flags=risk_flags,
                data_quality_flags={
                    "atr20_pct_available": indicator.atr20_pct is not None,
                    "rs_percentile_available": indicator.rs_percentile is not None,
                    "volume_ma50_available": indicator.volume_ma50 is not None,
                    "breakout_available": getattr(indicator, "breakout", None) is not None,
                    "high_52w_available": high_52w is not None,
                    "sector_rs_score_available": getattr(indicator, "sector_rs_score", None) is not None,
                    "market_regime_available": bool(market_regime),
                    **self._hardening_data_quality_flags(indicator, fundamentals, market_regime, risk_metadata),
                },
                optional_conditions=optional_conditions,
                risk_metadata=risk_metadata,
            ),
        )

    def _market_regime_allowed(self, market_regime: str) -> bool:
        allowed_regimes = {"bull"}
        if bool(self.config.get("allow_neutral_market", True)):
            allowed_regimes.add("neutral")
        return market_regime in allowed_regimes

    def _entry_chase_risk_flags(self, indicator: IndicatorSnapshot) -> dict[str, bool]:
        close = self._as_float(getattr(indicator, "close", None))
        high_52w = self._as_float(getattr(indicator, "high_52w", None))
        distance = self._as_float(getattr(indicator, "distance_from_52w_high", None))
        threshold = float(self.config.get("entry_chase_warning_threshold_pct", 0.03))
        too_close_to_high = distance is not None and 0 <= distance <= threshold
        extended_above_high = (
            close is not None
            and high_52w is not None
            and high_52w > 0
            and close > high_52w * (1 + threshold)
        )
        return {
            "entry_chase_warning": too_close_to_high or extended_above_high,
            "distance_from_52w_high_too_low": too_close_to_high,
            "close_extended_above_52w_high": extended_above_high,
        }
