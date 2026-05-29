from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import Any


def build_access_token_diagnostics(token: object, *, now: datetime | None = None) -> dict[str, Any]:
    """Access token JWT metadata를 raw token 없이 진단한다."""
    current_time = now or datetime.now(UTC)
    configured = _configured(token)
    diagnostics: dict[str, Any] = {
        "access_token_present": configured,
        "access_token_jwt_like": False,
        "access_token_payload_decoded": False,
        "access_token_exp_present": False,
        "access_token_expired": None,
        "access_token_expires_at": None,
        "access_token_seconds_until_expiry": None,
        "values_redacted": True,
    }
    if not configured:
        return diagnostics

    parts = str(token).strip().split(".")
    diagnostics["access_token_jwt_like"] = len(parts) == 3
    if len(parts) != 3:
        return diagnostics

    try:
        payload_raw = _urlsafe_b64decode(parts[1])
        payload = json.loads(payload_raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return diagnostics
    if not isinstance(payload, dict):
        return diagnostics

    diagnostics["access_token_payload_decoded"] = True
    exp = _numeric_date(payload.get("exp"))
    if exp is None:
        return diagnostics

    expires_at = datetime.fromtimestamp(exp, tz=UTC)
    seconds_until_expiry = int((expires_at - current_time).total_seconds())
    diagnostics.update(
        {
            "access_token_exp_present": True,
            "access_token_expired": seconds_until_expiry <= 0,
            "access_token_expires_at": expires_at.isoformat(),
            "access_token_seconds_until_expiry": seconds_until_expiry,
        }
    )
    return diagnostics


def _urlsafe_b64decode(value: str) -> bytes:
    padded = value + ("=" * (-len(value) % 4))
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _numeric_date(value: object) -> int | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        parsed = int(float(str(value)))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _configured(value: object) -> bool:
    stripped = str(value or "").strip()
    return bool(stripped and "placeholder" not in stripped.lower())
