from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.app.models.tables import BacktestRun, BacktestTradeLedger


class BacktestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, run: BacktestRun, trades: list[BacktestTradeLedger] | None = None) -> None:
        self.db.merge(run)
        if trades is not None:
            self.db.execute(delete(BacktestTradeLedger).where(BacktestTradeLedger.run_id == run.run_id))
            self.db.add_all(trades)
        self.db.commit()

    def trades_for_run(self, run_id: str) -> list[BacktestTradeLedger]:
        """저장된 backtest trade ledger를 run 내부 순서대로 반환한다."""
        return list(
            self.db.scalars(
                select(BacktestTradeLedger)
                .where(BacktestTradeLedger.run_id == run_id)
                .order_by(BacktestTradeLedger.trade_index)
            ).all()
        )

    def trade_count_for_run(self, run_id: str) -> int:
        """저장된 backtest trade ledger row 수를 반환한다."""
        return int(
            self.db.scalar(
                select(func.count()).select_from(BacktestTradeLedger).where(BacktestTradeLedger.run_id == run_id)
            )
            or 0
        )
