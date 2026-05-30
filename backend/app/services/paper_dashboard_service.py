from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.tables import PaperAccountSnapshot, PaperBotDecision, PaperFill, PaperOrder, PaperPosition
from backend.app.services.paper_metrics_service import PaperOperationalMetricsService
from backend.app.workers.realtime_market_worker import RealtimeMarketWorker, realtime_market_worker

OPEN_ORDER_STATUSES = {"pending_submitted", "submitted", "partially_filled", "open", "pending"}


class PaperDashboardService:
    """paper trading dashboard payload를 secret 없이 조립한다."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def dashboard(self) -> dict[str, Any]:
        """계좌, 포지션, 주문, 체결, PnL, risk, worker, metrics를 반환한다."""
        positions = list(self.db.scalars(select(PaperPosition).order_by(PaperPosition.symbol.asc())).all())
        open_orders = list(
            self.db.scalars(
                select(PaperOrder)
                .where(PaperOrder.status.in_(OPEN_ORDER_STATUSES))
                .order_by(PaperOrder.created_ts.desc())
            ).all()
        )
        fills = list(self.db.scalars(select(PaperFill).order_by(PaperFill.fill_ts.desc()).limit(100)).all())
        account = self._latest_account()
        pnl = self._pnl_payload(positions=positions, fills=fills, account=account)
        risk = self._risk_payload(positions=positions, open_orders=open_orders)
        worker_status = RealtimeMarketWorker(db=self.db, quote_cache=realtime_market_worker.quote_cache).status()
        return {
            "ok": True,
            "account": account,
            "positions": [self._position_payload(row) for row in positions],
            "open_orders": [self._order_payload(row) for row in open_orders],
            "fills": [self._fill_payload(row) for row in fills],
            "pnl": pnl,
            "risk": risk,
            "worker_status": worker_status,
            "metrics": PaperOperationalMetricsService(self.db).summary(),
            "live_order_created": False,
            "network_call_performed": False,
            "counts": self._counts(),
        }

    def _latest_account(self) -> dict[str, Any]:
        row = self.db.scalar(
            select(PaperAccountSnapshot).order_by(
                PaperAccountSnapshot.snapshot_ts.desc(),
                PaperAccountSnapshot.created_at.desc(),
            )
        )
        if row is None:
            return {
                "available": False,
                "cash_balance": None,
                "buying_power": None,
                "market_value": None,
                "total_equity": None,
                "realized_pnl": None,
                "unrealized_pnl": None,
            }
        return {
            "available": True,
            "snapshot_id": row.snapshot_id,
            "snapshot_ts": row.snapshot_ts.isoformat() if row.snapshot_ts else None,
            "cash_balance": row.cash_balance,
            "buying_power": row.buying_power,
            "market_value": row.market_value,
            "total_equity": row.total_equity,
            "realized_pnl": row.realized_pnl,
            "unrealized_pnl": row.unrealized_pnl,
            "source": row.source,
            "status": row.status,
        }

    @staticmethod
    def _position_payload(row: PaperPosition) -> dict[str, Any]:
        return {
            "symbol": row.symbol,
            "strategy_tag": row.strategy_tag,
            "qty": row.qty,
            "avg_price": row.avg_price,
            "last_price": row.last_price,
            "market_value": row.market_value,
            "realized_pnl": row.realized_pnl,
            "unrealized_pnl": row.unrealized_pnl,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    @staticmethod
    def _order_payload(row: PaperOrder) -> dict[str, Any]:
        return {
            "paper_order_id": row.paper_order_id,
            "symbol": row.symbol,
            "side": row.side,
            "qty": row.qty,
            "filled_qty": row.filled_qty,
            "remaining_qty": row.remaining_qty,
            "limit_price": row.limit_price,
            "stop_price": row.stop_price,
            "status": row.status,
            "strategy_tag": row.strategy_tag,
            "created_ts": row.created_ts.isoformat() if row.created_ts else None,
            "live_order_created": bool(row.live_order_created),
            "network_call_performed": bool(row.network_call_performed),
        }

    @staticmethod
    def _fill_payload(row: PaperFill) -> dict[str, Any]:
        return {
            "paper_fill_id": row.paper_fill_id,
            "paper_order_id": row.paper_order_id,
            "symbol": row.symbol,
            "side": row.side,
            "qty": row.qty,
            "price": row.price,
            "fill_ts": row.fill_ts.isoformat() if row.fill_ts else None,
            "commission": row.commission,
            "slippage_bps": row.slippage_bps,
        }

    @staticmethod
    def _pnl_payload(
        *,
        positions: list[PaperPosition],
        fills: list[PaperFill],
        account: dict[str, Any],
    ) -> dict[str, Any]:
        realized = account.get("realized_pnl")
        unrealized = account.get("unrealized_pnl")
        if realized is None:
            realized = sum(float(row.realized_pnl or 0.0) for row in positions)
        if unrealized is None:
            unrealized = sum(float(row.unrealized_pnl or 0.0) for row in positions)
        return {
            "realized_pnl": round(float(realized or 0.0), 4),
            "unrealized_pnl": round(float(unrealized or 0.0), 4),
            "fill_count": len(fills),
        }

    def _risk_payload(self, *, positions: list[PaperPosition], open_orders: list[PaperOrder]) -> dict[str, Any]:
        exposure = sum(self._position_value(row) for row in positions)
        open_order_notional = sum(float(row.limit_price or 0.0) * int(row.remaining_qty or row.qty or 0) for row in open_orders)
        rejected_reasons = self._reject_reason_counts()
        return {
            "position_count": len([row for row in positions if int(row.qty or 0) > 0]),
            "open_order_count": len(open_orders),
            "current_exposure": round(exposure, 4),
            "open_order_notional": round(open_order_notional, 4),
            "reject_reason_counts": rejected_reasons,
        }

    @staticmethod
    def _position_value(row: PaperPosition) -> float:
        if row.market_value is not None:
            return float(row.market_value)
        price = row.last_price if row.last_price is not None else row.avg_price
        return float(price or 0.0) * int(row.qty or 0)

    def _reject_reason_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        rows = self.db.scalars(
            select(PaperBotDecision.reason_codes_json).where(PaperBotDecision.action == "rejected")
        ).all()
        for raw in rows:
            try:
                parsed = json.loads(raw or "[]")
            except json.JSONDecodeError:
                parsed = []
            if not isinstance(parsed, list):
                continue
            for reason in parsed:
                key = str(reason)
                counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))

    def _counts(self) -> dict[str, int]:
        return {
            "paper_orders_count": int(self.db.scalar(select(func.count()).select_from(PaperOrder)) or 0),
            "paper_fills_count": int(self.db.scalar(select(func.count()).select_from(PaperFill)) or 0),
            "paper_positions_count": int(self.db.scalar(select(func.count()).select_from(PaperPosition)) or 0),
            "paper_bot_decisions_count": int(
                self.db.scalar(select(func.count()).select_from(PaperBotDecision)) or 0
            ),
        }
