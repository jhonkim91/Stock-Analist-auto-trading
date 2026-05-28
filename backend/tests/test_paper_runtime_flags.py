from __future__ import annotations

from textwrap import dedent

from sqlalchemy import func, select

from backend.app.models.tables import PaperOrder
from backend.app.services.paper_order_service import PaperOrderService
from backend.app.services.paper_trading_service import PaperConfigService


def _write_paper_config(tmp_path, *, network_enabled: bool = False, kill_switch_enabled: bool = False) -> None:
    tmp_path.joinpath("paper.yaml").write_text(
        dedent(
            f"""
            paper:
              mode: "paper"
              enabled: true
              can_create: true
              can_simulate_fills: false
              preview_only: false
              kill_switch_enabled: {str(kill_switch_enabled).lower()}
              network_enabled: {str(network_enabled).lower()}
              live_order_enabled: false
              broker_order_enabled: false
            risk_gate:
              allow_buy_preview: true
              allow_sell_preview: true
              allow_short_sell: false
              max_order_qty: 1000000
              max_order_notional: 100000000
            audit:
              persistence_enabled: false
              sanitize_enabled: true
            simulator:
              enabled: false
              auto_fill_on_create: false
            broker_adapter:
              name: "kis_paper"
              enabled: false
              official_endpoint_confirmed: false
              official_balance_endpoint_confirmed: false
              balance_inquiry_enabled: false
              live_fallback_enabled: false
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _clear_runtime_flags(monkeypatch) -> None:
    for name in (
        "PAPER_TRADING_ENABLED",
        "PAPER_TRADING_CAN_CREATE",
        "PAPER_TRADING_NETWORK_ENABLED",
        "PAPER_TRADING_KILL_SWITCH",
        "PAPER_BOT_CONFIRM",
        "KIS_ENV",
        "BROKER_MODE",
        "PAPER_ORDER_SUBMIT_ENABLED",
    ):
        monkeypatch.delenv(name, raising=False)


def _enable_local_submit_flags(monkeypatch) -> None:
    monkeypatch.setenv("KIS_ENV", "paper")
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRADING_CAN_CREATE", "true")
    monkeypatch.setenv("PAPER_TRADING_KILL_SWITCH", "false")
    monkeypatch.setenv("PAPER_BOT_CONFIRM", "true")
    monkeypatch.delenv("PAPER_TRADING_NETWORK_ENABLED", raising=False)
    monkeypatch.delenv("BROKER_MODE", raising=False)
    monkeypatch.delenv("PAPER_ORDER_SUBMIT_ENABLED", raising=False)


def _paper_order_count(db_session) -> int:
    return int(db_session.scalar(select(func.count()).select_from(PaperOrder)) or 0)


def test_paper_config_true_uses_yaml_gates_but_still_requires_paper_env(tmp_path, monkeypatch, db_session) -> None:
    _clear_runtime_flags(monkeypatch)
    _write_paper_config(tmp_path)

    config, reasons = PaperConfigService(tmp_path).load()
    result = PaperOrderService(db_session, config_dir=tmp_path).submit_order(
        symbol="KR009",
        side="buy",
        qty=1,
        limit_price=100.0,
        confirm=True,
        idempotency_key="runtime-flags-required",
    )

    assert config["enabled"] is True
    assert config["configured_can_create"] is True
    assert config["kill_switch_enabled"] is False
    assert set(reasons) == {"KIS_ENV_PAPER_REQUIRED"}
    assert result["paper_order_created"] is False
    assert result["network_call_performed"] is False
    assert _paper_order_count(db_session) == 0


def test_local_paper_submit_requires_runtime_flags_and_stays_non_network(
    tmp_path,
    monkeypatch,
    db_session,
) -> None:
    _enable_local_submit_flags(monkeypatch)
    _write_paper_config(tmp_path)

    result = PaperOrderService(db_session, config_dir=tmp_path).submit_order(
        symbol="KR009",
        side="buy",
        qty=1,
        limit_price=100.0,
        confirm=True,
        idempotency_key="runtime-flags-local-submit",
    )

    assert result["ok"] is True
    assert result["paper_order_created"] is True
    assert result["live_order_created"] is False
    assert result["broker_order_created"] is False
    assert result["network_call_performed"] is False
    assert _paper_order_count(db_session) == 1


def test_network_enabled_requires_paper_broker_submit_and_adapter_gates(
    tmp_path,
    monkeypatch,
    db_session,
) -> None:
    _enable_local_submit_flags(monkeypatch)
    _write_paper_config(tmp_path, network_enabled=True)

    missing_network_flag = PaperOrderService(db_session, config_dir=tmp_path).submit_order(
        symbol="KR009",
        side="buy",
        qty=1,
        limit_price=100.0,
        confirm=True,
        idempotency_key="runtime-flags-network-missing",
    )

    monkeypatch.setenv("PAPER_TRADING_NETWORK_ENABLED", "true")
    missing_broker_submit_flags = PaperOrderService(db_session, config_dir=tmp_path).submit_order(
        symbol="KR009",
        side="buy",
        qty=1,
        limit_price=100.0,
        confirm=True,
        idempotency_key="runtime-flags-network-enabled",
    )
    monkeypatch.setenv("BROKER_MODE", "paper_kis")
    monkeypatch.setenv("PAPER_ORDER_SUBMIT_ENABLED", "true")
    unsupported_network_submit = PaperOrderService(db_session, config_dir=tmp_path).submit_order(
        symbol="KR009",
        side="buy",
        qty=1,
        limit_price=100.0,
        confirm=True,
        idempotency_key="runtime-flags-network-confirmed-gates",
    )

    assert "BROKER_MODE_PAPER_KIS_REQUIRED" in missing_network_flag["reason_codes"]
    assert "PAPER_ORDER_SUBMIT_ENABLED_REQUIRED" in missing_network_flag["reason_codes"]
    assert missing_network_flag["network_call_performed"] is False
    assert "BROKER_MODE_PAPER_KIS_REQUIRED" in missing_broker_submit_flags["reason_codes"]
    assert "PAPER_ORDER_SUBMIT_ENABLED_REQUIRED" in missing_broker_submit_flags["reason_codes"]
    assert missing_broker_submit_flags["network_call_performed"] is False
    assert "KIS_PAPER_ADAPTER_DISABLED" in unsupported_network_submit["reason_codes"]
    assert "KIS_PAPER_OFFICIAL_ENDPOINT_CONFIRMATION_REQUIRED" in unsupported_network_submit["reason_codes"]
    assert unsupported_network_submit["network_call_performed"] is False
    assert unsupported_network_submit["live_order_created"] is False
    assert unsupported_network_submit["broker_order_created"] is False
    assert _paper_order_count(db_session) == 0
