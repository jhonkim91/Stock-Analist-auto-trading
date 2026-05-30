from __future__ import annotations

from datetime import datetime
from textwrap import dedent

from sqlalchemy import select

from backend.app.models.schemas import (
    BrokerPreviewRequest,
    OrderGovernanceFields,
    PaperOrderCancelRequest,
    PaperOrderSubmitRequest,
)
from backend.app.models.tables import PaperAuditEvent
from backend.app.services.paper_order_service import PaperOrderService


def _write_paper_config(tmp_path) -> None:
    tmp_path.joinpath("paper.yaml").write_text(
        dedent(
            """
            paper:
              mode: "safety_scaffold"
              enabled: true
              can_create: true
              can_simulate_fills: false
              preview_only: false
              kill_switch_enabled: false
              network_enabled: false
              live_order_enabled: false
              broker_order_enabled: false
            risk_gate:
              allow_buy_preview: true
              allow_sell_preview: true
              allow_short_sell: false
              max_order_qty: 1000000
              max_order_notional: 100000000
            audit:
              persistence_enabled: true
              sanitize_enabled: true
            simulator:
              enabled: false
              auto_fill_on_create: false
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _enable_manual_paper_runtime(monkeypatch) -> None:
    monkeypatch.setenv("KIS_ENV", "paper")
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRADING_CAN_CREATE", "true")
    monkeypatch.setenv("PAPER_TRADING_KILL_SWITCH", "false")
    monkeypatch.setenv("PAPER_BOT_CONFIRM", "true")
    monkeypatch.delenv("PAPER_TRADING_NETWORK_ENABLED", raising=False)


def test_order_request_schemas_accept_optional_governance_fields_and_default_none() -> None:
    """주문성 스키마는 필드를 생략해도 동작하고 모두 None 기본값을 가진다(하위호환)."""
    submit = PaperOrderSubmitRequest(symbol="KR009", qty=1)
    assert submit.request_id is None
    assert submit.command_source is None
    assert submit.client_ts is None

    enriched = PaperOrderSubmitRequest(
        symbol="KR009",
        qty=1,
        request_id="req-1",
        command_source="telegram",
        client_ts="2026-05-30T00:00:00Z",
    )
    assert enriched.request_id == "req-1"
    assert enriched.command_source == "telegram"
    assert isinstance(enriched.client_ts, datetime)

    assert BrokerPreviewRequest(symbol="KR009", qty=1).command_source is None
    assert PaperOrderCancelRequest().command_source is None
    assert issubclass(PaperOrderSubmitRequest, OrderGovernanceFields)


def test_paper_submit_persists_command_source_into_audit_event(db_session, tmp_path, monkeypatch) -> None:
    """성공한 paper submit은 정규화된 command_source를 audit event에 남긴다."""
    _enable_manual_paper_runtime(monkeypatch)
    _write_paper_config(tmp_path)
    service = PaperOrderService(db_session, config_dir=tmp_path)
    result = service.submit_order(
        symbol="KR009",
        side="buy",
        qty=1,
        confirm=True,
        idempotency_key="idem-gov-1",
        limit_price=100.0,
        command_source="Telegram",
    )
    assert result["status"] == "submitted"
    events = db_session.scalars(
        select(PaperAuditEvent).where(PaperAuditEvent.event_type == "paper_order_submit")
    ).all()
    assert events
    assert all(event.command_source == "telegram" for event in events)


def test_paper_submit_command_source_defaults_to_none_when_absent(db_session, tmp_path, monkeypatch) -> None:
    """command_source를 주지 않으면 audit event에 None으로 기록된다."""
    _enable_manual_paper_runtime(monkeypatch)
    _write_paper_config(tmp_path)
    service = PaperOrderService(db_session, config_dir=tmp_path)
    result = service.submit_order(
        symbol="KR009",
        side="buy",
        qty=1,
        confirm=True,
        idempotency_key="idem-gov-2",
        limit_price=100.0,
    )
    assert result["status"] == "submitted"
    event = db_session.scalars(
        select(PaperAuditEvent).where(PaperAuditEvent.event_type == "paper_order_submit")
    ).first()
    assert event is not None
    assert event.command_source is None


def test_normalize_command_source_trims_and_lowercases() -> None:
    norm = PaperOrderService._normalize_command_source
    assert norm(None) is None
    assert norm("") is None
    assert norm("   ") is None
    assert norm("  Telegram  ") == "telegram"
    assert norm("X" * 50) == "x" * 32
