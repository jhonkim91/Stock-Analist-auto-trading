from __future__ import annotations

import base64
import json
from datetime import UTC, datetime

from tools.token_diagnostics import build_access_token_diagnostics


def test_access_token_diagnostics_reports_jwt_expiry_without_raw_token() -> None:
    token = _fake_jwt({"exp": 1_700_000_000})

    diagnostics = build_access_token_diagnostics(
        token,
        now=datetime.fromtimestamp(1_800_000_000, tz=UTC),
    )
    serialized = json.dumps(diagnostics, ensure_ascii=False, sort_keys=True)

    assert diagnostics["access_token_present"] is True
    assert diagnostics["access_token_jwt_like"] is True
    assert diagnostics["access_token_payload_decoded"] is True
    assert diagnostics["access_token_exp_present"] is True
    assert diagnostics["access_token_expired"] is True
    assert diagnostics["access_token_expires_at"] == "2023-11-14T22:13:20+00:00"
    assert token not in serialized


def test_access_token_diagnostics_handles_non_jwt_token_without_values() -> None:
    diagnostics = build_access_token_diagnostics("opaque-token-value")
    serialized = json.dumps(diagnostics, ensure_ascii=False, sort_keys=True)

    assert diagnostics["access_token_present"] is True
    assert diagnostics["access_token_jwt_like"] is False
    assert diagnostics["access_token_payload_decoded"] is False
    assert diagnostics["access_token_exp_present"] is False
    assert diagnostics["access_token_expired"] is None
    assert "opaque-token-value" not in serialized


def _fake_jwt(payload: dict[str, object]) -> str:
    header = {"typ": "JWT", "alg": "none"}
    return ".".join([_b64_json(header), _b64_json(payload), "signature"])


def _b64_json(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
