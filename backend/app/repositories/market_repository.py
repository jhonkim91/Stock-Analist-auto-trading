from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.models.tables import (
    CorporateAction,
    DailyOhlcv,
    EarningsEvent,
    FundamentalsPti,
    IndexOhlcv,
    SectorOhlcv,
    SymbolMaster,
)


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
        for table in (EarningsEvent, FundamentalsPti, CorporateAction, SectorOhlcv, IndexOhlcv, DailyOhlcv, SymbolMaster):
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
        """trade_date 기준으로 이미 유효한 최신 fundamentals row만 반환한다."""
        stmt = (
            select(FundamentalsPti)
            .where(FundamentalsPti.symbol == symbol, FundamentalsPti.effective_date <= trade_date)
            .order_by(FundamentalsPti.effective_date.desc(), FundamentalsPti.asof_date.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def corporate_actions_asof(self, symbol: str, trade_date: date) -> list[CorporateAction]:
        """trade_date까지 유효한 corporate action만 최신순으로 반환한다.

        현재 DB 모델의 `action_date`를 backtest/adjusted-price 계층에서
        effective-date로 해석하며, future action은 절대 반환하지 않는다.
        """
        stmt = (
            select(CorporateAction)
            .where(CorporateAction.symbol == symbol, CorporateAction.action_date <= trade_date)
            .order_by(CorporateAction.action_date.desc(), CorporateAction.id.desc())
        )
        return list(self.db.scalars(stmt).all())

    def earnings_event_asof(
        self,
        symbol: str,
        trade_date: date,
        *,
        lookback_days: int = 120,
        lookahead_days: int = 120,
    ) -> EarningsEvent | None:
        """blackout 판단용 event-calendar row를 trade_date 주변 대칭 window에서 반환한다.

        fundamentals/corporate action과 달리 earnings blackout은 예정 이벤트도
        위험 요인으로 보므로 lookahead window를 허용한다. timestamp/session 품질
        검증과 fail-closed 판단은 strategy 계층에서 수행한다.
        """
        start_date = trade_date - timedelta(days=max(int(lookback_days), 0))
        end_date = trade_date + timedelta(days=max(int(lookahead_days), 0))
        stmt = (
            select(EarningsEvent)
            .where(
                EarningsEvent.symbol == symbol,
                EarningsEvent.earnings_date >= start_date,
                EarningsEvent.earnings_date <= end_date,
            )
            .order_by(EarningsEvent.earnings_date)
        )
        rows = list(self.db.scalars(stmt).all())
        if not rows:
            return None
        return min(
            rows,
            key=lambda row: self._earnings_sort_key(row, trade_date),
        )

    @staticmethod
    def _earnings_sort_key(row: EarningsEvent, trade_date: date) -> tuple[object, ...]:
        release_ts = row.release_ts
        release_date = release_ts.date() if isinstance(release_ts, datetime) else row.earnings_date
        session = str(row.session or "").strip().lower()
        session_rank = {
            "before_open": 0,
            "pre_market": 0,
            "regular": 1,
            "during_market": 1,
            "after_close": 2,
            "after_market": 2,
        }.get(session, 3)
        return (
            abs((release_date - trade_date).days),
            0 if release_date >= trade_date else 1,
            release_ts is None,
            session_rank,
            release_date,
            row.earnings_date,
        )
