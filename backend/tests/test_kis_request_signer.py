from __future__ import annotations

import pytest

from backend.app.services.kis_request_signer import (
    HASHKEY_CONFIRMATION_REQUIRED,
    SIGNING_PROVIDER_REQUIRED,
    TOKEN_METADATA_REQUIRED,
    KisRequestSigner,
    KisRequestSigningError,
)


def test_request_signer_defaults_to_fail_closed_without_provider_call():
    calls: list[dict[str, object]] = []
    signer = KisRequestSigner(hashkey_provider=lambda payload: calls.append(dict(payload)) or "HASH")

    assert signer.status()["signing_enabled"] is False
    assert signer.status()["reason"] == HASHKEY_CONFIRMATION_REQUIRED

    with pytest.raises(KisRequestSigningError, match=HASHKEY_CONFIRMATION_REQUIRED):
        signer.sign_order_request({"PDNO": "005930"}, token_metadata={"token_issued": True})
    assert calls == []


def test_request_signer_rejects_missing_token_metadata():
    signer = KisRequestSigner(hashkey_confirmed=True, hashkey_provider=lambda payload: "HASH")

    with pytest.raises(KisRequestSigningError, match=TOKEN_METADATA_REQUIRED):
        signer.require_submit_prerequisites(token_metadata={"token_issued": False})


def test_request_signer_rejects_missing_hashkey_provider():
    signer = KisRequestSigner(hashkey_confirmed=True)

    with pytest.raises(KisRequestSigningError, match=SIGNING_PROVIDER_REQUIRED):
        signer.require_submit_prerequisites(token_metadata={"token_issued": True})


def test_request_signer_sanitizes_payload_before_pluggable_hashkey_provider():
    captured: list[dict[str, object]] = []

    def provider(payload):
        captured.append(dict(payload))
        return "SAFE_HASH_VALUE"

    signer = KisRequestSigner(hashkey_confirmed=True, hashkey_provider=provider)
    result = signer.sign_order_request(
        {"PDNO": "005930", "CANO": "12345678", "ORD_QTY": "1"},
        token_metadata={"token_issued": True},
    )

    assert result["signed"] is True
    assert result["headers"]["hashkey"] == "SAFE_HASH_VALUE"
    assert result["network_call_performed"] is False
    assert captured == [{"PDNO": "005930", "ORD_QTY": "1"}]
