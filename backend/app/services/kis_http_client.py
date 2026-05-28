from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx

from backend.app.services.credential_redaction import CredentialRedactionService

KIS_HTTP_RATE_LIMITED = "KIS_HTTP_RATE_LIMITED"
KIS_HTTP_TIMEOUT = "KIS_HTTP_TIMEOUT"
KIS_HTTP_TRANSPORT_ERROR = "KIS_HTTP_TRANSPORT_ERROR"
KIS_HTTP_RESPONSE_ERROR = "KIS_HTTP_RESPONSE_ERROR"


@dataclass(frozen=True)
class KisHttpResult:
    """KIS HTTP 호출 결과를 raw secret 없이 운반한다."""

    ok: bool
    status_code: int | None
    body: dict[str, Any]
    reason: str | None
    trace: dict[str, Any]


class KisHttpClient:
    """KIS REST 호출에 timeout/retry/error mapping/redaction을 적용하는 공통 client다."""

    def __init__(
        self,
        *,
        http_client: Any | None = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 0,
        redaction_service: CredentialRedactionService | None = None,
    ) -> None:
        self.http_client = http_client
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.redactor = redaction_service or CredentialRedactionService()

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        retry_enabled: bool | None = None,
        operation: str = "kis_http_request",
        tr_id: str | None = None,
        redact_body: bool = True,
        correlation_prefix: str = "kis-http",
    ) -> KisHttpResult:
        """KIS HTTP 요청을 실행하고 domain-safe 결과로 변환한다."""
        method_name = method.upper()
        close_client = self.http_client is None
        client = self.http_client or httpx.Client(timeout=self.timeout_seconds)
        attempts = 1 + (self.max_retries if (retry_enabled if retry_enabled is not None else method_name == "GET") else 0)
        started = time.perf_counter()
        correlation_id = f"{correlation_prefix}-{uuid4().hex[:16]}"
        status_code: int | None = None
        last_reason = KIS_HTTP_TRANSPORT_ERROR
        try:
            for attempt in range(attempts):
                try:
                    response = self._send(
                        client,
                        method_name,
                        url,
                        headers=headers or {},
                        json_body=json_body or {},
                        params=params or {},
                    )
                    status_code = int(response.status_code)
                    trace = self._trace(
                        operation=operation,
                        method=method_name,
                        url=url,
                        tr_id=tr_id,
                        status_code=status_code,
                        started=started,
                        correlation_id=correlation_id,
                        retry_count=attempt,
                    )
                    if status_code == 429:
                        return KisHttpResult(False, status_code, {}, KIS_HTTP_RATE_LIMITED, trace)
                    if status_code >= 500 and attempt + 1 < attempts:
                        last_reason = KIS_HTTP_TRANSPORT_ERROR
                        continue
                    if status_code >= 400:
                        return KisHttpResult(False, status_code, {}, KIS_HTTP_RESPONSE_ERROR, trace)
                    body = response.json()
                    if not isinstance(body, dict):
                        return KisHttpResult(False, status_code, {}, KIS_HTTP_RESPONSE_ERROR, trace)
                    mapped_body = self.redactor.redact(body) if redact_body else body
                    return KisHttpResult(True, status_code, mapped_body, None, trace)
                except httpx.TimeoutException:
                    last_reason = KIS_HTTP_TIMEOUT
                    if attempt + 1 >= attempts:
                        break
                except httpx.TransportError:
                    last_reason = KIS_HTTP_TRANSPORT_ERROR
                    if attempt + 1 >= attempts:
                        break
        finally:
            if close_client:
                client.close()
        return KisHttpResult(
            False,
            status_code,
            {},
            last_reason,
            self._trace(
                operation=operation,
                method=method_name,
                url=url,
                tr_id=tr_id,
                status_code=status_code,
                started=started,
                correlation_id=correlation_id,
                retry_count=attempts - 1,
            ),
        )

    def _send(
        self,
        client: Any,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json_body: dict[str, Any],
        params: dict[str, Any],
    ) -> Any:
        if method == "POST":
            return client.post(url, headers=headers, json=json_body, timeout=self.timeout_seconds)
        return client.get(url, headers=headers, params=params, timeout=self.timeout_seconds)

    def _trace(
        self,
        *,
        operation: str,
        method: str,
        url: str,
        tr_id: str | None,
        status_code: int | None,
        started: float,
        correlation_id: str,
        retry_count: int,
    ) -> dict[str, Any]:
        return self.redactor.redact(
            {
                "operation": operation,
                "method": method,
                "host": httpx.URL(url).host,
                "path": httpx.URL(url).path,
                "endpoint_path": httpx.URL(url).path,
                "tr_id": tr_id,
                "status_code": status_code,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                "correlation_id": correlation_id,
                "retry_count": retry_count,
                "network_call_performed": status_code is not None,
                "secrets_redacted": True,
            }
        )
