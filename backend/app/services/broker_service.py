from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.paths import CONFIG_DIR
from backend.app.models.tables import Position
from backend.app.services.kis_service import KIS_APP_KEY_ENV, KIS_APP_SECRET_ENV, KisReadOnlyService
from backend.app.services.market_data_import_service import DataSourceService
from backend.app.services.market_session_service import MarketSessionService

BROKER_CONFIG_NAME = "broker.yaml"
DEFAULT_SOURCE_ID = "kis_openapi"
SENSITIVE_AUDIT_KEY_PARTS = (
    "secret",
    "token",
    "password",
    "api_key",
    "app_key",
    "appkey",
    "app_secret",
    "appsecret",
    "authorization",
    "header",
    "account",
    "account_no",
    "cano",
    "hts_id",
    "approval_key",
    "credential",
    "raw",
)


class BrokerAuditService:
    def sanitize(self, value: Any, key: str = "") -> Any:
        """감사 이벤트 후보 payload에서 secret/account/token 계열 값을 제거한다."""
        if self._is_sensitive_key(key):
            return None
        if isinstance(value, Mapping):
            sanitized: dict[str, Any] = {}
            for item_key, item_value in value.items():
                normalized_key = str(item_key)
                if self._is_sensitive_key(normalized_key):
                    continue
                sanitized[normalized_key] = self.sanitize(item_value, normalized_key)
            return sanitized
        if isinstance(value, list):
            return [self.sanitize(item) for item in value]
        return value

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        normalized = key.lower()
        return any(part in normalized for part in SENSITIVE_AUDIT_KEY_PARTS)


class TokenLifecycleService:
    def status(self) -> dict[str, object]:
        """Phase 3D에서는 token 발급 없이 configured boolean과 비활성 상태만 반환한다."""
        app_key_configured = KisReadOnlyService._env_configured(KIS_APP_KEY_ENV)
        app_secret_configured = KisReadOnlyService._env_configured(KIS_APP_SECRET_ENV)
        return {
            "state": "DISABLED_BLOCKED" if app_key_configured and app_secret_configured else "UNCONFIGURED",
            "app_key_configured": app_key_configured,
            "app_secret_configured": app_secret_configured,
            "token_issued": False,
            "token_cache_enabled": False,
            "token_refresh_enabled": False,
            "token_db_persistence_enabled": False,
            "disabled_reason": "phase_3d_status_only",
        }


class BrokerConfigService:
    def __init__(self, config_dir: Path = CONFIG_DIR) -> None:
        self.config_dir = config_dir

    def load(self) -> tuple[dict[str, object], list[str]]:
        """broker.yaml을 읽되 실패 시 주문 불가 상태로 fail-closed config를 반환한다."""
        path = self.config_dir / BROKER_CONFIG_NAME
        if not path.exists():
            return self._closed_config(), ["CONFIG_LOAD_FAILED"]
        try:
            with path.open("r", encoding="utf-8") as file:
                raw = yaml.safe_load(file) or {}
        except Exception:
            return self._closed_config(), ["CONFIG_PARSE_FAILED"]
        if not isinstance(raw, dict):
            return self._closed_config(), ["CONFIG_PARSE_FAILED"]

        broker = raw.get("broker", {})
        risk_gate = raw.get("risk_gate", {})
        audit = raw.get("audit", {})
        if not isinstance(broker, dict) or not isinstance(risk_gate, dict) or not isinstance(audit, dict):
            return self._closed_config(), ["CONFIG_PARSE_FAILED"]

        config = self._closed_config()
        config.update(
            {
                "mode": str(broker.get("mode") or "disabled"),
                "broker_mode": str(broker.get("broker_mode") or "disabled"),
                "source_id": str(broker.get("source_id") or DEFAULT_SOURCE_ID),
                "provider_name": str(broker.get("provider_name") or "kis"),
                "provider_type": str(broker.get("provider_type") or "broker_placeholder"),
                "enabled": bool(broker.get("enabled", False)),
                "network_enabled": bool(broker.get("network_enabled", False)),
                "can_submit": bool(broker.get("can_submit", False)),
                "paper_trading_enabled": bool(broker.get("paper_trading_enabled", False)),
                "live_trading_enabled": bool(broker.get("live_trading_enabled", False)),
                "websocket_enabled": bool(broker.get("websocket_enabled", False)),
                "preview_only": bool(broker.get("preview_only", True)),
                "kill_switch_enabled": bool(broker.get("kill_switch_enabled", True)),
                "allow_buy_preview": bool(risk_gate.get("allow_buy_preview", True)),
                "allow_sell_preview": bool(risk_gate.get("allow_sell_preview", True)),
                "allow_short_sell": bool(risk_gate.get("allow_short_sell", False)),
                "max_order_qty": int(risk_gate.get("max_order_qty") or 0),
                "max_order_notional": float(risk_gate.get("max_order_notional") or 0),
                "audit_persistence_enabled": bool(audit.get("persistence_enabled", False)),
                "audit_sanitize_enabled": bool(audit.get("sanitize_enabled", True)),
            }
        )
        reasons: list[str] = []
        if config["mode"] not in {"disabled", "safety_scaffold"}:
            reasons.append("UNKNOWN_BROKER_MODE")
            config["mode"] = "disabled"
        return config, reasons

    @staticmethod
    def _closed_config() -> dict[str, object]:
        return {
            "mode": "disabled",
            "broker_mode": "disabled",
            "source_id": DEFAULT_SOURCE_ID,
            "provider_name": "kis",
            "provider_type": "broker_placeholder",
            "enabled": False,
            "network_enabled": False,
            "can_submit": False,
            "paper_trading_enabled": False,
            "live_trading_enabled": False,
            "websocket_enabled": False,
            "preview_only": True,
            "kill_switch_enabled": True,
            "allow_buy_preview": True,
            "allow_sell_preview": True,
            "allow_short_sell": False,
            "max_order_qty": 0,
            "max_order_notional": 0.0,
            "audit_persistence_enabled": False,
            "audit_sanitize_enabled": True,
        }


class OrderRiskGate:
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
        """주문 preview 입력을 검토하고 Phase 3D에서는 항상 submit 불가 결정을 반환한다."""
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
            reason_codes.append("ORDER_QTY_LIMIT_EXCEEDED")
        max_notional = float(config.get("max_order_notional") or 0)
        if max_notional and limit_price is not None and qty > 0 and qty * limit_price > max_notional:
            reason_codes.append("ORDER_NOTIONAL_LIMIT_EXCEEDED")

        if normalized_side == "buy" and not bool(config.get("allow_buy_preview")):
            reason_codes.append("BUY_PREVIEW_DISABLED")
        if normalized_side == "sell":
            if not bool(config.get("allow_sell_preview")):
                reason_codes.append("SELL_PREVIEW_DISABLED")
            reason_codes.extend(self._sell_position_reasons(symbol=normalized_symbol, qty=qty))

        return {
            "decision": "deny",
            "passed": False,
            "reason_codes": reason_codes,
        }

    def _sell_position_reasons(self, *, symbol: str, qty: int) -> list[str]:
        if not symbol or qty <= 0:
            return []
        if self.db is None:
            return ["POSITION_STATE_UNAVAILABLE", "SHORT_SELL_UNSUPPORTED"]
        positions = list(self.db.scalars(select(Position).where(Position.symbol == symbol)).all())
        long_qty = sum(max(int(position.qty or 0), 0) for position in positions)
        if long_qty <= 0:
            return ["SELL_POSITION_NOT_FOUND", "SHORT_SELL_UNSUPPORTED"]
        if qty > long_qty:
            return ["SELL_QTY_EXCEEDS_POSITION", "SHORT_SELL_UNSUPPORTED"]
        return []


class BrokerService:
    def __init__(
        self,
        db: Session | None = None,
        *,
        config_dir: Path = CONFIG_DIR,
        source_service: DataSourceService | None = None,
        market_session_service: MarketSessionService | None = None,
    ) -> None:
        self.db = db
        self.config_service = BrokerConfigService(config_dir)
        self.source_service = source_service or DataSourceService()
        self.token_service = TokenLifecycleService()
        self.audit_service = BrokerAuditService()
        self.market_session_service = market_session_service or MarketSessionService()

    def status(self) -> dict[str, object]:
        """Phase 3D broker safety scaffold 상태를 secret 없이 반환한다."""
        config, config_reasons = self.config_service.load()
        source, source_reasons = self._broker_source(config)
        token_status = self.token_service.status()
        reason_codes = self._base_reason_codes(config, config_reasons, source_reasons, token_status)
        adapter_selected = source is not None and "PROVIDER_SOURCE_MISMATCH" not in source_reasons
        return {
            "mode": str(config["mode"]),
            "broker_mode": str(config["broker_mode"]),
            "can_submit": False,
            "preview_only": True,
            "live_trading_enabled": False,
            "paper_trading_enabled": False,
            "websocket_enabled": False,
            "live_order_supported": False,
            "paper_order_supported": False,
            "cancel_supported": False,
            "fill_supported": False,
            "token_issued": False,
            "token_cache_enabled": False,
            "network_call_performed": False,
            "adapter_selected": adapter_selected,
            "adapter_name": str(config["source_id"]),
            "adapter_capability_checked": adapter_selected,
            "adapter_order_call_performed": False,
            "adapter_network_call_performed": False,
            "audit_persistence_enabled": False,
            "reason": "broker_safety_scaffold_disabled",
            "kill_switch": {
                "blocking": True,
                "reason_codes": reason_codes,
            },
            "risk_gate": {
                "decision": "deny",
                "passed": False,
                "reason_codes": reason_codes,
            },
            "token_lifecycle": token_status,
        }

    def preview_order(
        self,
        symbol: str,
        side: str,
        qty: int,
        limit_price: float | None = None,
        stop_price: float | None = None,
        strategy_tag: str | None = None,
        venue: str | None = None,
        as_of: datetime | None = None,
    ) -> dict[str, object]:
        """실제 주문 없이 broker safety scaffold용 dry-run preview만 생성한다."""
        config, config_reasons = self.config_service.load()
        source, source_reasons = self._broker_source(config)
        token_status = self.token_service.status()
        session_metadata = self.market_session_service.preview_metadata(venue=venue, as_of=as_of)
        adapter_selected = source is not None and "PROVIDER_SOURCE_MISMATCH" not in source_reasons
        risk_gate = OrderRiskGate(self.db).evaluate(
            config=config,
            symbol=symbol,
            side=side,
            qty=qty,
            limit_price=limit_price,
            stop_price=stop_price,
        )
        reason_codes = self._merge_reason_codes(
            self._base_reason_codes(config, config_reasons, source_reasons, token_status),
            list(risk_gate["reason_codes"]),
        )
        risk_gate["reason_codes"] = reason_codes
        return {
            "preview_id": f"dryrun-{uuid4().hex[:12]}",
            "mode": str(config["mode"]),
            "broker_mode": str(config["broker_mode"]),
            "can_submit": False,
            "preview_only": True,
            "order_created": False,
            "paper_trading_enabled": False,
            "live_trading_enabled": False,
            "websocket_enabled": False,
            "token_issued": False,
            "token_cache_enabled": False,
            "network_call_performed": False,
            "adapter_selected": adapter_selected,
            "adapter_name": str(config["source_id"]),
            "adapter_capability_checked": adapter_selected,
            "adapter_order_call_performed": False,
            "adapter_network_call_performed": False,
            "audit_persistence_enabled": False,
            "reason": "broker_safety_scaffold_disabled",
            "symbol": symbol,
            "side": side.strip().lower(),
            "qty": qty,
            "venue": session_metadata["venue"],
            "session": session_metadata["session"],
            "session_metadata": session_metadata,
            "limit_price": limit_price,
            "stop_price": stop_price,
            "strategy_tag": strategy_tag,
            "risk_gate": risk_gate,
            "kill_switch": {
                "blocking": True,
                "reason_codes": reason_codes,
            },
            "token_lifecycle": token_status,
        }

    def _broker_source(self, config: dict[str, object]) -> tuple[dict[str, object] | None, list[str]]:
        reasons: list[str] = []
        expected_source_id = str(config.get("source_id") or DEFAULT_SOURCE_ID)
        try:
            source = next(
                (item for item in self.source_service.list_sources() if item["source_id"] == expected_source_id),
                None,
            )
        except ValueError:
            return None, ["BROKER_SOURCE_LOAD_FAILED"]
        if source is None:
            return None, ["BROKER_SOURCE_NOT_FOUND", "PROVIDER_SOURCE_MISMATCH"]
        if str(source.get("provider_type")) != str(config.get("provider_type")):
            reasons.append("PROVIDER_SOURCE_MISMATCH")
        if str(source.get("provider_name")) != str(config.get("provider_name")):
            reasons.append("PROVIDER_SOURCE_MISMATCH")
        if not bool(source.get("enabled")):
            reasons.append("BROKER_SOURCE_DISABLED")
        if not bool(source.get("network_enabled")):
            reasons.append("BROKER_SOURCE_NETWORK_DISABLED")
        if not bool(source.get("paper_trading_enabled")):
            reasons.append("BROKER_SOURCE_PAPER_DISABLED")
        if not bool(source.get("live_trading_enabled")):
            reasons.append("BROKER_SOURCE_LIVE_DISABLED")
        return source, self._merge_reason_codes(reasons, [])

    def _base_reason_codes(
        self,
        config: dict[str, object],
        config_reasons: list[str],
        source_reasons: list[str],
        token_status: dict[str, object],
    ) -> list[str]:
        reasons = list(config_reasons)
        if not bool(config.get("enabled")):
            reasons.append("BROKER_DISABLED")
        if not bool(config.get("can_submit")):
            reasons.append("BROKER_SUBMIT_DISABLED")
        if not bool(config.get("network_enabled")):
            reasons.append("BROKER_NETWORK_DISABLED")
        if not bool(config.get("paper_trading_enabled")):
            reasons.append("PAPER_TRADING_DISABLED")
        if not bool(config.get("live_trading_enabled")):
            reasons.append("LIVE_TRADING_DISABLED")
        if bool(config.get("kill_switch_enabled")) or os.getenv("KIS_BROKER_KILL_SWITCH", "").strip() in {"1", "true", "TRUE"}:
            reasons.append("KILL_SWITCH_ACTIVE")
        if token_status.get("state") != "DISABLED_BLOCKED":
            reasons.append("TOKEN_UNCONFIGURED")
        else:
            reasons.append("TOKEN_DISABLED")
        reasons.extend(source_reasons)
        return self._merge_reason_codes(reasons, [])

    @staticmethod
    def _merge_reason_codes(*groups: list[str]) -> list[str]:
        merged: list[str] = []
        for group in groups:
            for code in group:
                if code not in merged:
                    merged.append(code)
        return merged
