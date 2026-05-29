from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.paths import CONFIG_DIR
from backend.app.models.tables import Order, PaperAuditEvent, PaperFill, PaperOrder, PaperPosition, utc_now
from backend.app.services.paper_order_service import OPEN_ORDER_STATUSES
from backend.app.services.paper_trading_service import PaperConfigService

CONFIRM_REQUIRED_REASON = "PAPER_CONFIRM_TRUE_REQUIRED"
IDEMPOTENCY_REQUIRED_REASON = "PAPER_IDEMPOTENCY_KEY_REQUIRED"
PAPER_FILL_SIMULATOR_DISABLED_REASON = "PAPER_FILL_SIMULATOR_DISABLED"
PAPER_CAN_SIMULATE_FILLS_REQUIRED_REASON = "PAPER_CAN_SIMULATE_FILLS_REQUIRED"
PAPER_ORDER_NOT_FOUND_REASON = "PAPER_ORDER_NOT_FOUND"
PAPER_ORDER_NOT_OPEN_REASON = "PAPER_ORDER_NOT_OPEN"
PAPER_POSITION_NOT_FOUND_REASON = "PAPER_POSITION_NOT_FOUND"
PAPER_SELL_QTY_EXCEEDS_POSITION_REASON = "PAPER_SELL_QTY_EXCEEDS_POSITION"


class PaperFillSimulatorService:
    """local paper fill, position, stop-loss/trailing-stop lifecycle을 담당한다."""

    def __init__(self, db: Session, *, config_dir: Path = CONFIG_DIR) -> None:
        self.db = db
        self.config_service = PaperConfigService(config_dir)

    def simulate_fill(
        self,
        *,
        paper_order_id: str,
        fill_price: float,
        confirm: bool,
        idempotency_key: str | None,
        qty: int | None = None,
        commission: float = 0.0,
        slippage_bps: float = 0.0,
    ) -> dict[str, Any]:
        """명시적 confirm/idempotency/simulator gate 뒤에서 paper fill과 position을 갱신한다."""
        payload = {
            "operation": "simulate_fill",
            "paper_order_id": paper_order_id,
            "fill_price": fill_price,
            "qty": qty,
            "commission": commission,
            "slippage_bps": slippage_bps,
        }
        request_hash = self._request_hash(payload)
        validation_reasons = self._request_reasons(confirm=confirm, idempotency_key=idempotency_key)
        validation_reasons.extend(self._positive_price_reasons(fill_price, "INVALID_FILL_PRICE"))
        if qty is not None and qty <= 0:
            validation_reasons.append("INVALID_FILL_QTY")
        if validation_reasons:
            return self._blocked_response(
                status="blocked",
                reason_codes=validation_reasons,
                request_hash=request_hash,
                idempotency_key=idempotency_key,
            )

        normalized_key = idempotency_key.strip()
        replay = self._fill_by_idempotency(normalized_key)
        if replay is not None:
            return self._success_response(
                status="idempotent_replay",
                fill=replay,
                position=self._position_for_symbol(replay.symbol, None),
                request_hash=request_hash,
                idempotency_key=normalized_key,
                created=False,
            )

        gate_reasons = self._gate_reasons()
        if gate_reasons:
            return self._blocked_response(
                status="blocked",
                reason_codes=gate_reasons,
                request_hash=request_hash,
                idempotency_key=normalized_key,
            )

        order = self.db.scalar(select(PaperOrder).where(PaperOrder.paper_order_id == paper_order_id))
        if order is None:
            return self._blocked_response(
                status="not_found",
                reason_codes=[PAPER_ORDER_NOT_FOUND_REASON],
                request_hash=request_hash,
                idempotency_key=normalized_key,
            )
        if order.status not in OPEN_ORDER_STATUSES or int(order.remaining_qty or 0) <= 0:
            return self._blocked_response(
                status="not_open",
                reason_codes=[PAPER_ORDER_NOT_OPEN_REASON],
                request_hash=request_hash,
                idempotency_key=normalized_key,
            )

        fill_qty = int(qty or order.remaining_qty or 0)
        if fill_qty <= 0 or fill_qty > int(order.remaining_qty or 0):
            return self._blocked_response(
                status="blocked",
                reason_codes=["PAPER_FILL_QTY_EXCEEDS_REMAINING"],
                request_hash=request_hash,
                idempotency_key=normalized_key,
            )
        position_result = self._apply_position_fill(
            symbol=order.symbol,
            strategy_tag=order.strategy_tag,
            side=order.side,
            qty=fill_qty,
            price=fill_price,
        )
        if position_result["reason_codes"]:
            return self._blocked_response(
                status="blocked",
                reason_codes=list(position_result["reason_codes"]),
                request_hash=request_hash,
                idempotency_key=normalized_key,
            )

        now = utc_now()
        fill = PaperFill(
            paper_fill_id=self._local_fill_id(normalized_key),
            paper_order_id=order.paper_order_id,
            symbol=order.symbol,
            side=order.side,
            qty=fill_qty,
            price=fill_price,
            fill_ts=now,
            fill_source="local_simulator",
            simulator_version="phase2_local_simulator",
            commission=commission,
            slippage_bps=slippage_bps,
            live_order_created=False,
            broker_order_created=False,
            network_call_performed=False,
        )
        order.filled_qty = int(order.filled_qty or 0) + fill_qty
        order.remaining_qty = max(int(order.remaining_qty or 0) - fill_qty, 0)
        order.status = "filled" if order.remaining_qty == 0 else "partially_filled"
        order.updated_ts = now
        self.db.add(fill)
        self.db.add(order)
        position = position_result["position"]
        if position is not None:
            self.db.add(position)
        self._add_audit(
            event_type="paper_fill_simulated",
            paper_order_id=order.paper_order_id,
            decision="allow",
            reason_codes=[],
            payload={
                **payload,
                "request_hash": request_hash,
                "fill_idempotency_key_hash": self._short_hash(normalized_key),
                "position_changed": position is not None,
            },
        )
        self.db.commit()
        self.db.refresh(fill)
        if position is not None:
            self.db.refresh(position)
        return self._success_response(
            status="filled" if order.remaining_qty == 0 else "partially_filled",
            fill=fill,
            position=position,
            request_hash=request_hash,
            idempotency_key=normalized_key,
            created=True,
        )

    def check_risk_exit(
        self,
        *,
        symbol: str,
        current_price: float,
        confirm: bool,
        idempotency_key: str | None,
        stop_price: float | None = None,
        trailing_high_price: float | None = None,
        trailing_stop_pct: float | None = None,
        strategy_tag: str | None = None,
    ) -> dict[str, Any]:
        """스탑로스/트레일링 스탑 trigger 시 local sell order와 fill을 생성한다."""
        payload = {
            "operation": "risk_exit",
            "symbol": symbol,
            "current_price": current_price,
            "stop_price": stop_price,
            "trailing_high_price": trailing_high_price,
            "trailing_stop_pct": trailing_stop_pct,
            "strategy_tag": strategy_tag,
        }
        request_hash = self._request_hash(payload)
        validation_reasons = self._positive_price_reasons(current_price, "INVALID_CURRENT_PRICE")
        if stop_price is not None:
            validation_reasons.extend(self._positive_price_reasons(stop_price, "INVALID_STOP_PRICE"))
        if trailing_high_price is not None:
            validation_reasons.extend(self._positive_price_reasons(trailing_high_price, "INVALID_TRAILING_HIGH_PRICE"))
        if trailing_stop_pct is not None and not (0 < trailing_stop_pct < 100):
            validation_reasons.append("INVALID_TRAILING_STOP_PCT")
        if stop_price is None and (trailing_high_price is None or trailing_stop_pct is None):
            validation_reasons.append("PAPER_EXIT_RULE_REQUIRED")
        if validation_reasons:
            return self._blocked_response(
                status="blocked",
                reason_codes=validation_reasons,
                request_hash=request_hash,
                idempotency_key=idempotency_key,
            )

        position = self._position_for_symbol(symbol, strategy_tag)
        if position is None or int(position.qty or 0) <= 0:
            return self._blocked_response(
                status="position_not_found",
                reason_codes=[PAPER_POSITION_NOT_FOUND_REASON],
                request_hash=request_hash,
                idempotency_key=idempotency_key,
            )

        trigger = self._exit_trigger(
            current_price=current_price,
            stop_price=stop_price,
            trailing_high_price=trailing_high_price,
            trailing_stop_pct=trailing_stop_pct,
        )
        if not trigger["triggered"]:
            return {
                "ok": True,
                "status": "not_triggered",
                "exit_order_created": False,
                "fill_created": False,
                "position_changed": False,
                "trigger": trigger,
                "request_hash": request_hash,
                "idempotency_key": idempotency_key,
                "live_order_created": False,
                "broker_order_created": False,
                "network_call_performed": False,
                "counts": self._counts(),
            }

        validation_reasons = self._request_reasons(confirm=confirm, idempotency_key=idempotency_key)
        if validation_reasons:
            return self._blocked_response(
                status="blocked",
                reason_codes=validation_reasons,
                request_hash=request_hash,
                idempotency_key=idempotency_key,
                trigger=trigger,
            )
        normalized_key = idempotency_key.strip()
        replay = self._fill_by_idempotency(normalized_key)
        if replay is not None:
            return self._success_response(
                status="idempotent_replay",
                fill=replay,
                position=self._position_for_symbol(replay.symbol, strategy_tag),
                request_hash=request_hash,
                idempotency_key=normalized_key,
                created=False,
                trigger=trigger,
            )

        gate_reasons = self._gate_reasons()
        if gate_reasons:
            return self._blocked_response(
                status="blocked",
                reason_codes=gate_reasons,
                request_hash=request_hash,
                idempotency_key=normalized_key,
                trigger=trigger,
            )

        now = utc_now()
        qty = int(position.qty or 0)
        order = PaperOrder(
            paper_order_id=f"paper-exit-{self._short_hash(normalized_key)}",
            created_ts=now,
            updated_ts=now,
            symbol=position.symbol,
            side="sell",
            qty=qty,
            filled_qty=qty,
            remaining_qty=0,
            order_type="trailing_stop" if trigger["trailing_stop_triggered"] else "stop_loss",
            limit_price=current_price,
            stop_price=float(trigger["trigger_price"]),
            status="filled",
            idempotency_key=f"exit-order-{self._short_hash(normalized_key)}",
            request_hash=request_hash,
            strategy_tag=position.strategy_tag,
            reason_codes_json="[]",
            risk_gate_json=json.dumps({"decision": "allow", "passed": True, "reason_codes": []}, sort_keys=True),
            live_order_created=False,
            broker_order_created=False,
            network_call_performed=False,
            submitted_at=now,
        )
        fill = PaperFill(
            paper_fill_id=self._local_fill_id(normalized_key),
            paper_order_id=order.paper_order_id,
            symbol=position.symbol,
            side="sell",
            qty=qty,
            price=current_price,
            fill_ts=now,
            fill_source="local_trailing_stop" if trigger["trailing_stop_triggered"] else "local_stop_loss",
            simulator_version="phase2_risk_exit",
            live_order_created=False,
            broker_order_created=False,
            network_call_performed=False,
        )
        self._apply_position_fill(
            symbol=position.symbol,
            strategy_tag=position.strategy_tag,
            side="sell",
            qty=qty,
            price=current_price,
            existing_position=position,
        )
        self.db.add(order)
        self.db.add(fill)
        self.db.add(position)
        self._add_audit(
            event_type="paper_risk_exit_triggered",
            paper_order_id=order.paper_order_id,
            decision="allow",
            reason_codes=[],
            payload={
                **payload,
                "trigger": trigger,
                "qty": qty,
                "request_hash": request_hash,
                "fill_idempotency_key_hash": self._short_hash(normalized_key),
            },
        )
        self.db.commit()
        self.db.refresh(fill)
        self.db.refresh(position)
        return self._success_response(
            status="exit_filled",
            fill=fill,
            position=position,
            request_hash=request_hash,
            idempotency_key=normalized_key,
            created=True,
            trigger=trigger,
            exit_order=order,
        )

    def _apply_position_fill(
        self,
        *,
        symbol: str,
        strategy_tag: str | None,
        side: str,
        qty: int,
        price: float,
        existing_position: PaperPosition | None = None,
    ) -> dict[str, Any]:
        normalized_side = side.strip().lower()
        position = existing_position or self._position_for_symbol(symbol, strategy_tag)
        if normalized_side == "buy":
            if position is None:
                position = PaperPosition(symbol=symbol, strategy_tag=strategy_tag, broker_position_key=f"local|{symbol}")
            current_qty = int(position.qty or 0)
            new_qty = current_qty + qty
            position.avg_price = ((float(position.avg_price or 0.0) * current_qty) + (price * qty)) / new_qty
            position.qty = new_qty
            position.last_price = price
            position.market_value = new_qty * price
            position.unrealized_pnl = (price - float(position.avg_price or 0.0)) * new_qty
            position.updated_at = utc_now()
            return {"position": position, "reason_codes": []}
        if normalized_side == "sell":
            if position is None or int(position.qty or 0) <= 0:
                return {"position": None, "reason_codes": [PAPER_POSITION_NOT_FOUND_REASON]}
            current_qty = int(position.qty or 0)
            if qty > current_qty:
                return {"position": position, "reason_codes": [PAPER_SELL_QTY_EXCEEDS_POSITION_REASON]}
            avg_price = float(position.avg_price or 0.0)
            position.qty = current_qty - qty
            position.realized_pnl = float(position.realized_pnl or 0.0) + ((price - avg_price) * qty)
            position.last_price = price
            position.market_value = position.qty * price
            position.unrealized_pnl = (price - avg_price) * position.qty
            position.updated_at = utc_now()
            return {"position": position, "reason_codes": []}
        return {"position": position, "reason_codes": ["INVALID_SIDE"]}

    def _position_for_symbol(self, symbol: str, strategy_tag: str | None) -> PaperPosition | None:
        normalized_symbol = symbol.strip()
        statement = select(PaperPosition).where(PaperPosition.symbol == normalized_symbol)
        if strategy_tag:
            statement = statement.where(PaperPosition.strategy_tag == strategy_tag)
        return self.db.scalar(statement.order_by(PaperPosition.id.asc()).limit(1))

    def _fill_by_idempotency(self, idempotency_key: str) -> PaperFill | None:
        return self.db.get(PaperFill, self._local_fill_id(idempotency_key))

    def _gate_reasons(self) -> list[str]:
        config, config_reasons = self.config_service.load()
        reasons = list(config_reasons)
        if str(config.get("mode")) != "paper":
            reasons.append("KIS_PAPER_MODE_REQUIRED")
        if str(config.get("kis_env") or "").strip().lower() != "paper":
            reasons.append("KIS_ENV_PAPER_REQUIRED")
        if not bool(config.get("enabled")):
            reasons.append("PAPER_TRADING_DISABLED")
        if not bool(config.get("configured_can_create")):
            reasons.append("PAPER_CREATE_DISABLED")
        if not bool(config.get("configured_can_simulate_fills")):
            reasons.append(PAPER_CAN_SIMULATE_FILLS_REQUIRED_REASON)
        if not bool(config.get("simulator_enabled")):
            reasons.append(PAPER_FILL_SIMULATOR_DISABLED_REASON)
        if bool(config.get("preview_only", True)):
            reasons.append("PAPER_PREVIEW_ONLY")
        if bool(config.get("kill_switch_enabled")):
            reasons.append("KILL_SWITCH_ACTIVE")
        if bool(config.get("live_order_enabled")) or bool(config.get("live_fallback_enabled")):
            reasons.append("KIS_LIVE_PATH_BLOCKED")
        if bool(config.get("broker_order_enabled")):
            reasons.append("BROKER_ORDER_UNSUPPORTED")
        if os.getenv("ENABLE_REAL_ORDER", "").strip().lower() in {"1", "true", "yes", "on"}:
            reasons.append("ENABLE_REAL_ORDER_MUST_BE_FALSE")
        return self._merge_reason_codes(reasons)

    @staticmethod
    def _request_reasons(*, confirm: bool, idempotency_key: str | None) -> list[str]:
        reasons: list[str] = []
        if not confirm:
            reasons.append(CONFIRM_REQUIRED_REASON)
        if not idempotency_key or not idempotency_key.strip():
            reasons.append(IDEMPOTENCY_REQUIRED_REASON)
        return reasons

    @staticmethod
    def _positive_price_reasons(price: float | None, reason: str) -> list[str]:
        return [reason] if price is None or price <= 0 else []

    @staticmethod
    def _exit_trigger(
        *,
        current_price: float,
        stop_price: float | None,
        trailing_high_price: float | None,
        trailing_stop_pct: float | None,
    ) -> dict[str, Any]:
        trailing_stop_price = None
        if trailing_high_price is not None and trailing_stop_pct is not None:
            trailing_stop_price = trailing_high_price * (1 - trailing_stop_pct / 100)
        hard_stop_triggered = stop_price is not None and current_price <= stop_price
        trailing_stop_triggered = trailing_stop_price is not None and current_price <= trailing_stop_price
        trigger_candidates = [
            value for value in (stop_price if hard_stop_triggered else None, trailing_stop_price if trailing_stop_triggered else None) if value is not None
        ]
        trigger_price = max(trigger_candidates) if trigger_candidates else None
        return {
            "triggered": bool(hard_stop_triggered or trailing_stop_triggered),
            "hard_stop_triggered": hard_stop_triggered,
            "trailing_stop_triggered": trailing_stop_triggered,
            "stop_price": stop_price,
            "trailing_stop_price": trailing_stop_price,
            "trigger_price": trigger_price,
        }

    def _success_response(
        self,
        *,
        status: str,
        fill: PaperFill,
        position: PaperPosition | None,
        request_hash: str,
        idempotency_key: str,
        created: bool,
        trigger: dict[str, Any] | None = None,
        exit_order: PaperOrder | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "status": status,
            "fill_created": created,
            "position_changed": position is not None and created,
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": False,
            "request_hash": request_hash,
            "idempotency_key": idempotency_key,
            "fill": self._fill_payload(fill),
            "position": self._position_payload(position),
            "exit_order": self._order_payload(exit_order),
            "trigger": trigger,
            "counts": self._counts(),
        }

    def _blocked_response(
        self,
        *,
        status: str,
        reason_codes: list[str],
        request_hash: str,
        idempotency_key: str | None,
        trigger: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "status": status,
            "fill_created": False,
            "position_changed": False,
            "exit_order_created": False,
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": False,
            "reason": reason_codes[0] if reason_codes else "PAPER_FILL_SIMULATOR_BLOCKED",
            "reason_codes": reason_codes,
            "request_hash": request_hash,
            "idempotency_key": idempotency_key,
            "trigger": trigger,
            "counts": self._counts(),
        }

    def _add_audit(
        self,
        *,
        event_type: str,
        paper_order_id: str,
        decision: str,
        reason_codes: list[str],
        payload: dict[str, Any],
    ) -> None:
        self.db.add(
            PaperAuditEvent(
                event_type=event_type,
                paper_order_id=paper_order_id,
                decision=decision,
                reason_codes_json=json.dumps(reason_codes, sort_keys=True),
                payload_json=json.dumps(payload, sort_keys=True, default=str),
            )
        )

    def _counts(self) -> dict[str, int]:
        return {
            "paper_orders_count": int(self.db.scalar(select(func.count()).select_from(PaperOrder)) or 0),
            "paper_fills_count": int(self.db.scalar(select(func.count()).select_from(PaperFill)) or 0),
            "paper_positions_count": int(self.db.scalar(select(func.count()).select_from(PaperPosition)) or 0),
            "paper_audit_events_count": int(self.db.scalar(select(func.count()).select_from(PaperAuditEvent)) or 0),
            "orders_count": int(self.db.scalar(select(func.count()).select_from(Order)) or 0),
        }

    @staticmethod
    def _fill_payload(fill: PaperFill | None) -> dict[str, Any] | None:
        if fill is None:
            return None
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
        }

    @staticmethod
    def _position_payload(position: PaperPosition | None) -> dict[str, Any] | None:
        if position is None:
            return None
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
        }

    @staticmethod
    def _order_payload(order: PaperOrder | None) -> dict[str, Any] | None:
        if order is None:
            return None
        return {
            "paper_order_id": order.paper_order_id,
            "symbol": order.symbol,
            "side": order.side,
            "qty": order.qty,
            "filled_qty": order.filled_qty,
            "remaining_qty": order.remaining_qty,
            "order_type": order.order_type,
            "limit_price": order.limit_price,
            "stop_price": order.stop_price,
            "status": order.status,
            "live_order_created": bool(order.live_order_created),
            "broker_order_created": bool(order.broker_order_created),
            "network_call_performed": bool(order.network_call_performed),
        }

    @staticmethod
    def _request_hash(payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def _local_fill_id(idempotency_key: str) -> str:
        return f"paper-fill-local-{PaperFillSimulatorService._short_hash(idempotency_key)}"

    @staticmethod
    def _short_hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _merge_reason_codes(codes: list[str]) -> list[str]:
        merged: list[str] = []
        for code in codes:
            if code not in merged:
                merged.append(code)
        return merged
