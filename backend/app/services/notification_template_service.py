from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from backend.app.services.credential_redaction import CredentialRedactionService

DEFAULT_NOTIFICATION_TEMPLATES: dict[str, str] = {
    "default": "[Stock Analyst]\nevent: {event_type}\nsubject: {subject}\nsummary: {summary}",
    "bot_started": "[Paper Bot Started]\nsubject: {subject}\nmode: {mode}\nstatus: {status}",
    "bot_stopped": "[Paper Bot Stopped]\nsubject: {subject}\nreason: {reason}",
    "order_signal_created": "[Order Signal]\nsymbol: {symbol}\nside: {side}\nqty: {qty}\nstrategy: {strategy_tag}",
    "paper_order_previewed": "[Paper Order Preview]\nsymbol: {symbol}\nside: {side}\nqty: {qty}\nstatus: {status}",
    "paper_order_submitted": "[Paper Order Submitted]\nsymbol: {symbol}\nside: {side}\nqty: {qty}\nstatus: {status}",
    "paper_order_rejected": "[Paper Order Rejected]\nsymbol: {symbol}\nreason: {reason}\nstatus: {status}",
    "paper_order_filled": "[Paper Fill]\nsymbol: {symbol}\nside: {side}\nqty: {qty}\nprice: {price}",
    "paper_order_cancelled": "[Paper Order Cancelled]\nsymbol: {symbol}\nreason: {reason}\nstatus: {status}",
    "portfolio_snapshot": "[Portfolio Snapshot]\ntotal_equity: {total_equity}\npositions_count: {positions_count}",
    "daily_report_generated": "[Daily Report]\nreport_id: {report_id}\nstatus: {status}",
    "weekly_report_generated": "[Weekly Report]\nreport_id: {report_id}\nstatus: {status}",
    "daily_report_automation_completed": "[Daily Report Automation]\nreport_id: {report_id}\nstatus: {status}",
    "weekly_report_automation_completed": "[Weekly Report Automation]\nreport_id: {report_id}\nstatus: {status}",
    "report_automation_failed": "[Report Automation Failed]\nsubject: {subject}\nreport_type: {report_type}\nreason: {reason}",
    "risk_limit_warning": "[Risk Warning]\nsubject: {subject}\nreason: {reason}",
    "kis_token_error": "[KIS Token Error]\nsubject: {subject}\nreason: {reason}",
    "broker_error": "[Broker Error]\nsubject: {subject}\nreason: {reason}",
    "kill_switch_triggered": "[Kill Switch]\nsubject: {subject}\nreason: {reason}",
}


class _TemplateValues(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "not_available"


class NotificationTemplateService:
    """Notification event payload를 secret-safe plain text 메시지로 렌더링한다."""

    def __init__(self, templates: Mapping[str, Any] | None = None) -> None:
        self.templates = self._normalize_templates(templates)
        self.redactor = CredentialRedactionService()

    def render(
        self,
        *,
        event_type: str,
        subject: str | None = None,
        payload_summary: Mapping[str, Any] | None = None,
    ) -> str:
        """event type별 템플릿을 적용하고 누락 값은 fail-closed 표시값으로 대체한다."""
        safe_payload = self.redactor.remove_sensitive(dict(payload_summary or {}))
        if not isinstance(safe_payload, dict):
            safe_payload = {}
        values = _TemplateValues({key: self._safe_scalar(value) for key, value in safe_payload.items()})
        values.update(
            {
                "event_type": self._safe_text(event_type),
                "subject": self._safe_text(subject) if subject else "not_available",
                "summary": self._summary(safe_payload),
            }
        )
        template = self.templates.get(event_type) or self.templates.get("default") or DEFAULT_NOTIFICATION_TEMPLATES["default"]
        try:
            rendered = template.format_map(values)
        except (IndexError, KeyError, ValueError):
            rendered = DEFAULT_NOTIFICATION_TEMPLATES["default"].format_map(values)
        return self._safe_text(rendered).strip()

    @staticmethod
    def _normalize_templates(templates: Mapping[str, Any] | None) -> dict[str, str]:
        normalized = dict(DEFAULT_NOTIFICATION_TEMPLATES)
        if not isinstance(templates, Mapping):
            return normalized
        for event_type, template in templates.items():
            if isinstance(template, str) and template.strip():
                normalized[str(event_type)] = template.strip()
        return normalized

    def _summary(self, payload: Mapping[str, Any]) -> str:
        if not payload:
            return "not_available"
        return self._safe_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))

    def _safe_scalar(self, value: Any) -> str:
        if value is None:
            return "not_available"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int | float | str):
            return self._safe_text(str(value))
        return self._safe_text(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))

    @staticmethod
    def _safe_text(value: Any) -> str:
        text = str(value)
        patterns = [
            r"https://discord\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+",
            r"\b[0-9]{8,10}:[A-Za-z0-9_-]{20,}\b",
            r"(?i)(access_token|refresh_token|app_secret|app_key|account_no|account_number|cano|chat_id|webhook_url|authorization)\s*[:=]\s*[^ \n]+",
        ]
        for pattern in patterns:
            text = re.sub(pattern, "[REDACTED]", text)
        return text
