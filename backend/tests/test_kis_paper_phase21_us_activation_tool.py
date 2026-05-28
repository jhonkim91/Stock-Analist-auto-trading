from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from tools import kis_paper_phase21_us_activation as phase21
from tools import kis_paper_phase12c_dry_run as phase12c

US_REGULAR_SESSION = datetime(2026, 5, 28, 10, 0, tzinfo=ZoneInfo("America/New_York"))
US_PREMARKET_SESSION = datetime(2026, 5, 28, 5, 0, tzinfo=ZoneInfo("America/New_York"))


class _FakeTokenManager:
    def issue_paper_access_token(self, *, confirm: bool = False, install_to_process_env: bool = False) -> dict[str, Any]:
        raw_token = "RAW_" + "TOKEN_SHOULD_NOT_LEAK"
        return {
            "ok": confirm,
            "status": "token_issued" if confirm else "token_issue_blocked",
            "token_issued": confirm,
            "access_token": raw_token,
            "network_call_performed": confirm,
            "reason_codes": [] if confirm else ["KIS_TOKEN_CONFIRM_REQUIRED"],
        }


class _FakeWebSocketService:
    def issue_approval_key(self, *, confirm: bool = False, install_to_process_env: bool = False) -> dict[str, Any]:
        raw_approval = "RAW_" + "APPROVAL_SHOULD_NOT_LEAK"
        return {
            "ok": confirm,
            "status": "websocket_approval_issued" if confirm else "websocket_approval_blocked",
            "approval_key": raw_approval,
            "network_call_performed": confirm,
            "reason_codes": [] if confirm else ["KIS_WEBSOCKET_APPROVAL_CONFIRM_REQUIRED"],
        }

    def subscription_preview(
        self,
        *,
        symbol: str,
        kind: str = "quote",
        market: str = "KR",
        exchange: str | None = None,
        subscribe: bool = True,
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "status": "subscription_preview",
            "tr_id": "HDFSCNT0",
            "market": market,
            "exchange": exchange,
            "network_call_performed": False,
        }

    def bounded_connect_smoke(
        self,
        *,
        symbol: str,
        kind: str = "quote",
        market: str = "KR",
        exchange: str | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        raw_approval = "RAW_" + "APPROVAL_SHOULD_NOT_LEAK"
        return {
            "ok": confirm,
            "status": "websocket_message_received" if confirm else "websocket_connect_blocked",
            "message_received": confirm,
            "approval_key": raw_approval,
            "network_call_performed": confirm,
            "reason_codes": [] if confirm else ["KIS_WEBSOCKET_CONNECT_CONFIRM_REQUIRED"],
        }


class _FakePhase21Adapter:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def submit_order(self, request) -> dict[str, Any]:
        if self.config["kill_switch_enabled"]:
            return {
                "ok": False,
                "status": "submit_blocked",
                "reason_codes": ["KILL_SWITCH_ACTIVE"],
                "network_call_performed": False,
            }
        return {
            "ok": True,
            "status": "submitted",
            "broker_order_id": "OVRS|900001|1|145.25|00|NASD|AAPL",
            "network_call_performed": True,
            "live_order_created": False,
            "broker_trace": {"endpoint_path": "/uapi/overseas-stock/v1/trading/order", "tr_id": "VTTT1002U"},
        }

    def list_orders(self, *, status: str | None = None) -> dict[str, Any]:
        return {
            "ok": True,
            "status": "query_ok",
            "orders": [{"broker_order_id": "OVRS|900001|1|145.25|00|NASD|AAPL", "symbol": "AAPL"}],
            "fills": [],
            "network_call_performed": True,
        }

    def sync(self, *, scope: str = "all") -> dict[str, Any]:
        return {
            "ok": True,
            "status": "sync_ok",
            "orders": [{"broker_order_id": "OVRS|900001|1|145.25|00|NASD|AAPL"}],
            "fills": [{"broker_fill_id": "RAW_FILL_ID_SHOULD_HASH"}],
            "positions": [{"symbol": "AAPL", "qty": 1}],
            "portfolio": {"total_equity": 1000},
            "network_call_performed": True,
        }

    def cancel_order(self, *, broker_order_id: str, confirm: bool = False) -> dict[str, Any]:
        return {"ok": True, "status": "cancelled", "broker_order_id": broker_order_id, "network_call_performed": True}


def _ready_env() -> dict[str, str]:
    return {
        "KIS_APP_KEY": "TESTVALUE123456",
        "KIS_APP_SECRET": "TESTVALUE123456",
        "KIS_ACCESS_TOKEN": "TESTVALUE123456",
        "KIS_ACCOUNT_NO": "12345678",
        "KIS_PRODUCT_CODE": "01",
        "KIS_PAPER_BASE_URL": "https://openapivts.koreainvestment.com:29443",
        "KIS_ENV": "paper",
        "BROKER_MODE": "paper_kis",
        "ENABLE_REAL_ORDER": "false",
        "PAPER_BOT_AUTO_SUBMIT": "false",
        "PAPER_ORDER_SUBMIT_ENABLED": "true",
        "PAPER_TRADING_ENABLED": "true",
        "PAPER_TRADING_CAN_CREATE": "true",
        "PAPER_TRADING_NETWORK_ENABLED": "true",
        "PAPER_TRADING_KILL_SWITCH": "false",
        "PAPER_BOT_CONFIRM": "true",
    }


def test_phase21_us_activation_default_is_preview_only_and_secret_free() -> None:
    record = phase21.run_phase21_us_activation(
        websocket_service_factory=_FakeWebSocketService,
    )

    assert record["status"] == "completed"
    assert record["network_call_performed"] is False
    assert [step["name"] for step in record["steps"]] == ["websocket_us_subscription_preview"]


def test_phase21_us_activation_full_mock_lifecycle_redacts_and_uses_confirmations() -> None:
    record = phase21.run_phase21_us_activation(
        symbol="AAPL",
        qty=1,
        limit_price=145.25,
        issue_token=True,
        issue_websocket_approval=True,
        websocket_smoke=True,
        execute_submit=True,
        confirm_token=phase21.PHASE21_TOKEN_CONFIRMATION_TOKEN,
        confirm_websocket=phase21.PHASE21_WEBSOCKET_CONFIRMATION_TOKEN,
        confirm_submit=phase12c.CONFIRMATION_TOKEN,
        confirm_cancel=phase12c.CONFIRMATION_TOKEN,
        confirm_trading_window=phase12c.TRADING_WINDOW_CONFIRMATION_TOKEN,
        as_of=US_REGULAR_SESSION,
        env=_ready_env(),
        token_manager_factory=_FakeTokenManager,
        websocket_service_factory=_FakeWebSocketService,
        adapter_factory=lambda config: _FakePhase21Adapter(config),
    )
    serialized = json.dumps(record, sort_keys=True)

    assert record["status"] == "completed"
    assert [step["name"] for step in record["steps"]] == [
        "issue_token",
        "issue_websocket_approval",
        "websocket_us_subscription_preview",
        "websocket_us_bounded_smoke",
        "controlled_us_submit_list_sync_cancel",
    ]
    assert "RAW_" + "TOKEN_SHOULD_NOT_LEAK" not in serialized
    assert "RAW_" + "APPROVAL_SHOULD_NOT_LEAK" not in serialized
    assert "OVRS|900001" not in serialized
    assert "RAW_FILL_ID_SHOULD_HASH" not in serialized
    assert "sha256:" in serialized


def test_phase21_us_activation_stops_submit_outside_us_regular_session() -> None:
    record = phase21.run_phase21_us_activation(
        symbol="AAPL",
        qty=1,
        limit_price=145.25,
        execute_submit=True,
        confirm_submit=phase12c.CONFIRMATION_TOKEN,
        confirm_cancel=phase12c.CONFIRMATION_TOKEN,
        confirm_trading_window=phase12c.TRADING_WINDOW_CONFIRMATION_TOKEN,
        as_of=US_PREMARKET_SESSION,
        env=_ready_env(),
        websocket_service_factory=_FakeWebSocketService,
        adapter_factory=lambda config: (_ for _ in ()).throw(AssertionError("adapter must not run")),
    )

    assert record["status"] == "submit_lifecycle_incomplete"
    assert record["network_call_performed"] is False
    assert "US_REGULAR_SESSION_REQUIRED" in record["reason_codes"]
    controlled_step = record["steps"][-1]["result"]
    assert controlled_step["status"] == "trading_window_closed"
    assert controlled_step["steps"] == []


def test_phase21_us_activation_stops_before_submit_when_token_confirm_missing() -> None:
    record = phase21.run_phase21_us_activation(
        issue_token=True,
        execute_submit=True,
        token_manager_factory=_FakeTokenManager,
        websocket_service_factory=_FakeWebSocketService,
        adapter_factory=lambda config: (_ for _ in ()).throw(AssertionError("adapter must not run")),
    )

    assert record["status"] == "token_failed"
    assert record["network_call_performed"] is False
    assert "KIS_TOKEN_CONFIRM_REQUIRED" in record["reason_codes"]
