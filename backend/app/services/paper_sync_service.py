from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.paths import CONFIG_DIR
from backend.app.models.tables import PaperFill, PaperPortfolioSnapshot, PaperPosition
from backend.app.repositories.paper_repository import PaperRepository
from backend.app.services.kis_paper_balance import (
    KIS_PAPER_BALANCE_PATH,
    KIS_PAPER_BALANCE_TR_ID,
    KisPaperBalanceClient,
    KisPaperBalanceConfigError,
    KisPaperBalanceCredentials,
    KisPaperBalanceRequestError,
    kis_real_order_enabled,
)
from backend.app.services.paper_trading_service import PaperConfigService
from backend.app.services.portfolio_service import PortfolioService

SYNC_CONFIRMATION_REQUIRED = "KIS_PAPER_SYNC_CONFIRMATION_REQUIRED"
SUPPORTED_SYNC_SCOPES = {"orders", "fills", "positions", "portfolio", "all"}
KIS_PAPER_BALANCE_FETCH_FAILED = "KIS_PAPER_BALANCE_FETCH_FAILED"


class PaperSyncService:
    def __init__(
        self,
        db: Session,
        *,
        config_dir: Path = CONFIG_DIR,
        balance_client: KisPaperBalanceClient | None = None,
    ) -> None:
        self.db = db
        self.config_dir = config_dir
        self.balance_client = balance_client or KisPaperBalanceClient()
        self.repository = PaperRepository(db)

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
        fills = self.repository.list_fills(symbol=symbol)
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
        positions = self.repository.list_positions(symbol=symbol)
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
        """KIS paper 잔고조회가 안전하게 활성화되면 우선 호출하고, 아니면 local snapshot으로 fallback한다."""
        config, config_reasons = PaperConfigService(self.config_dir).load()
        balance_status = self._balance_status(config, config_reasons)
        if balance_status["enabled"]:
            try:
                payload = self.balance_client.fetch_balance()
                payload.update(
                    {
                        "counts": self._counts(),
                        "separation_contract": PortfolioService(self.db).paper_state_separation_contract(),
                    }
                )
                return payload
            except (KisPaperBalanceConfigError, KisPaperBalanceRequestError):
                fallback = self._local_portfolio_payload()
                fallback.update(
                    {
                        "ok": False,
                        "reason": KIS_PAPER_BALANCE_FETCH_FAILED,
                        "kis_balance": {
                            **balance_status,
                            "status": "failed",
                            "reason_codes": [KIS_PAPER_BALANCE_FETCH_FAILED],
                            "network_call_performed": False,
                        },
                    }
                )
                return fallback

        fallback = self._local_portfolio_payload()
        fallback["kis_balance"] = balance_status
        return fallback

    def _local_portfolio_payload(self) -> dict[str, Any]:
        """기존 `paper_portfolio_snapshots`와 `paper_positions` 조회 응답을 유지한다."""
        snapshot = self.repository.latest_portfolio_snapshot()
        positions = self.repository.list_positions()
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

    def _balance_status(self, config: dict[str, object], config_reasons: list[str]) -> dict[str, Any]:
        credentials = KisPaperBalanceCredentials.configured_fields()
        reason_codes = list(config_reasons)
        if str(config.get("mode")) != "paper":
            reason_codes.append("KIS_PAPER_BALANCE_MODE_NOT_PAPER")
        if not bool(config.get("enabled")):
            reason_codes.append("PAPER_TRADING_DISABLED")
        if not bool(config.get("network_enabled")):
            reason_codes.append("PAPER_NETWORK_DISABLED")
        if not bool(config.get("balance_inquiry_enabled")):
            reason_codes.append("KIS_PAPER_BALANCE_DISABLED")
        if str(config.get("broker_adapter_name") or "") != "kis_paper":
            reason_codes.append("KIS_PAPER_ADAPTER_REQUIRED")
        if not bool(config.get("broker_adapter_enabled")):
            reason_codes.append("KIS_PAPER_ADAPTER_DISABLED")
        if not bool(config.get("official_balance_endpoint_confirmed")):
            reason_codes.append("KIS_PAPER_BALANCE_ENDPOINT_UNCONFIRMED")
        if bool(config.get("live_order_enabled")) or bool(config.get("live_fallback_enabled")):
            reason_codes.append("KIS_LIVE_PATH_BLOCKED")
        if bool(config.get("broker_order_enabled")):
            reason_codes.append("KIS_ORDER_PATH_BLOCKED")
        if kis_real_order_enabled():
            reason_codes.append("ENABLE_REAL_ORDER_MUST_BE_FALSE")
        for field_name, configured in credentials.items():
            if not configured:
                reason_codes.append(field_name.upper().replace("_CONFIGURED", "_MISSING"))
        reason_codes = self._merge_reason_codes(reason_codes)
        enabled = not reason_codes
        return {
            "enabled": enabled,
            "status": "enabled" if enabled else "fallback",
            "source": "kis_paper_balance" if enabled else "paper_portfolio_snapshots",
            "endpoint_path": KIS_PAPER_BALANCE_PATH,
            "tr_id": KIS_PAPER_BALANCE_TR_ID,
            "credential_fields": credentials,
            "reason_codes": reason_codes,
            "secrets_redacted": True,
            "read_only": True,
            "real_order_enabled": False,
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
        return self.repository.counts()

    @staticmethod
    def _merge_reason_codes(codes: list[str]) -> list[str]:
        merged: list[str] = []
        for code in codes:
            if code not in merged:
                merged.append(code)
        return merged
