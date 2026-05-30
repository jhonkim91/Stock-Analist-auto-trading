from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from backend.app.repositories.paper_repository import PaperRepository
from tools import kis_paper_phase21_us_activation as phase21
from tools import kis_paper_phase12c_dry_run as phase12c

US_REGULAR_SESSION = datetime(2026, 5, 28, 10, 0, tzinfo=ZoneInfo("America/New_York"))
US_PREMARKET_SESSION = datetime(2026, 5, 28, 5, 0, tzinfo=ZoneInfo("America/New_York"))
US_CLOSED_SESSION = datetime(2026, 5, 28, 3, 30, tzinfo=ZoneInfo("America/New_York"))


class _FakeHttpResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self.payload


class _FakePriceHttpClient:
    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self.payload = payload or {"rt_cd": "0", "output": {"last": "310.915"}}
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, *, headers=None, params=None, timeout=None):
        self.calls.append({"url": url, "headers": headers or {}, "params": params or {}, "timeout": timeout})
        return _FakeHttpResponse(self.payload)


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


class _FakeServiceSubmitAdapter:
    broker_order_id = "OVRS|900002|1|145.25|00|NASD|AAPL"

    def submit_order(self, request) -> dict[str, Any]:
        return {
            "ok": True,
            "status": "submitted",
            "broker_order_id": self.broker_order_id,
            "broker_order_status": "submitted",
            "network_call_performed": True,
            "broker_trace": {
                "endpoint_path": "/uapi/overseas-stock/v1/trading/order",
                "tr_id": "VTTT1002U",
                "secrets_redacted": True,
            },
            "order": {
                "symbol": request.symbol,
                "side": request.side,
                "qty": request.qty,
                "filled_qty": 0,
                "remaining_qty": request.qty,
                "status": "submitted",
                "market": request.metadata.get("market"),
                "venue": request.metadata.get("venue"),
            },
        }


class _FakeServiceSyncAdapter:
    def sync(self, *, scope: str = "all") -> dict[str, Any]:
        broker_order_id = _FakeServiceSubmitAdapter.broker_order_id
        return {
            "ok": True,
            "status": "sync_ok",
            "scope": scope,
            "sync_performed": True,
            "network_call_performed": True,
            "orders": [
                {
                    "broker_order_id": broker_order_id,
                    "symbol": "AAPL",
                    "side": "buy",
                    "qty": 1,
                    "filled_qty": 1,
                    "remaining_qty": 0,
                    "limit_price": 145.25,
                    "status": "filled",
                    "broker_order_status": "filled",
                }
            ],
            "fills": [
                {
                    "broker_fill_id": f"{broker_order_id}|fill|1",
                    "broker_order_id": broker_order_id,
                    "symbol": "AAPL",
                    "side": "buy",
                    "qty": 1,
                    "price": 145.25,
                }
            ],
            "positions": [
                {
                    "symbol": "AAPL",
                    "qty": 1,
                    "avg_price": 145.25,
                    "last_price": 146.0,
                    "market_value": 146.0,
                    "unrealized_pnl": 0.75,
                    "broker_position_key": "kis_paper_us|AAPL",
                }
            ],
            "portfolio": {
                "snapshot_id": "phase21-activation-service-lifecycle",
                "cash_balance": 1000.0,
                "buying_power": 854.75,
                "market_value": 146.0,
                "total_equity": 1000.75,
                "unrealized_pnl": 0.75,
                "realized_pnl": 0.0,
                "status": "synced",
            },
            "broker_trace": {
                "operation": "sync",
                "endpoint_path": "/uapi/overseas-stock/v1/trading/inquire-ccnl",
                "tr_id": "VTTS3035R",
                "secrets_redacted": True,
            },
        }


class _FailSubmitAdapter:
    def submit_order(self, request) -> dict[str, Any]:
        raise AssertionError("submit adapter must not run")


class _FailSyncAdapter:
    def sync(self, *, scope: str = "all") -> dict[str, Any]:
        raise AssertionError("sync adapter must not run")


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


def _apply_ready_env(monkeypatch) -> None:
    for key, value in _ready_env().items():
        monkeypatch.setenv(key, value)


def test_phase21_us_activation_default_is_preview_only_and_secret_free() -> None:
    record = phase21.run_phase21_us_activation(
        websocket_service_factory=_FakeWebSocketService,
    )

    assert record["status"] == "completed"
    assert record["network_call_performed"] is False
    assert [step["name"] for step in record["steps"]] == ["websocket_us_subscription_preview"]
    assert record["completion_audit"]["complete"] is False
    assert "token_issued" in record["completion_audit"]["missing_requirements"]
    assert "service_lifecycle_completed" in record["completion_audit"]["missing_requirements"]


def test_phase21_env_file_loader_is_allowlisted_and_secret_free(tmp_path) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "KIS_ENV=paper",
                "KIS_APP_" + "KEY=ENV_FILE_VALUE_A",
                "KIS_APP_" + "SECRET='ENV_FILE_VALUE_B'",
                'PAPER_TRADING_ENABLED="true"',
                "UNRELATED_" + "SECRET=ENV_FILE_VALUE_C",
            ]
        ),
        encoding="utf-8",
    )
    target = {"KIS_ENV": "existing"}

    result = phase21._load_env_file(env_file, target=target)
    serialized = json.dumps(result, sort_keys=True)

    assert result["ok"] is True
    assert target["KIS_ENV"] == "existing"
    assert target["KIS_APP_KEY"] == "ENV_FILE_VALUE_A"
    assert target["KIS_APP_SECRET"] == "ENV_FILE_VALUE_B"
    assert target["PAPER_TRADING_ENABLED"] == "true"
    assert "UNRELATED_SECRET" not in target
    assert "KIS_ENV" in result["skipped_existing_keys"]
    assert "KIS_APP_KEY" not in result["loaded_keys"]
    assert "KIS_APP_SECRET" not in result["loaded_keys"]
    assert "UNRELATED_SECRET" not in result["ignored_keys"]
    assert result["loaded_secret_like_key_count"] == 2
    assert result["ignored_secret_like_key_count"] == 1
    assert result["secret_like_key_names_redacted"] is True
    assert "ENV_FILE_VALUE_A" not in serialized
    assert "ENV_FILE_VALUE_B" not in serialized
    assert "ENV_FILE_VALUE_C" not in serialized


def test_phase21_env_file_loader_can_override_existing_values(tmp_path) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text("KIS_ENV=paper\n", encoding="utf-8")
    target = {"KIS_ENV": "live"}

    result = phase21._load_env_file(env_file, override=True, target=target)

    assert result["ok"] is True
    assert target["KIS_ENV"] == "paper"
    assert result["loaded_keys"] == ["KIS_ENV"]


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


def test_phase21_us_activation_integrates_service_lifecycle_persistence(
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    _apply_ready_env(monkeypatch)

    record = phase21.run_phase21_us_activation(
        symbol="AAPL",
        qty=1,
        limit_price=145.25,
        issue_token=True,
        issue_websocket_approval=True,
        websocket_smoke=True,
        execute_service_lifecycle=True,
        confirm_token=phase21.PHASE21_TOKEN_CONFIRMATION_TOKEN,
        confirm_websocket=phase21.PHASE21_WEBSOCKET_CONFIRMATION_TOKEN,
        confirm_submit=phase12c.CONFIRMATION_TOKEN,
        confirm_sync=phase12c.CONFIRMATION_TOKEN,
        confirm_cancel=phase12c.CONFIRMATION_TOKEN,
        confirm_trading_window=phase12c.TRADING_WINDOW_CONFIRMATION_TOKEN,
        as_of=US_REGULAR_SESSION,
        token_manager_factory=_FakeTokenManager,
        websocket_service_factory=_FakeWebSocketService,
        session_factory=lambda: db_session,
        config_dir=tmp_path,
        submit_adapter=_FakeServiceSubmitAdapter(),
        sync_adapter=_FakeServiceSyncAdapter(),
    )
    serialized = json.dumps(record, sort_keys=True)
    service_step = record["steps"][-1]["result"]
    evidence = service_step["lifecycle_evidence"]

    assert record["status"] == "completed"
    assert record["network_call_performed"] is True
    assert record["steps"][-1]["name"] == "service_us_submit_sync_cancel"
    assert service_step["status"] == "completed"
    assert evidence["paper_order_created"] is True
    assert evidence["paper_fill_created"] is True
    assert evidence["paper_position_changed"] is True
    assert evidence["orders_count_delta"] == 0
    assert service_step["completion_audit"]["complete"] is True
    assert record["completion_audit"]["complete"] is True
    assert record["completion_audit"]["requirements"]["token_issued"] is True
    assert record["completion_audit"]["requirements"]["websocket_smoke_message_received"] is True
    assert record["completion_audit"]["requirements"]["paper_position_changed"] is True
    assert PaperRepository(db_session).counts()["orders_count"] == 0
    assert "OVRS|900002" not in serialized


def test_phase21_us_activation_derives_limit_price_after_regular_window(
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    _apply_ready_env(monkeypatch)
    price_client = _FakePriceHttpClient()

    record = phase21.run_phase21_us_activation(
        symbol="AAPL",
        qty=1,
        exchange="NASD",
        currency="USD",
        execute_service_lifecycle=True,
        derive_limit_from_price=True,
        limit_premium_bps=300,
        confirm_submit=phase12c.CONFIRMATION_TOKEN,
        confirm_sync=phase12c.CONFIRMATION_TOKEN,
        confirm_cancel=phase12c.CONFIRMATION_TOKEN,
        confirm_trading_window=phase12c.TRADING_WINDOW_CONFIRMATION_TOKEN,
        as_of=US_REGULAR_SESSION,
        websocket_service_factory=_FakeWebSocketService,
        session_factory=lambda: db_session,
        config_dir=tmp_path,
        submit_adapter=_FakeServiceSubmitAdapter(),
        sync_adapter=_FakeServiceSyncAdapter(),
        price_http_client=price_client,
    )
    price_step = next(step["result"] for step in record["steps"] if step["name"] == "derive_limit_from_price")
    service_step = record["steps"][-1]["result"]
    submit_step = service_step["steps"][0]["result"]

    assert record["status"] == "completed"
    assert record["completion_audit"]["complete"] is False
    assert "token_issued" in record["completion_audit"]["missing_requirements"]
    assert "websocket_smoke_message_received" in record["completion_audit"]["missing_requirements"]
    assert price_client.calls[0]["url"].endswith("/uapi/overseas-price/v1/quotations/price")
    assert price_client.calls[0]["params"] == {"AUTH": "", "EXCD": "NAS", "SYMB": "AAPL"}
    assert price_step["last_price"] == 310.915
    assert price_step["derived_limit_price"] == 320.24
    assert submit_step["order"]["limit_price"] == 320.24


def test_phase21_us_activation_skips_price_derivation_before_regular_session(
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    _apply_ready_env(monkeypatch)
    price_client = _FakePriceHttpClient()

    record = phase21.run_phase21_us_activation(
        symbol="AAPL",
        qty=1,
        exchange="NASD",
        currency="USD",
        execute_service_lifecycle=True,
        derive_limit_from_price=True,
        confirm_submit=phase12c.CONFIRMATION_TOKEN,
        confirm_sync=phase12c.CONFIRMATION_TOKEN,
        confirm_cancel=phase12c.CONFIRMATION_TOKEN,
        confirm_trading_window=phase12c.TRADING_WINDOW_CONFIRMATION_TOKEN,
        as_of=US_PREMARKET_SESSION,
        websocket_service_factory=_FakeWebSocketService,
        session_factory=lambda: db_session,
        config_dir=tmp_path,
        submit_adapter=_FailSubmitAdapter(),
        sync_adapter=_FailSyncAdapter(),
        price_http_client=price_client,
    )
    skipped_step = next(step["result"] for step in record["steps"] if step["name"] == "derive_limit_from_price_skipped")

    assert record["status"] == "service_lifecycle_incomplete"
    assert record["completion_audit"]["complete"] is False
    assert "service_lifecycle_completed" in record["completion_audit"]["missing_requirements"]
    assert price_client.calls == []
    assert skipped_step["status"] == "trading_window_closed"
    assert skipped_step["network_call_performed"] is False


def test_phase21_us_activation_stops_premarket_before_submit_lifecycle() -> None:
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
        adapter_factory=lambda config: _FakePhase21Adapter(config),
    )

    assert record["status"] == "submit_lifecycle_incomplete"
    assert record["network_call_performed"] is False
    assert "US_REGULAR_SESSION_REQUIRED" in record["reason_codes"]
    controlled_step = record["steps"][-1]["result"]
    assert controlled_step["status"] == "trading_window_closed"
    assert controlled_step["trading_window"]["session"] == "premarket"


def test_phase21_us_activation_does_not_reach_adapter_in_premarket() -> None:
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
    controlled_step = record["steps"][-1]["result"]
    assert controlled_step["status"] == "trading_window_closed"
    assert controlled_step["trading_window"]["session"] == "premarket"


def test_phase21_us_activation_stops_submit_outside_us_premarket_or_regular_session() -> None:
    record = phase21.run_phase21_us_activation(
        symbol="AAPL",
        qty=1,
        limit_price=145.25,
        execute_submit=True,
        confirm_submit=phase12c.CONFIRMATION_TOKEN,
        confirm_cancel=phase12c.CONFIRMATION_TOKEN,
        confirm_trading_window=phase12c.TRADING_WINDOW_CONFIRMATION_TOKEN,
        as_of=US_CLOSED_SESSION,
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


def test_phase21_us_activation_service_lifecycle_stops_before_submit_in_premarket(
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    _apply_ready_env(monkeypatch)

    record = phase21.run_phase21_us_activation(
        symbol="AAPL",
        qty=1,
        limit_price=145.25,
        execute_service_lifecycle=True,
        confirm_submit=phase12c.CONFIRMATION_TOKEN,
        confirm_sync=phase12c.CONFIRMATION_TOKEN,
        confirm_cancel=phase12c.CONFIRMATION_TOKEN,
        confirm_trading_window=phase12c.TRADING_WINDOW_CONFIRMATION_TOKEN,
        as_of=US_PREMARKET_SESSION,
        websocket_service_factory=_FakeWebSocketService,
        session_factory=lambda: db_session,
        config_dir=tmp_path,
        submit_adapter=_FailSubmitAdapter(),
        sync_adapter=_FailSyncAdapter(),
    )

    assert record["status"] == "service_lifecycle_incomplete"
    assert record["network_call_performed"] is False
    assert record["completion_audit"]["complete"] is False
    assert "network_call_performed" in record["completion_audit"]["missing_requirements"]
    assert "paper_order_created" in record["completion_audit"]["missing_requirements"]
    assert "US_REGULAR_SESSION_REQUIRED" in record["reason_codes"]
    service_step = record["steps"][-1]["result"]
    assert service_step["status"] == "trading_window_closed"
    assert service_step["trading_window"]["session"] == "premarket"


def test_phase21_us_activation_rejects_double_submit_path() -> None:
    record = phase21.run_phase21_us_activation(
        execute_submit=True,
        execute_service_lifecycle=True,
        websocket_service_factory=_FakeWebSocketService,
    )

    assert record["status"] == "invalid_request"
    assert record["network_call_performed"] is False
    assert record["steps"] == []


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
