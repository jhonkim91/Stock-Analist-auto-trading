from __future__ import annotations

import json
from textwrap import dedent

from sqlalchemy import select

from backend.app.models.tables import PaperAuditEvent, PaperOrder
from backend.app.services.kis_token_manager import KisTokenManager
from backend.app.services.paper_trading_service import PaperTradingService
from backend.app.services.telegram_bot_service import TelegramBotService


class _TokenResponse:
    status_code = 200

    def json(self) -> dict[str, object]:
        return {
            "access_token": "RAW_" + "RESET_TOKEN_SHOULD_NOT_LEAK",
            "refresh_token": "RAW_" + "RESET_REFRESH_SHOULD_NOT_LEAK",
            "expires_in": 3600,
        }


class _TokenClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, *, headers: dict[str, str], json: dict[str, str], timeout: float) -> _TokenResponse:
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return _TokenResponse()


def _enable_paper_runtime(monkeypatch) -> None:
    monkeypatch.setenv("KIS_ENV", "paper")
    monkeypatch.setenv("BROKER_MODE", "paper_kis")
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRADING_CAN_CREATE", "true")
    monkeypatch.setenv("PAPER_TRADING_KILL_SWITCH", "false")
    monkeypatch.setenv("PAPER_BOT_CONFIRM", "true")
    monkeypatch.setenv("PAPER_TRADING_NETWORK_ENABLED", "false")
    monkeypatch.setenv("ENABLE_REAL_ORDER", "false")


def _write_paper_config(
    tmp_path,
    *,
    kill_switch_enabled: bool = False,
    blacklist: list[str] | None = None,
    cooldown_seconds: int = 0,
) -> None:
    blacklist_items = blacklist or []
    blacklist_yaml = " [" + ", ".join(f'"{item}"' for item in blacklist_items) + "]" if blacklist_items else " []"
    tmp_path.joinpath("paper.yaml").write_text(
        dedent(
            f"""
            paper:
              mode: "paper"
              kis_env: "paper"
              broker_mode: "paper_kis"
              market: "KR"
              enabled: true
              can_create: true
              can_simulate_fills: false
              preview_only: false
              kill_switch_enabled: {str(kill_switch_enabled).lower()}
              network_enabled: false
              live_order_enabled: false
              broker_order_enabled: false
              require_bot_confirm: true
              paper_order_submit_enabled: true
            risk_gate:
              allow_buy_preview: true
              allow_sell_preview: true
              allow_short_sell: false
              max_order_qty: 100
              max_order_notional: 1000000
              max_open_positions: 5
              blacklist:{blacklist_yaml}
              cooldown_seconds: {cooldown_seconds}
            audit:
              persistence_enabled: false
              sanitize_enabled: true
            simulator:
              enabled: false
              auto_fill_on_create: false
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def test_kis_token_config_load_and_cache_are_secret_safe(tmp_path, monkeypatch) -> None:
    raw_token = "RAW_" + "RESET_TOKEN_SHOULD_NOT_LEAK"
    raw_refresh = "RAW_" + "RESET_REFRESH_SHOULD_NOT_LEAK"
    cache_path = tmp_path / "kis-token.json"
    monkeypatch.setenv("KIS_ENV", "paper")
    monkeypatch.setenv("KIS_APP_KEY", "RESET_APP_KEY_VALUE")
    monkeypatch.setenv("KIS_APP_SECRET", "RESET_APP_SECRET_VALUE")
    monkeypatch.setenv("KIS_TOKEN_ISSUE_ENABLED", "true")
    monkeypatch.setenv("KIS_TOKEN_CACHE_ENABLED", "true")
    monkeypatch.setenv("KIS_TOKEN_CACHE_PATH", str(cache_path))
    monkeypatch.setenv("KIS_PAPER_BASE_URL", "https://openapivts.koreainvestment.com:29443")
    monkeypatch.setenv("ENABLE_REAL_ORDER", "false")
    client = _TokenClient()

    issued = KisTokenManager().issue_paper_access_token(confirm=True, http_client=client)
    cached = KisTokenManager().ensure_paper_access_token(confirm=True, http_client=client)
    serialized = json.dumps({"issued": issued, "cached": cached}, ensure_ascii=False, default=str)
    cache_payload = json.loads(cache_path.read_text(encoding="utf-8"))

    assert issued["ok"] is True
    assert issued["token_cache_write_performed"] is True
    assert issued["metadata"]["token_cache_enabled"] is True
    assert issued["metadata"]["token_cache_exists"] is True
    assert cached["status"] == "token_cache_hit"
    assert cached["network_call_performed"] is False
    assert len(client.calls) == 1
    assert cache_payload["access_token"] == raw_token
    assert cache_payload["refresh_token"] == raw_refresh
    assert raw_token not in serialized
    assert raw_refresh not in serialized


def test_telegram_command_parsing_and_search_fallback(full_flow_client, monkeypatch) -> None:
    monkeypatch.delenv("KIS_MARKET_QUOTE_ENABLED", raising=False)

    status = full_flow_client.get("/api/telegram/status")
    search = full_flow_client.post("/api/telegram/command", json={"text": "/search KR009"})
    buy_preview = full_flow_client.post("/api/telegram/command", json={"text": "/buy KR009 qty=1 price=100"})

    assert status.status_code == 200
    assert "/search" in status.json()["supported_commands"]
    assert search.status_code == 200
    search_payload = search.json()
    assert search_payload["ok"] is True
    assert search_payload["command"] == "/search"
    assert search_payload["payload"]["quote"]["fallback_used"] is True
    assert "KIS_MARKET_QUOTE_DISABLED" in search_payload["payload"]["quote"]["fallback_reason_codes"]
    assert buy_preview.status_code == 200
    assert buy_preview.json()["status"] == "preview"
    assert buy_preview.json()["payload"]["paper_order_created"] is False


def test_stock_detail_api_uses_db_fallback_without_kis_network(full_flow_client, monkeypatch) -> None:
    monkeypatch.setenv("KIS_MARKET_QUOTE_ENABLED", "false")

    response = full_flow_client.get("/api/stocks/KR009")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"]["symbol"] == "KR009"
    assert payload["quote"]["available"] is True
    assert payload["quote"]["source"] == "local_daily_ohlcv"
    assert payload["quote"]["fallback_used"] is True
    assert payload["network_call_performed"] is False


def test_mock_kis_paper_order_preview_and_create_respect_kill_switch_blacklist_and_cooldown(
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    _enable_paper_runtime(monkeypatch)
    _write_paper_config(tmp_path)
    service = PaperTradingService(db_session, config_dir=tmp_path)

    preview = service.preview_order(symbol="KR009", side="buy", qty=1, limit_price=100.0)
    created = service.submit_order(
        symbol="KR009",
        side="buy",
        qty=1,
        limit_price=100.0,
        confirm=True,
        idempotency_key="reset-create",
    )

    _write_paper_config(tmp_path, kill_switch_enabled=True)
    monkeypatch.setenv("PAPER_TRADING_KILL_SWITCH", "true")
    kill_switch = service.preview_order(symbol="KR010", side="buy", qty=1, limit_price=100.0)

    _write_paper_config(tmp_path, blacklist=["KR011"])
    monkeypatch.setenv("PAPER_TRADING_KILL_SWITCH", "false")
    blacklist = service.preview_order(symbol="KR011", side="buy", qty=1, limit_price=100.0)

    _write_paper_config(tmp_path, cooldown_seconds=3600)
    cooldown = service.submit_order(
        symbol="KR009",
        side="buy",
        qty=1,
        limit_price=100.0,
        confirm=True,
        idempotency_key="reset-cooldown",
    )

    orders = list(db_session.scalars(select(PaperOrder)).all())
    audit_events = list(db_session.scalars(select(PaperAuditEvent)).all())

    assert preview["risk_gate"]["passed"] is True
    assert preview["paper_order_created"] is False
    assert created["ok"] is True
    assert created["paper_order_created"] is True
    assert created["network_call_performed"] is False
    assert "KILL_SWITCH_ACTIVE" in kill_switch["reason_codes"]
    assert "PAPER_SYMBOL_BLACKLISTED" in blacklist["reason_codes"]
    assert cooldown["ok"] is False
    assert "PAPER_ORDER_COOLDOWN_ACTIVE" in cooldown["reason_codes"]
    assert len(orders) == 1
    assert len(audit_events) == 1
