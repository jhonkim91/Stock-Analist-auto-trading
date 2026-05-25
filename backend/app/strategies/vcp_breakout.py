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
        pivot_distance_pct = self._pivot_distance_pct(indicator.close, indicator.pivot_high_20_prev)
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
            "market_regime_not_bear": self._market_regime_allowed(market_regime),
        }
        optional_conditions = []
        if bool(self.config.get("pivot_distance_limit_enabled", False)):
            flags["pivot_distance_limit"] = self._lte(pivot_distance_pct, self.config["max_pivot_distance_pct"])
            optional_conditions.append("pivot_distance_limit")
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
        risk_metadata = self._risk_metadata(indicator, entry_chase_reference=indicator.pivot_high_20_prev)
        metadata = self._metadata(
            flags,
            failed,
            summary,
            data_quality_flags={
                "atr20_pct_available": indicator.atr20_pct is not None,
                "atr20_pct_ma60_available": indicator.atr20_pct_ma60 is not None,
                "pivot_high_20_prev_available": indicator.pivot_high_20_prev is not None,
                "pivot_distance_pct_available": pivot_distance_pct is not None,
                **self._hardening_data_quality_flags(indicator, fundamentals, market_regime, risk_metadata),
            },
            optional_conditions=optional_conditions,
            risk_metadata=risk_metadata,
        )
        metadata.update(
            {
                "pivot_distance_pct": self._round_optional(pivot_distance_pct),
                "contraction_confirmed": flags["atr20_pct_contracting"] and flags["std20_lt_std60"],
                "volume_dry_up_confirmed": flags["volume_dry_up"],
                "breakout_volume_confirmed": flags["pivot_breakout"] and flags["volume_surge"],
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

    def _market_regime_allowed(self, market_regime: str) -> bool:
        if bool(self.config.get("allow_neutral_market", True)):
            return market_regime != "bear"
        return market_regime == "bull"

    def _sector_rs_filter_enabled(self) -> bool:
        return bool(self.config.get("sector_rs_filter_enabled", False)) or bool(
            self.config.get("sector_rs_score_min_enabled", False)
        )

    def _atr_risk_filter_enabled(self) -> bool:
        return bool(self.config.get("atr_risk_filter_enabled", False)) or bool(
            self.config.get("atr20_pct_max_enabled", False)
        )

    def _max_atr20_pct(self) -> float | None:
        return self.config.get("max_atr20_pct", self.config.get("atr20_pct_max"))

    def _pivot_distance_pct(self, close: float | None, pivot_high: float | None) -> float | None:
        close_value = self._as_float(close)
        pivot_high_value = self._as_float(pivot_high)
        if close_value is None or pivot_high_value is None or pivot_high_value <= 0:
            return None
        return (close_value - pivot_high_value) / pivot_high_value

    @staticmethod
    def _round_optional(value: float | None) -> float | None:
        return round(value, 6) if value is not None else None
