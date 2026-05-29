from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

TRUE_VALUES = {"1", "true", "yes", "on"}
MAX_CANARY_NOTIONAL_CAP = 1_000_000.0


class LiveOrderSafetyService:
    """실계좌 주문 전 필수 안전장치의 fail-closed preflight를 평가한다."""

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self.env = os.environ if env is None else env

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
        if not idempotency_key or not idempotency_key.strip():
            request_blockers.append("LIVE_ORDER_IDEMPOTENCY_KEY_REQUIRED")

        blacklist = set(_symbol_list(self.env.get("LIVE_SYMBOL_BLACKLIST", "")))
        if normalized_symbol and normalized_symbol in blacklist:
            request_blockers.append("LIVE_ORDER_SYMBOL_BLACKLISTED")

        max_notional = _float_env(self.env, "LIVE_MAX_ORDER_NOTIONAL")
        estimated_notional = float(qty) * float(limit_price or 0.0) if qty > 0 else 0.0
        if max_notional is not None and estimated_notional > max_notional:
            request_blockers.append("LIVE_ORDER_NOTIONAL_EXCEEDS_LIMIT")

        cooldown_blocker = self._cooldown_request_blocker(normalized_symbol)
        if cooldown_blocker:
            request_blockers.append(cooldown_blocker)

        blockers = sorted(set(preflight["blockers"] + request_blockers))
        return {
            "passed": not blockers,
            "decision": "allow" if not blockers else "deny",
            "blockers": blockers,
            "request_blockers": sorted(set(request_blockers)),
            "estimated_notional": estimated_notional,
            "symbol": normalized_symbol,
            "side": normalized_side,
            "idempotency_key_present": bool(idempotency_key and idempotency_key.strip()),
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

    def _cooldown_request_blocker(self, symbol: str) -> str | None:
        cooldown_seconds = _int_env(self.env, "LIVE_ORDER_COOLDOWN_SECONDS")
        last_symbol = str(self.env.get("LIVE_LAST_ORDER_SYMBOL", "")).strip().upper()
        last_ts = _parse_iso_datetime(str(self.env.get("LIVE_LAST_ORDER_TS", "")).strip())
        if not symbol or not cooldown_seconds or not last_symbol or last_ts is None:
            return None
        if symbol != last_symbol:
            return None
        elapsed = (datetime.now(UTC) - last_ts).total_seconds()
        return "LIVE_ORDER_COOLDOWN_ACTIVE" if elapsed < cooldown_seconds else None

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
