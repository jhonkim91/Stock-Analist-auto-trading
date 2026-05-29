from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from backend.app.core.paths import CONFIG_DIR

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
    "account",
    "account_no",
    "cano",
    "hts_id",
    "approval_key",
    "webhook",
    "chat_id",
    "bot_token",
)


@dataclass(frozen=True)
class RuntimeEnvToggleSpec:
    name: str
    label: str
    category: str
    description: str
    false_locked: bool = False
    high_impact: bool = False


RUNTIME_ENV_TOGGLE_SPECS: tuple[RuntimeEnvToggleSpec, ...] = (
    RuntimeEnvToggleSpec(
        "PAPER_TRADING_ENABLED",
        "Paper trading",
        "paper",
        "모의투자 기능 전체를 현재 backend 프로세스에서 켜거나 끕니다.",
    ),
    RuntimeEnvToggleSpec(
        "PAPER_TRADING_CAN_CREATE",
        "Paper create",
        "paper",
        "paper_orders에 모의 주문을 생성할 수 있는지 제어합니다.",
    ),
    RuntimeEnvToggleSpec(
        "PAPER_TRADING_NETWORK_ENABLED",
        "Paper network",
        "paper",
        "KIS 모의투자 API 호출 허용 게이트입니다. 버튼 클릭만으로 주문이 즉시 전송되지는 않습니다.",
        high_impact=True,
    ),
    RuntimeEnvToggleSpec(
        "PAPER_TRADING_KILL_SWITCH",
        "Paper kill switch",
        "paper",
        "켜져 있으면 신규 모의 주문 생성을 차단합니다.",
        high_impact=True,
    ),
    RuntimeEnvToggleSpec(
        "PAPER_BOT_ENABLED",
        "Bot enabled",
        "bot",
        "모의 자동매매봇 실행 자체를 현재 backend 프로세스에서 켜거나 끕니다.",
    ),
    RuntimeEnvToggleSpec(
        "PAPER_BOT_AUTO_SUBMIT",
        "Bot auto-submit",
        "bot",
        "봇 실행 결과가 조건을 통과했을 때 모의 주문 제출까지 허용할지 제어합니다.",
        high_impact=True,
    ),
    RuntimeEnvToggleSpec(
        "PAPER_BOT_KILL_SWITCH",
        "Bot kill switch",
        "bot",
        "켜져 있으면 봇의 모의 주문 제출을 차단합니다.",
        high_impact=True,
    ),
    RuntimeEnvToggleSpec(
        "PAPER_BOT_CONFIRM",
        "Bot confirm",
        "bot",
        "봇과 모의 주문 제출에 필요한 최종 확인 게이트입니다.",
    ),
    RuntimeEnvToggleSpec(
        "PAPER_ORDER_SUBMIT_ENABLED",
        "Paper order submit",
        "broker",
        "KIS 모의투자 주문 adapter 제출 게이트입니다.",
        high_impact=True,
    ),
    RuntimeEnvToggleSpec(
        "KIS_TOKEN_ISSUE_ENABLED",
        "Token issue",
        "kis",
        "KIS 모의투자 access token 발급 API 호출 게이트입니다.",
        high_impact=True,
    ),
    RuntimeEnvToggleSpec(
        "KIS_WEBSOCKET_APPROVAL_ENABLED",
        "WS approval",
        "kis",
        "KIS 모의투자 WebSocket approval key 발급 게이트입니다.",
        high_impact=True,
    ),
    RuntimeEnvToggleSpec(
        "PAPER_WEBSOCKET_ENABLED",
        "Paper WebSocket",
        "kis",
        "모의투자 WebSocket 상태와 구독 preview 기능을 켜거나 끕니다.",
    ),
    RuntimeEnvToggleSpec(
        "PAPER_WEBSOCKET_CONNECT_ENABLED",
        "WS bounded connect",
        "kis",
        "제한 시간 있는 WebSocket smoke 연결 게이트입니다. 장시간 loop는 시작하지 않습니다.",
        high_impact=True,
    ),
    RuntimeEnvToggleSpec(
        "REPORT_AUTOMATION_ENABLED",
        "Report automation",
        "reports",
        "일간/주간 리포트 자동 생성 실행 게이트입니다.",
    ),
    RuntimeEnvToggleSpec(
        "REPORT_AUTOMATION_DRY_RUN",
        "Report dry-run",
        "reports",
        "리포트 자동화가 실제 전송 대신 dry-run으로 동작할지 정합니다.",
    ),
    RuntimeEnvToggleSpec(
        "REPORT_AUTOMATION_NOTIFY",
        "Report notify",
        "reports",
        "리포트 자동화 완료 알림을 notification queue에 넣을지 제어합니다.",
    ),
    RuntimeEnvToggleSpec(
        "NOTIFICATIONS_ENABLED",
        "Notifications",
        "notifications",
        "Telegram/Discord 알림 서비스를 현재 backend 프로세스에서 켜거나 끕니다.",
    ),
    RuntimeEnvToggleSpec(
        "NOTIFICATIONS_DEFAULT_DRY_RUN",
        "Notification dry-run",
        "notifications",
        "알림 전송 기본값을 dry-run으로 둘지 제어합니다.",
    ),
    RuntimeEnvToggleSpec(
        "ENABLE_REAL_ORDER",
        "Live order lock",
        "locked",
        "실계좌 주문 잠금입니다. 버튼을 눌러도 false로만 강제 적용됩니다.",
        false_locked=True,
        high_impact=True,
    ),
)


RUNTIME_ENV_TOGGLE_MAP = {spec.name: spec for spec in RUNTIME_ENV_TOGGLE_SPECS}


class SettingsService:
    def __init__(self, config_dir: Path = CONFIG_DIR) -> None:
        self.config_dir = config_dir

    def read_settings(self) -> dict[str, Any]:
        """backend/config/*.yaml만 읽어 read-only 설정 요약을 반환한다."""
        result: dict[str, Any] = {}
        for name in (
            "strategies",
            "risk",
            "backtest",
            "app",
            "data_sources",
            "notifications",
            "bot",
            "paper",
            "broker",
            "reports",
        ):
            path = self.config_dir / f"{name}.yaml"
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8") as file:
                data = yaml.safe_load(file) or {}
            result[name] = self._redact(data)
        return result

    def runtime_env_status(self) -> dict[str, Any]:
        """UI에서 토글 가능한 process-only env gate 상태를 반환한다."""
        return {
            "scope": "process",
            "persistence": "process_only",
            "file_write_performed": False,
            "secrets_redacted": True,
            "toggles": [self._toggle_status(spec) for spec in RUNTIME_ENV_TOGGLE_SPECS],
        }

    def set_runtime_env_toggle(self, *, name: str, enabled: bool, confirm: bool) -> dict[str, Any]:
        """allowlist boolean env만 현재 backend 프로세스에 반영한다."""
        normalized = name.strip().upper()
        spec = RUNTIME_ENV_TOGGLE_MAP.get(normalized)
        if spec is None:
            return self._toggle_result(
                ok=False,
                status="blocked",
                reason_codes=["ENV_TOGGLE_NOT_ALLOWED"],
                name=normalized,
                enabled=self._env_enabled(normalized),
            )
        if not confirm:
            return self._toggle_result(
                ok=False,
                status="blocked",
                reason_codes=["ENV_TOGGLE_CONFIRM_REQUIRED"],
                name=spec.name,
                enabled=self._env_enabled(spec.name),
            )
        applied_enabled = False if spec.false_locked else enabled
        os.environ[spec.name] = "true" if applied_enabled else "false"
        return self._toggle_result(
            ok=True,
            status="locked_false_applied" if spec.false_locked else "updated",
            reason_codes=["LIVE_ENV_FORCED_FALSE"] if spec.false_locked and enabled else [],
            name=spec.name,
            enabled=applied_enabled,
            toggle=self._toggle_status(spec),
        )

    @classmethod
    def _redact(cls, value: Any, key: str = "") -> Any:
        if cls._is_sensitive_key(key):
            return "***REDACTED***"
        if isinstance(value, dict):
            redacted: dict[str, Any] = {}
            sensitive_index = 0
            for item_key, item_value in value.items():
                item_key_text = str(item_key)
                if cls._is_sensitive_key(item_key_text):
                    redacted[f"redacted_field_{sensitive_index}"] = "***REDACTED***"
                    sensitive_index += 1
                else:
                    redacted[item_key] = cls._redact(item_value, item_key_text)
            return redacted
        if isinstance(value, list):
            return [cls._redact(item) for item in value]
        return value

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        normalized = key.lower()
        return any(part in normalized for part in SENSITIVE_KEY_PARTS)

    @classmethod
    def _toggle_status(cls, spec: RuntimeEnvToggleSpec) -> dict[str, Any]:
        configured = spec.name in os.environ
        enabled = cls._env_enabled(spec.name)
        reason_codes: list[str] = []
        if spec.false_locked:
            reason_codes.append("LIVE_ENV_TOGGLE_LOCKED_FALSE")
        return {
            "name": spec.name,
            "label": spec.label,
            "category": spec.category,
            "description": spec.description,
            "enabled": enabled,
            "configured": configured,
            "value": "true" if enabled else "false",
            "can_toggle": True,
            "false_locked": spec.false_locked,
            "high_impact": spec.high_impact,
            "scope": "process",
            "reason_codes": reason_codes,
        }

    @staticmethod
    def _env_enabled(name: str) -> bool:
        return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _toggle_result(
        *,
        ok: bool,
        status: str,
        reason_codes: list[str],
        name: str,
        enabled: bool,
        toggle: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "ok": ok,
            "status": status,
            "name": name,
            "enabled": enabled,
            "scope": "process",
            "persistence": "process_only",
            "file_write_performed": False,
            "network_call_performed": False,
            "live_order_created": False,
            "secrets_redacted": True,
            "reason_codes": reason_codes,
        }
        if toggle is not None:
            payload["toggle"] = toggle
        return payload
