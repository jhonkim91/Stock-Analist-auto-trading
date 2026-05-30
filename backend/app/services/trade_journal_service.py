from __future__ import annotations

import csv
from io import StringIO
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.tables import BacktestTradeLedger, PaperFill, PaperOrder

JournalSource = Literal["all", "backtest", "paper"]

CSV_COLUMNS = [
    "source",
    "event_date",
    "symbol",
    "side",
    "qty",
    "entry_price",
    "exit_price",
    "fill_price",
    "pnl",
    "return_pct",
    "strategy_name",
    "status",
    "run_id",
    "order_id",
    "fill_id",
    "notes",
]


class TradeJournalService:
    """backtest ledger와 paper 체결/주문을 CSV 매매일지 형태로 정규화한다."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def entries(
        self,
        *,
        source: JournalSource = "all",
        run_id: str | None = None,
        limit: int = 500,
    ) -> dict[str, object]:
        """매매일지 row 목록을 최신순으로 반환한다."""
        normalized_source = self._normalize_source(source)
        rows = self._entries(normalized_source, run_id=run_id, limit=limit)
        return {
            "ok": True,
            "source": normalized_source,
            "count": len(rows),
            "entries": rows,
            "csv_columns": CSV_COLUMNS,
            "network_call_performed": False,
            "live_order_created": False,
            "broker_order_created": False,
        }

    def csv_text(
        self,
        *,
        source: JournalSource = "all",
        run_id: str | None = None,
        limit: int = 500,
    ) -> str:
        """매매일지 row를 UTF-8 CSV 문자열로 반환한다."""
        rows = self._entries(self._normalize_source(source), run_id=run_id, limit=limit)
        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in CSV_COLUMNS})
        return buffer.getvalue()

    def _entries(self, source: JournalSource, *, run_id: str | None, limit: int) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        if source in {"all", "backtest"}:
            rows.extend(self._backtest_entries(run_id=run_id, limit=limit))
        if source in {"all", "paper"}:
            rows.extend(self._paper_entries(limit=limit))
        rows.sort(key=lambda row: str(row.get("event_date") or ""), reverse=True)
        return rows[:limit]

    def _backtest_entries(self, *, run_id: str | None, limit: int) -> list[dict[str, object]]:
        statement = select(BacktestTradeLedger).order_by(BacktestTradeLedger.exit_date.desc(), BacktestTradeLedger.id.desc())
        if run_id:
            statement = statement.where(BacktestTradeLedger.run_id == run_id)
        rows = list(self.db.scalars(statement.limit(limit)).all())
        return [
            {
                "source": "backtest",
                "event_date": row.exit_date,
                "symbol": row.symbol,
                "side": row.side,
                "qty": row.qty,
                "entry_price": row.entry_price,
                "exit_price": row.exit_price,
                "fill_price": None,
                "pnl": row.pnl,
                "return_pct": row.return_pct,
                "strategy_name": row.strategy_name,
                "status": row.status,
                "run_id": row.run_id,
                "order_id": None,
                "fill_id": None,
                "notes": row.exit_reason,
            }
            for row in rows
        ]

    def _paper_entries(self, *, limit: int) -> list[dict[str, object]]:
        fill_rows = list(self.db.scalars(select(PaperFill).order_by(PaperFill.fill_ts.desc()).limit(limit)).all())
        order_rows = list(self.db.scalars(select(PaperOrder).order_by(PaperOrder.created_ts.desc()).limit(limit)).all())
        rows = [
            {
                "source": "paper_fill",
                "event_date": row.fill_ts,
                "symbol": row.symbol,
                "side": row.side,
                "qty": row.qty,
                "entry_price": None,
                "exit_price": None,
                "fill_price": row.price,
                "pnl": None,
                "return_pct": None,
                "strategy_name": None,
                "status": "filled",
                "run_id": None,
                "order_id": row.paper_order_id,
                "fill_id": row.paper_fill_id,
                "notes": row.fill_source,
            }
            for row in fill_rows
        ]
        filled_order_ids = {row.paper_order_id for row in fill_rows}
        rows.extend(
            {
                "source": "paper_order",
                "event_date": row.created_ts,
                "symbol": row.symbol,
                "side": row.side,
                "qty": row.qty,
                "entry_price": row.limit_price,
                "exit_price": None,
                "fill_price": None,
                "pnl": None,
                "return_pct": None,
                "strategy_name": row.strategy_tag,
                "status": row.status,
                "run_id": None,
                "order_id": row.paper_order_id,
                "fill_id": None,
                "notes": "paper_order" if row.paper_order_id not in filled_order_ids else "paper_order_with_fill",
            }
            for row in order_rows
        )
        return rows

    @staticmethod
    def _normalize_source(source: str) -> JournalSource:
        normalized = source.strip().lower()
        if normalized not in {"all", "backtest", "paper"}:
            raise ValueError("source는 all, backtest, paper 중 하나여야 합니다.")
        return normalized  # type: ignore[return-value]
