from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.tables import (
    BrokerAuditEvent,
    KisTokenStatusMetadata,
    Order,
    PaperFill,
    PaperOrder,
    PaperPortfolioSnapshot,
    PaperPosition,
    Position,
)


class PaperRepository:
    """paper 전용 거래 상태를 조회하는 repository."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_orders(self, *, status: str | None = None) -> list[PaperOrder]:
        """저장된 `paper_orders` rows를 최신순으로 반환한다."""
        statement = select(PaperOrder).order_by(PaperOrder.created_ts.desc())
        normalized_status = status.strip() if status else None
        if normalized_status:
            statement = statement.where(PaperOrder.status == normalized_status)
        return list(self.db.scalars(statement).all())

    def list_fills(self, *, symbol: str | None = None) -> list[PaperFill]:
        """저장된 `paper_fills` rows를 체결시각 최신순으로 반환한다."""
        statement = select(PaperFill).order_by(PaperFill.fill_ts.desc())
        normalized_symbol = symbol.strip() if symbol else None
        if normalized_symbol:
            statement = statement.where(PaperFill.symbol == normalized_symbol)
        return list(self.db.scalars(statement).all())

    def list_positions(self, *, symbol: str | None = None) -> list[PaperPosition]:
        """저장된 `paper_positions` rows만 심볼순으로 반환한다."""
        statement = select(PaperPosition).order_by(PaperPosition.symbol.asc(), PaperPosition.id.asc())
        normalized_symbol = symbol.strip() if symbol else None
        if normalized_symbol:
            statement = statement.where(PaperPosition.symbol == normalized_symbol)
        return list(self.db.scalars(statement).all())

    def latest_portfolio_snapshot(self) -> PaperPortfolioSnapshot | None:
        """가장 최신 `paper_portfolio_snapshots` row를 반환한다."""
        return self.db.scalar(
            select(PaperPortfolioSnapshot).order_by(
                PaperPortfolioSnapshot.snapshot_ts.desc(),
                PaperPortfolioSnapshot.created_at.desc(),
            )
        )

    def counts(self) -> dict[str, int]:
        """paper persistence와 분리 확인에 필요한 대표 row 수를 반환한다."""
        return {
            "paper_orders_count": self._count(PaperOrder),
            "paper_fills_count": self._count(PaperFill),
            "paper_positions_count": self._count(PaperPosition),
            "paper_portfolio_snapshots_count": self._count(PaperPortfolioSnapshot),
            "broker_audit_events_count": self._count(BrokerAuditEvent),
            "kis_token_status_metadata_count": self._count(KisTokenStatusMetadata),
            "orders_count": self._count(Order),
            "synthetic_positions_count": self._count(Position),
        }

    def _count(self, model: type[object]) -> int:
        return int(self.db.scalar(select(func.count()).select_from(model)) or 0)
