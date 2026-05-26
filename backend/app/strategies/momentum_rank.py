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
        if self._atr_risk_filter_enabled():
            flags["atr20_pct_max"] = self._lte(getattr(indicator, "atr20_pct", None), self._max_atr20_pct())
            optional_conditions.append("atr20_pct_max")
        if self._volume_confirmation_enabled():
            flags["volume_ratio_50_min"] = self._gte(
                getattr(indicator, "volume_ratio_50", None),
                self._min_volume_ratio_50(),
            )
            optional_conditions.append("volume_ratio_50_min")
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
        risk_flags = self._risk_flags(indicator)
        momentum_quality_score = self._momentum_quality_score(indicator)
        metadata = self._metadata(
            flags,
            failed,
            summary,
            risk_flags=risk_flags,
            data_quality_flags={
                **self._data_quality_flags(indicator),
                **self._hardening_data_quality_flags(indicator, fundamentals, market_regime, risk_metadata),
            },
            optional_conditions=optional_conditions,
            risk_metadata=risk_metadata,
        )
        momentum_score_metadata = {
            "momentum_quality_score": momentum_quality_score,
            "relative_strength_score": self._round_optional(getattr(indicator, "relative_strength_score", None)),
            "trend_score": self._round_optional(getattr(indicator, "trend_score", None)),
            "sector_rs_score": self._round_optional(getattr(indicator, "sector_rs_score", None)),
            "market_score": self._round_optional(getattr(indicator, "market_score", None)),
            "atr20_pct": self._round_optional(getattr(indicator, "atr20_pct", None)),
            "volume_ratio_50": self._round_optional(getattr(indicator, "volume_ratio_50", None)),
        }
        ranking_metadata = {
            "signal_type": "ranking_candidate",
            "execution_requires_portfolio_constructor": True,
            "rebalance_rule_not_available_in_current_mvp": True,
        }
        metadata["score_breakdown"].update(momentum_score_metadata)
        metadata.update({**momentum_score_metadata, **ranking_metadata})
        return StrategyResult(
            strategy_tag=self.name,
            passed=passed,
            pass_flags=flags,
            failed_conditions=failed,
            reason_summary=summary,
            metadata=metadata,
        )

    def _atr_risk_filter_enabled(self) -> bool:
        return bool(self.config.get("atr_risk_filter_enabled", False)) or bool(
            self.config.get("atr20_pct_max_enabled", False)
        )

    def _volume_confirmation_enabled(self) -> bool:
        return bool(self.config.get("volume_confirmation_enabled", False)) or bool(
            self.config.get("volume_ratio_50_min_enabled", False)
        )

    def _max_atr20_pct(self) -> float | None:
        return self._as_float(self.config.get("max_atr20_pct", self.config.get("atr20_pct_max")))

    def _min_volume_ratio_50(self) -> float | None:
        return self._as_float(self.config.get("min_volume_ratio_50", self.config.get("volume_ratio_50_min")))

    def _momentum_quality_score(self, indicator: IndicatorSnapshot) -> float | None:
        scores = [
            self._as_float(getattr(indicator, "relative_strength_score", None)),
            self._as_float(getattr(indicator, "trend_score", None)),
            self._as_float(getattr(indicator, "sector_rs_score", None)),
            self._as_float(getattr(indicator, "market_score", None)),
        ]
        if any(score is None for score in scores):
            return None
        return round(sum(score for score in scores if score is not None) / len(scores), 6)

    def _risk_flags(self, indicator: IndicatorSnapshot) -> dict[str, bool]:
        atr20_pct = self._as_float(getattr(indicator, "atr20_pct", None))
        max_atr20_pct = self._max_atr20_pct()
        volume_ratio_50 = self._as_float(getattr(indicator, "volume_ratio_50", None))
        min_volume_ratio_50 = self._min_volume_ratio_50()
        return {
            "atr20_pct_too_high": (
                atr20_pct is not None and max_atr20_pct is not None and atr20_pct > max_atr20_pct
            ),
            "volume_ratio_50_too_low": (
                volume_ratio_50 is not None
                and min_volume_ratio_50 is not None
                and volume_ratio_50 < min_volume_ratio_50
            ),
            "execution_requires_portfolio_constructor": True,
            "rebalance_rule_not_available_in_current_mvp": True,
        }

    @staticmethod
    def _data_quality_flags(indicator: IndicatorSnapshot) -> dict[str, bool]:
        return {
            "rs_percentile_available": indicator.rs_percentile is not None,
            "relative_strength_score_available": indicator.relative_strength_score is not None,
            "trend_score_available": indicator.trend_score is not None,
            "sector_rs_score_available": indicator.sector_rs_score is not None,
            "market_score_available": indicator.market_score is not None,
            "atr20_pct_available": getattr(indicator, "atr20_pct", None) is not None,
            "volume_ratio_50_available": getattr(indicator, "volume_ratio_50", None) is not None,
            "close_available": indicator.close is not None,
            "sma50_available": indicator.sma50 is not None,
            "sma150_available": indicator.sma150 is not None,
            "sma200_available": indicator.sma200 is not None,
            "sma200_slope_available": indicator.sma200_slope is not None,
        }

    def _round_optional(self, value: float | None) -> float | None:
        number = self._as_float(value)
        return round(number, 6) if number is not None else None
