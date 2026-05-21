from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.models.tables import Report


class ReportRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, report: Report) -> None:
        self.db.merge(report)
        self.db.commit()
