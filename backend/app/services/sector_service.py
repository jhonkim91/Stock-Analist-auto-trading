from __future__ import annotations

import pandas as pd
from sqlalchemy.orm import Session

from backend.app.repositories.market_repository import MarketRepository


class SectorService:
    def __init__(self, db: Session) -> None:
        self.repo = MarketRepository(db)

    def latest_rotation(self) -> list[dict[str, object]]:
        """최신 섹터 상대강도 순위를 반환한다."""
        sector_df = self.repo.sector_df()
        if sector_df.empty:
            return []
        sector_df = sector_df.sort_values(["sector", "trade_date"]).copy()
        sector_df["ret_126"] = sector_df.groupby("sector")["close"].pct_change(126)
        latest_date = sector_df["trade_date"].max()
        latest = sector_df[sector_df["trade_date"] == latest_date].copy()
        latest["rs_rank"] = latest["ret_126"].rank(ascending=False, method="min")
        latest["trend_ok"] = latest["ret_126"] > 0
        return [
            {
                "sector": row.sector,
                "rs_rank": int(row.rs_rank) if not pd.isna(row.rs_rank) else None,
                "trend_ok": bool(row.trend_ok),
                "note": "상대강도 양호" if bool(row.trend_ok) else "상대강도 약함",
            }
            for row in latest.sort_values("rs_rank").itertuples(index=False)
        ]
