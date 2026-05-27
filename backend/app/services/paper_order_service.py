from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.paths import CONFIG_DIR
from backend.app.brokers.base import BrokerOrderRequest
from backend.app.models.tables import BrokerAuditEvent, Order, PaperAuditEvent, PaperFill, PaperOrder, PaperPosition, utc_now
from backend.app.services.credential_redaction import CredentialRedactionService
from backend.app.services.kis_paper_broker_adapter import KisPaperBrokerAdapter
from backend.app.services.paper_trading_service import PaperConfigService, PaperRiskGate

CANCEL_DISABLED_REASON = "KIS_PAPER_CANCEL_CONFIRMATION_REQUIRED"
CONFIRM_REQUIRED_REASON = "PAPER_CONFIRM_TRUE_REQUIRED"
IDEMPOTENCY_REQUIRED_REASON = "PAPER_IDEMPOTENCY_KEY_REQUIRED"
IDEMPOTENCY_CONFLICT_REASON = "PAPER_IDEMPOTENCY_KEY_CONFLICT"
NETWORK_DISABLED_REASON = "KIS_PAPER_NETWORK_DISABLED"


class PaperOrderService:
    def __init__(
        self,
        db: Session,
        *,
        config_dir: Path = CONFIG_DIR,
        adapter: KisPaperBrokerAdapter | None = None,
    ) -> None:
        self.db = db
        self.config_service = PaperConfigService(config_dir)
        self.adapter = adapter
        self.redactor = CredentialRedactionService()

    def submit_order(
        self,
        *,
        symbol: str,
        side: str,
        qty: int,
        confirm: bool,
        idempotency_key: str | None,
        limit_price: float | None = None,
        stop_price: float | None = None,
        strategy_tag: str | None = None,
        venue: str | None = None,
        as_of: datetime | None = None,
    ) -> dict[str, Any]:
        """confirm/idempotency/kill-switch gate를 통과한 local paper order만 저장한다."""
        request_payload = self._canonical_payload(
            symbol=symbol,
            side=side,
            qty=qty,
            limit_price=limit_price,
            stop_price=stop_price,
            strategy_tag=strategy_tag,
            venue=venue,
            as_of=as_of,
        )
        request_hash = self.canonical_request_hash(request_payload)

        if not confirm:
            return self._blocked_response(
                status="confirm_required",
                reason_codes=[CONFIRM_REQUIRED_REASON],
                request_hash=request_hash,
                idempotency_key=idempotency_key,
            )
        if not idempotency_key or not idempotency_key.strip():
            return self._blocked_response(
                status="idempotency_required",
                reason_codes=[IDEMPOTENCY_REQUIRED_REASON],
                request_hash=request_hash,
                idempotency_key=idempotency_key,
            )

        normalized_key = idempotency_key.strip()
        existing = self.db.scalar(select(PaperOrder).where(PaperOrder.idempotency_key == normalized_key))
        if existing is not None:
            if existing.request_hash == request_hash:
                return self._success_response(
                    status="idempotent_replay",
                    order=existing,
                    request_hash=request_hash,
                    idempotency_key=normalized_key,
                    created=False,
                )
            return self._blocked_response(
                status="idempotency_conflict",
                reason_codes=[IDEMPOTENCY_CONFLICT_REASON],
                request_hash=request_hash,
                idempotency_key=normalized_key,
            )

        config, config_reasons = self.config_service.load()
        risk_gate = PaperRiskGate(self.db).evaluate(
            config=config,
            symbol=symbol,
            side=side,
            qty=qty,
            limit_price=limit_price,
            stop_price=stop_price,
        )
        reason_codes = self._merge_reason_codes(
            config_reasons,
            self._submit_config_reasons(config),
            list(risk_gate["reason_codes"]),
        )
        if reason_codes:
            risk_gate["decision"] = "deny"
            risk_gate["passed"] = False
            risk_gate["reason_codes"] = reason_codes
            return self._blocked_response(
                status="blocked",
                reason_codes=reason_codes,
                request_hash=request_hash,
                idempotency_key=normalized_key,
                risk_gate=risk_gate,
            )

        if bool(config.get("network_enabled")):
            return self._submit_network_order(
                request_payload=request_payload,
                request_hash=request_hash,
                idempotency_key=normalized_key,
                risk_gate=risk_gate,
                config=config,
            )

        now = utc_now()
        order = PaperOrder(
            paper_order_id=f"paper-{uuid4().hex[:16]}",
            created_ts=now,
            updated_ts=now,
            symbol=symbol.strip(),
            side=side.strip().lower(),
            qty=qty,
            filled_qty=0,
            remaining_qty=qty,
            order_type="limit" if limit_price is not None else "market",
            limit_price=limit_price,
            stop_price=stop_price,
            status="submitted",
            idempotency_key=normalized_key,
            request_hash=request_hash,
            strategy_tag=strategy_tag,
            reason_codes_json="[]",
            risk_gate_json=json.dumps({"decision": "allow", "passed": True, "reason_codes": []}, sort_keys=True),
            live_order_created=False,
            broker_order_created=False,
            network_call_performed=False,
            broker_order_id=None,
            broker_order_status=None,
            submitted_at=now,
        )
        self.db.add(order)
        if bool(config.get("audit_persistence_enabled")):
            self.db.add(
                PaperAuditEvent(
                    event_type="paper_order_submit",
                    paper_order_id=order.paper_order_id,
                    decision="allow",
                    reason_codes_json="[]",
                    payload_json=json.dumps(
                        {
                            "request_hash": request_hash,
                            "symbol": order.symbol,
                            "side": order.side,
                            "qty": order.qty,
                            "limit_price": order.limit_price,
                            "stop_price": order.stop_price,
                        },
                        sort_keys=True,
                    ),
                )
            )
        self.db.commit()
        self.db.refresh(order)
        return self._success_response(
            status="submitted",
            order=order,
            request_hash=request_hash,
            idempotency_key=normalized_key,
            created=True,
        )

    def cancel_order(
        self,
        *,
        paper_order_id: str,
        confirm: bool,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        """network gate가 닫혀 있으면 cancel을 막고, 열려 있을 때만 KIS paper cancel을 호출한다."""
        request_hash = self.canonical_request_hash({"paper_order_id": paper_order_id, "operation": "cancel"})
        if not confirm:
            return self._cancel_disabled_response(
                status="confirm_required",
                reason_codes=[CONFIRM_REQUIRED_REASON],
                paper_order_id=paper_order_id,
                request_hash=request_hash,
                idempotency_key=idempotency_key,
            )
        if not idempotency_key or not idempotency_key.strip():
            return self._cancel_disabled_response(
                status="idempotency_required",
                reason_codes=[IDEMPOTENCY_REQUIRED_REASON],
                paper_order_id=paper_order_id,
                request_hash=request_hash,
                idempotency_key=idempotency_key,
            )
        config, config_reasons = self.config_service.load()
        if not bool(config.get("network_enabled")):
            return self._cancel_disabled_response(
                status="cancel_disabled",
                reason_codes=[CANCEL_DISABLED_REASON],
                paper_order_id=paper_order_id,
                request_hash=request_hash,
                idempotency_key=idempotency_key.strip(),
            )
        reason_codes = self._merge_reason_codes(config_reasons, self._cancel_config_reasons(config))
        if reason_codes:
            return self._cancel_disabled_response(
                status="cancel_blocked",
                reason_codes=reason_codes,
                paper_order_id=paper_order_id,
                request_hash=request_hash,
                idempotency_key=idempotency_key.strip(),
            )
        order = self.db.scalar(select(PaperOrder).where(PaperOrder.paper_order_id == paper_order_id))
        if order is None:
            return self._cancel_disabled_response(
                status="cancel_blocked",
                reason_codes=["PAPER_ORDER_NOT_FOUND"],
                paper_order_id=paper_order_id,
                request_hash=request_hash,
                idempotency_key=idempotency_key.strip(),
            )
        if not order.broker_order_id:
            return self._cancel_disabled_response(
                status="cancel_blocked",
                reason_codes=["PAPER_BROKER_ORDER_ID_REQUIRED"],
                paper_order_id=paper_order_id,
                request_hash=request_hash,
                idempotency_key=idempotency_key.strip(),
            )
        adapter = self._adapter(config)
        broker_result = adapter.cancel_order(broker_order_id=order.broker_order_id, confirm=confirm)
        if not broker_result.get("ok"):
            return self._cancel_disabled_response(
                status=str(broker_result.get("status") or "cancel_blocked"),
                reason_codes=list(broker_result.get("reason_codes") or [str(broker_result.get("reason") or CANCEL_DISABLED_REASON)]),
                paper_order_id=paper_order_id,
                request_hash=request_hash,
                idempotency_key=idempotency_key.strip(),
                broker_trace=broker_result.get("broker_trace"),
            )
        now = utc_now()
        order.status = "cancelled"
        order.updated_ts = now
        order.canceled_at = now
        order.broker_order_status = str(broker_result.get("broker_order_status") or "cancelled")
        order.broker_status_json = json.dumps(self.redactor.redact(broker_result), sort_keys=True, default=str)
        self.db.add(
            BrokerAuditEvent(
                event_type="paper_order_cancel",
                broker_name="kis_paper",
                broker_mode="paper",
                account_alias="kis_paper",
                paper_order_id=paper_order_id,
                broker_order_id=order.broker_order_id,
                decision="allow",
                reason_codes_json="[]",
                sanitized_payload_json=json.dumps(
                    self.redactor.redact(
                        {
                            "paper_order_id": paper_order_id,
                            "broker_order_id": order.broker_order_id,
                            "broker_trace": broker_result.get("broker_trace"),
                        }
                    ),
                    sort_keys=True,
                    default=str,
                ),
            )
        )
        self.db.commit()
        self.db.refresh(order)
        return {
            "ok": True,
            "status": "cancelled",
            "cancel_supported": True,
            "order_cancelled": True,
            "paper_order_id": paper_order_id,
            "paper_order_created": False,
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": True,
            "reason": "KIS_PAPER_ORDER_CANCELLED",
            "reason_codes": [],
            "request_hash": request_hash,
            "idempotency_key": idempotency_key.strip(),
            "order": self._order_payload(order),
            "broker_trace": broker_result.get("broker_trace"),
            "counts": self._counts(),
        }

    def list_orders(self, *, status: str | None = None) -> dict[str, Any]:
        """저장된 local paper order 목록을 secret 없이 반환한다."""
        statement = select(PaperOrder).order_by(PaperOrder.created_ts.desc())
        if status:
            statement = statement.where(PaperOrder.status == status)
        orders = list(self.db.scalars(statement).all())
        return {
            "ok": True,
            "orders": [self._order_payload(order) for order in orders],
            "counts": self._counts(),
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": False,
        }

    @staticmethod
    def canonical_request_hash(payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def _canonical_payload(
        *,
        symbol: str,
        side: str,
        qty: int,
        limit_price: float | None,
        stop_price: float | None,
        strategy_tag: str | None,
        venue: str | None,
        as_of: datetime | None,
    ) -> dict[str, Any]:
        return {
            "symbol": symbol.strip(),
            "side": side.strip().lower(),
            "qty": qty,
            "limit_price": limit_price,
            "stop_price": stop_price,
            "strategy_tag": strategy_tag,
            "venue": venue,
            "as_of": as_of.isoformat() if as_of else None,
        }

    @staticmethod
    def _submit_config_reasons(config: dict[str, object]) -> list[str]:
        reasons: list[str] = []
        if not bool(config.get("enabled")):
            reasons.append("PAPER_TRADING_DISABLED")
        if not bool(config.get("configured_can_create")):
            reasons.append("PAPER_CREATE_DISABLED")
        if bool(config.get("preview_only", True)):
            reasons.append("PAPER_PREVIEW_ONLY")
        if bool(config.get("kill_switch_enabled")) or os.getenv("PAPER_TRADING_KILL_SWITCH", "").strip() in {
            "1",
            "true",
            "TRUE",
        }:
            reasons.append("KILL_SWITCH_ACTIVE")
        if bool(config.get("live_order_enabled")):
            reasons.append("LIVE_ORDER_UNSUPPORTED")
        return reasons

    @staticmethod
    def _cancel_config_reasons(config: dict[str, object]) -> list[str]:
        reasons: list[str] = []
        if str(config.get("mode")) != "paper":
            reasons.append("KIS_PAPER_MODE_REQUIRED")
        if not bool(config.get("enabled")):
            reasons.append("PAPER_TRADING_DISABLED")
        if not bool(config.get("configured_can_create")):
            reasons.append("PAPER_CREATE_DISABLED")
        if bool(config.get("preview_only", True)):
            reasons.append("PAPER_PREVIEW_ONLY")
        if bool(config.get("kill_switch_enabled")):
            reasons.append("KILL_SWITCH_ACTIVE")
        if not bool(config.get("network_enabled")):
            reasons.append(NETWORK_DISABLED_REASON)
        if bool(config.get("live_order_enabled")) or bool(config.get("live_fallback_enabled")):
            reasons.append("KIS_LIVE_PATH_BLOCKED")
        return reasons

    def _submit_network_order(
        self,
        *,
        request_payload: dict[str, Any],
        request_hash: str,
        idempotency_key: str,
        risk_gate: dict[str, Any],
        config: dict[str, object],
    ) -> dict[str, Any]:
        request = BrokerOrderRequest(
            symbol=str(request_payload["symbol"]),
            side=str(request_payload["side"]),
            qty=int(request_payload["qty"]),
            limit_price=request_payload.get("limit_price"),
            stop_price=request_payload.get("stop_price"),
            idempotency_key=idempotency_key,
            metadata={
                "strategy_tag": request_payload.get("strategy_tag"),
                "venue": request_payload.get("venue") or "KRX",
            },
        )
        broker_result = self._adapter(config).submit_order(request)
        if not broker_result.get("ok"):
            return self._blocked_response(
                status=str(broker_result.get("status") or "blocked"),
                reason_codes=list(broker_result.get("reason_codes") or [str(broker_result.get("reason") or "KIS_PAPER_ORDER_BLOCKED")]),
                request_hash=request_hash,
                idempotency_key=idempotency_key,
                risk_gate={**risk_gate, "decision": "deny", "passed": False},
                broker_trace=broker_result.get("broker_trace"),
            )

        now = utc_now()
        order_payload = broker_result.get("order") if isinstance(broker_result.get("order"), dict) else {}
        order = PaperOrder(
            paper_order_id=f"paper-{uuid4().hex[:16]}",
            created_ts=now,
            updated_ts=now,
            symbol=str(request_payload["symbol"]),
            side=str(request_payload["side"]),
            qty=int(request_payload["qty"]),
            filled_qty=int(order_payload.get("filled_qty") or 0),
            remaining_qty=int(order_payload.get("remaining_qty") or request_payload["qty"]),
            order_type="limit" if request_payload.get("limit_price") is not None else "market",
            limit_price=request_payload.get("limit_price"),
            stop_price=request_payload.get("stop_price"),
            status=str(order_payload.get("status") or "submitted"),
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            strategy_tag=request_payload.get("strategy_tag"),
            reason_codes_json="[]",
            risk_gate_json=json.dumps({"decision": "allow", "passed": True, "reason_codes": []}, sort_keys=True),
            live_order_created=False,
            broker_order_created=True,
            network_call_performed=True,
            broker_order_id=str(broker_result.get("broker_order_id") or ""),
            broker_order_status=str(broker_result.get("broker_order_status") or "submitted"),
            account_alias="kis_paper",
            submitted_at=now,
            broker_status_json=json.dumps(self.redactor.redact(broker_result), sort_keys=True, default=str),
        )
        self.db.add(order)
        self.db.add(
            BrokerAuditEvent(
                event_type="paper_order_submit",
                broker_name="kis_paper",
                broker_mode="paper",
                account_alias="kis_paper",
                paper_order_id=order.paper_order_id,
                broker_order_id=order.broker_order_id,
                decision="allow",
                reason_codes_json="[]",
                sanitized_payload_json=json.dumps(
                    self.redactor.redact(
                        {
                            "request_hash": request_hash,
                            "symbol": order.symbol,
                            "side": order.side,
                            "qty": order.qty,
                            "broker_order_id": order.broker_order_id,
                            "broker_trace": broker_result.get("broker_trace"),
                        }
                    ),
                    sort_keys=True,
                    default=str,
                ),
            )
        )
        self.db.commit()
        self.db.refresh(order)
        return self._success_response(
            status="submitted",
            order=order,
            request_hash=request_hash,
            idempotency_key=idempotency_key,
            created=True,
            reason="KIS_PAPER_ORDER_SUBMITTED",
            broker_trace=broker_result.get("broker_trace"),
        )

    def _blocked_response(
        self,
        *,
        status: str,
        reason_codes: list[str],
        request_hash: str,
        idempotency_key: str | None,
        risk_gate: dict[str, Any] | None = None,
        broker_trace: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "status": status,
            "paper_order_created": False,
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": False,
            "reason": reason_codes[0] if reason_codes else "PAPER_ORDER_BLOCKED",
            "reason_codes": reason_codes,
            "risk_gate": risk_gate or {"decision": "deny", "passed": False, "reason_codes": reason_codes},
            "request_hash": request_hash,
            "idempotency_key": idempotency_key,
            "broker_trace": broker_trace,
            "counts": self._counts(),
        }

    def _success_response(
        self,
        *,
        status: str,
        order: PaperOrder,
        request_hash: str,
        idempotency_key: str,
        created: bool,
        reason: str = "PAPER_ORDER_LOCAL_ONLY",
        broker_trace: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "status": status,
            "paper_order_created": created,
            "live_order_created": False,
            "broker_order_created": bool(order.broker_order_created),
            "network_call_performed": bool(order.network_call_performed),
            "reason": reason,
            "reason_codes": [],
            "risk_gate": {"decision": "allow", "passed": True, "reason_codes": []},
            "request_hash": request_hash,
            "idempotency_key": idempotency_key,
            "order": self._order_payload(order),
            "broker_trace": broker_trace,
            "counts": self._counts(),
        }

    def _cancel_disabled_response(
        self,
        *,
        status: str,
        reason_codes: list[str],
        paper_order_id: str,
        request_hash: str,
        idempotency_key: str | None,
        broker_trace: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "status": status,
            "cancel_supported": False,
            "order_cancelled": False,
            "paper_order_id": paper_order_id,
            "paper_order_created": False,
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": False,
            "reason": reason_codes[0],
            "reason_codes": reason_codes,
            "request_hash": request_hash,
            "idempotency_key": idempotency_key,
            "broker_trace": broker_trace,
            "counts": self._counts(),
        }

    @staticmethod
    def _order_payload(order: PaperOrder) -> dict[str, Any]:
        return {
            "paper_order_id": order.paper_order_id,
            "created_ts": order.created_ts.isoformat() if order.created_ts else None,
            "updated_ts": order.updated_ts.isoformat() if order.updated_ts else None,
            "symbol": order.symbol,
            "side": order.side,
            "qty": order.qty,
            "filled_qty": order.filled_qty,
            "remaining_qty": order.remaining_qty,
            "order_type": order.order_type,
            "limit_price": order.limit_price,
            "stop_price": order.stop_price,
            "status": order.status,
            "idempotency_key": order.idempotency_key,
            "request_hash": order.request_hash,
            "strategy_tag": order.strategy_tag,
            "live_order_created": bool(order.live_order_created),
            "broker_order_created": bool(order.broker_order_created),
            "network_call_performed": bool(order.network_call_performed),
            "broker_order_id": order.broker_order_id,
            "broker_order_status": order.broker_order_status,
            "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
            "canceled_at": order.canceled_at.isoformat() if order.canceled_at else None,
        }

    def _counts(self) -> dict[str, int]:
        return {
            "paper_orders_count": int(self.db.scalar(select(func.count()).select_from(PaperOrder)) or 0),
            "paper_fills_count": int(self.db.scalar(select(func.count()).select_from(PaperFill)) or 0),
            "paper_positions_count": int(self.db.scalar(select(func.count()).select_from(PaperPosition)) or 0),
            "paper_audit_events_count": int(self.db.scalar(select(func.count()).select_from(PaperAuditEvent)) or 0),
            "orders_count": int(self.db.scalar(select(func.count()).select_from(Order)) or 0),
        }

    def _adapter(self, config: dict[str, object]) -> KisPaperBrokerAdapter:
        if self.adapter is not None:
            return self.adapter
        return KisPaperBrokerAdapter(config=dict(config))

    @staticmethod
    def _merge_reason_codes(*groups: list[str]) -> list[str]:
        merged: list[str] = []
        for group in groups:
            for code in group:
                if code not in merged:
                    merged.append(code)
        return merged
