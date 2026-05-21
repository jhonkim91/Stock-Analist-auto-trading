from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.paths import CONFIG_DIR
from backend.app.models.tables import Order, PaperAuditEvent, PaperFill, PaperOrder, PaperPosition
from backend.app.services.broker_service import TokenLifecycleService

PAPER_CONFIG_NAME = "paper.yaml"


class LocalPaperSimulator:
    def status(self) -> dict[str, object]:
        """Phase 3E-1에서는 체결 시뮬레이션 실행 없이 비활성 상태만 반환한다."""
        return {
            "enabled": False,
            "auto_fill_on_create": False,
            "can_simulate_fills": False,
            "fill_created": False,
            "position_changed": False,
            "network_call_performed": False,
            "reason": "phase_3e1_simulator_skeleton_only",
        }


class PaperConfigService:
    def __init__(self, config_dir: Path = CONFIG_DIR) -> None:
        self.config_dir = config_dir

    def load(self) -> tuple[dict[str, object], list[str]]:
        """paper.yaml을 읽고 실패 시 disabled/fail-closed 설정을 반환한다."""
        path = self.config_dir / PAPER_CONFIG_NAME
        if not path.exists():
            return self._closed_config(), ["PAPER_CONFIG_LOAD_FAILED"]
        try:
            with path.open("r", encoding="utf-8") as file:
                raw = yaml.safe_load(file) or {}
        except Exception:
            return self._closed_config(), ["PAPER_CONFIG_PARSE_FAILED"]
        if not isinstance(raw, dict):
            return self._closed_config(), ["PAPER_CONFIG_PARSE_FAILED"]

        paper = raw.get("paper", {})
        risk_gate = raw.get("risk_gate", {})
        audit = raw.get("audit", {})
        simulator = raw.get("simulator", {})
        if not all(isinstance(item, dict) for item in (paper, risk_gate, audit, simulator)):
            return self._closed_config(), ["PAPER_CONFIG_PARSE_FAILED"]

        config = self._closed_config()
        try:
            config.update(
                {
                    "mode": str(paper.get("mode") or "disabled"),
                    "enabled": bool(paper.get("enabled", False)),
                    "configured_can_create": bool(paper.get("can_create", False)),
                    "configured_can_simulate_fills": bool(paper.get("can_simulate_fills", False)),
                    "preview_only": bool(paper.get("preview_only", True)),
                    "kill_switch_enabled": bool(paper.get("kill_switch_enabled", True)),
                    "network_enabled": bool(paper.get("network_enabled", False)),
                    "live_order_enabled": bool(paper.get("live_order_enabled", False)),
                    "broker_order_enabled": bool(paper.get("broker_order_enabled", False)),
                    "allow_buy_preview": bool(risk_gate.get("allow_buy_preview", True)),
                    "allow_sell_preview": bool(risk_gate.get("allow_sell_preview", True)),
                    "allow_short_sell": bool(risk_gate.get("allow_short_sell", False)),
                    "max_order_qty": int(risk_gate.get("max_order_qty") or 0),
                    "max_order_notional": float(risk_gate.get("max_order_notional") or 0),
                    "audit_persistence_enabled": bool(audit.get("persistence_enabled", False)),
                    "audit_sanitize_enabled": bool(audit.get("sanitize_enabled", True)),
                    "simulator_enabled": bool(simulator.get("enabled", False)),
                    "auto_fill_on_create": bool(simulator.get("auto_fill_on_create", False)),
                }
            )
        except (TypeError, ValueError):
            return self._closed_config(), ["PAPER_CONFIG_PARSE_FAILED"]

        reasons: list[str] = []
        if config["mode"] not in {"disabled", "safety_scaffold"}:
            reasons.append("UNKNOWN_PAPER_MODE")
            config["mode"] = "disabled"
        return config, reasons

    @staticmethod
    def _closed_config() -> dict[str, object]:
        return {
            "mode": "disabled",
            "enabled": False,
            "configured_can_create": False,
            "configured_can_simulate_fills": False,
            "preview_only": True,
            "kill_switch_enabled": True,
            "network_enabled": False,
            "live_order_enabled": False,
            "broker_order_enabled": False,
            "allow_buy_preview": True,
            "allow_sell_preview": True,
            "allow_short_sell": False,
            "max_order_qty": 0,
            "max_order_notional": 0.0,
            "audit_persistence_enabled": False,
            "audit_sanitize_enabled": True,
            "simulator_enabled": False,
            "auto_fill_on_create": False,
        }


class PaperRiskGate:
    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    def evaluate(
        self,
        *,
        config: dict[str, object],
        symbol: str,
        side: str,
        qty: int,
        limit_price: float | None,
        stop_price: float | None,
    ) -> dict[str, object]:
        """Paper preview 입력을 검증하되 Phase 3E-1에서는 항상 deny로 반환한다."""
        reason_codes: list[str] = []
        normalized_symbol = symbol.strip()
        normalized_side = side.strip().lower()
        if not normalized_symbol:
            reason_codes.append("MISSING_SYMBOL")
        if normalized_side not in {"buy", "sell"}:
            reason_codes.append("INVALID_SIDE")
        if qty <= 0:
            reason_codes.append("INVALID_QTY")
        if limit_price is not None and limit_price <= 0:
            reason_codes.append("INVALID_LIMIT_PRICE")
        if stop_price is not None and stop_price <= 0:
            reason_codes.append("INVALID_STOP_PRICE")
        if limit_price is not None and stop_price is not None and normalized_side == "buy" and stop_price >= limit_price:
            reason_codes.append("STOP_NOT_BELOW_ENTRY")

        max_order_qty = int(config.get("max_order_qty") or 0)
        if max_order_qty and qty > max_order_qty:
            reason_codes.append("PAPER_ORDER_QTY_LIMIT_EXCEEDED")
        max_notional = float(config.get("max_order_notional") or 0)
        if max_notional and limit_price is not None and qty > 0 and qty * limit_price > max_notional:
            reason_codes.append("PAPER_ORDER_NOTIONAL_LIMIT_EXCEEDED")

        if normalized_side == "buy" and not bool(config.get("allow_buy_preview")):
            reason_codes.append("PAPER_BUY_PREVIEW_DISABLED")
        if normalized_side == "sell":
            if not bool(config.get("allow_sell_preview")):
                reason_codes.append("PAPER_SELL_PREVIEW_DISABLED")
            reason_codes.extend(self._sell_position_reasons(symbol=normalized_symbol, qty=qty))

        return {"decision": "deny", "passed": False, "reason_codes": reason_codes}

    def _sell_position_reasons(self, *, symbol: str, qty: int) -> list[str]:
        if not symbol or qty <= 0:
            return []
        if self.db is None:
            return ["PAPER_POSITION_STATE_UNAVAILABLE", "SHORT_SELL_UNSUPPORTED"]
        long_qty = int(
            self.db.scalar(select(func.coalesce(func.sum(PaperPosition.qty), 0)).where(PaperPosition.symbol == symbol))
            or 0
        )
        if long_qty <= 0:
            return ["PAPER_POSITION_NOT_FOUND", "SHORT_SELL_UNSUPPORTED"]
        if qty > long_qty:
            return ["PAPER_SELL_QTY_EXCEEDS_POSITION", "SHORT_SELL_UNSUPPORTED"]
        return []


class PaperTradingService:
    def __init__(self, db: Session | None = None, *, config_dir: Path = CONFIG_DIR) -> None:
        self.db = db
        self.config_service = PaperConfigService(config_dir)
        self.token_service = TokenLifecycleService()
        self.simulator = LocalPaperSimulator()

    def status(self) -> dict[str, object]:
        """Paper trading scaffold 상태를 secret이나 외부 호출 없이 반환한다."""
        config, config_reasons = self.config_service.load()
        token_status = self.token_service.status()
        reason_codes = self._base_reason_codes(config, config_reasons, token_status)
        return {
            "mode": str(config["mode"]),
            "enabled": False,
            "configured_enabled": bool(config.get("enabled", False)),
            "can_create": False,
            "can_simulate_fills": False,
            "preview_only": True,
            "paper_order_supported": False,
            "fill_simulator_supported": False,
            "cancel_supported": False,
            "paper_order_created": False,
            "live_order_created": False,
            "broker_order_created": False,
            "fill_created": False,
            "position_changed": False,
            "token_issued": False,
            "token_cache_enabled": False,
            "network_call_performed": False,
            "adapter_order_call_performed": False,
            "adapter_network_call_performed": False,
            "audit_persistence_enabled": False,
            "paper_tables_write_enabled": False,
            "reason": "paper_trading_safety_scaffold_disabled",
            "kill_switch": {"blocking": True, "reason_codes": reason_codes},
            "risk_gate": {"decision": "deny", "passed": False, "reason_codes": reason_codes},
            "token_lifecycle": token_status,
            "simulator": self.simulator.status(),
            "counts": self._counts(),
        }

    def preview_order(
        self,
        symbol: str,
        side: str,
        qty: int,
        limit_price: float | None = None,
        stop_price: float | None = None,
        strategy_tag: str | None = None,
    ) -> dict[str, object]:
        """DB write 없이 paper order preview deny 응답만 생성한다."""
        config, config_reasons = self.config_service.load()
        token_status = self.token_service.status()
        risk_gate = PaperRiskGate(self.db).evaluate(
            config=config,
            symbol=symbol,
            side=side,
            qty=qty,
            limit_price=limit_price,
            stop_price=stop_price,
        )
        reason_codes = self._merge_reason_codes(
            self._base_reason_codes(config, config_reasons, token_status),
            list(risk_gate["reason_codes"]),
        )
        risk_gate["reason_codes"] = reason_codes
        return {
            "preview_id": f"paper-preview-{uuid4().hex[:12]}",
            "mode": str(config["mode"]),
            "enabled": False,
            "can_create": False,
            "can_simulate_fills": False,
            "preview_only": True,
            "paper_order_supported": False,
            "fill_simulator_supported": False,
            "paper_order_created": False,
            "live_order_created": False,
            "broker_order_created": False,
            "fill_created": False,
            "position_changed": False,
            "token_issued": False,
            "token_cache_enabled": False,
            "network_call_performed": False,
            "adapter_order_call_performed": False,
            "adapter_network_call_performed": False,
            "audit_persistence_enabled": False,
            "paper_tables_write_enabled": False,
            "reason": "paper_trading_safety_scaffold_disabled",
            "symbol": symbol,
            "side": side.strip().lower(),
            "qty": qty,
            "limit_price": limit_price,
            "stop_price": stop_price,
            "strategy_tag": strategy_tag,
            "risk_gate": risk_gate,
            "kill_switch": {"blocking": True, "reason_codes": reason_codes},
            "token_lifecycle": token_status,
            "simulator": self.simulator.status(),
            "counts": self._counts(),
        }

    def _base_reason_codes(
        self,
        config: dict[str, object],
        config_reasons: list[str],
        token_status: dict[str, object],
    ) -> list[str]:
        reasons = list(config_reasons)
        if not bool(config.get("enabled")):
            reasons.append("PAPER_TRADING_DISABLED")
        if not bool(config.get("configured_can_create")):
            reasons.append("PAPER_CREATE_DISABLED")
        if not bool(config.get("configured_can_simulate_fills")):
            reasons.append("PAPER_FILL_SIMULATION_DISABLED")
        reasons.append("PAPER_ORDER_CREATE_NOT_IMPLEMENTED")
        reasons.append("PAPER_FILL_SIMULATOR_NOT_IMPLEMENTED")
        if bool(config.get("preview_only", True)):
            reasons.append("PAPER_PREVIEW_ONLY")
        if bool(config.get("kill_switch_enabled")) or os.getenv("PAPER_TRADING_KILL_SWITCH", "").strip() in {"1", "true", "TRUE"}:
            reasons.append("KILL_SWITCH_ACTIVE")
        if bool(config.get("network_enabled")):
            reasons.append("PAPER_NETWORK_UNSUPPORTED")
        if bool(config.get("live_order_enabled")):
            reasons.append("LIVE_ORDER_UNSUPPORTED")
        if bool(config.get("broker_order_enabled")):
            reasons.append("BROKER_ORDER_UNSUPPORTED")
        if bool(config.get("audit_persistence_enabled")):
            reasons.append("PAPER_AUDIT_PERSISTENCE_DISABLED_IN_PHASE_3E1")
        if token_status.get("state") != "DISABLED_BLOCKED":
            reasons.append("TOKEN_UNCONFIGURED")
        else:
            reasons.append("TOKEN_DISABLED")
        return self._merge_reason_codes(reasons, [])

    def _counts(self) -> dict[str, int]:
        if self.db is None:
            return {
                "paper_orders_count": 0,
                "paper_fills_count": 0,
                "paper_positions_count": 0,
                "paper_audit_events_count": 0,
                "orders_count": 0,
            }
        return {
            "paper_orders_count": int(self.db.scalar(select(func.count()).select_from(PaperOrder)) or 0),
            "paper_fills_count": int(self.db.scalar(select(func.count()).select_from(PaperFill)) or 0),
            "paper_positions_count": int(self.db.scalar(select(func.count()).select_from(PaperPosition)) or 0),
            "paper_audit_events_count": int(self.db.scalar(select(func.count()).select_from(PaperAuditEvent)) or 0),
            "orders_count": int(self.db.scalar(select(func.count()).select_from(Order)) or 0),
        }

    @staticmethod
    def _merge_reason_codes(*groups: list[str]) -> list[str]:
        merged: list[str] = []
        for group in groups:
            for code in group:
                if code not in merged:
                    merged.append(code)
        return merged
