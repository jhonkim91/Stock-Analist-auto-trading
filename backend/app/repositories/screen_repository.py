from __future__ import annotations

from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.models.tables import IndicatorSnapshot, ScreenResult


class ScreenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def clear_results(self, trade_date: date) -> None:
        self.db.execute(delete(ScreenResult).where(ScreenResult.trade_date == trade_date))
        self.db.commit()

    def latest_indicator_date(self) -> date | None:
        return self.db.scalar(select(IndicatorSnapshot.trade_date).order_by(IndicatorSnapshot.trade_date.desc()).limit(1))

    def indicators_for_date(self, trade_date: date) -> list[IndicatorSnapshot]:
        return list(
            self.db.scalars(
                select(IndicatorSnapshot).where(IndicatorSnapshot.trade_date == trade_date).order_by(IndicatorSnapshot.symbol)
            ).all()
        )

    def save_results(self, results: list[ScreenResult]) -> None:
        self.db.add_all(results)
        self.db.commit()

    def list_results(self, trade_date: date | None = None) -> list[ScreenResult]:
        stmt = select(ScreenResult)
        if trade_date:
            stmt = stmt.where(ScreenResult.trade_date == trade_date)
        return list(self.db.scalars(stmt.order_by(ScreenResult.trade_date.desc(), ScreenResult.total_score.desc())).all())
