from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from backend.app.services.credential_redaction import CredentialRedactionService

HASHKEY_CONFIRMATION_REQUIRED = "KIS_HASHKEY_CONFIRMATION_REQUIRED"
TOKEN_METADATA_REQUIRED = "KIS_TOKEN_METADATA_REQUIRED"
SIGNING_PROVIDER_REQUIRED = "KIS_HASHKEY_PROVIDER_REQUIRED"


class KisRequestSigningError(RuntimeError):
    """KIS request signing prerequisite가 부족할 때 발생한다."""


class KisRequestSigner:
    """KIS hashkey signing을 pluggable fail-closed utility로 제공한다."""

    def __init__(
        self,
        *,
        hashkey_confirmed: bool = False,
        hashkey_provider: Callable[[Mapping[str, Any]], str] | None = None,
        redaction_service: CredentialRedactionService | None = None,
    ) -> None:
        self.hashkey_confirmed = hashkey_confirmed
        self.hashkey_provider = hashkey_provider
        self.redaction_service = redaction_service or CredentialRedactionService()

    def status(self) -> dict[str, object]:
        return {
            "hashkey_confirmed": self.hashkey_confirmed,
            "hashkey_provider_configured": self.hashkey_provider is not None,
            "signing_enabled": self.hashkey_confirmed and self.hashkey_provider is not None,
            "network_call_performed": False,
            "fail_closed": True,
            "reason": None if self.hashkey_confirmed else HASHKEY_CONFIRMATION_REQUIRED,
        }

    def sign_order_request(
        self,
        payload: Mapping[str, Any],
        *,
        token_metadata: Mapping[str, Any],
    ) -> dict[str, object]:
        if not self.hashkey_confirmed:
            raise KisRequestSigningError(HASHKEY_CONFIRMATION_REQUIRED)
        if not bool(token_metadata.get("token_issued")):
            raise KisRequestSigningError(TOKEN_METADATA_REQUIRED)
        if self.hashkey_provider is None:
            raise KisRequestSigningError(SIGNING_PROVIDER_REQUIRED)

        sanitized_payload = self.redaction_service.remove_sensitive(dict(payload))
        hashkey = self.hashkey_provider(sanitized_payload)
        return {
            "signed": True,
            "headers": {"hashkey": hashkey},
            "payload_metadata": {
                "field_count": len(sanitized_payload),
                "sensitive_fields_removed": len(payload) - len(sanitized_payload),
            },
            "network_call_performed": False,
        }

    def require_submit_prerequisites(self, *, token_metadata: Mapping[str, Any]) -> None:
        if not self.hashkey_confirmed:
            raise KisRequestSigningError(HASHKEY_CONFIRMATION_REQUIRED)
        if not bool(token_metadata.get("token_issued")):
            raise KisRequestSigningError(TOKEN_METADATA_REQUIRED)
        if self.hashkey_provider is None:
            raise KisRequestSigningError(SIGNING_PROVIDER_REQUIRED)
