from __future__ import annotations

from backend.app.models.tables import FundamentalsPti, IndicatorSnapshot
from backend.app.strategies.base import BaseStrategy, StrategyResult


class DarvasBoxStrategy(BaseStrategy):
    """Evaluate an approximate Darvas Box breakout from indicator snapshots."""

    name = "darvas_box"

    def evaluate(
        self,
        indicator: IndicatorSnapshot,
        fundamentals: FundamentalsPti | None,
        market_regime: str,
    ) -> StrategyResult:
        """Return a pass/fail result using pivot fields already stored in indicator_snapshot."""
        box_top = indicator.pivot_high_20_prev
        box_bottom = indicator.pivot_low_20_prev
        box_height_pct = self._box_height_pct(box_top, box_bottom)
        flags = {
            "pivot_high_20_prev_available": box_top is not None,
            "pivot_low_20_prev_available": box_bottom is not None,
            "valid_box_range": box_height_pct is not None,
            "box_height_pct_max": self._lte(box_height_pct, self.config["max_box_height_pct"]),
            "close_gt_box_top": self._gt(indicator.close, box_top),
            "breakout": bool(indicator.breakout),
            "volume_surge": self._volume_surge(indicator.volume, indicator.volume_ma50),
            "rs_percentile_min": self._gte(indicator.rs_percentile, self.config["rs_percentile_min"]),
            "close_gt_sma50": self._gt(indicator.close, indicator.sma50),
            "sma50_gt_sma150": self._gt(indicator.sma50, indicator.sma150),
        }
        optional_conditions = []
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
        risk_metadata = self._risk_metadata(indicator, entry_chase_reference=box_top)
        metadata = self._metadata(
            flags,
            failed,
            summary,
            data_quality_flags={
                "pivot_high_20_prev_available": box_top is not None,
                "pivot_low_20_prev_available": box_bottom is not None,
                "box_height_pct_available": box_height_pct is not None,
                "volume_ma50_available": indicator.volume_ma50 is not None,
                "rs_percentile_available": indicator.rs_percentile is not None,
                "sma50_available": indicator.sma50 is not None,
                "sma150_available": indicator.sma150 is not None,
                **self._hardening_data_quality_flags(indicator, fundamentals, market_regime, risk_metadata),
            },
            optional_conditions=optional_conditions,
            risk_metadata=risk_metadata,
        )
        box_details = self._box_details(box_top, box_bottom, box_height_pct)
        metadata.update(box_details)
        metadata["score_breakdown"].update(box_details)
        return StrategyResult(
            strategy_tag=self.name,
            passed=passed,
            pass_flags=flags,
            failed_conditions=failed,
            reason_summary=summary,
            metadata=metadata,
        )

    @staticmethod
    def _box_height_pct(box_top: float | None, box_bottom: float | None) -> float | None:
        if box_top is None or box_bottom is None or box_bottom <= 0 or box_top <= box_bottom:
            return None
        return (box_top - box_bottom) / box_bottom

    @staticmethod
    def _box_details(
        box_top: float | None,
        box_bottom: float | None,
        box_height_pct: float | None,
    ) -> dict[str, float | None]:
        return {
            "box_top": round(float(box_top), 4) if box_top is not None else None,
            "box_bottom": round(float(box_bottom), 4) if box_bottom is not None else None,
            "box_height_pct": round(float(box_height_pct), 6) if box_height_pct is not None else None,
        }

    def _volume_surge(self, volume: float | None, volume_ma50: float | None) -> bool:
        multiple = float(self.config["volume_surge_multiple"])
        return volume is not None and volume_ma50 is not None and volume_ma50 > 0 and volume >= volume_ma50 * multiple
