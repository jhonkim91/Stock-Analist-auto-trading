from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from backend.app.core.paths import CONFIG_DIR
from backend.app.services.discord_webhook_notifier import DiscordWebhookNotifier
from backend.app.services.notification_template_service import DEFAULT_NOTIFICATION_TEMPLATES, NotificationTemplateService
from backend.app.services.telegram_notifier import TelegramNotifier

NOTIFICATIONS_CONFIG_NAME = "notifications.yaml"
DEFAULT_ALIASES = ("telegram_main", "discord_ops")
PLACEHOLDER_VALUES = {"", "<placeholder>", "placeholder", "***REDACTED***"}
SUPPORTED_NOTIFICATION_EVENTS = (
    "bot_started",
    "bot_stopped",
    "order_signal_created",
    "paper_order_previewed",
    "paper_order_submitted",
    "paper_order_rejected",
    "paper_order_filled",
    "paper_order_cancelled",
    "portfolio_snapshot",
    "daily_report_generated",
    "weekly_report_generated",
    "daily_report_automation_completed",
    "weekly_report_automation_completed",
    "report_automation_failed",
    "risk_limit_warning",
    "kis_token_error",
    "broker_error",
    "kill_switch_triggered",
)


class NotificationConfigService:
    def __init__(self, config_dir: Path = CONFIG_DIR) -> None:
        self.config_dir = config_dir

    def load(self) -> tuple[dict[str, Any], list[str]]:
        """notifications.yaml을 읽고 실패 시 disabled/dry-run 상태로 닫는다."""
        path = self.config_dir / NOTIFICATIONS_CONFIG_NAME
        if not path.exists():
            return self._default_config(), ["CONFIG_LOAD_FAILED"]
        try:
            with path.open("r", encoding="utf-8") as file:
                raw = yaml.safe_load(file) or {}
        except Exception:
            return self._default_config(), ["CONFIG_PARSE_FAILED"]
        if not isinstance(raw, dict):
            return self._default_config(), ["CONFIG_PARSE_FAILED"]
        notifications = raw.get("notifications", raw)
        if not isinstance(notifications, dict):
            return self._default_config(), ["CONFIG_PARSE_FAILED"]
        config = self._default_config()
        config.update(
            {
                "enabled": bool(notifications.get("enabled", False)),
                "default_dry_run": bool(notifications.get("default_dry_run", True)),
                "channels": notifications.get("channels") if isinstance(notifications.get("channels"), dict) else {},
                "templates": self._merge_templates(notifications.get("templates")),
            }
        )
        config["enabled"] = _env_bool("NOTIFICATIONS_ENABLED", bool(config["enabled"]))
        config["default_dry_run"] = _env_bool("NOTIFICATIONS_DEFAULT_DRY_RUN", bool(config["default_dry_run"]))
        return config, []

    @staticmethod
    def _default_config() -> dict[str, Any]:
        return {
            "enabled": False,
            "default_dry_run": True,
            "channels": {
                "discord_ops": {
                    "type": "discord",
                    "enabled": False,
                    "mode": "disabled",
                    "webhook_env": "DISCORD_OPS_WEBHOOK_URL",
                    "dry_run": True,
                    "allowed_mentions": {"parse": []},
                },
                "telegram_main": {
                    "type": "telegram",
                    "enabled": False,
                    "mode": "disabled",
                    "bot_token_env": "TELEGRAM_BOT_TOKEN",
                    "chat_id_env": "TELEGRAM_CHAT_ID",
                    "dry_run": True,
                    "parse_mode": None,
                },
            },
            "templates": dict(DEFAULT_NOTIFICATION_TEMPLATES),
        }

    @staticmethod
    def _merge_templates(raw_templates: Any) -> dict[str, str]:
        templates = dict(DEFAULT_NOTIFICATION_TEMPLATES)
        if not isinstance(raw_templates, dict):
            return templates
        for event_type, template in raw_templates.items():
            if isinstance(template, str) and template.strip():
                templates[str(event_type)] = template.strip()
        return templates


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class NotificationService:
    def __init__(self, config_dir: Path = CONFIG_DIR) -> None:
        self.config_service = NotificationConfigService(config_dir)

    def status(self) -> dict[str, Any]:
        """notification 채널 상태를 secret 값 없이 반환한다."""
        config, reasons = self.config_service.load()
        channels = [self._channel_status(alias, raw, config) for alias, raw in self._iter_channels(config)]
        return {
            "enabled": bool(config.get("enabled", False)),
            "default_dry_run": bool(config.get("default_dry_run", True)),
            "config_status": "ok" if not reasons else "disabled",
            "reason_codes": reasons,
            "network_delivery_allowed": any(channel["can_dispatch"] for channel in channels),
            "secrets_redacted": True,
            "supported_events": list(SUPPORTED_NOTIFICATION_EVENTS),
            "template_events": sorted(str(key) for key in config.get("templates", {}).keys()),
            "channels": channels,
        }

    def send_test(self, *, channel_alias: str | None = None, message: str = "notification test", dry_run: bool = True) -> dict[str, Any]:
        """상태 전이를 막지 않는 안전한 테스트 알림을 수행한다."""
        config, reasons = self.config_service.load()
        alias, raw = self._select_channel(config, channel_alias)
        if raw is None:
            return {
                "ok": False,
                "status": "channel_not_found",
                "attempted": False,
                "delivered": False,
                "dry_run": True,
                "reason_codes": self._merge_reason_codes(reasons, ["CHANNEL_NOT_FOUND"]),
            }

        channel = self._channel_status(alias, raw, config)
        effective_dry_run = dry_run or bool(raw.get("dry_run", config.get("default_dry_run", True)))
        reason_codes = self._merge_reason_codes(reasons, list(channel["reason_codes"]))
        payload_shape = self._payload_shape(raw)
        if not channel["enabled"] or channel["mode"] == "disabled":
            return self._test_result(
                status="disabled",
                channel=channel,
                reason_codes=reason_codes,
                dry_run=True,
                payload_shape=payload_shape,
                message=message,
            )
        if effective_dry_run or channel["mode"] == "mock":
            return self._test_result(
                status="dry_run" if effective_dry_run else "mock_sent",
                channel=channel,
                reason_codes=reason_codes,
                dry_run=effective_dry_run,
                payload_shape=payload_shape,
                message=message,
                delivered=channel["mode"] == "mock" and not effective_dry_run,
            )
        if not channel["can_dispatch"]:
            return self._test_result(
                status="blocked",
                channel=channel,
                reason_codes=reason_codes,
                dry_run=True,
                payload_shape=payload_shape,
                message=message,
            )
        try:
            delivery = self._dispatch(raw, message)
        except Exception:
            return self._test_result(
                status="failed",
                channel=channel,
                reason_codes=self._merge_reason_codes(reason_codes, ["DELIVERY_FAILED"]),
                dry_run=False,
                payload_shape=payload_shape,
                message=message,
            )
        return self._test_result(
            status="sent" if delivery.get("delivered") else "failed",
            channel=channel,
            reason_codes=reason_codes,
            dry_run=False,
            payload_shape=payload_shape,
            message=message,
            delivered=bool(delivery.get("delivered")),
        )

    def resolve_channel(self, channel_alias: str | None = None) -> dict[str, Any]:
        """report delivery가 secret 없이 channel 상태와 payload shape를 재사용하도록 반환한다."""
        config, reasons = self.config_service.load()
        alias, raw = self._select_channel(config, channel_alias)
        if raw is None:
            return {
                "found": False,
                "alias": alias,
                "raw": None,
                "channel": None,
                "reason_codes": self._merge_reason_codes(reasons, ["CHANNEL_NOT_FOUND"]),
                "payload_shape": {},
                "default_dry_run": True,
            }
        channel = self._channel_status(alias, raw, config)
        return {
            "found": True,
            "alias": alias,
            "raw": raw,
            "channel": channel,
            "reason_codes": self._merge_reason_codes(reasons, list(channel["reason_codes"])),
            "payload_shape": self._payload_shape(raw),
            "default_dry_run": bool(config.get("default_dry_run", True)),
        }

    def dispatch(self, raw: dict[str, Any], message: str) -> dict[str, Any]:
        """검증된 channel raw config로 실제 dispatch를 수행한다."""
        return self._dispatch(raw, message)

    def render_event_message(
        self,
        *,
        event_type: str,
        subject: str | None = None,
        payload_summary: dict[str, Any] | None = None,
    ) -> str:
        """notifications.yaml 템플릿으로 event 메시지를 secret-safe plain text로 렌더링한다."""
        config, _ = self.config_service.load()
        templates = config.get("templates") if isinstance(config.get("templates"), dict) else {}
        return NotificationTemplateService(templates).render(
            event_type=event_type,
            subject=subject,
            payload_summary=payload_summary,
        )

    def _iter_channels(self, config: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        raw_channels = config.get("channels")
        channels = raw_channels if isinstance(raw_channels, dict) else {}
        items: list[tuple[str, dict[str, Any]]] = []
        for alias in DEFAULT_ALIASES:
            raw = channels.get(alias)
            if isinstance(raw, dict):
                items.append((alias, raw))
        for alias, raw in channels.items():
            if alias in DEFAULT_ALIASES or not isinstance(raw, dict):
                continue
            items.append((str(alias), raw))
        return items

    def _select_channel(self, config: dict[str, Any], channel_alias: str | None) -> tuple[str, dict[str, Any] | None]:
        channels = self._iter_channels(config)
        if channel_alias:
            for alias, raw in channels:
                if alias == channel_alias:
                    return alias, raw
            return channel_alias, None
        return channels[0] if channels else ("", None)

    def _channel_status(self, alias: str, raw: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        channel_type = str(raw.get("type") or "disabled")
        mode = str(raw.get("mode") or "disabled")
        if mode not in {"disabled", "mock", "live"}:
            mode = "disabled"
        enabled = bool(config.get("enabled", False)) and bool(raw.get("enabled", False))
        credentials = self._credential_status(channel_type, raw)
        reason_codes: list[str] = []
        if not bool(config.get("enabled", False)):
            reason_codes.append("NOTIFICATIONS_DISABLED")
        if not bool(raw.get("enabled", False)):
            reason_codes.append("CHANNEL_DISABLED")
        if mode == "disabled":
            reason_codes.append("CHANNEL_MODE_DISABLED")
        if mode == "live" and not credentials["configured"]:
            reason_codes.append("CHANNEL_CREDENTIALS_MISSING")
        return {
            "alias": alias,
            "type": channel_type,
            "enabled": enabled,
            "mode": mode,
            "dry_run": bool(raw.get("dry_run", config.get("default_dry_run", True))),
            "configured": credentials["configured"],
            "credential_fields": credentials["fields"],
            "can_dispatch": enabled and mode == "live" and credentials["configured"],
            "reason_codes": self._merge_reason_codes(reason_codes, []),
            "secrets_redacted": True,
        }

    def _credential_status(self, channel_type: str, raw: dict[str, Any]) -> dict[str, Any]:
        if channel_type == "discord":
            configured = self._env_configured(str(raw.get("webhook_env") or ""))
            return {"configured": configured, "fields": {"webhook_url": configured}}
        if channel_type == "telegram":
            token_configured = self._env_configured(str(raw.get("bot_token_env") or ""))
            chat_configured = self._env_configured(str(raw.get("chat_id_env") or ""))
            return {
                "configured": token_configured and chat_configured,
                "fields": {"bot_token": token_configured, "chat_id": chat_configured},
            }
        return {"configured": False, "fields": {}}

    def _payload_shape(self, raw: dict[str, Any]) -> dict[str, Any]:
        channel_type = str(raw.get("type") or "disabled")
        if channel_type == "discord":
            return {"allowed_mentions_parse": []}
        if channel_type == "telegram":
            parse_mode = raw.get("parse_mode")
            return {"parse_mode": None if parse_mode == "MarkdownV2" else parse_mode}
        return {}

    def _dispatch(self, raw: dict[str, Any], message: str) -> dict[str, Any]:
        channel_type = str(raw.get("type") or "")
        if channel_type == "discord":
            webhook_url = os.getenv(str(raw.get("webhook_env") or ""), "").strip()
            return DiscordWebhookNotifier(raw).send(webhook_url=webhook_url, message=message)
        if channel_type == "telegram":
            token = os.getenv(str(raw.get("bot_token_env") or ""), "").strip()
            chat_id = os.getenv(str(raw.get("chat_id_env") or ""), "").strip()
            return TelegramNotifier(raw).send(bot_token=token, chat_id=chat_id, message=message)
        return {"delivered": False}

    @staticmethod
    def _test_result(
        *,
        status: str,
        channel: dict[str, Any],
        reason_codes: list[str],
        dry_run: bool,
        payload_shape: dict[str, Any],
        message: str,
        delivered: bool = False,
    ) -> dict[str, Any]:
        return {
            "ok": status not in {"failed", "channel_not_found"},
            "status": status,
            "attempted": status == "sent",
            "delivered": delivered,
            "dry_run": dry_run,
            "message_length": len(message),
            "payload_shape": payload_shape,
            "channel": channel,
            "reason_codes": reason_codes,
            "secrets_redacted": True,
        }

    @staticmethod
    def _env_configured(env_name: str) -> bool:
        if not env_name:
            return False
        value = os.getenv(env_name, "").strip()
        return value.lower() not in PLACEHOLDER_VALUES

    @staticmethod
    def _merge_reason_codes(*groups: list[str]) -> list[str]:
        merged: list[str] = []
        for group in groups:
            for code in group:
                if code not in merged:
                    merged.append(code)
        return merged
