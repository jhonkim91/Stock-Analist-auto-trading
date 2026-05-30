from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.tables import PaperAccountSnapshot, PaperPosition, SymbolMaster
from backend.app.repositories.paper_repository import PaperRepository
from backend.app.services.portfolio_service import PortfolioService


class AccountService:
    """paper 계좌 mirror와 portfolio risk를 조회 전용 report로 조립한다."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.paper_repo = PaperRepository(db)

    def summary(self) -> dict[str, object]:
        """최신 paper account snapshot 또는 position 집계 기반 계좌 요약을 반환한다."""
        snapshot = self.paper_repo.latest_account_snapshot()
        holdings = self._holdings()
        derived = self._derived_summary(holdings)
        summary = self._snapshot_summary(snapshot) if snapshot else derived
        return {
            "ok": True,
            "source": "paper_account_snapshots" if snapshot else "paper_positions_derived",
            "summary": summary,
            "snapshot": self._snapshot_payload(snapshot),
            "counts": self.paper_repo.counts(),
            "network_call_performed": False,
            "live_order_created": False,
            "broker_order_created": False,
        }

    def holdings(self) -> dict[str, object]:
        """현재 저장된 paper_positions 기반 보유 종목 목록을 반환한다."""
        holdings = self._holdings()
        return {
            "ok": True,
            "source": "paper_positions",
            "count": len(holdings),
            "holdings": holdings,
            "reason": None if holdings else "PAPER_HOLDINGS_NOT_FOUND",
            "counts": self.paper_repo.counts(),
            "network_call_performed": False,
            "live_order_created": False,
            "broker_order_created": False,
        }

    def report(self) -> dict[str, object]:
        """계좌 요약, 보유 종목, preview portfolio risk를 하나의 report payload로 반환한다."""
        summary = self.summary()
        holdings = self.holdings()
        risk = PortfolioService(self.db).risk_summary()
        return {
            "ok": True,
            "report_type": "account_portfolio",
            "source": "paper_tables_and_synthetic_risk",
            "account": summary["summary"],
            "snapshot": summary["snapshot"],
            "holdings": holdings["holdings"],
            "portfolio_risk": risk,
            "separation_contract": PortfolioService(self.db).paper_state_separation_contract(),
            "counts": self.paper_repo.counts(),
            "network_call_performed": False,
            "live_order_created": False,
            "broker_order_created": False,
            "notes": [
                "paper_positions는 실계좌 보유가 아니라 paper mirror입니다.",
                "portfolio_risk는 positions와 latest screen_results 기반 preview summary입니다.",
            ],
        }

    def _holdings(self) -> list[dict[str, object]]:
        rows = list(self.db.scalars(select(PaperPosition).order_by(PaperPosition.symbol, PaperPosition.id)).all())
        names = self._symbol_names({row.symbol for row in rows})
        return [self._holding_payload(row, names.get(row.symbol, row.symbol)) for row in rows]

    def _symbol_names(self, symbols: set[str]) -> dict[str, str]:
        if not symbols:
            return {}
        rows = self.db.scalars(select(SymbolMaster).where(SymbolMaster.symbol.in_(symbols))).all()
        return {row.symbol: row.name for row in rows}

    @staticmethod
    def _holding_payload(row: PaperPosition, name: str) -> dict[str, object]:
        current_price = row.last_price if row.last_price is not None else row.avg_price
        market_value = row.market_value
        if market_value is None:
            market_value = float(current_price or 0.0) * int(row.qty or 0)
        purchase_amount = float(row.avg_price or 0.0) * int(row.qty or 0)
        profit_loss_amount = row.unrealized_pnl
        if profit_loss_amount is None:
            profit_loss_amount = float(market_value or 0.0) - purchase_amount
        profit_loss_rate = None if purchase_amount <= 0 else round(float(profit_loss_amount or 0.0) / purchase_amount, 6)
        return {
            "symbol": row.symbol,
            "name": name,
            "strategy_tag": row.strategy_tag,
            "quantity": row.qty,
            "average_price": row.avg_price,
            "current_price": current_price,
            "purchase_amount": round(purchase_amount, 4),
            "market_value": round(float(market_value or 0.0), 4),
            "realized_pnl": row.realized_pnl,
            "unrealized_pnl": round(float(profit_loss_amount or 0.0), 4),
            "profit_loss_rate": profit_loss_rate,
            "account_alias": row.account_alias,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _derived_summary(holdings: list[dict[str, object]]) -> dict[str, Any]:
        market_value = sum(float(row.get("market_value") or 0.0) for row in holdings)
        purchase_amount = sum(float(row.get("purchase_amount") or 0.0) for row in holdings)
        unrealized = sum(float(row.get("unrealized_pnl") or 0.0) for row in holdings)
        realized = sum(float(row.get("realized_pnl") or 0.0) for row in holdings)
        return {
            "cash_balance": None,
            "buying_power": None,
            "market_value": round(market_value, 4),
            "total_equity": None,
            "total_purchase_amount": round(purchase_amount, 4),
            "realized_pnl": round(realized, 4),
            "unrealized_pnl": round(unrealized, 4),
            "asset_change_amount": None,
            "asset_change_rate": None,
            "holding_count": len(holdings),
        }

    @staticmethod
    def _snapshot_summary(row: PaperAccountSnapshot) -> dict[str, object]:
        previous = None
        total = row.total_equity
        change_amount = None if total is None or previous is None else round(float(total) - float(previous), 4)
        change_rate = None if previous in {None, 0.0} or change_amount is None else round(change_amount / float(previous), 6)
        return {
            "cash_balance": row.cash_balance,
            "buying_power": row.buying_power,
            "market_value": row.market_value,
            "total_equity": row.total_equity,
            "total_purchase_amount": None,
            "realized_pnl": row.realized_pnl,
            "unrealized_pnl": row.unrealized_pnl,
            "previous_total_asset_amount": previous,
            "asset_change_amount": change_amount,
            "asset_change_rate": change_rate,
        }

    @staticmethod
    def _snapshot_payload(row: PaperAccountSnapshot | None) -> dict[str, object] | None:
        if row is None:
            return None
        return {
            "snapshot_id": row.snapshot_id,
            "snapshot_ts": row.snapshot_ts,
            "account_alias": row.account_alias,
            "source": row.source,
            "status": row.status,
            "created_at": row.created_at,
        }
