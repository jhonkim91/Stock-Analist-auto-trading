from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.models.tables import DailyOhlcv, FundamentalsPti, IndexOhlcv, SectorOhlcv, SymbolMaster


class MarketRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def latest_trade_date(self) -> date | None:
        return self.db.scalar(select(DailyOhlcv.trade_date).order_by(DailyOhlcv.trade_date.desc()).limit(1))

    def list_symbols(self) -> list[SymbolMaster]:
        return list(self.db.scalars(select(SymbolMaster).order_by(SymbolMaster.symbol)).all())

    def get_symbol(self, symbol: str) -> SymbolMaster | None:
        return self.db.get(SymbolMaster, symbol)

    def clear_market_data(self) -> None:
        for table in (FundamentalsPti, SectorOhlcv, IndexOhlcv, DailyOhlcv, SymbolMaster):
            self.db.execute(delete(table))
        self.db.commit()

    def daily_df(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        stmt = select(DailyOhlcv)
        if start_date:
            stmt = stmt.where(DailyOhlcv.trade_date >= start_date)
        if end_date:
            stmt = stmt.where(DailyOhlcv.trade_date <= end_date)
        rows = self.db.scalars(stmt.order_by(DailyOhlcv.symbol, DailyOhlcv.trade_date)).all()
        return pd.DataFrame(
            [
                {
                    "trade_date": row.trade_date,
                    "symbol": row.symbol,
                    "open": row.open,
                    "high": row.high,
                    "low": row.low,
                    "close": row.close,
                    "adj_close": row.adj_close,
                    "volume": row.volume,
                    "turnover_value": row.turnover_value,
                    "venue": row.venue,
                }
                for row in rows
            ]
        )

    def index_df(self, symbol: str = "KOSPI_SAMPLE") -> pd.DataFrame:
        rows = self.db.scalars(select(IndexOhlcv).where(IndexOhlcv.symbol == symbol).order_by(IndexOhlcv.trade_date)).all()
        return pd.DataFrame(
            [
                {
                    "trade_date": row.trade_date,
                    "symbol": row.symbol,
                    "open": row.open,
                    "high": row.high,
                    "low": row.low,
                    "close": row.close,
                    "volume": row.volume,
                }
                for row in rows
            ]
        )

    def sector_df(self) -> pd.DataFrame:
        rows = self.db.scalars(select(SectorOhlcv).order_by(SectorOhlcv.sector, SectorOhlcv.trade_date)).all()
        return pd.DataFrame(
            [
                {
                    "trade_date": row.trade_date,
                    "sector": row.sector,
                    "open": row.open,
                    "high": row.high,
                    "low": row.low,
                    "close": row.close,
                    "volume": row.volume,
                }
                for row in rows
            ]
        )

    def fundamentals_asof(self, symbol: str, trade_date: date) -> FundamentalsPti | None:
        stmt = (
            select(FundamentalsPti)
            .where(FundamentalsPti.symbol == symbol, FundamentalsPti.effective_date <= trade_date)
            .order_by(FundamentalsPti.effective_date.desc(), FundamentalsPti.asof_date.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)
