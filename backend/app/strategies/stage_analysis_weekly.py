from __future__ import annotations

from backend.app.models.tables import FundamentalsPti, IndicatorSnapshot
from backend.app.strategies.base import BaseStrategy, StrategyResult


class StageAnalysisWeeklyStrategy(BaseStrategy):
    """Evaluate a weekly Stage 2 approximation from indicator snapshots."""

    name = "stage_analysis_weekly"

    def evaluate(
        self,
        indicator: IndicatorSnapshot,
        fundamentals: FundamentalsPti | None,
        market_regime: str,
    ) -> StrategyResult:
        """Return a pass/fail result for Weinstein-style Stage 2 conditions."""
        weekly_close_available = indicator.weekly_close is not None
        weekly_sma30_available = indicator.weekly_sma30 is not None
        weekly_sma30_slope_available = indicator.weekly_sma30_slope is not None
        weekly_data_available = (
            weekly_close_available
            and weekly_sma30_available
            and weekly_sma30_slope_available
        )
        require_stage1_breakout = bool(self.config.get("require_stage1_breakout", True))
        weekly_breakout_available = self._availability(indicator, "weekly_breakout_available")
        weekly_volume_ratio_available = self._availability(indicator, "weekly_volume_ratio_available")
        weekly_rs_score_available = self._availability(indicator, "weekly_rs_score_available")
        weekly_breakout = bool(getattr(indicator, "weekly_breakout", False))
        weekly_volume_ratio = self._as_float(getattr(indicator, "weekly_volume_ratio", None))
        weekly_rs_score = self._as_float(getattr(indicator, "weekly_rs_score", None))
        flags = {
            "weekly_close_available": weekly_close_available,
            "weekly_sma30_available": weekly_sma30_available,
            "weekly_sma30_slope_available": weekly_sma30_slope_available,
            "weekly_data_available": weekly_data_available,
            "weekly_close_gt_sma30": self._gt(indicator.weekly_close, indicator.weekly_sma30),
            "weekly_sma30_slope_positive": self._gt(indicator.weekly_sma30_slope, 0),
            "weekly_volume_ratio_available": weekly_volume_ratio_available,
            "weekly_volume_ratio_min": (
                weekly_volume_ratio_available
                and self._gte(weekly_volume_ratio, self.config.get("min_weekly_volume_ratio", 1.0))
            ),
            "weekly_rs_score_available": weekly_rs_score_available,
            "weekly_rs_score_min": (
                weekly_rs_score_available
                and self._gte(weekly_rs_score, self.config.get("min_weekly_rs_score", 0.70))
            ),
            "close_gt_sma200": self._gt(indicator.close, indicator.sma200),
            "sma50_gt_sma150": self._gt(indicator.sma50, indicator.sma150),
            "sma150_gt_sma200": self._gt(indicator.sma150, indicator.sma200),
            "market_regime_not_bear": market_regime != "bear",
        }
        if require_stage1_breakout:
            flags["weekly_breakout_available"] = weekly_breakout_available
            flags["weekly_breakout"] = weekly_breakout_available and weekly_breakout
        optional_conditions = []
        if self._sector_rs_filter_enabled():
            flags["sector_rs_score_min"] = self._gte(
                getattr(indicator, "sector_rs_score", None),
                self.config["sector_rs_score_min"],
            )
            optional_conditions.append("sector_rs_score_min")
        if self._market_score_filter_enabled():
            flags["market_score_min"] = self._gte(
                getattr(indicator, "market_score", None),
                self.config["market_score_min"],
            )
            optional_conditions.append("market_score_min")
        if self._fundamentals_quality_enabled():
            flags["roe_min"] = self._gte(getattr(fundamentals, "roe", None), self.config["min_roe"])
            optional_conditions.append("roe_min")
        self._apply_optional_hardening_flags(
            flags,
            optional_conditions,
            indicator,
            fundamentals,
            market_regime,
        )
        failed = self._failed(flags)
        passed = self._all_flags(flags)
        summary = self._summary(self.name, passed, failed)
        risk_metadata = self._weekly_risk_metadata(indicator, weekly_data_available)
        weekly_close_to_sma30_pct = self._weekly_close_to_sma30_pct(indicator)
        weekly_metadata = {
            "suggested_stop_basis": "weekly_sma30",
            "weekly_close_to_sma30_pct": self._round_optional(weekly_close_to_sma30_pct),
            "weekly_sma30_slope": self._round_optional(indicator.weekly_sma30_slope),
            "weekly_data_available": weekly_data_available,
            "weekly_breakout": weekly_breakout if weekly_breakout_available else None,
            "weekly_volume_ratio": self._round_optional(weekly_volume_ratio) if weekly_volume_ratio_available else None,
            "weekly_rs_score": self._round_optional(weekly_rs_score) if weekly_rs_score_available else None,
        }
        if risk_metadata:
            risk_metadata.update(weekly_metadata)
        metadata = self._metadata(
            flags,
            failed,
            summary,
            data_quality_flags={
                **self._data_quality_flags(indicator, fundamentals, weekly_data_available),
                **self._hardening_data_quality_flags(indicator, fundamentals, market_regime, risk_metadata),
            },
            optional_conditions=optional_conditions,
            risk_metadata=risk_metadata,
        )
        metadata["score_breakdown"].update(
            {
                "weekly_close_to_sma30_pct": weekly_metadata["weekly_close_to_sma30_pct"],
                "weekly_sma30_slope": weekly_metadata["weekly_sma30_slope"],
                "weekly_data_available": weekly_data_available,
                "weekly_breakout": weekly_metadata["weekly_breakout"],
                "weekly_volume_ratio": weekly_metadata["weekly_volume_ratio"],
                "weekly_rs_score": weekly_metadata["weekly_rs_score"],
            }
        )
        metadata.update(weekly_metadata)
        return StrategyResult(
            strategy_tag=self.name,
            passed=passed,
            pass_flags=flags,
            failed_conditions=failed,
            reason_summary=summary,
            metadata=metadata,
        )

    def _sector_rs_filter_enabled(self) -> bool:
        return bool(self.config.get("sector_rs_filter_enabled", False)) or bool(
            self.config.get("sector_rs_score_min_enabled", False)
        )

    def _market_score_filter_enabled(self) -> bool:
        return bool(self.config.get("market_score_filter_enabled", False)) or bool(
            self.config.get("market_score_min_enabled", False)
        )

    def _fundamentals_quality_enabled(self) -> bool:
        return bool(self.config.get("fundamentals_quality_enabled", False)) or bool(
            self.config.get("optional_fundamental_quality_enabled", False)
        )

    def _weekly_close_to_sma30_pct(self, indicator: IndicatorSnapshot) -> float | None:
        weekly_close = self._as_float(indicator.weekly_close)
        weekly_sma30 = self._as_float(indicator.weekly_sma30)
        if weekly_close is None or weekly_sma30 is None or weekly_sma30 <= 0:
            return None
        return (weekly_close / weekly_sma30) - 1

    def _weekly_risk_metadata(
        self,
        indicator: IndicatorSnapshot,
        weekly_data_available: bool,
    ) -> dict[str, object]:
        fallback_policy = (
            "weekly_sma30_stop_fallback_to_common_risk"
            if weekly_data_available
            else "fail_closed_missing_weekly_data_fallback_to_common_risk"
        )
        return self._risk_metadata_from_stop(
            indicator.close,
            indicator.weekly_sma30,
            "weekly_sma30",
            entry_chase_reference=indicator.weekly_sma30,
            fallback_policy=fallback_policy,
        )

    @staticmethod
    def _data_quality_flags(
        indicator: IndicatorSnapshot,
        fundamentals: FundamentalsPti | None,
        weekly_data_available: bool,
    ) -> dict[str, bool]:
        return {
            "weekly_data_available": weekly_data_available,
            "weekly_close_available": indicator.weekly_close is not None,
            "weekly_sma30_available": indicator.weekly_sma30 is not None,
            "weekly_sma30_slope_available": indicator.weekly_sma30_slope is not None,
            "weekly_breakout_available": bool(getattr(indicator, "weekly_breakout_available", False)),
            "weekly_volume_ratio_available": bool(getattr(indicator, "weekly_volume_ratio_available", False)),
            "weekly_rs_score_available": bool(getattr(indicator, "weekly_rs_score_available", False)),
            "sma50_available": indicator.sma50 is not None,
            "sma150_available": indicator.sma150 is not None,
            "sma200_available": indicator.sma200 is not None,
            "rs_percentile_available": indicator.rs_percentile is not None,
            "volume_ratio_50_available": indicator.volume_ratio_50 is not None,
            "sector_rs_score_available": getattr(indicator, "sector_rs_score", None) is not None,
            "market_score_available": getattr(indicator, "market_score", None) is not None,
            "fundamentals_available": fundamentals is not None,
            "roe_available": fundamentals is not None and getattr(fundamentals, "roe", None) is not None,
        }

    @staticmethod
    def _round_optional(value: float | None) -> float | None:
        return round(float(value), 6) if value is not None else None

    @staticmethod
    def _availability(indicator: IndicatorSnapshot, field_name: str) -> bool:
        return bool(getattr(indicator, field_name, False))
