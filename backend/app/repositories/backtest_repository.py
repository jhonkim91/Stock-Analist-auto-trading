from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.models.tables import BacktestRun


class BacktestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, run: BacktestRun) -> None:
        self.db.merge(run)
        self.db.commit()
