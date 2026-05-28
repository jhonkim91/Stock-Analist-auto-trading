from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from tools import kis_paper_phase12c_dry_run as phase12c

US_REGULAR_SESSION = datetime(2026, 5, 28, 10, 0, tzinfo=ZoneInfo("America/New_York"))
US_PREMARKET_SESSION = datetime(2026, 5, 28, 5, 0, tzinfo=ZoneInfo("America/New_York"))


class _FakeAdapter:
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
            "broker_order_id": "001|000001|1|70000|00|KRX",
            "network_call_performed": True,
            "live_order_created": False,
            "broker_trace": {"endpoint_path": "/uapi/domestic-stock/v1/trading/order-cash", "tr_id": "VTTC0012U"},
        }

    def list_orders(self, *, status: str | None = None) -> dict[str, Any]:
        return {
            "ok": True,
            "status": "query_ok",
            "orders": [{"broker_order_id": "001|000001|1|70000|00|KRX", "symbol": "005930"}],
            "fills": [{"broker_fill_id": "raw-fill-id", "qty": 1}],
            "network_call_performed": True,
        }

    def sync(self, *, scope: str = "all") -> dict[str, Any]:
        return {
            "ok": True,
            "status": "sync_ok",
            "sync_performed": True,
            "orders": [{"broker_order_id": "001|000001|1|70000|00|KRX"}],
            "fills": [{"broker_fill_id": "raw-fill-id"}],
            "positions": [{"symbol": "005930", "qty": 1}],
            "portfolio": {"total_equity": 1000},
            "network_call_performed": True,
        }

    def cancel_order(self, *, broker_order_id: str, confirm: bool = False) -> dict[str, Any]:
        return {
            "ok": True,
            "status": "cancelled",
            "broker_order_id": broker_order_id,
            "order_cancelled": True,
            "network_call_performed": True,
        }


class _QueryFailingAdapter(_FakeAdapter):
    def list_orders(self, *, status: str | None = None) -> dict[str, Any]:
        return {
            "ok": False,
            "status": "query_failed",
            "reason_codes": ["QUERY_CONTRACT_MISMATCH"],
            "network_call_performed": True,
        }


class _RecordingMarketAdapter(_FakeAdapter):
    def __init__(self, config: dict[str, Any], calls: list[dict[str, Any]]) -> None:
        super().__init__(config)
        self.calls = calls

    def submit_order(self, request) -> dict[str, Any]:
        self.calls.append({"config": self.config, "metadata": request.metadata, "symbol": request.symbol})
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


def _ready_config() -> dict[str, object]:
    return {
        "mode": "paper",
        "kis_env": "paper",
        "broker_mode": "paper_kis",
        "enabled": True,
        "configured_can_create": True,
        "paper_order_submit_enabled": True,
        "paper_bot_confirm_enabled": True,
        "network_enabled": True,
        "balance_inquiry_enabled": True,
        "broker_adapter_enabled": True,
        "official_endpoint_confirmed": True,
        "official_balance_endpoint_confirmed": True,
        "kill_switch_enabled": False,
        "live_order_enabled": False,
        "live_fallback_enabled": False,
    }


def test_phase12c_preflight_without_env_is_redacted_and_noop() -> None:
    record = phase12c.run_controlled_dry_run(
        execute=False,
        symbol="005930",
        side="buy",
        qty=1,
        limit_price=None,
        confirm_submit=None,
        confirm_cancel=None,
        env={},
        adapter_factory=lambda config: (_ for _ in ()).throw(AssertionError("adapter must not be called")),
    )

    assert record["status"] == "preflight_only"
    assert record["network_call_performed"] is False
    assert record["preflight"]["ok"] is False
    assert "KIS_APP_KEY_MISSING" in record["preflight"]["blockers"]


def test_phase12c_execute_missing_env_stops_before_adapter() -> None:
    record = phase12c.run_controlled_dry_run(
        execute=True,
        symbol="005930",
        side="buy",
        qty=1,
        limit_price=None,
        confirm_submit=phase12c.CONFIRMATION_TOKEN,
        confirm_cancel=phase12c.CONFIRMATION_TOKEN,
        env={},
        adapter_factory=lambda config: (_ for _ in ()).throw(AssertionError("adapter must not be called")),
    )

    assert record["status"] == "preflight_stopped"
    assert record["network_call_performed"] is False
    assert "KIS_ACCESS_TOKEN_MISSING" in record["reason_codes"]


def test_phase12c_preflight_requires_broker_mode_and_submit_flag() -> None:
    env = _ready_env()
    env.pop("BROKER_MODE")
    env.pop("PAPER_ORDER_SUBMIT_ENABLED")

    record = phase12c.run_controlled_dry_run(
        execute=True,
        symbol="005930",
        side="buy",
        qty=1,
        limit_price=None,
        confirm_submit=phase12c.CONFIRMATION_TOKEN,
        confirm_cancel=phase12c.CONFIRMATION_TOKEN,
        env=env,
        config=_ready_config(),
        adapter_factory=lambda config: (_ for _ in ()).throw(AssertionError("adapter must not be called")),
    )

    assert record["status"] == "preflight_stopped"
    assert record["network_call_performed"] is False
    assert "BROKER_MODE_PAPER_KIS_REQUIRED" in record["reason_codes"]
    assert "PAPER_ORDER_SUBMIT_ENABLED_REQUIRED" in record["reason_codes"]


def test_phase12c_temporary_config_is_process_only_and_requires_confirmation() -> None:
    record = phase12c.run_controlled_dry_run(
        execute=True,
        symbol="005930",
        side="buy",
        qty=1,
        limit_price=None,
        confirm_submit=None,
        confirm_cancel=None,
        env=_ready_env(),
        config={"mode": "safety_scaffold", "kill_switch_enabled": True},
        use_temporary_paper_config=True,
        adapter_factory=lambda config: (_ for _ in ()).throw(AssertionError("adapter must not be called")),
    )

    assert record["status"] == "confirmation_required"
    assert record["temporary_config_used"] is True
    assert record["network_call_performed"] is False
    assert record["preflight"]["ok"] is True
    assert record["preflight"]["config_gates"]["mode"] == "paper"


def test_phase12c_cli_execute_without_confirmation_returns_failure(capsys) -> None:
    exit_code = phase12c.main(["--execute", "--temporary-paper-config"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert output["status"] == "confirmation_required"
    assert output["network_call_performed"] is False
    assert "PHASE12C_SUBMIT_CANCEL_CONFIRMATION_REQUIRED" in output["reason_codes"]


def test_phase12c_requires_trading_window_confirmation_before_adapter() -> None:
    record = phase12c.run_controlled_dry_run(
        execute=True,
        symbol="005930",
        side="buy",
        qty=1,
        limit_price=70000,
        confirm_submit=phase12c.CONFIRMATION_TOKEN,
        confirm_cancel=phase12c.CONFIRMATION_TOKEN,
        env=_ready_env(),
        config=_ready_config(),
        adapter_factory=lambda config: (_ for _ in ()).throw(AssertionError("adapter must not be called")),
    )

    assert record["status"] == "trading_window_confirmation_required"
    assert record["network_call_performed"] is False
    assert record["steps"] == []
    assert "PHASE12C_TRADING_WINDOW_CONFIRMATION_REQUIRED" in record["reason_codes"]


def test_phase12c_us_market_options_reach_adapter_metadata() -> None:
    calls: list[dict[str, Any]] = []

    record = phase12c.run_controlled_dry_run(
        execute=True,
        symbol="AAPL",
        side="buy",
        qty=1,
        limit_price=145.25,
        market="US",
        exchange="NASD",
        currency="USD",
        confirm_submit=phase12c.CONFIRMATION_TOKEN,
        confirm_cancel=phase12c.CONFIRMATION_TOKEN,
        confirm_trading_window=phase12c.TRADING_WINDOW_CONFIRMATION_TOKEN,
        as_of=US_REGULAR_SESSION,
        env=_ready_env(),
        config=_ready_config(),
        adapter_factory=lambda config: _RecordingMarketAdapter(config, calls),
    )

    assert record["status"] == "completed"
    assert record["market"] == "US"
    assert record["exchange"] == "NASD"
    assert calls[0]["config"]["market"] == "US"
    assert calls[0]["config"]["venue"] == "NASD"
    assert calls[0]["config"]["currency"] == "USD"
    assert calls[0]["metadata"] == {
        "market": "US",
        "venue": "NASD",
        "exchange": "NASD",
        "currency": "USD",
    }
    assert calls[0]["symbol"] == "AAPL"


def test_phase12c_us_market_closed_stops_before_adapter() -> None:
    record = phase12c.run_controlled_dry_run(
        execute=True,
        symbol="AAPL",
        side="buy",
        qty=1,
        limit_price=145.25,
        market="US",
        exchange="NASD",
        currency="USD",
        confirm_submit=phase12c.CONFIRMATION_TOKEN,
        confirm_cancel=phase12c.CONFIRMATION_TOKEN,
        confirm_trading_window=phase12c.TRADING_WINDOW_CONFIRMATION_TOKEN,
        as_of=US_PREMARKET_SESSION,
        env=_ready_env(),
        config=_ready_config(),
        adapter_factory=lambda config: (_ for _ in ()).throw(AssertionError("adapter must not be called")),
    )

    assert record["status"] == "trading_window_closed"
    assert record["network_call_performed"] is False
    assert record["steps"] == []
    assert record["trading_window"]["timezone"] == "America/New_York"
    assert "US_REGULAR_SESSION_REQUIRED" in record["reason_codes"]


def test_phase12c_attempts_cancel_after_query_failure_and_redacts_identifier() -> None:
    record = phase12c.run_controlled_dry_run(
        execute=True,
        symbol="005930",
        side="buy",
        qty=1,
        limit_price=70000,
        confirm_submit=phase12c.CONFIRMATION_TOKEN,
        confirm_cancel=phase12c.CONFIRMATION_TOKEN,
        confirm_trading_window=phase12c.TRADING_WINDOW_CONFIRMATION_TOKEN,
        env=_ready_env(),
        config=_ready_config(),
        adapter_factory=lambda config: _QueryFailingAdapter(config),
    )
    serialized = json.dumps(record, sort_keys=True)

    assert record["status"] == "query_failed"
    assert [step["name"] for step in record["steps"]] == [
        "kill_switch_block",
        "submit",
        "list_orders",
        "cancel_after_query_failed",
    ]
    assert record["kill_switch_reenabled"] is True
    assert "001|000001|1|70000|00|KRX" not in serialized
    assert "sha256:" in serialized


def test_phase12c_record_path_must_stay_inside_repo() -> None:
    outside_path = phase12c.PROJECT_ROOT.parent / "phase12c-outside.json"

    with pytest.raises(ValueError, match="inside the repository"):
        phase12c.write_record({"status": "blocked"}, outside_path)


def test_phase12c_execute_uses_kill_switch_proof_and_redacts_identifiers() -> None:
    record = phase12c.run_controlled_dry_run(
        execute=True,
        symbol="005930",
        side="buy",
        qty=1,
        limit_price=70000,
        confirm_submit=phase12c.CONFIRMATION_TOKEN,
        confirm_cancel=phase12c.CONFIRMATION_TOKEN,
        confirm_trading_window=phase12c.TRADING_WINDOW_CONFIRMATION_TOKEN,
        env=_ready_env(),
        config=_ready_config(),
        adapter_factory=lambda config: _FakeAdapter(config),
    )
    serialized = json.dumps(record, sort_keys=True)

    assert record["status"] == "completed"
    assert [step["name"] for step in record["steps"]] == ["kill_switch_block", "submit", "list_orders", "sync", "cancel"]
    assert record["kill_switch_reenabled"] is True
    assert "001|000001|1|70000|00|KRX" not in serialized
    assert "raw-fill-id" not in serialized
    assert "sha256:" in serialized
