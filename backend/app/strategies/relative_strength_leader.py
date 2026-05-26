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
            "market_regime_not_bear": market_regime != "bear",
        }
        optional_conditions = []
        if self._market_score_filter_enabled():
            flags["market_score_min"] = self._gte(
                getattr(indicator, "market_score", None),
                self.config["market_score_min"],
            )
            optional_conditions.append("market_score_min")
        if self._atr_risk_filter_enabled():
            flags["atr20_pct_max"] = self._lte(getattr(indicator, "atr20_pct", None), self._max_atr20_pct())
            optional_conditions.append("atr20_pct_max")
        if self._fundamentals_quality_enabled():
            flags["roe_min"] = self._gte(getattr(fundamentals, "roe", None), self.config["min_roe"])
            optional_conditions.append("roe_min")
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
        risk_flags = self._risk_flags(indicator, fundamentals, market_regime)
        leadership_metadata = {
            "leadership_score": self._leadership_score(indicator),
            "rs_percentile": self._round_optional(getattr(indicator, "rs_percentile", None)),
            "relative_strength_score": self._round_optional(getattr(indicator, "relative_strength_score", None)),
            "sector_rs_score": self._round_optional(getattr(indicator, "sector_rs_score", None)),
            "near_high_52w": flags["near_high_52w"],
        }
        ranking_metadata = {
            "signal_type": "ranking_candidate",
            "execution_requires_portfolio_constructor": True,
        }
        metadata = self._metadata(
            flags,
            failed,
            summary,
            risk_flags=risk_flags,
            data_quality_flags={
                **self._data_quality_flags(indicator, fundamentals),
                **self._hardening_data_quality_flags(indicator, fundamentals, market_regime, risk_metadata),
            },
            optional_conditions=optional_conditions,
            risk_metadata=risk_metadata,
        )
        metadata["score_breakdown"].update(leadership_metadata)
        metadata.update({**leadership_metadata, **ranking_metadata})
        return StrategyResult(
            strategy_tag=self.name,
            passed=passed,
            pass_flags=flags,
            failed_conditions=failed,
            reason_summary=summary,
            metadata=metadata,
        )

    def _market_score_filter_enabled(self) -> bool:
        return bool(self.config.get("market_score_filter_enabled", False)) or bool(
            self.config.get("market_score_min_enabled", False)
        )

    def _atr_risk_filter_enabled(self) -> bool:
        return bool(self.config.get("atr_risk_filter_enabled", False)) or bool(
            self.config.get("atr20_pct_max_enabled", False)
        )

    def _fundamentals_quality_enabled(self) -> bool:
        return bool(self.config.get("fundamentals_quality_enabled", False)) or bool(
            self.config.get("optional_fundamental_quality_enabled", False)
        )

    def _max_atr20_pct(self) -> float | None:
        return self._as_float(self.config.get("max_atr20_pct", self.config.get("atr20_pct_max")))

    def _leadership_score(self, indicator: IndicatorSnapshot) -> float | None:
        rs_percentile = self._as_float(getattr(indicator, "rs_percentile", None))
        relative_strength_score = self._as_float(getattr(indicator, "relative_strength_score", None))
        sector_rs_score = self._as_float(getattr(indicator, "sector_rs_score", None))
        close = self._as_float(getattr(indicator, "close", None))
        high_52w = self._as_float(getattr(indicator, "high_52w", None))
        near_high_score = 1.0 if self._near_high_52w(indicator.close, indicator.high_52w) else 0.0
        if (
            rs_percentile is None
            or relative_strength_score is None
            or sector_rs_score is None
            or close is None
            or high_52w is None
            or high_52w <= 0
        ):
            return None
        return round(((rs_percentile / 100) + relative_strength_score + sector_rs_score + near_high_score) / 4, 6)

    def _risk_flags(
        self,
        indicator: IndicatorSnapshot,
        fundamentals: FundamentalsPti | None,
        market_regime: str,
    ) -> dict[str, bool]:
        market_score = self._as_float(getattr(indicator, "market_score", None))
        market_score_min = self._as_float(self.config.get("market_score_min"))
        atr20_pct = self._as_float(getattr(indicator, "atr20_pct", None))
        max_atr20_pct = self._max_atr20_pct()
        roe = self._as_float(getattr(fundamentals, "roe", None))
        min_roe = self._as_float(self.config.get("min_roe"))
        return {
            "bear_market": market_regime == "bear",
            "market_score_below_min": (
                market_score is not None and market_score_min is not None and market_score < market_score_min
            ),
            "atr20_pct_too_high": (
                atr20_pct is not None and max_atr20_pct is not None and atr20_pct > max_atr20_pct
            ),
            "fundamentals_missing": fundamentals is None,
            "roe_below_min": roe is not None and min_roe is not None and roe < min_roe,
            "leadership_score_unavailable": self._leadership_score(indicator) is None,
            "execution_requires_portfolio_constructor": True,
        }

    def _near_high_52w(self, close: float | None, high_52w: float | None) -> bool:
        threshold = float(self.config["near_high_52w_threshold"])
        return close is not None and high_52w is not None and high_52w > 0 and close >= high_52w * threshold

    @staticmethod
    def _data_quality_flags(indicator: IndicatorSnapshot, fundamentals: FundamentalsPti | None) -> dict[str, bool]:
        return {
            "rs_percentile_available": indicator.rs_percentile is not None,
            "relative_strength_score_available": indicator.relative_strength_score is not None,
            "sector_rs_score_available": indicator.sector_rs_score is not None,
            "market_score_available": getattr(indicator, "market_score", None) is not None,
            "high_52w_available": indicator.high_52w is not None,
            "volume_ratio_50_available": indicator.volume_ratio_50 is not None,
            "atr20_pct_available": getattr(indicator, "atr20_pct", None) is not None,
            "close_available": indicator.close is not None,
            "sma50_available": indicator.sma50 is not None,
            "sma150_available": indicator.sma150 is not None,
            "sma200_slope_available": indicator.sma200_slope is not None,
            "fundamentals_available": fundamentals is not None,
            "roe_available": fundamentals is not None and getattr(fundamentals, "roe", None) is not None,
        }

    def _round_optional(self, value: float | None) -> float | None:
        number = self._as_float(value)
        return round(number, 6) if number is not None else None
