from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class BrokerCapabilityError(RuntimeError):
    """공식 문서 확인 전 broker capability 실행을 막는 예외다."""


class BrokerDisabledError(RuntimeError):
    """비활성 broker adapter 호출을 막는 예외다."""


@dataclass(frozen=True)
class BrokerOrderRequest:
    symbol: str
    side: str
    qty: int
    limit_price: float | None = None
    stop_price: float | None = None
    idempotency_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BrokerAdapter(ABC):
    """paper/live broker adapter가 따라야 하는 최소 주문 contract다."""

    name: str
    mode: str

    @abstractmethod
    def status(self) -> dict[str, Any]:
        """adapter 상태를 secret 없이 반환한다."""

    @abstractmethod
    def preview_order(self, request: BrokerOrderRequest) -> dict[str, Any]:
        """주문 preview contract를 수행한다."""

    @abstractmethod
    def submit_order(self, request: BrokerOrderRequest) -> dict[str, Any]:
        """주문 submit contract를 수행한다."""

    @abstractmethod
    def cancel_order(self, *, broker_order_id: str, confirm: bool = False) -> dict[str, Any]:
        """주문 cancel contract를 수행한다."""

    @abstractmethod
    def list_orders(self, *, status: str | None = None) -> dict[str, Any]:
        """주문 목록 조회 contract를 수행한다."""

    @abstractmethod
    def sync(self, *, scope: str = "all") -> dict[str, Any]:
        """외부 broker 상태 sync contract를 수행한다."""
