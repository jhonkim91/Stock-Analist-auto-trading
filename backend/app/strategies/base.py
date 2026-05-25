from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.models.tables import FundamentalsPti, IndicatorSnapshot


@dataclass
class StrategyResult:
    strategy_tag: str
    passed: bool
    pass_flags: dict[str, bool]
    failed_conditions: list[str] = field(default_factory=list)
    reason_summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseStrategy:
    name = "base"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def evaluate(
        self,
        indicator: IndicatorSnapshot,
        fundamentals: FundamentalsPti | None,
        market_regime: str,
    ) -> StrategyResult:
        raise NotImplementedError

    @staticmethod
    def _all_flags(flags: dict[str, bool]) -> bool:
        return all(flags.values())

    @staticmethod
    def _failed(flags: dict[str, bool]) -> list[str]:
        return [key for key, value in flags.items() if not value]

    @staticmethod
    def _summary(strategy_name: str, passed: bool, failed: list[str]) -> str:
        if passed:
            return f"{strategy_name} 조건을 모두 충족했습니다."
        return f"{strategy_name} 탈락 조건: {', '.join(failed)}"

    @classmethod
    def _metadata(
        cls,
        flags: dict[str, bool],
        failed: list[str],
        explanation: str,
        *,
        risk_flags: dict[str, bool] | None = None,
        data_quality_flags: dict[str, bool] | None = None,
        optional_conditions: list[str] | None = None,
        risk_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        triggered = [key for key, value in flags.items() if value]
        total_conditions = max(len(flags), 1)
        return {
            "triggered_conditions": triggered,
            "failed_conditions": failed,
            "score_breakdown": {
                "condition_score": round(len(triggered) / total_conditions, 4),
                "triggered_count": len(triggered),
                "failed_count": len(failed),
                "total_conditions": len(flags),
            },
            "risk_flags": risk_flags or {},
            "data_quality_flags": data_quality_flags or {},
            "optional_conditions": optional_conditions or [],
            "risk_metadata": risk_metadata or {},
            "explanation": explanation,
            "rationale": explanation,
        }

    @staticmethod
    def _gt(left: float | None, right: float | None) -> bool:
        return left is not None and right is not None and left > right

    @staticmethod
    def _gte(left: float | None, right: float | None) -> bool:
        return left is not None and right is not None and left >= right

    @staticmethod
    def _lte(left: float | None, right: float | None) -> bool:
        return left is not None and right is not None and left <= right

    def _apply_optional_hardening_flags(
        self,
        flags: dict[str, bool],
        optional_conditions: list[str],
        indicator: IndicatorSnapshot,
        fundamentals: FundamentalsPti | None,
        market_regime: str,
        *,
        include_near_high: bool = False,
        include_fundamental_quality: bool = False,
        include_earnings_quality: bool = False,
    ) -> None:
        if bool(self.config.get("market_regime_not_bear_enabled", False)) and "market_regime_not_bear" not in flags:
            flags["market_regime_not_bear"] = market_regime != "bear"
            optional_conditions.append("market_regime_not_bear")
        if bool(self.config.get("sector_rs_score_min_enabled", False)) and "sector_rs_score_min" not in flags:
            flags["sector_rs_score_min"] = self._gte(
                getattr(indicator, "sector_rs_score", None),
                self.config["sector_rs_score_min"],
            )
            optional_conditions.append("sector_rs_score_min")
        if bool(self.config.get("market_score_min_enabled", False)) and "market_score_min" not in flags:
            flags["market_score_min"] = self._gte(getattr(indicator, "market_score", None), self.config["market_score_min"])
            optional_conditions.append("market_score_min")
        if bool(self.config.get("atr20_pct_max_enabled", False)) and "atr20_pct_max" not in flags:
            atr20_pct_max = self.config.get("atr20_pct_max", self.config.get("max_atr20_pct"))
            flags["atr20_pct_max"] = self._lte(getattr(indicator, "atr20_pct", None), atr20_pct_max)
            optional_conditions.append("atr20_pct_max")
        if bool(self.config.get("volume_ratio_50_min_enabled", False)) and "volume_ratio_50_min" not in flags:
            volume_ratio_50_min = self.config.get("volume_ratio_50_min", self.config.get("min_volume_ratio_50"))
            flags["volume_ratio_50_min"] = self._gte(
                getattr(indicator, "volume_ratio_50", None),
                volume_ratio_50_min,
            )
            optional_conditions.append("volume_ratio_50_min")
        if (
            include_near_high
            and bool(self.config.get("near_high_52w_threshold_enabled", False))
            and "near_high_52w_threshold" not in flags
        ):
            flags["near_high_52w_threshold"] = self._near_high_52w_threshold(indicator)
            optional_conditions.append("near_high_52w_threshold")
        if include_fundamental_quality and bool(self.config.get("optional_fundamental_quality_enabled", False)):
            flags["optional_fundamental_quality"] = self._optional_fundamental_quality(fundamentals)
            optional_conditions.append("optional_fundamental_quality")
        if include_earnings_quality and bool(self.config.get("optional_earnings_quality_enabled", False)):
            flags["optional_earnings_quality"] = self._optional_earnings_quality(fundamentals)
            optional_conditions.append("optional_earnings_quality")

    def _hardening_data_quality_flags(
        self,
        indicator: IndicatorSnapshot,
        fundamentals: FundamentalsPti | None,
        market_regime: str,
        risk_metadata: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        risk_metadata = risk_metadata or {}
        return {
            "market_regime_available": bool(market_regime),
            "sector_rs_score_available": getattr(indicator, "sector_rs_score", None) is not None,
            "market_score_available": getattr(indicator, "market_score", None) is not None,
            "atr20_pct_available": getattr(indicator, "atr20_pct", None) is not None,
            "volume_ratio_50_available": getattr(indicator, "volume_ratio_50", None) is not None,
            "near_high_52w_available": (
                getattr(indicator, "close", None) is not None and getattr(indicator, "high_52w", None) is not None
            ),
            "fundamentals_available": fundamentals is not None,
            "fundamental_quality_available": (
                fundamentals is not None
                and getattr(fundamentals, "roe", None) is not None
                and getattr(fundamentals, "gross_profitability", None) is not None
            ),
            "earnings_quality_available": (
                fundamentals is not None
                and getattr(fundamentals, "quarterly_eps_growth", None) is not None
                and getattr(fundamentals, "sales_growth", None) is not None
            ),
            "suggested_stop_price_available": risk_metadata.get("suggested_stop_price") is not None,
            "risk_per_share_available": risk_metadata.get("risk_per_share") is not None,
            "entry_chase_reference_available": risk_metadata.get("entry_chase_reference") is not None,
        }

    def _risk_metadata(
        self,
        indicator: IndicatorSnapshot,
        *,
        entry_chase_reference: float | None = None,
    ) -> dict[str, Any]:
        if not bool(self.config.get("risk_metadata_enabled", True)):
            return {}

        close = self._as_float(getattr(indicator, "close", None))
        reference = self._as_float(entry_chase_reference)
        if close is None or close <= 0:
            return {
                "suggested_stop_price": None,
                "risk_per_share": None,
                "risk_basis": "unavailable",
                "entry_chase_warning": False,
                "entry_chase_reference": reference,
            }

        candidates: list[tuple[float, str]] = []
        atr20 = self._as_float(getattr(indicator, "atr20", None))
        atr20_pct = self._as_float(getattr(indicator, "atr20_pct", None))
        if atr20 is None and atr20_pct is not None:
            atr20 = close * atr20_pct
        if atr20 is not None and atr20 > 0:
            candidates.append((close - atr20 * float(self.config.get("risk_stop_atr_multiple", 2.0)), "atr20"))

        hard_stop = close * (1 - float(self.config.get("risk_hard_stop_pct", 0.08)))
        candidates.append((hard_stop, "hard_stop_pct"))

        pivot_low = self._as_float(getattr(indicator, "pivot_low_20_prev", None))
        if pivot_low is not None and 0 < pivot_low < close:
            candidates.append((pivot_low, "pivot_low_20_prev"))

        valid_candidates = [(price, basis) for price, basis in candidates if 0 < price < close]
        suggested_stop_price, risk_basis = max(valid_candidates, default=(None, "unavailable"), key=lambda item: item[0])
        risk_per_share = close - suggested_stop_price if suggested_stop_price is not None else None
        chase_threshold = float(self.config.get("entry_chase_warning_threshold_pct", 0.03))
        entry_chase_warning = reference is not None and reference > 0 and close > reference * (1 + chase_threshold)
        return {
            "suggested_stop_price": round(suggested_stop_price, 4) if suggested_stop_price is not None else None,
            "risk_per_share": round(risk_per_share, 4) if risk_per_share is not None else None,
            "risk_basis": risk_basis,
            "entry_chase_warning": entry_chase_warning,
            "entry_chase_reference": round(reference, 4) if reference is not None else None,
        }

    def _near_high_52w_threshold(self, indicator: IndicatorSnapshot) -> bool:
        threshold = float(self.config["near_high_52w_threshold"])
        close = getattr(indicator, "close", None)
        high_52w = getattr(indicator, "high_52w", None)
        return close is not None and high_52w is not None and high_52w > 0 and close >= high_52w * threshold

    def _optional_fundamental_quality(self, fundamentals: FundamentalsPti | None) -> bool:
        return bool(
            fundamentals
            and getattr(fundamentals, "roe", None) is not None
            and getattr(fundamentals, "gross_profitability", None) is not None
            and fundamentals.roe >= float(self.config["min_roe"])
            and fundamentals.gross_profitability >= float(self.config["min_gross_profitability"])
        )

    def _optional_earnings_quality(self, fundamentals: FundamentalsPti | None) -> bool:
        return bool(
            fundamentals
            and getattr(fundamentals, "quarterly_eps_growth", None) is not None
            and getattr(fundamentals, "sales_growth", None) is not None
            and fundamentals.quarterly_eps_growth >= float(self.config["quarterly_eps_growth_min"])
            and fundamentals.sales_growth >= float(self.config["sales_growth_min"])
        )

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
