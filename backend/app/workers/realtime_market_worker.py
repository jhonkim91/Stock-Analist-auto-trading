from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.paths import CONFIG_DIR
from backend.app.models.tables import PaperOrder, PaperPosition, ScreenResult
from backend.app.services.paper_trading_service import PaperConfigService

OPEN_ORDER_STATUSES = {"pending_submitted", "submitted", "partially_filled", "open", "pending"}


@dataclass(frozen=True)
class QuoteSnapshot:
    """관심종목 latest quote cache에 저장하는 redacted quote record다."""

    symbol: str
    price: float
    quote_ts: datetime
    source: str = "manual_or_mock"


class LatestQuoteCache:
    """KIS realtime WebSocket 전까지 polling/mock quote를 보관하는 in-memory cache다."""

    def __init__(self) -> None:
        self._quotes: dict[str, QuoteSnapshot] = {}
        self._heartbeat_at: datetime | None = None

    def update_quote(
        self,
        *,
        symbol: str,
        price: float,
        quote_ts: datetime | None = None,
        source: str = "manual_or_mock",
    ) -> QuoteSnapshot:
        """테스트 또는 polling worker가 latest quote를 갱신할 때 사용한다."""
        snapshot = QuoteSnapshot(
            symbol=symbol.strip(),
            price=float(price),
            quote_ts=quote_ts or datetime.now(UTC),
            source=source,
        )
        self._quotes[snapshot.symbol] = snapshot
        self._heartbeat_at = datetime.now(UTC)
        return snapshot

    def get_quote(self, symbol: str) -> QuoteSnapshot | None:
        return self._quotes.get(symbol.strip())

    def heartbeat(self) -> None:
        """worker loop 생존 신호를 기록한다."""
        self._heartbeat_at = datetime.now(UTC)

    def clear(self) -> None:
        """테스트와 worker 재시작 시 quote cache를 비운다."""
        self._quotes.clear()
        self._heartbeat_at = None

    def status(self, *, stale_quote_threshold_seconds: int, heartbeat_timeout_seconds: int) -> dict[str, Any]:
        now = datetime.now(UTC)
        stale_symbols = [
            symbol
            for symbol, quote in sorted(self._quotes.items())
            if (now - quote.quote_ts).total_seconds() > stale_quote_threshold_seconds
        ]
        heartbeat_age = (now - self._heartbeat_at).total_seconds() if self._heartbeat_at else None
        return {
            "quote_count": len(self._quotes),
            "latest_symbols": sorted(self._quotes),
            "stale_symbols": stale_symbols,
            "stale_quote_threshold_seconds": stale_quote_threshold_seconds,
            "heartbeat_at": self._heartbeat_at.isoformat() if self._heartbeat_at else None,
            "heartbeat_age_seconds": round(heartbeat_age, 3) if heartbeat_age is not None else None,
            "heartbeat_stale": heartbeat_age is None or heartbeat_age > heartbeat_timeout_seconds,
        }


class RealtimeMarketWorker:
    """paper universe quote cache와 order/fill sync 상태를 관리하는 fail-closed worker다."""

    def __init__(
        self,
        *,
        db: Session | None = None,
        config_dir: Path = CONFIG_DIR,
        quote_cache: LatestQuoteCache | None = None,
    ) -> None:
        self.db = db
        self.config_dir = config_dir
        self.quote_cache = quote_cache or LatestQuoteCache()
        self._websocket_reconnect_count = 0
        self._last_reconnect_at: datetime | None = None

    def build_universe(self) -> list[str]:
        """최근 screener 통과 종목, 보유 position, open order를 합쳐 관심종목 universe를 만든다."""
        if self.db is None:
            return []
        symbols: set[str] = set()
        symbols.update(
            self.db.scalars(
                select(ScreenResult.symbol).where(ScreenResult.passed.is_(True)).order_by(ScreenResult.trade_date.desc()).limit(100)
            ).all()
        )
        symbols.update(
            self.db.scalars(select(PaperPosition.symbol).where(PaperPosition.qty > 0)).all()
        )
        symbols.update(
            self.db.scalars(select(PaperOrder.symbol).where(PaperOrder.status.in_(OPEN_ORDER_STATUSES))).all()
        )
        return sorted(symbol for symbol in symbols if symbol)

    def status(self) -> dict[str, Any]:
        """realtime worker 상태를 secret 없이 반환한다."""
        config, config_reasons = PaperConfigService(self.config_dir).load()
        from backend.app.services.kis_paper_websocket_service import KisPaperWebSocketService

        websocket_status = KisPaperWebSocketService().status(config=config, config_reasons=config_reasons)
        threshold = int(config.get("realtime_stale_quote_threshold_seconds") or 30)
        heartbeat_timeout = int(config.get("realtime_heartbeat_timeout_seconds") or 60)
        cache_status = self.quote_cache.status(
            stale_quote_threshold_seconds=threshold,
            heartbeat_timeout_seconds=heartbeat_timeout,
        )
        enabled = bool(config.get("realtime_enabled"))
        reason_codes = list(config_reasons)
        if not enabled:
            reason_codes.append("PAPER_REALTIME_DISABLED")
        if bool(config.get("live_fallback_enabled")):
            reason_codes.append("KIS_LIVE_PATH_BLOCKED")
        if cache_status["heartbeat_stale"]:
            reason_codes.append("PAPER_REALTIME_HEARTBEAT_STALE")
        return {
            "ok": True,
            "enabled": enabled,
            "mode": str(config.get("realtime_mode") or "polling"),
            "websocket_enabled": bool(websocket_status.get("websocket_enabled", False)),
            "websocket": websocket_status,
            "polling_enabled": enabled and bool(config.get("realtime_polling_enabled", True)),
            "universe": self.build_universe(),
            "quote_cache": cache_status,
            "stale_quote_blocks_orders": bool(config.get("realtime_require_fresh_quote_for_orders")),
            "sync_mode": "polling",
            "network_call_performed": False,
            "live_order_created": False,
            "metrics": {
                "websocket_reconnect_count": self._websocket_reconnect_count,
                "last_reconnect_at": self._last_reconnect_at.isoformat() if self._last_reconnect_at else None,
            },
            "reason_codes": _merge_reason_codes(reason_codes),
        }

    def quote_gate_result(self, *, symbol: str, stale_quote_threshold_seconds: int) -> dict[str, Any]:
        """신규 주문 전 latest quote freshness를 검증한다."""
        quote = self.quote_cache.get_quote(symbol)
        if quote is None:
            return {
                "passed": False,
                "reason_codes": ["PAPER_REALTIME_QUOTE_MISSING", "PAPER_REALTIME_STALE_QUOTE"],
                "quote_age_seconds": None,
            }
        age = (datetime.now(UTC) - quote.quote_ts).total_seconds()
        stale = age > stale_quote_threshold_seconds
        return {
            "passed": not stale,
            "reason_codes": ["PAPER_REALTIME_STALE_QUOTE"] if stale else [],
            "quote_age_seconds": round(age, 3),
            "quote_source": quote.source,
        }

    def record_reconnect(self) -> None:
        """WebSocket 재연결 이벤트를 worker 상태에 기록한다."""
        self._websocket_reconnect_count += 1
        self._last_reconnect_at = datetime.now(UTC)


def _merge_reason_codes(codes: list[str]) -> list[str]:
    merged: list[str] = []
    for code in codes:
        if code not in merged:
            merged.append(code)
    return merged


realtime_market_worker = RealtimeMarketWorker()
