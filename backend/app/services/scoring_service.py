from __future__ import annotations

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
