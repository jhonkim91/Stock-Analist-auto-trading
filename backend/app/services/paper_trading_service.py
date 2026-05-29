from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.paths import CONFIG_DIR
from backend.app.models.tables import Order, PaperAccountSnapshot, PaperAuditEvent, PaperFill, PaperOrder, PaperPosition
from backend.app.services.kis_paper_broker_adapter import KisPaperBrokerAdapter
from backend.app.services.market_session_service import MarketSessionService
from backend.app.services.token_manager import TokenLifecycleService

PAPER_CONFIG_NAME = "paper.yaml"
TRUE_ENV_VALUES = {"1", "true", "yes", "on"}
FALSE_ENV_VALUES = {"0", "false", "no", "off"}
BROKER_MODE_ENV = "BROKER_MODE"
PAPER_ORDER_SUBMIT_ENABLED_ENV = "PAPER_ORDER_SUBMIT_ENABLED"
PAPER_BOT_CONFIRM_ENV = "PAPER_BOT_CONFIRM"
KIS_ENV_ENV = "KIS_ENV"
PAPER_REALTIME_ENABLED_ENV = "PAPER_REALTIME_ENABLED"
PAPER_REALTIME_REQUIRE_FRESH_QUOTES_ENV = "PAPER_REALTIME_REQUIRE_FRESH_QUOTES"
PAPER_REALTIME_STALE_QUOTE_THRESHOLD_SECONDS_ENV = "PAPER_REALTIME_STALE_QUOTE_THRESHOLD_SECONDS"
PAPER_TRADING_MARKET_ENV = "PAPER_TRADING_MARKET"
PAPER_TRADING_CAN_SIMULATE_FILLS_ENV = "PAPER_TRADING_CAN_SIMULATE_FILLS"
PAPER_FILL_SIMULATOR_ENABLED_ENV = "PAPER_FILL_SIMULATOR_ENABLED"
KIS_OVERSEAS_EXCHANGE_CODE_ENV = "KIS_OVERSEAS_EXCHANGE_CODE"
KIS_OVERSEAS_CURRENCY_ENV = "KIS_OVERSEAS_CURRENCY"
KIS_OVERSEAS_ORDER_SESSION_ENV = "KIS_OVERSEAS_ORDER_SESSION"
REQUIRED_PAPER_BROKER_MODE = "paper_kis"


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
        broker_adapter = raw.get("broker_adapter", {})
        realtime = raw.get("realtime", {})
        if not all(isinstance(item, dict) for item in (paper, risk_gate, audit, simulator, broker_adapter, realtime)):
            return self._closed_config(), ["PAPER_CONFIG_PARSE_FAILED"]

        config = self._closed_config()
        try:
            config_enabled = bool(paper.get("enabled", False))
            config_can_create = bool(paper.get("can_create", False))
            config_can_simulate = bool(paper.get("can_simulate_fills", False))
            config_network_enabled = bool(paper.get("network_enabled", False))
            config_kill_switch_enabled = bool(paper.get("kill_switch_enabled", True))
            config_simulator_enabled = bool(simulator.get("enabled", False))
            runtime_enabled = self._env_bool("PAPER_TRADING_ENABLED", config_enabled)
            runtime_can_create = self._env_bool("PAPER_TRADING_CAN_CREATE", config_can_create)
            runtime_can_simulate = self._env_bool(PAPER_TRADING_CAN_SIMULATE_FILLS_ENV, config_can_simulate)
            runtime_network_enabled = self._env_bool("PAPER_TRADING_NETWORK_ENABLED", config_network_enabled)
            runtime_kill_switch_enabled = self._env_bool("PAPER_TRADING_KILL_SWITCH", config_kill_switch_enabled)
            runtime_simulator_enabled = self._env_bool(PAPER_FILL_SIMULATOR_ENABLED_ENV, config_simulator_enabled)
            runtime_broker_mode = os.getenv(
                BROKER_MODE_ENV,
                str(paper.get("broker_mode") or ""),
            ).strip().lower()
            runtime_order_submit_enabled = self._env_bool(
                PAPER_ORDER_SUBMIT_ENABLED_ENV,
                bool(paper.get("paper_order_submit_enabled", False)),
            )
            runtime_bot_confirm = self._env_bool(
                PAPER_BOT_CONFIRM_ENV,
                bool(paper.get("require_bot_confirm", True)),
            )
            runtime_kis_env = os.getenv(
                KIS_ENV_ENV,
                str(paper.get("kis_env") or ""),
            ).strip().lower()
            runtime_market = os.getenv(
                PAPER_TRADING_MARKET_ENV,
                str(paper.get("market") or "US"),
            ).strip().upper() or "US"
            runtime_overseas_exchange = os.getenv(KIS_OVERSEAS_EXCHANGE_CODE_ENV, "NASD").strip().upper() or "NASD"
            runtime_overseas_currency = os.getenv(KIS_OVERSEAS_CURRENCY_ENV, "USD").strip().upper() or "USD"
            runtime_overseas_order_session = os.getenv(
                KIS_OVERSEAS_ORDER_SESSION_ENV,
                str(paper.get("overseas_order_session") or "regular"),
            ).strip().lower()
            realtime_enabled = bool(realtime.get("enabled", False)) and self._env_bool(
                PAPER_REALTIME_ENABLED_ENV,
                bool(realtime.get("enabled", False)),
            )
            require_fresh_quotes = self._env_bool(
                PAPER_REALTIME_REQUIRE_FRESH_QUOTES_ENV,
                bool(realtime.get("require_fresh_quote_for_orders", False)),
            )
            config.update(
                {
                    "mode": str(paper.get("mode") or "disabled"),
                    "kis_env": runtime_kis_env,
                    "kis_env_paper": runtime_kis_env == "paper",
                    "broker_mode": runtime_broker_mode,
                    "market": runtime_market,
                    "venue": runtime_overseas_exchange if runtime_market in {"US", "USA", "OVERSEAS"} else "KRX",
                    "currency": runtime_overseas_currency if runtime_market in {"US", "USA", "OVERSEAS"} else "KRW",
                    "overseas_exchange": runtime_overseas_exchange,
                    "overseas_order_session": runtime_overseas_order_session,
                    "enabled": config_enabled and runtime_enabled,
                    "configured_can_create": config_can_create and runtime_can_create,
                    "paper_order_submit_enabled": runtime_order_submit_enabled,
                    "paper_bot_confirm_enabled": runtime_bot_confirm,
                    "configured_can_simulate_fills": config_can_simulate and runtime_can_simulate,
                    "preview_only": bool(paper.get("preview_only", True)),
                    "kill_switch_enabled": runtime_kill_switch_enabled,
                    "network_enabled": config_network_enabled and runtime_network_enabled,
                    "live_order_enabled": bool(paper.get("live_order_enabled", False)),
                    "broker_order_enabled": bool(paper.get("broker_order_enabled", False)),
                    "balance_inquiry_enabled": bool(
                        paper.get("balance_inquiry_enabled", broker_adapter.get("balance_inquiry_enabled", False))
                    ),
                    "broker_adapter_name": str(broker_adapter.get("name") or "kis_paper"),
                    "broker_adapter_enabled": bool(broker_adapter.get("enabled", False)),
                    "official_endpoint_confirmed": bool(broker_adapter.get("official_endpoint_confirmed", False)),
                    "official_balance_endpoint_confirmed": bool(
                        broker_adapter.get("official_balance_endpoint_confirmed", False)
                    ),
                    "live_fallback_enabled": bool(broker_adapter.get("live_fallback_enabled", False)),
                    "allow_buy_preview": bool(risk_gate.get("allow_buy_preview", True)),
                    "allow_sell_preview": bool(risk_gate.get("allow_sell_preview", True)),
                    "allow_short_sell": bool(risk_gate.get("allow_short_sell", False)),
                    "max_order_qty": int(risk_gate.get("max_order_qty") or 0),
                    "max_order_notional": float(risk_gate.get("max_order_notional") or 0),
                    "max_open_positions": int(risk_gate.get("max_open_positions") or 0),
                    "blacklist": self._env_list("PAPER_SYMBOL_BLACKLIST", risk_gate.get("blacklist") or []),
                    "cooldown_seconds": self._env_int(
                        "PAPER_ORDER_COOLDOWN_SECONDS",
                        int(risk_gate.get("cooldown_seconds") or 0),
                    ),
                    "audit_persistence_enabled": bool(audit.get("persistence_enabled", False)),
                    "audit_sanitize_enabled": bool(audit.get("sanitize_enabled", True)),
                    "simulator_enabled": config_simulator_enabled and runtime_simulator_enabled,
                    "auto_fill_on_create": bool(simulator.get("auto_fill_on_create", False)),
                    "realtime_enabled": realtime_enabled,
                    "realtime_mode": str(realtime.get("mode") or "polling"),
                    "realtime_websocket_enabled": bool(realtime.get("websocket_enabled", False)),
                    "realtime_polling_enabled": bool(realtime.get("polling_enabled", False)),
                    "realtime_require_fresh_quote_for_orders": require_fresh_quotes,
                    "realtime_stale_quote_threshold_seconds": self._env_int(
                        PAPER_REALTIME_STALE_QUOTE_THRESHOLD_SECONDS_ENV,
                        int(realtime.get("stale_quote_threshold_seconds") or 30),
                    ),
                    "realtime_heartbeat_timeout_seconds": int(realtime.get("heartbeat_timeout_seconds") or 60),
                }
            )
        except (TypeError, ValueError):
            return self._closed_config(), ["PAPER_CONFIG_PARSE_FAILED"]

        reasons: list[str] = []
        if config["mode"] not in {"disabled", "safety_scaffold", "paper"}:
            reasons.append("UNKNOWN_PAPER_MODE")
            config["mode"] = "disabled"
        if config_enabled and not runtime_enabled:
            reasons.append("PAPER_TRADING_ENV_FLAG_REQUIRED")
        if runtime_kis_env != "paper":
            reasons.append("KIS_ENV_PAPER_REQUIRED")
        if config_can_create and not runtime_can_create:
            reasons.append("PAPER_CREATE_ENV_FLAG_REQUIRED")
        if config_network_enabled and not runtime_network_enabled:
            reasons.append("PAPER_NETWORK_ENV_FLAG_REQUIRED")
        return config, reasons

    @staticmethod
    def _closed_config() -> dict[str, object]:
        return {
            "mode": "disabled",
            "kis_env": "",
            "kis_env_paper": False,
            "broker_mode": "",
            "market": "KR",
            "venue": "KRX",
            "currency": "KRW",
            "overseas_exchange": "NASD",
            "overseas_order_session": "",
            "enabled": False,
            "configured_can_create": False,
            "paper_order_submit_enabled": False,
            "paper_bot_confirm_enabled": False,
            "configured_can_simulate_fills": False,
            "preview_only": True,
            "kill_switch_enabled": True,
            "network_enabled": False,
            "live_order_enabled": False,
            "broker_order_enabled": False,
            "balance_inquiry_enabled": False,
            "broker_adapter_name": "kis_paper",
            "broker_adapter_enabled": False,
            "official_endpoint_confirmed": False,
            "official_balance_endpoint_confirmed": False,
            "live_fallback_enabled": False,
            "allow_buy_preview": True,
            "allow_sell_preview": True,
            "allow_short_sell": False,
            "max_order_qty": 0,
            "max_order_notional": 0.0,
            "max_open_positions": 0,
            "blacklist": [],
            "cooldown_seconds": 0,
            "audit_persistence_enabled": False,
            "audit_sanitize_enabled": True,
            "simulator_enabled": False,
            "auto_fill_on_create": False,
            "realtime_enabled": False,
            "realtime_mode": "polling",
            "realtime_websocket_enabled": False,
            "realtime_polling_enabled": False,
            "realtime_require_fresh_quote_for_orders": False,
            "realtime_stale_quote_threshold_seconds": 30,
            "realtime_heartbeat_timeout_seconds": 60,
        }

    @staticmethod
    def _env_flag_true(name: str) -> bool:
        value = os.getenv(name)
        return value is not None and value.strip().lower() in TRUE_ENV_VALUES

    @staticmethod
    def _env_flag_false(name: str) -> bool:
        value = os.getenv(name)
        return value is not None and value.strip().lower() in FALSE_ENV_VALUES

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in TRUE_ENV_VALUES

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        value = os.getenv(name)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default

    @staticmethod
    def _env_list(name: str, default: object) -> list[str]:
        value = os.getenv(name)
        raw_items = value.split(",") if value is not None else default
        if not isinstance(raw_items, list):
            return []
        return [str(item).strip().upper() for item in raw_items if str(item).strip()]


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
        blacklist = {str(item).strip().upper() for item in config.get("blacklist") or []}
        if normalized_symbol and normalized_symbol.upper() in blacklist:
            reason_codes.append("PAPER_SYMBOL_BLACKLISTED")
        cooldown_seconds = int(config.get("cooldown_seconds") or 0)
        if cooldown_seconds > 0:
            reason_codes.extend(
                self._cooldown_reasons(
                    symbol=normalized_symbol,
                    side=normalized_side,
                    cooldown_seconds=cooldown_seconds,
                )
            )
        max_open_positions = int(config.get("max_open_positions") or 0)
        if max_open_positions > 0 and normalized_side == "buy":
            reason_codes.extend(
                self._open_position_reasons(
                    symbol=normalized_symbol,
                    max_open_positions=max_open_positions,
                )
            )

        if normalized_side == "buy" and not bool(config.get("allow_buy_preview")):
            reason_codes.append("PAPER_BUY_PREVIEW_DISABLED")
        if normalized_side == "sell":
            if not bool(config.get("allow_sell_preview")):
                reason_codes.append("PAPER_SELL_PREVIEW_DISABLED")
            reason_codes.extend(self._sell_position_reasons(symbol=normalized_symbol, qty=qty))

        passed = not reason_codes
        return {"decision": "allow" if passed else "deny", "passed": passed, "reason_codes": reason_codes}

    def _cooldown_reasons(self, *, symbol: str, side: str, cooldown_seconds: int) -> list[str]:
        if self.db is None or not symbol:
            return []
        latest = self.db.scalar(
            select(PaperOrder)
            .where(PaperOrder.symbol == symbol, PaperOrder.side == side)
            .order_by(PaperOrder.created_ts.desc())
            .limit(1)
        )
        if latest is None:
            return []
        created_ts = latest.created_ts
        if created_ts.tzinfo is None:
            created_ts = created_ts.replace(tzinfo=UTC)
        elapsed = (datetime.now(UTC) - created_ts).total_seconds()
        if elapsed < cooldown_seconds:
            return ["PAPER_ORDER_COOLDOWN_ACTIVE"]
        return []

    def _open_position_reasons(self, *, symbol: str, max_open_positions: int) -> list[str]:
        if self.db is None or not symbol:
            return []
        held_symbols = {
            row
            for row in self.db.scalars(select(PaperPosition.symbol).where(PaperPosition.qty > 0)).all()
            if row
        }
        open_symbols = {
            row
            for row in self.db.scalars(
                select(PaperOrder.symbol).where(PaperOrder.status.in_(["pending_submitted", "submitted", "pending", "open", "partially_filled"]))
            ).all()
            if row
        }
        active_symbols = held_symbols | open_symbols
        if symbol not in active_symbols and len(active_symbols) >= max_open_positions:
            return ["PAPER_MAX_OPEN_POSITIONS_EXCEEDED"]
        return []

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
    def __init__(
        self,
        db: Session | None = None,
        *,
        config_dir: Path = CONFIG_DIR,
        market_session_service: MarketSessionService | None = None,
    ) -> None:
        self.db = db
        self.config_service = PaperConfigService(config_dir)
        self.token_service = TokenLifecycleService()
        self.simulator = LocalPaperSimulator()
        self.market_session_service = market_session_service or MarketSessionService()
        self.paper_adapter = KisPaperBrokerAdapter()

    def status(self) -> dict[str, object]:
        """Paper trading scaffold 상태를 secret이나 외부 호출 없이 반환한다."""
        config, config_reasons = self.config_service.load()
        token_status = self.token_service.status()
        reason_codes = self._base_reason_codes(config, config_reasons, token_status)
        blocking = bool(reason_codes)
        return {
            "mode": str(config["mode"]),
            "enabled": bool(config.get("enabled", False)),
            "configured_enabled": bool(config.get("enabled", False)),
            "can_create": bool(config.get("configured_can_create", False)) and not blocking,
            "can_simulate_fills": bool(config.get("configured_can_simulate_fills", False)),
            "preview_only": bool(config.get("preview_only", True)),
            "paper_order_supported": bool(config.get("configured_can_create", False)) and not blocking,
            "fill_simulator_supported": bool(config.get("simulator_enabled", False)),
            "cancel_supported": False,
            "paper_order_created": False,
            "live_order_created": False,
            "broker_order_created": False,
            "fill_created": False,
            "position_changed": False,
            "token_issued": bool(token_status.get("token_issued", False)),
            "token_cache_enabled": bool(token_status.get("token_cache_enabled", False)),
            "network_call_performed": False,
            "adapter_order_call_performed": False,
            "adapter_network_call_performed": False,
            "audit_persistence_enabled": bool(config.get("audit_persistence_enabled", False)),
            "paper_tables_write_enabled": bool(config.get("configured_can_create", False)) and not blocking,
            "paper_bot_confirm_enabled": bool(config.get("paper_bot_confirm_enabled", False)),
            "kis_env": config.get("kis_env"),
            "kis_env_paper": bool(config.get("kis_env_paper", False)),
            "realtime": {
                "enabled": bool(config.get("realtime_enabled", False)),
                "websocket_enabled": bool(config.get("realtime_websocket_enabled", False)),
                "polling_enabled": bool(config.get("realtime_polling_enabled", False)),
                "require_fresh_quote_for_orders": bool(config.get("realtime_require_fresh_quote_for_orders", False)),
                "stale_quote_threshold_seconds": int(config.get("realtime_stale_quote_threshold_seconds") or 30),
            },
            "reason": reason_codes[0] if reason_codes else "paper_trading_enabled",
            "kill_switch": {"blocking": bool(config.get("kill_switch_enabled", True)), "reason_codes": reason_codes},
            "risk_gate": {"decision": "deny" if blocking else "allow", "passed": not blocking, "reason_codes": reason_codes},
            "token_lifecycle": token_status,
            "broker_adapter": KisPaperBrokerAdapter(config=dict(config)).status(),
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
        venue: str | None = None,
        as_of: datetime | None = None,
    ) -> dict[str, object]:
        """DB write 없이 paper order preview 응답을 생성한다."""
        config, config_reasons = self.config_service.load()
        token_status = self.token_service.status()
        session_metadata = self.market_session_service.preview_metadata(venue=venue, as_of=as_of)
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
        risk_gate["decision"] = "deny" if reason_codes else "allow"
        risk_gate["passed"] = not reason_codes
        blocking = bool(reason_codes)
        return {
            "preview_id": f"paper-preview-{uuid4().hex[:12]}",
            "mode": str(config["mode"]),
            "enabled": bool(config.get("enabled", False)),
            "can_create": bool(config.get("configured_can_create", False)) and not blocking,
            "can_simulate_fills": bool(config.get("configured_can_simulate_fills", False)),
            "preview_only": bool(config.get("preview_only", True)),
            "paper_order_supported": bool(config.get("configured_can_create", False)) and not blocking,
            "fill_simulator_supported": bool(config.get("simulator_enabled", False)),
            "paper_order_created": False,
            "live_order_created": False,
            "broker_order_created": False,
            "fill_created": False,
            "position_changed": False,
            "token_issued": bool(token_status.get("token_issued", False)),
            "token_cache_enabled": bool(token_status.get("token_cache_enabled", False)),
            "network_call_performed": False,
            "adapter_order_call_performed": False,
            "adapter_network_call_performed": False,
            "audit_persistence_enabled": bool(config.get("audit_persistence_enabled", False)),
            "paper_tables_write_enabled": bool(config.get("configured_can_create", False)) and not blocking,
            "reason": reason_codes[0] if reason_codes else "paper_order_preview_allowed",
            "reason_codes": reason_codes,
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
            "kill_switch": {"blocking": bool(config.get("kill_switch_enabled", True)), "reason_codes": reason_codes},
            "token_lifecycle": token_status,
            "simulator": self.simulator.status(),
            "counts": self._counts(),
        }

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
    ) -> dict[str, object]:
        """local paper order submit은 별도 service의 safety gate에 위임한다."""
        if self.db is None:
            return {
                "ok": False,
                "status": "blocked",
                "paper_order_created": False,
                "live_order_created": False,
                "broker_order_created": False,
                "network_call_performed": False,
                "reason": "PAPER_DB_SESSION_REQUIRED",
                "reason_codes": ["PAPER_DB_SESSION_REQUIRED"],
                "counts": self._counts(),
            }
        from backend.app.services.paper_order_service import PaperOrderService

        return PaperOrderService(self.db, config_dir=self.config_service.config_dir).submit_order(
            symbol=symbol,
            side=side,
            qty=qty,
            confirm=confirm,
            idempotency_key=idempotency_key,
            limit_price=limit_price,
            stop_price=stop_price,
            strategy_tag=strategy_tag,
            venue=venue,
            as_of=as_of,
        )

    def cancel_order(
        self,
        *,
        paper_order_id: str,
        confirm: bool,
        idempotency_key: str | None,
    ) -> dict[str, object]:
        """공식 cancel contract 확인 전에는 submit과 분리된 disabled 응답을 반환한다."""
        if self.db is None:
            return {
                "ok": False,
                "status": "blocked",
                "cancel_supported": False,
                "order_cancelled": False,
                "paper_order_id": paper_order_id,
                "live_order_created": False,
                "broker_order_created": False,
                "network_call_performed": False,
                "reason": "PAPER_DB_SESSION_REQUIRED",
                "reason_codes": ["PAPER_DB_SESSION_REQUIRED"],
                "counts": self._counts(),
            }
        from backend.app.services.paper_order_service import PaperOrderService

        return PaperOrderService(self.db, config_dir=self.config_service.config_dir).cancel_order(
            paper_order_id=paper_order_id,
            confirm=confirm,
            idempotency_key=idempotency_key,
        )

    def list_orders(self, *, status: str | None = None) -> dict[str, object]:
        """저장된 local paper order 목록을 반환한다."""
        if self.db is None:
            return {
                "ok": True,
                "orders": [],
                "counts": self._counts(),
                "live_order_created": False,
                "broker_order_created": False,
                "network_call_performed": False,
            }
        from backend.app.services.paper_order_service import PaperOrderService

        return PaperOrderService(self.db, config_dir=self.config_service.config_dir).list_orders(status=status)

    def list_open_orders(self) -> dict[str, object]:
        """미체결 local paper order 목록을 반환한다."""
        if self.db is None:
            return {
                "ok": True,
                "orders": [],
                "counts": self._counts(),
                "live_order_created": False,
                "broker_order_created": False,
                "network_call_performed": False,
            }
        from backend.app.services.paper_order_service import PaperOrderService

        return PaperOrderService(self.db, config_dir=self.config_service.config_dir).list_open_orders()

    def get_order(self, *, paper_order_id: str) -> dict[str, object]:
        """단일 paper order를 반환한다."""
        if self.db is None:
            return self._paper_sync_unavailable_payload("orders")
        from backend.app.services.paper_order_service import PaperOrderService

        return PaperOrderService(self.db, config_dir=self.config_service.config_dir).get_order(
            paper_order_id=paper_order_id
        )

    def list_fills(self, *, symbol: str | None = None) -> dict[str, object]:
        """저장된 paper fill 목록을 반환한다."""
        if self.db is None:
            return self._paper_sync_unavailable_payload("fills")
        from backend.app.services.paper_sync_service import PaperSyncService

        return PaperSyncService(self.db).list_fills(symbol=symbol)

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
    ) -> dict[str, object]:
        """명시적 gate 통과 시 local paper fill과 position을 갱신한다."""
        if self.db is None:
            return self._paper_sync_unavailable_payload("fill_simulator")
        from backend.app.services.paper_fill_simulator_service import PaperFillSimulatorService

        return PaperFillSimulatorService(self.db, config_dir=self.config_service.config_dir).simulate_fill(
            paper_order_id=paper_order_id,
            fill_price=fill_price,
            qty=qty,
            confirm=confirm,
            idempotency_key=idempotency_key,
            commission=commission,
            slippage_bps=slippage_bps,
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
        ma_fast_current: float | None = None,
        ma_slow_current: float | None = None,
        ma_fast_previous: float | None = None,
        ma_slow_previous: float | None = None,
        strategy_tag: str | None = None,
    ) -> dict[str, object]:
        """스탑로스/트레일링/이동평균 하향 교차를 평가하고 trigger 시 local exit fill을 생성한다."""
        if self.db is None:
            return self._paper_sync_unavailable_payload("risk_exit")
        from backend.app.services.paper_fill_simulator_service import PaperFillSimulatorService

        return PaperFillSimulatorService(self.db, config_dir=self.config_service.config_dir).check_risk_exit(
            symbol=symbol,
            current_price=current_price,
            stop_price=stop_price,
            trailing_high_price=trailing_high_price,
            trailing_stop_pct=trailing_stop_pct,
            ma_fast_current=ma_fast_current,
            ma_slow_current=ma_slow_current,
            ma_fast_previous=ma_fast_previous,
            ma_slow_previous=ma_slow_previous,
            strategy_tag=strategy_tag,
            confirm=confirm,
            idempotency_key=idempotency_key,
        )

    def list_positions(self, *, symbol: str | None = None) -> dict[str, object]:
        """저장된 paper position 목록을 반환한다."""
        if self.db is None:
            return self._paper_sync_unavailable_payload("positions")
        from backend.app.services.paper_sync_service import PaperSyncService

        return PaperSyncService(self.db).list_positions(symbol=symbol)

    def portfolio(self) -> dict[str, object]:
        """저장된 paper portfolio snapshot과 paper position 요약을 반환한다."""
        if self.db is None:
            return self._paper_sync_unavailable_payload("portfolio")
        from backend.app.services.paper_sync_service import PaperSyncService

        return PaperSyncService(self.db, config_dir=self.config_service.config_dir).portfolio()

    def account(self) -> dict[str, object]:
        """저장된 paper account snapshot을 반환한다."""
        if self.db is None:
            return self._paper_sync_unavailable_payload("account")
        from backend.app.services.paper_sync_service import PaperSyncService

        return PaperSyncService(self.db, config_dir=self.config_service.config_dir).account()

    def realtime_status(self) -> dict[str, object]:
        """paper realtime worker 상태를 반환한다."""
        from backend.app.workers.realtime_market_worker import RealtimeMarketWorker, realtime_market_worker

        if self.db is None:
            return realtime_market_worker.status()
        return RealtimeMarketWorker(db=self.db, config_dir=self.config_service.config_dir, quote_cache=realtime_market_worker.quote_cache).status()

    def sync(self, *, scope: str = "all") -> dict[str, object]:
        """공식 KIS sync contract 확인 전에는 no-op sync 응답을 반환한다."""
        if self.db is None:
            return self._paper_sync_unavailable_payload(scope)
        from backend.app.services.paper_sync_service import PaperSyncService

        return PaperSyncService(self.db, config_dir=self.config_service.config_dir).sync(scope=scope)

    def bot_status(self) -> dict[str, object]:
        """paper bot scheduler 상태를 반환한다."""
        if self.db is None:
            return self._paper_sync_unavailable_payload("bot")
        from backend.app.services.paper_bot_service import PaperBotService

        return PaperBotService(self.db, config_dir=self.config_service.config_dir).status()

    def run_bot_once(self, *, auto_submit: bool | None = None) -> dict[str, object]:
        """paper bot once 실행을 안전한 no-op service에 위임한다."""
        if self.db is None:
            return self._paper_sync_unavailable_payload("bot")
        from backend.app.services.paper_bot_service import PaperBotService

        return PaperBotService(self.db, config_dir=self.config_service.config_dir).run_once(auto_submit=auto_submit)

    def bot_preview(
        self,
        *,
        trade_date,
        strategies: list[str],
        max_candidates: int,
    ) -> dict[str, object]:
        """Phase 5 bot executor dry-run preview를 실행한다."""
        if self.db is None:
            return self._paper_sync_unavailable_payload("bot")
        from backend.app.services.paper_bot_executor import PaperBotExecutor

        return PaperBotExecutor(self.db, config_dir=self.config_service.config_dir).preview(
            trade_date=trade_date,
            strategies=strategies,
            max_candidates=max_candidates,
        )

    def run_bot(
        self,
        *,
        trade_date,
        strategies: list[str],
        max_candidates: int,
        dry_run: bool,
    ) -> dict[str, object]:
        """Phase 5 bot executor run을 실행한다."""
        if self.db is None:
            return self._paper_sync_unavailable_payload("bot")
        from backend.app.services.paper_bot_executor import PaperBotExecutor

        return PaperBotExecutor(self.db, config_dir=self.config_service.config_dir).run(
            trade_date=trade_date,
            strategies=strategies,
            max_candidates=max_candidates,
            dry_run=dry_run,
        )

    def get_bot_run(self, *, run_id: str) -> dict[str, object]:
        """저장된 Phase 5 bot run을 반환한다."""
        if self.db is None:
            return self._paper_sync_unavailable_payload("bot")
        from backend.app.services.paper_bot_executor import PaperBotExecutor

        return PaperBotExecutor(self.db, config_dir=self.config_service.config_dir).get_run(run_id=run_id)

    def dashboard(self) -> dict[str, object]:
        """paper trading dashboard payload를 반환한다."""
        if self.db is None:
            return self._paper_sync_unavailable_payload("dashboard")
        from backend.app.services.paper_dashboard_service import PaperDashboardService

        return PaperDashboardService(self.db).dashboard()

    def _paper_sync_unavailable_payload(self, scope: str) -> dict[str, object]:
        return {
            "ok": False,
            "status": "blocked",
            "scope": scope,
            "sync_performed": False,
            "reason": "PAPER_DB_SESSION_REQUIRED",
            "reason_codes": ["PAPER_DB_SESSION_REQUIRED"],
            "counts": self._counts(),
            "live_order_created": False,
            "broker_order_created": False,
            "network_call_performed": False,
            "synthetic_positions_touched": False,
        }

    def _base_reason_codes(
        self,
        config: dict[str, object],
        config_reasons: list[str],
        token_status: dict[str, object],
    ) -> list[str]:
        reasons = list(config_reasons)
        if str(config.get("mode")) != "paper":
            reasons.append("KIS_PAPER_MODE_REQUIRED")
        if str(config.get("kis_env") or "").strip().lower() != "paper":
            reasons.append("KIS_ENV_PAPER_REQUIRED")
        if not bool(config.get("enabled")):
            reasons.append("PAPER_TRADING_DISABLED")
        if not bool(config.get("configured_can_create")):
            reasons.append("PAPER_CREATE_DISABLED")
        if not bool(config.get("paper_bot_confirm_enabled")):
            reasons.append("PAPER_BOT_CONFIRM_REQUIRED")
        if bool(config.get("preview_only", True)):
            reasons.append("PAPER_PREVIEW_ONLY")
        if bool(config.get("kill_switch_enabled")) or os.getenv("PAPER_TRADING_KILL_SWITCH", "").strip() in {"1", "true", "TRUE"}:
            reasons.append("KILL_SWITCH_ACTIVE")
        if bool(config.get("live_order_enabled")):
            reasons.append("LIVE_ORDER_UNSUPPORTED")
        if bool(config.get("live_fallback_enabled")):
            reasons.append("KIS_LIVE_PATH_BLOCKED")
        if bool(config.get("broker_order_enabled")):
            reasons.append("BROKER_ORDER_UNSUPPORTED")
        if bool(config.get("audit_persistence_enabled")):
            reasons.append("PAPER_AUDIT_PERSISTENCE_DISABLED_IN_PHASE_3E1")
        if os.getenv("ENABLE_REAL_ORDER", "").strip().lower() in {"1", "true", "yes", "on"}:
            reasons.append("ENABLE_REAL_ORDER_MUST_BE_FALSE")
        if bool(config.get("network_enabled")):
            if str(config.get("broker_mode") or "").strip().lower() != REQUIRED_PAPER_BROKER_MODE:
                reasons.append("BROKER_MODE_PAPER_KIS_REQUIRED")
            if not bool(config.get("paper_order_submit_enabled")):
                reasons.append("PAPER_ORDER_SUBMIT_ENABLED_REQUIRED")
            if not bool(config.get("broker_adapter_enabled")):
                reasons.append("KIS_PAPER_ADAPTER_DISABLED")
            if not bool(config.get("official_endpoint_confirmed")):
                reasons.append("KIS_PAPER_OFFICIAL_ENDPOINT_CONFIRMATION_REQUIRED")
            if not bool(token_status.get("token_issued", False)):
                reasons.append("KIS_ACCESS_TOKEN_REQUIRED_FOR_NETWORK")
        return self._merge_reason_codes(reasons, [])

    def _counts(self) -> dict[str, int]:
        if self.db is None:
            return {
                "paper_orders_count": 0,
                "paper_fills_count": 0,
                "paper_positions_count": 0,
                "paper_audit_events_count": 0,
                "paper_account_snapshots_count": 0,
                "orders_count": 0,
            }
        return {
            "paper_orders_count": int(self.db.scalar(select(func.count()).select_from(PaperOrder)) or 0),
            "paper_fills_count": int(self.db.scalar(select(func.count()).select_from(PaperFill)) or 0),
            "paper_positions_count": int(self.db.scalar(select(func.count()).select_from(PaperPosition)) or 0),
            "paper_audit_events_count": int(self.db.scalar(select(func.count()).select_from(PaperAuditEvent)) or 0),
            "paper_account_snapshots_count": int(
                self.db.scalar(select(func.count()).select_from(PaperAccountSnapshot)) or 0
            ),
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
