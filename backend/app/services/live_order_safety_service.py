from __future__ import annotations

import hashlib
import json
import os
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import monotonic
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.tables import BrokerAuditEvent, Order

TRUE_VALUES = {"1", "true", "yes", "on"}
MAX_CANARY_NOTIONAL_CAP = 1_000_000.0
SENSITIVE_KEY_PARTS = (
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
    "approval_key",
    "credential",
    "raw",
)


@dataclass
class LiveRateLimiter:
    """실계좌 주문 호출 전 사용할 process-local rate limiter다."""

    per_second: float | None
    burst: int | None
    clock: Any = monotonic
    _timestamps: deque[float] = field(default_factory=deque)

    def check(self, *, consume: bool = False) -> dict[str, Any]:
        """현재 호출이 rate limit을 통과하는지 평가하고 필요 시 토큰을 소비한다."""
        blockers: list[str] = []
        if self.per_second is None or self.per_second <= 0:
            blockers.append("LIVE_RATE_LIMIT_PER_SECOND_REQUIRED")
        if self.burst is None or self.burst <= 0:
            blockers.append("LIVE_RATE_LIMIT_BURST_REQUIRED")
        if blockers:
            return self._payload(False, blockers, remaining=0, reset_after_seconds=None, consume=consume)

        now = float(self.clock())
        window_seconds = 1.0
        while self._timestamps and self._timestamps[0] <= now - window_seconds:
            self._timestamps.popleft()

        allowed_in_window = min(int(self.burst), max(int(self.per_second), 1))
        remaining = max(allowed_in_window - len(self._timestamps), 0)
        if remaining <= 0:
            oldest = self._timestamps[0] if self._timestamps else now
            return self._payload(
                False,
                ["LIVE_ORDER_RATE_LIMIT_EXCEEDED"],
                remaining=0,
                reset_after_seconds=max((oldest + window_seconds) - now, 0.0),
                consume=consume,
            )
        if consume:
            self._timestamps.append(now)
            remaining -= 1
        return self._payload(True, [], remaining=remaining, reset_after_seconds=0.0, consume=consume)

    @staticmethod
    def _payload(
        passed: bool,
        blockers: list[str],
        *,
        remaining: int,
        reset_after_seconds: float | None,
        consume: bool,
    ) -> dict[str, Any]:
        return {
            "passed": passed,
            "reason_codes": blockers,
            "remaining": remaining,
            "reset_after_seconds": reset_after_seconds,
            "token_consumed": bool(consume and passed),
            "network_call_performed": False,
            "live_order_created": False,
        }


class LiveIdempotencyGuard:
    """실계좌 주문 idempotency key를 raw 값 노출 없이 검사한다."""

    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    def evaluate(self, *, idempotency_key: str | None, request_payload: Mapping[str, Any]) -> dict[str, Any]:
        """idempotency key 필수 여부와 기존 `orders` 중복 여부를 검사한다."""
        normalized = (idempotency_key or "").strip()
        reason_codes: list[str] = []
        if not normalized:
            reason_codes.append("LIVE_ORDER_IDEMPOTENCY_KEY_REQUIRED")
        if len(normalized) > 128:
            reason_codes.append("LIVE_ORDER_IDEMPOTENCY_KEY_TOO_LONG")
        existing_order_id: str | None = None
        if normalized and self.db is not None:
            existing = self.db.scalar(select(Order).where(Order.idempotency_key == normalized))
            if existing is not None:
                reason_codes.append("LIVE_ORDER_IDEMPOTENCY_KEY_DUPLICATE")
                existing_order_id = str(existing.order_id)
        return {
            "passed": not reason_codes,
            "reason_codes": reason_codes,
            "key_present": bool(normalized),
            "key_fingerprint": _fingerprint(normalized),
            "request_fingerprint": _fingerprint(_stable_json(request_payload)),
            "existing_order_id": existing_order_id,
            "network_call_performed": False,
            "live_order_created": False,
        }


class LiveCooldownGuard:
    """같은 종목 반복 주문을 막는 cooldown 평가기다."""

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self.env = os.environ if env is None else env

    def evaluate(self, *, symbol: str) -> dict[str, Any]:
        """환경 변수에 기록된 마지막 주문 시각 기준으로 cooldown을 검사한다."""
        cooldown_seconds = _int_env(self.env, "LIVE_ORDER_COOLDOWN_SECONDS")
        last_symbol = str(self.env.get("LIVE_LAST_ORDER_SYMBOL", "")).strip().upper()
        last_ts = _parse_iso_datetime(str(self.env.get("LIVE_LAST_ORDER_TS", "")).strip())
        reason_codes: list[str] = []
        elapsed_seconds: float | None = None
        if symbol and cooldown_seconds and last_symbol and last_ts is not None and symbol == last_symbol:
            elapsed_seconds = (datetime.now(UTC) - last_ts).total_seconds()
            if elapsed_seconds < cooldown_seconds:
                reason_codes.append("LIVE_ORDER_COOLDOWN_ACTIVE")
        return {
            "passed": not reason_codes,
            "reason_codes": reason_codes,
            "cooldown_seconds": cooldown_seconds,
            "last_symbol_match": bool(symbol and symbol == last_symbol),
            "elapsed_seconds": elapsed_seconds,
            "network_call_performed": False,
            "live_order_created": False,
        }


class LiveOrderAuditService:
    """실계좌 주문 안전성 평가 결과를 redacted audit event로 구성한다."""

    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    def build_event(
        self,
        *,
        event_type: str,
        decision: str,
        reason_codes: list[str],
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        """DB 기록 없이 감사 이벤트 후보를 만든다."""
        sanitized_payload = _sanitize(payload)
        return {
            "event_type": event_type,
            "broker_name": "kis_live",
            "broker_mode": "live",
            "decision": decision,
            "reason_codes": sorted(set(reason_codes)),
            "sanitized_payload": sanitized_payload,
            "payload_fingerprint": _fingerprint(_stable_json(sanitized_payload)),
            "secrets_redacted": True,
            "audit_event_persisted": False,
            "network_call_performed": False,
            "live_order_created": False,
        }

    def persist_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        """명시 호출 시에만 `broker_audit_events`에 redacted event를 저장한다."""
        if self.db is None:
            return {**dict(event), "audit_event_persisted": False, "reason": "AUDIT_DB_UNAVAILABLE"}
        row = BrokerAuditEvent(
            event_type=str(event.get("event_type") or "live_order_safety"),
            broker_name=str(event.get("broker_name") or "kis_live"),
            broker_mode=str(event.get("broker_mode") or "live"),
            decision=str(event.get("decision") or "deny"),
            reason_codes_json=json.dumps(list(event.get("reason_codes") or []), ensure_ascii=False),
            sanitized_payload_json=json.dumps(dict(event.get("sanitized_payload") or {}), ensure_ascii=False),
        )
        self.db.add(row)
        self.db.commit()
        return {**dict(event), "audit_event_persisted": True, "audit_event_id": row.id}


class LiveOrderSafetyService:
    """실계좌 주문 전 필수 안전장치의 fail-closed preflight를 평가한다."""

    def __init__(
        self,
        env: Mapping[str, str] | None = None,
        *,
        db: Session | None = None,
        rate_limiter: LiveRateLimiter | None = None,
    ) -> None:
        self.env = os.environ if env is None else env
        self.db = db
        self.rate_limiter = rate_limiter
        self.idempotency_guard = LiveIdempotencyGuard(db)
        self.cooldown_guard = LiveCooldownGuard(self.env)
        self.audit_service = LiveOrderAuditService(db)

    def preflight(self) -> dict[str, Any]:
        """네트워크 호출 없이 3단계 선행 안전장치 충족 여부를 redacted payload로 반환한다."""
        controls = {
            "kill_switch": self._kill_switch_control(),
            "rate_limiter": self._rate_limiter_control(),
            "idempotency_key": self._idempotency_control(),
            "audit_log": self._audit_control(),
            "max_order_notional": self._max_notional_control(),
            "blacklist": self._blacklist_control(),
            "cooldown": self._cooldown_control(),
            "token_refresh": self._token_refresh_control(),
        }
        blockers = [
            blocker
            for control in controls.values()
            for blocker in control["blockers"]
        ]
        return {
            "all_required_controls_passed": not blockers,
            "required_controls": controls,
            "blockers": sorted(set(blockers)),
            "live_order_created": False,
            "network_call_performed": False,
            "secrets_redacted": True,
        }

    def evaluate_order_request(
        self,
        *,
        symbol: str,
        side: str,
        qty: int,
        limit_price: float | None,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        """주문 후보를 3단계 안전장치 기준으로 평가하되 live 주문은 생성하지 않는다."""
        preflight = self.preflight()
        normalized_symbol = symbol.strip().upper()
        normalized_side = side.strip().lower()
        request_blockers: list[str] = []
        if not normalized_symbol:
            request_blockers.append("LIVE_ORDER_SYMBOL_REQUIRED")
        if normalized_side not in {"buy", "sell"}:
            request_blockers.append("LIVE_ORDER_SIDE_INVALID")
        if qty <= 0:
            request_blockers.append("LIVE_ORDER_QTY_INVALID")
        if limit_price is None or limit_price <= 0:
            request_blockers.append("LIVE_ORDER_LIMIT_PRICE_REQUIRED")

        blacklist = set(_symbol_list(self.env.get("LIVE_SYMBOL_BLACKLIST", "")))
        if normalized_symbol and normalized_symbol in blacklist:
            request_blockers.append("LIVE_ORDER_SYMBOL_BLACKLISTED")

        max_notional = _float_env(self.env, "LIVE_MAX_ORDER_NOTIONAL")
        estimated_notional = float(qty) * float(limit_price or 0.0) if qty > 0 else 0.0
        if max_notional is not None and estimated_notional > max_notional:
            request_blockers.append("LIVE_ORDER_NOTIONAL_EXCEEDS_LIMIT")

        request_payload = {
            "symbol": normalized_symbol,
            "side": normalized_side,
            "qty": qty,
            "limit_price": limit_price,
            "estimated_notional": estimated_notional,
        }
        idempotency_check = self.idempotency_guard.evaluate(
            idempotency_key=idempotency_key,
            request_payload=request_payload,
        )
        request_blockers.extend(idempotency_check["reason_codes"])
        rate_limiter_check = self._rate_limiter().check(consume=False)
        if "LIVE_ORDER_RATE_LIMIT_EXCEEDED" in rate_limiter_check["reason_codes"]:
            request_blockers.append("LIVE_ORDER_RATE_LIMIT_EXCEEDED")
        cooldown_check = self.cooldown_guard.evaluate(symbol=normalized_symbol)
        request_blockers.extend(cooldown_check["reason_codes"])

        blockers = sorted(set(preflight["blockers"] + request_blockers))
        decision = "allow" if not blockers else "deny"
        audit_event = self.audit_service.build_event(
            event_type="live_order_safety_evaluated",
            decision=decision,
            reason_codes=blockers,
            payload={
                **request_payload,
                "idempotency_key_fingerprint": idempotency_check["key_fingerprint"],
                "request_blockers": sorted(set(request_blockers)),
            },
        )
        return {
            "passed": not blockers,
            "decision": decision,
            "blockers": blockers,
            "request_blockers": sorted(set(request_blockers)),
            "estimated_notional": estimated_notional,
            "symbol": normalized_symbol,
            "side": normalized_side,
            "idempotency_key_present": bool(idempotency_key and idempotency_key.strip()),
            "control_checks": {
                "rate_limiter": rate_limiter_check,
                "idempotency": idempotency_check,
                "cooldown": cooldown_check,
                "audit": audit_event,
            },
            "live_order_created": False,
            "network_call_performed": False,
            "preflight": preflight,
        }

    def _kill_switch_control(self) -> dict[str, Any]:
        ready = _env_true(self.env, "LIVE_CANARY_KILL_SWITCH_READY") or _env_true(
            self.env, "LIVE_KILL_SWITCH_READY"
        )
        emergency_stop_armed = _env_true(self.env, "LIVE_EMERGENCY_STOP_ARMED")
        blockers: list[str] = []
        if not ready:
            blockers.append("LIVE_KILL_SWITCH_READY_REQUIRED")
        if not emergency_stop_armed:
            blockers.append("LIVE_EMERGENCY_STOP_ARMED_REQUIRED")
        return _control_payload(
            passed=not blockers,
            blockers=blockers,
            evidence={
                "kill_switch_ready": ready,
                "emergency_stop_armed": emergency_stop_armed,
            },
        )

    def _rate_limiter_control(self) -> dict[str, Any]:
        per_second = _float_env(self.env, "LIVE_RATE_LIMIT_PER_SECOND")
        burst = _int_env(self.env, "LIVE_RATE_LIMIT_BURST")
        blockers: list[str] = []
        if per_second is None or per_second <= 0:
            blockers.append("LIVE_RATE_LIMIT_PER_SECOND_REQUIRED")
        if per_second is not None and per_second > 10:
            blockers.append("LIVE_RATE_LIMIT_PER_SECOND_TOO_HIGH")
        if burst is None or burst <= 0:
            blockers.append("LIVE_RATE_LIMIT_BURST_REQUIRED")
        if burst is not None and burst > 50:
            blockers.append("LIVE_RATE_LIMIT_BURST_TOO_HIGH")
        return _control_payload(
            passed=not blockers,
            blockers=blockers,
            evidence={"per_second": per_second, "burst": burst},
        )

    def _idempotency_control(self) -> dict[str, Any]:
        required = _env_true(self.env, "LIVE_IDEMPOTENCY_REQUIRED")
        return _control_payload(
            passed=required,
            blockers=[] if required else ["LIVE_IDEMPOTENCY_REQUIRED_FLAG_MISSING"],
            evidence={"idempotency_required": required},
        )

    def _audit_control(self) -> dict[str, Any]:
        audit_enabled = _env_true(self.env, "LIVE_AUDIT_LOG_ENABLED")
        redaction_enabled = _env_true(self.env, "LIVE_AUDIT_REDACTION_ENABLED")
        blockers: list[str] = []
        if not audit_enabled:
            blockers.append("LIVE_AUDIT_LOG_ENABLED_REQUIRED")
        if not redaction_enabled:
            blockers.append("LIVE_AUDIT_REDACTION_ENABLED_REQUIRED")
        return _control_payload(
            passed=not blockers,
            blockers=blockers,
            evidence={
                "audit_log_enabled": audit_enabled,
                "audit_redaction_enabled": redaction_enabled,
            },
        )

    def _max_notional_control(self) -> dict[str, Any]:
        notional = _float_env(self.env, "LIVE_MAX_ORDER_NOTIONAL")
        blockers: list[str] = []
        if notional is None or notional <= 0:
            blockers.append("LIVE_MAX_ORDER_NOTIONAL_REQUIRED")
        if notional is not None and notional > MAX_CANARY_NOTIONAL_CAP:
            blockers.append("LIVE_MAX_ORDER_NOTIONAL_TOO_HIGH_FOR_CANARY")
        return _control_payload(
            passed=not blockers,
            blockers=blockers,
            evidence={
                "max_order_notional": notional,
                "max_canary_notional_cap": MAX_CANARY_NOTIONAL_CAP,
            },
        )

    def _blacklist_control(self) -> dict[str, Any]:
        enabled = _env_true(self.env, "LIVE_BLACKLIST_ENABLED")
        symbols = _symbol_list(self.env.get("LIVE_SYMBOL_BLACKLIST", ""))
        blockers: list[str] = []
        if not enabled:
            blockers.append("LIVE_BLACKLIST_ENABLED_REQUIRED")
        if not symbols:
            blockers.append("LIVE_SYMBOL_BLACKLIST_REQUIRED")
        return _control_payload(
            passed=not blockers,
            blockers=blockers,
            evidence={
                "blacklist_enabled": enabled,
                "symbol_count": len(symbols),
            },
        )

    def _cooldown_control(self) -> dict[str, Any]:
        cooldown_seconds = _int_env(self.env, "LIVE_ORDER_COOLDOWN_SECONDS")
        blockers: list[str] = []
        if cooldown_seconds is None or cooldown_seconds <= 0:
            blockers.append("LIVE_ORDER_COOLDOWN_SECONDS_REQUIRED")
        return _control_payload(
            passed=not blockers,
            blockers=blockers,
            evidence={"cooldown_seconds": cooldown_seconds},
        )

    def _token_refresh_control(self) -> dict[str, Any]:
        enabled = _env_true(self.env, "LIVE_TOKEN_REFRESH_ENABLED")
        process_only = _env_true(self.env, "LIVE_TOKEN_REFRESH_PROCESS_ONLY")
        blockers: list[str] = []
        if not enabled:
            blockers.append("LIVE_TOKEN_REFRESH_ENABLED_REQUIRED")
        if not process_only:
            blockers.append("LIVE_TOKEN_REFRESH_PROCESS_ONLY_REQUIRED")
        # 현재 repo에는 live token refresh network implementation이 없으므로 canary는 계속 차단된다.
        blockers.append("LIVE_TOKEN_REFRESH_NETWORK_IMPLEMENTATION_ABSENT")
        return _control_payload(
            passed=False,
            blockers=blockers,
            evidence={
                "token_refresh_enabled": enabled,
                "process_only": process_only,
                "network_implementation_present": False,
            },
        )

    def _rate_limiter(self) -> LiveRateLimiter:
        if self.rate_limiter is not None:
            return self.rate_limiter
        return LiveRateLimiter(
            per_second=_float_env(self.env, "LIVE_RATE_LIMIT_PER_SECOND"),
            burst=_int_env(self.env, "LIVE_RATE_LIMIT_BURST"),
        )


def _control_payload(*, passed: bool, blockers: list[str], evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "passed": passed,
        "blockers": blockers,
        "evidence": evidence,
    }


def _env_true(env: Mapping[str, str], name: str) -> bool:
    return str(env.get(name, "")).strip().lower() in TRUE_VALUES


def _float_env(env: Mapping[str, str], name: str) -> float | None:
    raw = str(env.get(name, "")).strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _int_env(env: Mapping[str, str], name: str) -> int | None:
    raw = str(env.get(name, "")).strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _symbol_list(raw: str) -> list[str]:
    return [item.strip().upper() for item in raw.split(",") if item.strip()]


def _parse_iso_datetime(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _fingerprint(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _stable_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sanitize(value: Any, key: str = "") -> Any:
    if _is_sensitive_key(key):
        return None
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for item_key, item_value in value.items():
            normalized_key = str(item_key)
            if _is_sensitive_key(normalized_key):
                continue
            sanitized[normalized_key] = _sanitize(item_value, normalized_key)
        return sanitized
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)
