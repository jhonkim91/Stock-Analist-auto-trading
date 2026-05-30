from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from backend.app.core import runtime_env
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


@dataclass(frozen=True)
class RuntimeEnvPresetSpec:
    name: str
    label: str
    category: str
    description: str
    values: tuple[tuple[str, str], ...]
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
        "PAPER_BOT_SCHEDULER_ENABLED",
        "Bot scheduler",
        "bot",
        "모의 자동매매봇 반복 실행 scheduler gate입니다.",
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
        "PAPER_SYNC_WORKER_ENABLED",
        "Paper sync worker",
        "broker",
        "모의투자 미체결/체결/잔고 동기화 worker 실행 게이트입니다.",
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
        "KIS_TOKEN_CACHE_ENABLED",
        "Token cache",
        "kis",
        "KIS 모의투자 access token을 로컬 cache 파일에 저장할지 제어합니다.",
        high_impact=True,
    ),
    RuntimeEnvToggleSpec(
        "KIS_MARKET_QUOTE_ENABLED",
        "KIS quote",
        "kis",
        "종목 상세 조회에서 KIS 현재가 API를 우선 사용할지 제어합니다.",
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
        "TELEGRAM_BOT_ENABLED",
        "Telegram bot",
        "telegram",
        "Telegram 명령 dispatcher를 현재 backend 프로세스에서 켜거나 끕니다.",
    ),
    RuntimeEnvToggleSpec(
        "TELEGRAM_POLLING_ENABLED",
        "Telegram polling",
        "telegram",
        "Telegram getUpdates polling runner 실행 게이트입니다.",
        high_impact=True,
    ),
    RuntimeEnvToggleSpec(
        "TELEGRAM_POLLING_SEND_REPLIES",
        "Telegram replies",
        "telegram",
        "polling 명령 처리 결과를 Telegram 메시지로 회신할지 제어합니다.",
        high_impact=True,
    ),
    RuntimeEnvToggleSpec(
        "TELEGRAM_REPORT_SCHEDULER_ENABLED",
        "Report scheduler",
        "telegram",
        "Telegram 장전/장후/주간 리포트 scheduler 실행 게이트입니다.",
    ),
    RuntimeEnvToggleSpec(
        "TELEGRAM_PRE_MARKET_REPORT_ENABLED",
        "Pre-market report",
        "telegram",
        "장 시작 전 Telegram 리포트 slot을 켜거나 끕니다.",
    ),
    RuntimeEnvToggleSpec(
        "TELEGRAM_POST_MARKET_REPORT_ENABLED",
        "Post-market report",
        "telegram",
        "장 종료 후 Telegram 리포트 slot을 켜거나 끕니다.",
    ),
    RuntimeEnvToggleSpec(
        "TELEGRAM_WEEKLY_REPORT_ENABLED",
        "Weekly report",
        "telegram",
        "주간 Telegram 리포트 slot을 켜거나 끕니다.",
    ),
    RuntimeEnvToggleSpec(
        "TELEGRAM_REPORT_DRY_RUN",
        "Telegram dry-run",
        "telegram",
        "Telegram 리포트 전송을 dry-run으로 둘지 제어합니다.",
    ),
    RuntimeEnvToggleSpec(
        "LIVE_TRADING_ENABLED",
        "Live trading",
        "live",
        "실계좌(라이브) 트레이딩 경로를 켭니다. 라이브 어댑터/주문 제출은 이 게이트가 켜져 있어야 합니다(고위험).",
        high_impact=True,
    ),
    RuntimeEnvToggleSpec(
        "LIVE_ORDER_SUBMIT_ENABLED",
        "Live order submit",
        "live",
        "라이브 주문 제출(실주문)을 허용합니다. ENABLE_REAL_ORDER, 라이브 자격증명과 함께 동작합니다(고위험).",
        high_impact=True,
    ),
    RuntimeEnvToggleSpec(
        "LIVE_ORDER_CONFIRM_REQUIRED",
        "Live order confirm",
        "live",
        "라이브 주문/취소에 명시적 confirm을 요구합니다(안전장치). 끄면 확인 없이 실주문이 나갈 수 있습니다.",
        high_impact=True,
    ),
    RuntimeEnvToggleSpec(
        "LIVE_KILL_SWITCH",
        "Live kill switch",
        "live",
        "켜져 있으면 모든 라이브 주문을 즉시 차단하는 비상 정지입니다.",
        high_impact=True,
    ),
    RuntimeEnvToggleSpec(
        "ENABLE_REAL_ORDER",
        "Real order enable",
        "live",
        "실계좌에 진짜 주문이 나가도록 허용합니다. 켜면 실제 금전 손실 위험이 있습니다(고위험). 라이브 자격증명과 LIVE_TRADING_ENABLED가 함께 필요합니다.",
        high_impact=True,
    ),
)


RUNTIME_ENV_TOGGLE_MAP = {spec.name: spec for spec in RUNTIME_ENV_TOGGLE_SPECS}

RUNTIME_ENV_PRESET_SPECS: tuple[RuntimeEnvPresetSpec, ...] = (
    RuntimeEnvPresetSpec(
        "paper_kis_ready",
        "모의 주문 준비",
        "paper",
        "KIS 모의투자 주문/취소/조회에 필요한 paper_kis gate를 한 번에 켭니다. 실계좌 주문은 계속 false로 잠급니다.",
        (
            ("EXECUTION_MODE", "paper_kis"),
            ("BROKER_MODE", "paper_kis"),
            ("KIS_ENV", "paper"),
            ("ENABLE_REAL_ORDER", "false"),
            ("PAPER_TRADING_ENABLED", "true"),
            ("PAPER_TRADING_CAN_CREATE", "true"),
            ("PAPER_TRADING_NETWORK_ENABLED", "true"),
            ("PAPER_TRADING_KILL_SWITCH", "false"),
            ("PAPER_ORDER_SUBMIT_ENABLED", "true"),
            ("KIS_TOKEN_ISSUE_ENABLED", "true"),
            ("KIS_TOKEN_CACHE_ENABLED", "true"),
            ("KIS_MARKET_QUOTE_ENABLED", "true"),
            ("PAPER_SYNC_WORKER_ENABLED", "true"),
            ("PAPER_SYNC_WORKER_MAX_ITERATIONS", "1"),
            ("PAPER_SYNC_WORKER_MAX_ITERATIONS_CAP", "10"),
            ("PAPER_BOT_CONFIRM", "true"),
            ("PAPER_BOT_KILL_SWITCH", "false"),
        ),
        high_impact=True,
    ),
    RuntimeEnvPresetSpec(
        "paper_bot_auto_on",
        "자동매매 ON",
        "bot",
        "모의 자동매매봇을 paper_kis 기준으로 켜고 auto-submit gate까지 켭니다. live 주문은 계속 차단됩니다.",
        (
            ("EXECUTION_MODE", "paper_kis"),
            ("BROKER_MODE", "paper_kis"),
            ("KIS_ENV", "paper"),
            ("ENABLE_REAL_ORDER", "false"),
            ("PAPER_TRADING_ENABLED", "true"),
            ("PAPER_TRADING_CAN_CREATE", "true"),
            ("PAPER_TRADING_NETWORK_ENABLED", "true"),
            ("PAPER_TRADING_KILL_SWITCH", "false"),
            ("PAPER_ORDER_SUBMIT_ENABLED", "true"),
            ("KIS_TOKEN_ISSUE_ENABLED", "true"),
            ("KIS_TOKEN_CACHE_ENABLED", "true"),
            ("KIS_MARKET_QUOTE_ENABLED", "true"),
            ("PAPER_SYNC_WORKER_ENABLED", "true"),
            ("PAPER_SYNC_WORKER_MAX_ITERATIONS", "1"),
            ("PAPER_SYNC_WORKER_MAX_ITERATIONS_CAP", "10"),
            ("PAPER_BOT_ENABLED", "true"),
            ("PAPER_BOT_AUTO_SUBMIT", "true"),
            ("PAPER_BOT_SCHEDULER_ENABLED", "true"),
            ("PAPER_BOT_CONFIRM", "true"),
            ("PAPER_BOT_KILL_SWITCH", "false"),
        ),
        high_impact=True,
    ),
    RuntimeEnvPresetSpec(
        "telegram_report_ready",
        "텔레그램 리포트 ON",
        "telegram",
        "Telegram bot/report scheduler와 장전/장후/주간 리포트 gate를 켭니다. 토큰과 chat_id 값은 .env에서만 읽습니다.",
        (
            ("TELEGRAM_BOT_ENABLED", "true"),
            ("TELEGRAM_REPORT_SCHEDULER_ENABLED", "true"),
            ("TELEGRAM_PRE_MARKET_REPORT_ENABLED", "true"),
            ("TELEGRAM_POST_MARKET_REPORT_ENABLED", "true"),
            ("TELEGRAM_WEEKLY_REPORT_ENABLED", "true"),
            ("TELEGRAM_REPORT_DRY_RUN", "false"),
            ("REPORT_AUTOMATION_ENABLED", "true"),
            ("REPORT_AUTOMATION_NOTIFY", "true"),
        ),
        high_impact=True,
    ),
    RuntimeEnvPresetSpec(
        "paper_bot_safe_stop",
        "봇/주문 정지",
        "locked",
        "모의 자동매매와 신규 모의 주문을 즉시 막는 process-only 정지 preset입니다. live 주문은 계속 false입니다.",
        (
            ("ENABLE_REAL_ORDER", "false"),
            ("PAPER_BOT_ENABLED", "false"),
            ("PAPER_BOT_AUTO_SUBMIT", "false"),
            ("PAPER_BOT_SCHEDULER_ENABLED", "false"),
            ("PAPER_BOT_KILL_SWITCH", "true"),
            ("PAPER_TRADING_KILL_SWITCH", "true"),
            ("PAPER_SYNC_WORKER_ENABLED", "false"),
            ("TELEGRAM_POLLING_ENABLED", "false"),
            ("TELEGRAM_POLLING_SEND_REPLIES", "false"),
        ),
        high_impact=True,
    ),
)

RUNTIME_ENV_PRESET_MAP = {spec.name.upper(): spec for spec in RUNTIME_ENV_PRESET_SPECS}

# 프로그램 내에서 직접 입력 가능한 자격증명/환경 값 그룹 (값은 마스킹되어 노출됨)
ENVIRONMENT_FIELD_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "category": "kis_credentials",
        "label": "KIS 자격증명",
        "fields": (
            {"key": "KIS_APP_KEY", "label": "앱키 (App Key)", "placeholder": "KIS Open API App Key"},
            {"key": "KIS_APP_SECRET", "label": "앱시크릿 (App Secret)", "placeholder": "KIS Open API App Secret"},
            {"key": "KIS_ACCOUNT_NO", "label": "계좌번호 (CANO)", "placeholder": "예: 50000000"},
            {"key": "KIS_PRODUCT_CODE", "label": "상품코드 (ACNT_PRDT_CD)", "placeholder": "예: 01"},
            {"key": "KIS_ACCESS_TOKEN", "label": "액세스 토큰", "placeholder": "발급된 토큰(선택)"},
            {"key": "KIS_REFRESH_TOKEN", "label": "리프레시 토큰", "placeholder": "라이브 토큰 갱신용(선택)"},
        ),
    },
    {
        "category": "kis_mode",
        "label": "KIS 모드 / 엔드포인트",
        "fields": (
            {"key": "KIS_ENV", "label": "KIS 환경 (paper/live)", "placeholder": "paper 또는 live"},
            {"key": "EXECUTION_MODE", "label": "실행 모드", "placeholder": "예: paper_kis / live_kis"},
            {"key": "BROKER_MODE", "label": "브로커 모드", "placeholder": "예: paper_kis / live_kis"},
            {"key": "KIS_PAPER_BASE_URL", "label": "모의 베이스 URL", "placeholder": "https://openapivts.koreainvestment.com:29443"},
            {"key": "KIS_LIVE_BASE_URL", "label": "라이브 베이스 URL", "placeholder": "https://openapi.koreainvestment.com:9443"},
        ),
    },
    {
        "category": "live_safety",
        "label": "라이브 안전장치 값",
        "fields": (
            {"key": "LIVE_MAX_ORDER_NOTIONAL", "label": "주문당 최대 금액", "placeholder": "예: 100000"},
            {"key": "LIVE_RATE_LIMIT_PER_SECOND", "label": "초당 주문 제한", "placeholder": "예: 2"},
            {"key": "LIVE_RATE_LIMIT_BURST", "label": "버스트 한도", "placeholder": "예: 5"},
            {"key": "LIVE_ORDER_COOLDOWN_SECONDS", "label": "주문 쿨다운(초)", "placeholder": "예: 1"},
            {"key": "LIVE_SYMBOL_BLACKLIST", "label": "차단 종목(쉼표구분)", "placeholder": "예: 000000,000001"},
        ),
    },
    {
        "category": "telegram",
        "label": "텔레그램",
        "fields": (
            {"key": "TELEGRAM_BOT_TOKEN", "label": "봇 토큰", "placeholder": "123456:ABC-..."},
            {"key": "TELEGRAM_CHAT_ID", "label": "챗 ID", "placeholder": "예: 123456789"},
        ),
    },
    {
        "category": "discord",
        "label": "디스코드",
        "fields": ({"key": "DISCORD_OPS_WEBHOOK_URL", "label": "운영 웹훅 URL", "placeholder": "https://discord.com/api/webhooks/..."},),
    },
)


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
        """UI에서 토글 가능한 env gate 상태를 현재 사용자 scope 기준으로 반환한다."""
        user_id = runtime_env.current_user_id()
        return {
            "scope": runtime_env.scope_label(user_id),
            "user_id": user_id,
            "persistence": "file",
            "file_write_performed": True,
            "secrets_redacted": True,
            "toggles": [self._toggle_status(spec) for spec in RUNTIME_ENV_TOGGLE_SPECS],
            "presets": [self._preset_status(spec) for spec in RUNTIME_ENV_PRESET_SPECS],
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
        applied_enabled = enabled
        # 현재 프로세스에 반영하고 runtime_env.json에 영속화한다(재시작에도 유지).
        runtime_env.set_persisted_env(spec.name, "true" if applied_enabled else "false")
        return self._toggle_result(
            ok=True,
            status="updated",
            reason_codes=[],
            name=spec.name,
            enabled=applied_enabled,
            toggle=self._toggle_status(spec),
        )

    def set_runtime_env_preset(self, *, name: str, confirm: bool) -> dict[str, Any]:
        """allowlist paper-only preset을 현재 backend 프로세스에 일괄 반영한다."""
        normalized = name.strip().upper()
        spec = RUNTIME_ENV_PRESET_MAP.get(normalized)
        if spec is None:
            return self._preset_result(
                ok=False,
                status="blocked",
                reason_codes=["ENV_PRESET_NOT_ALLOWED"],
                preset_name=normalized,
                applied=[],
            )
        if not confirm:
            return self._preset_result(
                ok=False,
                status="blocked",
                reason_codes=["ENV_PRESET_CONFIRM_REQUIRED"],
                preset_name=spec.name,
                applied=[],
                preset=self._preset_status(spec),
            )

        applied: list[dict[str, str]] = []
        for key, value in spec.values:
            safe_key = key.strip().upper()
            safe_value = value.strip()
            # 프로세스 반영 + 영속화. 허용 키가 아니면 os.environ만 반영한다.
            if not runtime_env.set_persisted_env(safe_key, safe_value):
                os.environ[safe_key] = safe_value
            applied.append({"name": safe_key, "value": safe_value})

        return self._preset_result(
            ok=True,
            status="updated",
            reason_codes=[],
            preset_name=spec.name,
            applied=applied,
            preset=self._preset_status(spec),
        )

    def environment_status(self) -> dict[str, Any]:
        """UI에서 입력 가능한 자격증명/환경 값의 (마스킹된) 현재 상태를 그룹별로 반환한다."""
        user_id = runtime_env.current_user_id()
        groups = []
        for group in ENVIRONMENT_FIELD_GROUPS:
            keys = [field["key"] for field in group["fields"]]
            snapshot = {row["key"]: row for row in runtime_env.masked_snapshot(keys)}
            fields = []
            for field in group["fields"]:
                row = snapshot.get(field["key"], {})
                fields.append(
                    {
                        **field,
                        "configured": row.get("configured", False),
                        "persisted": row.get("persisted", False),
                        "sensitive": row.get("sensitive", False),
                        "masked_value": row.get("masked_value", ""),
                    }
                )
            groups.append({"category": group["category"], "label": group["label"], "fields": fields})
        return {
            "scope": runtime_env.scope_label(user_id),
            "user_id": user_id,
            "persistence": "file",
            "secrets_redacted": True,
            "groups": groups,
        }

    def set_environment_value(self, *, key: str, value: str, confirm: bool) -> dict[str, Any]:
        """허용된 환경 값 하나를 영속 저장하고 현재 프로세스에 반영한다."""
        normalized = key.strip().upper()
        if not confirm:
            return {"ok": False, "status": "blocked", "key": normalized, "reason_codes": ["ENV_VALUE_CONFIRM_REQUIRED"]}
        if not runtime_env.is_allowed_key(normalized):
            return {"ok": False, "status": "blocked", "key": normalized, "reason_codes": ["ENV_VALUE_NOT_ALLOWED"]}
        trimmed = value.strip()
        if trimmed == "":
            runtime_env.delete_persisted_env(normalized)
            status = "cleared"
        else:
            runtime_env.set_persisted_env(normalized, trimmed)
            status = "updated"
        return {
            "ok": True,
            "status": status,
            "key": normalized,
            "persistence": "file",
            "file_write_performed": True,
            "secrets_redacted": True,
            "masked_value": runtime_env.mask_value(normalized, runtime_env.get_effective(normalized)),
            "configured": bool(runtime_env.get_effective(normalized)),
            "scope": runtime_env.scope_label(),
            "user_id": runtime_env.current_user_id(),
            "reason_codes": [],
        }

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
        configured = runtime_env.get_effective(spec.name) is not None
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
            "scope": runtime_env.scope_label(),
            "persisted": runtime_env.is_persisted(spec.name),
            "reason_codes": reason_codes,
        }

    @staticmethod
    def _preset_status(spec: RuntimeEnvPresetSpec) -> dict[str, Any]:
        return {
            "name": spec.name,
            "label": spec.label,
            "category": spec.category,
            "description": spec.description,
            "high_impact": spec.high_impact,
            "scope": runtime_env.scope_label(),
            "changes": [{"name": name, "value": value} for name, value in spec.values],
        }

    @staticmethod
    def _env_enabled(name: str) -> bool:
        return (runtime_env.get_effective(name) or "").strip().lower() in {"1", "true", "yes", "on"}

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
            "scope": runtime_env.scope_label(),
            "persistence": "file",
            "file_write_performed": True,
            "network_call_performed": False,
            "live_order_created": False,
            "secrets_redacted": True,
            "reason_codes": reason_codes,
        }
        if toggle is not None:
            payload["toggle"] = toggle
        return payload

    @staticmethod
    def _preset_result(
        *,
        ok: bool,
        status: str,
        reason_codes: list[str],
        preset_name: str,
        applied: list[dict[str, str]],
        preset: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "ok": ok,
            "status": status,
            "preset": preset_name,
            "applied": applied,
            "scope": runtime_env.scope_label(),
            "persistence": "file",
            "file_write_performed": True,
            "network_call_performed": False,
            "live_order_created": False,
            "secrets_redacted": True,
            "reason_codes": reason_codes,
        }
        if preset is not None:
            payload["definition"] = preset
        return payload
