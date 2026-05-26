from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.tables import (
    Order,
    PaperFill,
    PaperOrder,
    PaperPortfolioSnapshot,
    PaperPosition,
    Position,
)
from backend.app.services.portfolio_service import PortfolioService

SYNC_CONFIRMATION_REQUIRED = "KIS_PAPER_SYNC_CONFIRMATION_REQUIRED"
SUPPORTED_SYNC_SCOPES = {"orders", "fills", "positions", "portfolio", "all"}


class PaperSyncService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def sync(self, *, scope: str = "all") -> dict[str, Any]:
        """공식 KIS paper sync contract 확인 전에는 idempotent no-op으로 차단한다."""
        normalized_scope = scope.strip().lower() if scope else "all"
        if normalized_scope not in SUPPORTED_SYNC_SCOPES:
            return {
                "ok": False,
                "status": "invalid_scope",
                "scope": scope,
                "supported_scopes": sorted(SUPPORTED_SYNC_SCOPES),
                "sync_performed": False,
                "reason": "PAPER_SYNC_SCOPE_UNSUPPORTED",
                "reason_codes": ["PAPER_SYNC_SCOPE_UNSUPPORTED"],
                "counts": self._counts(),
                "dedupe": self._dedupe_payload(),
                "live_order_created": False,
                "broker_order_created": False,
                "network_call_performed": False,
                "synthetic_positions_touched": False,
            }
        return {
            "ok": False,
            "status": "sync_disabled",
            "scope": normalized_scope,
            "supported_scopes": sorted(SUPPORTED_SYNC_SCOPES),
            "sync_performed": False,
            "synced_scopes": self._expanded_scopes(normalized_scope),
            "reason": SYNC_CONFIRMATION_REQUIRED,
            "reason_codes": [SYNC_CONFIRMATION_REQUIRED],
            "counts": self._counts(),
            "dedupe": self._dedupe_payload(),
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": False,
            "synthetic_positions_touched": False,
        }

    def list_fills(self, *, symbol: str | None = None) -> dict[str, Any]:
        """`paper_fills` 전용 조회 결과를 반환한다."""
        statement = select(PaperFill).order_by(PaperFill.fill_ts.desc())
        if symbol:
            statement = statement.where(PaperFill.symbol == symbol.strip())
        fills = list(self.db.scalars(statement).all())
        return {
            "ok": True,
            "fills": [self._fill_payload(fill) for fill in fills],
            "counts": self._counts(),
            "source": "paper_fills",
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": False,
        }

    def list_positions(self, *, symbol: str | None = None) -> dict[str, Any]:
        """`paper_positions` 전용 조회 결과를 반환한다."""
        statement = select(PaperPosition).order_by(PaperPosition.symbol.asc(), PaperPosition.id.asc())
        if symbol:
            statement = statement.where(PaperPosition.symbol == symbol.strip())
        positions = list(self.db.scalars(statement).all())
        return {
            "ok": True,
            "positions": [self._position_payload(position) for position in positions],
            "counts": self._counts(),
            "source": "paper_positions",
            "synthetic_positions_included": False,
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": False,
        }

    def portfolio(self) -> dict[str, Any]:
        """최신 `paper_portfolio_snapshots`와 `paper_positions` 요약만 반환한다."""
        snapshot = self.db.scalar(
            select(PaperPortfolioSnapshot).order_by(
                PaperPortfolioSnapshot.snapshot_ts.desc(),
                PaperPortfolioSnapshot.created_at.desc(),
            )
        )
        positions = list(self.db.scalars(select(PaperPosition)).all())
        return {
            "ok": True,
            "source": "paper_portfolio_snapshots",
            "snapshot": self._snapshot_payload(snapshot) if snapshot is not None else None,
            "positions_summary": self._positions_summary(positions),
            "counts": self._counts(),
            "separation_contract": PortfolioService(self.db).paper_state_separation_contract(),
            "reason": None if snapshot is not None else "PAPER_PORTFOLIO_SNAPSHOT_NOT_FOUND",
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": False,
        }

    @staticmethod
    def _expanded_scopes(scope: str) -> list[str]:
        if scope == "all":
            return ["orders", "fills", "positions", "portfolio"]
        return [scope]

    @staticmethod
    def _dedupe_payload() -> dict[str, Any]:
        return {
            "idempotent": True,
            "orders_inserted": 0,
            "fills_inserted": 0,
            "positions_upserted": 0,
            "portfolio_snapshots_inserted": 0,
        }

    @staticmethod
    def _fill_payload(fill: PaperFill) -> dict[str, Any]:
        return {
            "paper_fill_id": fill.paper_fill_id,
            "paper_order_id": fill.paper_order_id,
            "symbol": fill.symbol,
            "side": fill.side,
            "qty": fill.qty,
            "price": fill.price,
            "fill_ts": fill.fill_ts.isoformat() if fill.fill_ts else None,
            "fill_source": fill.fill_source,
            "commission": fill.commission,
            "slippage_bps": fill.slippage_bps,
            "live_order_created": bool(fill.live_order_created),
            "broker_order_created": bool(fill.broker_order_created),
            "network_call_performed": bool(fill.network_call_performed),
            "broker_fill_id": fill.broker_fill_id,
            "broker_order_id": fill.broker_order_id,
            "broker_fill_ts": fill.broker_fill_ts.isoformat() if fill.broker_fill_ts else None,
        }

    @staticmethod
    def _position_payload(position: PaperPosition) -> dict[str, Any]:
        return {
            "id": position.id,
            "symbol": position.symbol,
            "strategy_tag": position.strategy_tag,
            "qty": position.qty,
            "avg_price": position.avg_price,
            "realized_pnl": position.realized_pnl,
            "last_price": position.last_price,
            "market_value": position.market_value,
            "unrealized_pnl": position.unrealized_pnl,
            "updated_at": position.updated_at.isoformat() if position.updated_at else None,
            "broker_position_key": position.broker_position_key,
            "account_alias": position.account_alias,
            "broker_synced_at": position.broker_synced_at.isoformat() if position.broker_synced_at else None,
        }

    @staticmethod
    def _snapshot_payload(snapshot: PaperPortfolioSnapshot) -> dict[str, Any]:
        return {
            "snapshot_id": snapshot.snapshot_id,
            "snapshot_ts": snapshot.snapshot_ts.isoformat() if snapshot.snapshot_ts else None,
            "account_alias": snapshot.account_alias,
            "cash_balance": snapshot.cash_balance,
            "buying_power": snapshot.buying_power,
            "market_value": snapshot.market_value,
            "total_equity": snapshot.total_equity,
            "unrealized_pnl": snapshot.unrealized_pnl,
            "realized_pnl": snapshot.realized_pnl,
            "source": snapshot.source,
            "status": snapshot.status,
            "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        }

    @staticmethod
    def _positions_summary(positions: list[PaperPosition]) -> dict[str, Any]:
        market_value = sum(float(position.market_value or 0.0) for position in positions)
        unrealized_pnl = sum(float(position.unrealized_pnl or 0.0) for position in positions)
        return {
            "source": "paper_positions",
            "count": len(positions),
            "total_qty": sum(int(position.qty or 0) for position in positions),
            "market_value": market_value,
            "unrealized_pnl": unrealized_pnl,
        }

    def _counts(self) -> dict[str, int]:
        return {
            "paper_orders_count": int(self.db.scalar(select(func.count()).select_from(PaperOrder)) or 0),
            "paper_fills_count": int(self.db.scalar(select(func.count()).select_from(PaperFill)) or 0),
            "paper_positions_count": int(self.db.scalar(select(func.count()).select_from(PaperPosition)) or 0),
            "paper_portfolio_snapshots_count": int(
                self.db.scalar(select(func.count()).select_from(PaperPortfolioSnapshot)) or 0
            ),
            "orders_count": int(self.db.scalar(select(func.count()).select_from(Order)) or 0),
            "synthetic_positions_count": int(self.db.scalar(select(func.count()).select_from(Position)) or 0),
        }
