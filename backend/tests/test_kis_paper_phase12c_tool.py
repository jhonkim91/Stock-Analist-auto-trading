from __future__ import annotations

import json
from typing import Any

from tools import kis_paper_phase12c_dry_run as phase12c


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


def _ready_env() -> dict[str, str]:
    return {
        "KIS_APP_KEY": "TESTVALUE123456",
        "KIS_APP_SECRET": "TESTVALUE123456",
        "KIS_ACCESS_TOKEN": "TESTVALUE123456",
        "KIS_ACCOUNT_NO": "12345678",
        "KIS_PRODUCT_CODE": "01",
        "KIS_PAPER_BASE_URL": "https://openapivts.koreainvestment.com:29443",
        "ENABLE_REAL_ORDER": "false",
        "PAPER_BOT_AUTO_SUBMIT": "false",
        "PAPER_TRADING_ENABLED": "true",
        "PAPER_TRADING_CAN_CREATE": "true",
        "PAPER_TRADING_NETWORK_ENABLED": "true",
        "PAPER_TRADING_KILL_SWITCH": "false",
    }


def _ready_config() -> dict[str, object]:
    return {
        "mode": "paper",
        "enabled": True,
        "configured_can_create": True,
        "network_enabled": True,
        "broker_adapter_enabled": True,
        "official_endpoint_confirmed": True,
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


def test_phase12c_execute_uses_kill_switch_proof_and_redacts_identifiers() -> None:
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
        adapter_factory=lambda config: _FakeAdapter(config),
    )
    serialized = json.dumps(record, sort_keys=True)

    assert record["status"] == "completed"
    assert [step["name"] for step in record["steps"]] == ["kill_switch_block", "submit", "list_orders", "sync", "cancel"]
    assert record["kill_switch_reenabled"] is True
    assert "001|000001|1|70000|00|KRX" not in serialized
    assert "raw-fill-id" not in serialized
    assert "sha256:" in serialized
