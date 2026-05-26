from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.models.tables import FundamentalsPti, IndicatorSnapshot


class ScoringService:
    def score(self, indicator: IndicatorSnapshot, fundamentals: FundamentalsPti | None, rr_score: float) -> float:
        """리포트와 스크리너 정렬용 총점을 계산한다."""
        fund_score = 0.0
        if fundamentals:
            eps_score = min(max(fundamentals.quarterly_eps_growth / 0.25, 0), 1)
            sales_score = min(max(fundamentals.sales_growth / 0.20, 0), 1)
            fund_score = (eps_score + sales_score) / 2
        total = (
            0.20 * indicator.market_score
            + 0.10 * indicator.sector_rs_score
            + 0.20 * indicator.trend_score
            + 0.15 * indicator.relative_strength_score
            + 0.10 * indicator.volume_score
            + 0.10 * indicator.pattern_score
            + 0.10 * fund_score
            + 0.05 * rr_score
        )
        return round(float(total), 4)

    def rank_score(
        self,
        strategy_name: str,
        indicator: IndicatorSnapshot,
        fundamentals: FundamentalsPti | None,
        rr_score: float,
        metadata: Mapping[str, Any] | None = None,
    ) -> float:
        """Ranking 전략의 포트폴리오 후보 정렬 점수를 계산한다."""
        metadata = metadata or {}
        metadata_key = {
            "momentum_rank": "momentum_quality_score",
            "relative_strength_leader": "leadership_score",
        }.get(strategy_name)
        if metadata_key:
            metadata_score = self._numeric_metadata_score(metadata.get(metadata_key))
            if metadata_score is not None:
                return metadata_score
        return self.score(indicator, fundamentals, rr_score)

    @staticmethod
    def _numeric_metadata_score(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return round(number, 4)
