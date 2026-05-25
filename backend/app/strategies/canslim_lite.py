from __future__ import annotations

from backend.app.models.tables import FundamentalsPti, IndicatorSnapshot
from backend.app.strategies.base import BaseStrategy, StrategyResult


class CanslimLiteStrategy(BaseStrategy):
    name = "canslim_lite"

    def evaluate(
        self,
        indicator: IndicatorSnapshot,
        fundamentals: FundamentalsPti | None,
        market_regime: str,
    ) -> StrategyResult:
        """CANSLIM Lite 조건을 보수적으로 평가하고 PTI 검증 상태를 기록한다."""
        fundamentals_available = fundamentals is not None
        fundamentals_effective_date_available = (
            fundamentals_available and getattr(fundamentals, "effective_date", None) is not None
        )
        flags = {
            "fundamentals_available_asof": fundamentals_available,
            "quarterly_eps_growth_min": self._gte(
                getattr(fundamentals, "quarterly_eps_growth", None),
                self.config["quarterly_eps_growth_min"],
            ),
            "sales_growth_min": self._gte(
                getattr(fundamentals, "sales_growth", None),
                self.config["sales_growth_min"],
            ),
            "rs_percentile_min": self._gte(indicator.rs_percentile, self.config["rs_percentile_min"]),
            "breakout": bool(indicator.breakout),
            "market_regime_bull": market_regime == self.config["required_market_regime"],
        }
        if bool(self.config.get("technical_trend_filter_enabled", False)):
            flags.update(
                {
                    "close_gt_sma50": self._gt(indicator.close, indicator.sma50),
                    "sma50_gt_sma150": self._gt(indicator.sma50, indicator.sma150),
                    "sma150_gt_sma200": self._gt(indicator.sma150, indicator.sma200),
                    "sma200_slope_positive": self._gt(indicator.sma200_slope, 0),
                }
            )
        if bool(self.config.get("volume_confirmation_enabled", False)):
            flags["volume_surge"] = self._volume_surge_confirmed(indicator)
        optional_conditions = []
        if bool(self.config.get("earnings_quality_enabled", False)):
            flags["roe_min"] = self._gte(getattr(fundamentals, "roe", None), self.config["min_roe"])
            optional_conditions.append("roe_min")
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
            include_fundamental_quality=True,
            include_earnings_quality=True,
        )
        failed = self._failed(flags)
        passed = self._all_flags(flags)
        summary = self._summary(self.name, passed, failed)
        risk_metadata = self._risk_metadata(indicator, entry_chase_reference=indicator.high_52w)
        metadata = self._metadata(
            flags,
            failed,
            summary,
            data_quality_flags={
                "fundamentals_available": fundamentals_available,
                "fundamentals_available_asof": fundamentals_available,
                "fundamentals_effective_date_available": fundamentals_effective_date_available,
                "quarterly_eps_growth_available": (
                    fundamentals_available and getattr(fundamentals, "quarterly_eps_growth", None) is not None
                ),
                "sales_growth_available": (
                    fundamentals_available and getattr(fundamentals, "sales_growth", None) is not None
                ),
                "roe_available": fundamentals_available and getattr(fundamentals, "roe", None) is not None,
                "rs_percentile_available": indicator.rs_percentile is not None,
                "breakout_available": getattr(indicator, "breakout", None) is not None,
                "close_available": indicator.close is not None,
                "sma50_available": indicator.sma50 is not None,
                "sma150_available": indicator.sma150 is not None,
                "sma200_available": indicator.sma200 is not None,
                "sma200_slope_available": indicator.sma200_slope is not None,
                "volume_available": indicator.volume is not None,
                "volume_ma50_available": indicator.volume_ma50 is not None,
                "technical_trend_available": self._technical_trend_available(indicator),
                "pti_validation_not_available_in_current_mvp": True,
                **self._hardening_data_quality_flags(indicator, fundamentals, market_regime, risk_metadata),
            },
            optional_conditions=optional_conditions,
            risk_metadata=risk_metadata,
        )
        metadata.update(
            {
                "fundamentals_available_asof": fundamentals_available,
                "fundamentals_effective_date_available": fundamentals_effective_date_available,
                "pti_validation_status": "pti_validation_not_available_in_current_mvp",
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

    def _volume_surge_confirmed(self, indicator: IndicatorSnapshot) -> bool:
        volume_ma50 = self._as_float(getattr(indicator, "volume_ma50", None))
        volume = self._as_float(getattr(indicator, "volume", None))
        return (
            volume is not None
            and volume_ma50 is not None
            and volume_ma50 > 0
            and volume >= volume_ma50 * float(self.config["volume_surge_multiple"])
        )

    @staticmethod
    def _technical_trend_available(indicator: IndicatorSnapshot) -> bool:
        return all(
            getattr(indicator, field_name, None) is not None
            for field_name in ("close", "sma50", "sma150", "sma200", "sma200_slope")
        )
