from __future__ import annotations

from typing import Any

from backend.app.services.credential_redaction import CredentialRedactionService


def paper_only_execution_response(payload: dict[str, Any], *, operation: str) -> dict[str, Any]:
    """paper submit/cancel API 응답에 paper-only 실행 표식을 추가한다."""
    redactor = CredentialRedactionService()
    broker_trace = redactor.redact(
        {
            "operation": operation,
            "adapter": "kis_paper",
            "paper_only": True,
            "live_fallback_enabled": False,
            "live_order_created": payload.get("live_order_created", False),
            "broker_order_created": payload.get("broker_order_created", False),
            "network_call_performed": payload.get("network_call_performed", False),
            "reason_codes": payload.get("reason_codes", []),
        }
    )
    return {
        **payload,
        "paper_only": True,
        "execution_mode": "paper",
        "live_fallback_enabled": False,
        "broker_trace": broker_trace,
    }
