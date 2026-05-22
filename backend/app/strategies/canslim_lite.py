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
        flags = {
            "fundamentals_available_asof": fundamentals is not None,
            "quarterly_eps_growth_min": bool(
                fundamentals and fundamentals.quarterly_eps_growth >= self.config["quarterly_eps_growth_min"]
            ),
            "sales_growth_min": bool(fundamentals and fundamentals.sales_growth >= self.config["sales_growth_min"]),
            "rs_percentile_min": self._gte(indicator.rs_percentile, self.config["rs_percentile_min"]),
            "breakout": bool(indicator.breakout),
            "market_regime_bull": market_regime == self.config["required_market_regime"],
        }
        optional_conditions = []
        if bool(self.config.get("earnings_quality_enabled", False)):
            flags["roe_min"] = bool(fundamentals and fundamentals.roe >= self.config["min_roe"])
            optional_conditions.append("roe_min")
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
                    "fundamentals_available": fundamentals is not None,
                    "rs_percentile_available": indicator.rs_percentile is not None,
                },
                optional_conditions=optional_conditions,
            ),
        )
