from __future__ import annotations

import pytest

from backend.app.models.schemas import BrokerAdapterStatus
from backend.app.brokers.kis_paper import (
    KIS_PAPER_US_DAYTIME_ORDER_UNSUPPORTED,
    KIS_PAPER_US_EXTENDED_SESSION_BLOCK_MESSAGE,
    kis_us_order_session_supported,
)
from backend.app.services.broker_adapter import BrokerAdapter, BrokerCapabilityError, BrokerOrderRequest
from backend.app.services.kis_paper_broker_adapter import (
    CANCEL_CONFIRMATION_REQUIRED,
    CONFIRMATION_REQUIRED,
    SYNC_CONFIRMATION_REQUIRED,
    KisPaperBrokerAdapter,
)
from backend.app.services.paper_trading_service import PaperTradingService


class _FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, object]:
        return self._payload


class _FakeHttpClient:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, *, headers: dict[str, str], json: dict[str, str], timeout: float) -> _FakeResponse:
        self.calls.append({"method": "POST", "url": url, "headers": headers, "json": json, "timeout": timeout})
        return self.responses.pop(0)

    def get(self, url: str, *, headers: dict[str, str], params: dict[str, str], timeout: float) -> _FakeResponse:
        self.calls.append({"method": "GET", "url": url, "headers": headers, "params": params, "timeout": timeout})
        return self.responses.pop(0)


def _enabled_config() -> dict[str, object]:
    return {
        "mode": "paper",
        "kis_env": "paper",
        "broker_mode": "paper_kis",
        "enabled": True,
        "configured_can_create": True,
        "paper_order_submit_enabled": True,
        "paper_bot_confirm_enabled": True,
        "preview_only": False,
        "kill_switch_enabled": False,
        "network_enabled": True,
        "broker_adapter_enabled": True,
        "official_endpoint_confirmed": True,
        "live_order_enabled": False,
        "live_fallback_enabled": False,
    }


def _set_kis_env(monkeypatch, secret: str = "PHASE12B_SENTINEL_SECRET") -> None:
    monkeypatch.setenv("KIS_ENV", "paper")
    monkeypatch.setenv("ENABLE_REAL_ORDER", "false")
    monkeypatch.setenv("BROKER_MODE", "paper_kis")
    monkeypatch.setenv("PAPER_ORDER_SUBMIT_ENABLED", "true")
    monkeypatch.setenv("PAPER_BOT_CONFIRM", "true")
    monkeypatch.setenv("KIS_APP_KEY", secret)
    monkeypatch.setenv("KIS_APP_SECRET", secret)
    monkeypatch.setenv("KIS_ACCESS_TOKEN", secret)
    monkeypatch.setenv("KIS_ACCOUNT_NO", "12345678")
    monkeypatch.setenv("KIS_PRODUCT_CODE", "01")
    monkeypatch.setenv("KIS_PAPER_BASE_URL", "https://openapivts.koreainvestment.com:29443")


def test_service_kis_paper_adapter_contract_is_fail_closed():
    adapter = KisPaperBrokerAdapter()
    request = BrokerOrderRequest(symbol="005930", side="buy", qty=1, limit_price=70000)

    assert isinstance(adapter, BrokerAdapter)
    status = adapter.status()
    parsed = BrokerAdapterStatus(**status)
    assert parsed.name == "kis_paper"
    assert parsed.mode == "paper"
    assert parsed.enabled is False
    assert parsed.live_trading_enabled is False
    assert parsed.network_enabled is False
    assert parsed.can_submit is False
    assert parsed.can_cancel is False
    assert parsed.can_sync is False
    assert parsed.adapter_boundary == "paper_only_service"
    assert parsed.live_fallback_enabled is False
    assert status["official_endpoint_confirmed"] is False
    assert status["reason"] == CONFIRMATION_REQUIRED

    with pytest.raises(BrokerCapabilityError, match=CONFIRMATION_REQUIRED):
        adapter.preview_order(request)
    submit = adapter.submit_order(request)
    cancel = adapter.cancel_order(broker_order_id="paper-1", confirm=True)
    listed = adapter.list_orders(status="open")
    synced = adapter.sync(scope="all")

    assert submit["status"] == "submit_blocked"
    assert CONFIRMATION_REQUIRED in submit["reason_codes"]
    assert submit["network_call_performed"] is False
    assert cancel["status"] == "cancel_blocked"
    assert CANCEL_CONFIRMATION_REQUIRED in cancel["reason_codes"]
    assert listed["status"] == "query_blocked"
    assert synced["status"] == "sync_blocked"
    assert synced["sync_performed"] is False


def test_paper_trading_service_uses_service_adapter_boundary():
    service = PaperTradingService()
    status = service.status()["broker_adapter"]

    assert status["name"] == "kis_paper"
    assert status["adapter_boundary"] == "paper_only_service"
    assert status["live_fallback_enabled"] is False
    assert status["can_submit"] is False
    assert status["network_enabled"] is False


def test_kis_paper_adapter_submit_cancel_query_sync_with_mock_http(monkeypatch):
    _set_kis_env(monkeypatch)
    client = _FakeHttpClient(
        [
            _FakeResponse({"rt_cd": "0", "msg_cd": "0", "msg1": "OK", "output": {"KRX_FWDG_ORD_ORGNO": "001", "ODNO": "000001"}}),
            _FakeResponse({"rt_cd": "0", "msg_cd": "0", "msg1": "OK", "output": {"ODNO": "000001"}}),
            _FakeResponse(
                {
                    "rt_cd": "0",
                    "msg_cd": "0",
                    "msg1": "OK",
                    "output1": [
                        {
                            "ord_gno_brno": "001",
                            "odno": "000001",
                            "pdno": "005930",
                            "ord_qty": "2",
                            "tot_ccld_qty": "1",
                            "sll_buy_dvsn_cd": "02",
                            "ord_unpr": "70000",
                        }
                    ],
                }
            ),
            _FakeResponse(
                {
                    "rt_cd": "0",
                    "msg_cd": "0",
                    "msg1": "OK",
                    "output1": [
                        {
                            "pdno": "005930",
                            "hldg_qty": "2",
                            "pchs_avg_pric": "70000",
                            "prpr": "71000",
                            "evlu_amt": "142000",
                            "evlu_pfls_amt": "2000",
                        }
                    ],
                    "output2": [{"dnca_tot_amt": "100000", "scts_evlu_amt": "142000", "tot_evlu_amt": "242000"}],
                }
            ),
            _FakeResponse(
                {
                    "rt_cd": "0",
                    "msg_cd": "0",
                    "msg1": "OK",
                    "output1": [
                        {
                            "ord_gno_brno": "001",
                            "odno": "000001",
                            "pdno": "005930",
                            "ord_qty": "2",
                            "tot_ccld_qty": "1",
                            "sll_buy_dvsn_cd": "02",
                            "ord_unpr": "70000",
                        }
                    ],
                }
            ),
            _FakeResponse(
                {
                    "rt_cd": "0",
                    "msg_cd": "0",
                    "msg1": "OK",
                    "output1": [
                        {
                            "pdno": "005930",
                            "hldg_qty": "2",
                            "pchs_avg_pric": "70000",
                            "prpr": "71000",
                            "evlu_amt": "142000",
                            "evlu_pfls_amt": "2000",
                        }
                    ],
                    "output2": [{"dnca_tot_amt": "100000", "scts_evlu_amt": "142000", "tot_evlu_amt": "242000"}],
                }
            ),
        ]
    )
    adapter = KisPaperBrokerAdapter(config=_enabled_config(), http_client=client, max_retries=0)
    request = BrokerOrderRequest(symbol="005930", side="buy", qty=2, limit_price=70000)

    submit = adapter.submit_order(request)
    cancel = adapter.cancel_order(broker_order_id=submit["broker_order_id"], confirm=True)
    listed = adapter.list_orders(status="filled")
    balance = adapter.query_balance()
    synced = adapter.sync(scope="all")

    assert submit["ok"] is True
    assert submit["broker_order_created"] is True
    assert submit["network_call_performed"] is True
    assert submit["broker_trace"]["endpoint_path"] == "/uapi/domestic-stock/v1/trading/order-cash"
    assert submit["broker_trace"]["correlation_id"].startswith("kis-paper-")
    assert cancel["ok"] is True
    assert cancel["order_cancelled"] is True
    assert listed["orders"][0]["symbol"] == "005930"
    assert listed["fills"][0]["qty"] == 1
    assert balance["ok"] is True
    assert balance["positions"][0]["symbol"] == "005930"
    assert balance["portfolio"]["total_equity"] == 242000.0
    assert synced["sync_performed"] is True
    assert synced["orders"][0]["broker_order_id"]
    assert synced["positions"][0]["symbol"] == "005930"
    assert synced["portfolio"]["total_equity"] == 242000.0
    assert client.calls[0]["headers"]["tr_id"] == "VTTC0012U"
    assert client.calls[1]["headers"]["tr_id"] == "VTTC0013U"
    assert client.calls[2]["headers"]["tr_id"] == "VTTC0081R"
    assert client.calls[3]["headers"]["tr_id"] == "VTTC8434R"
    assert client.calls[5]["headers"]["tr_id"] == "VTTC8434R"


def test_kis_paper_adapter_keeps_domestic_path_when_metadata_exchange_is_krx(monkeypatch):
    _set_kis_env(monkeypatch)
    client = _FakeHttpClient(
        [
            _FakeResponse(
                {"rt_cd": "0", "msg_cd": "0", "msg1": "OK", "output": {"KRX_FWDG_ORD_ORGNO": "001", "ODNO": "000002"}}
            )
        ]
    )
    adapter = KisPaperBrokerAdapter(config=_enabled_config(), http_client=client, max_retries=0)
    request = BrokerOrderRequest(
        symbol="005930",
        side="buy",
        qty=1,
        limit_price=70000,
        metadata={"exchange": "KRX", "venue": "KRX"},
    )

    submit = adapter.submit_order(request)

    assert submit["ok"] is True
    assert submit["broker_trace"]["endpoint_path"] == "/uapi/domestic-stock/v1/trading/order-cash"
    assert client.calls[0]["headers"]["tr_id"] == "VTTC0012U"
    assert client.calls[0]["json"]["EXCG_ID_DVSN_CD"] == "KRX"


def test_kis_paper_adapter_supports_us_overseas_order_query_sync_with_mock_http(monkeypatch):
    _set_kis_env(monkeypatch)
    client = _FakeHttpClient(
        [
            _FakeResponse({"rt_cd": "0", "msg_cd": "0", "msg1": "OK", "output": {"ODNO": "900001"}}),
            _FakeResponse({"rt_cd": "0", "msg_cd": "0", "msg1": "OK", "output": {"ODNO": "900001"}}),
            _FakeResponse(
                {
                    "rt_cd": "0",
                    "msg_cd": "0",
                    "msg1": "OK",
                    "output": [
                        {
                            "odno": "900001",
                            "ovrs_pdno": "AAPL",
                            "ord_qty": "1",
                            "ft_ccld_qty": "1",
                            "sll_buy_dvsn_cd": "02",
                            "ovrs_ord_unpr": "145.25",
                            "ovrs_excg_cd": "NASD",
                        }
                    ],
                }
            ),
            _FakeResponse(
                {
                    "rt_cd": "0",
                    "msg_cd": "0",
                    "msg1": "OK",
                    "output1": [
                        {
                            "ovrs_pdno": "AAPL",
                            "ovrs_cblc_qty": "1",
                            "pchs_avg_pric": "145.25",
                            "now_pric2": "146.00",
                            "frcr_evlu_amt2": "146.00",
                            "evlu_pfls_amt": "0.75",
                        }
                    ],
                    "output2": {"frcr_buy_amt_smtl1": "1000.00", "frcr_evlu_tota": "146.00", "tot_asst_amt": "1146.00"},
                }
            ),
            _FakeResponse(
                {
                    "rt_cd": "0",
                    "msg_cd": "0",
                    "msg1": "OK",
                    "output": [
                        {
                            "odno": "900001",
                            "ovrs_pdno": "AAPL",
                            "ord_qty": "1",
                            "ft_ccld_qty": "1",
                            "sll_buy_dvsn_cd": "02",
                            "ovrs_ord_unpr": "145.25",
                            "ovrs_excg_cd": "NASD",
                        }
                    ],
                }
            ),
            _FakeResponse(
                {
                    "rt_cd": "0",
                    "msg_cd": "0",
                    "msg1": "OK",
                    "output1": [
                        {
                            "ovrs_pdno": "AAPL",
                            "ovrs_cblc_qty": "1",
                            "pchs_avg_pric": "145.25",
                            "now_pric2": "146.00",
                            "frcr_evlu_amt2": "146.00",
                            "evlu_pfls_amt": "0.75",
                        }
                    ],
                    "output2": {"frcr_buy_amt_smtl1": "1000.00", "frcr_evlu_tota": "146.00", "tot_asst_amt": "1146.00"},
                }
            ),
        ]
    )
    adapter = KisPaperBrokerAdapter(
        config={**_enabled_config(), "market": "US", "venue": "NASD", "currency": "USD"},
        http_client=client,
        max_retries=0,
    )
    request = BrokerOrderRequest(
        symbol="AAPL",
        side="buy",
        qty=1,
        limit_price=145.25,
        metadata={"market": "US", "venue": "NASD", "currency": "USD", "order_session": "regular"},
    )

    submit = adapter.submit_order(request)
    cancel = adapter.cancel_order(broker_order_id=submit["broker_order_id"], confirm=True)
    listed = adapter.list_orders(status="filled")
    balance = adapter.query_balance()
    synced = adapter.sync(scope="all")

    assert submit["ok"] is True
    assert submit["broker_order_created"] is True
    assert submit["broker_trace"]["endpoint_path"] == "/uapi/overseas-stock/v1/trading/order"
    assert submit["order"]["market"] == "US"
    assert submit["order"]["venue"] == "NASD"
    assert cancel["ok"] is True
    assert listed["orders"][0]["symbol"] == "AAPL"
    assert listed["fills"][0]["qty"] == 1
    assert balance["positions"][0]["symbol"] == "AAPL"
    assert balance["portfolio"]["source"] == "kis_paper_us"
    assert synced["positions"][0]["broker_position_key"] == "kis_paper_us|AAPL"
    assert client.calls[0]["url"].endswith("/uapi/overseas-stock/v1/trading/order")
    assert client.calls[0]["headers"]["tr_id"] == "VTTT1002U"
    assert client.calls[0]["json"]["OVRS_EXCG_CD"] == "NASD"
    assert client.calls[0]["json"]["OVRS_ORD_UNPR"] == "145.25"
    assert client.calls[1]["headers"]["tr_id"] == "VTTT1004U"
    assert client.calls[2]["headers"]["tr_id"] == "VTTS3035R"
    assert client.calls[3]["headers"]["tr_id"] == "VTTS3012R"
    assert client.calls[5]["headers"]["tr_id"] == "VTTS3012R"


def test_kis_paper_adapter_allows_us_regular_order_on_paper_host(monkeypatch):
    _set_kis_env(monkeypatch)
    client = _FakeHttpClient([_FakeResponse({"rt_cd": "0", "msg_cd": "0", "msg1": "OK", "output": {"ODNO": "900002"}})])
    adapter = KisPaperBrokerAdapter(
        config={**_enabled_config(), "market": "US", "venue": "NASD", "currency": "USD"},
        http_client=client,
        max_retries=0,
    )
    request = BrokerOrderRequest(
        symbol="AAPL",
        side="buy",
        qty=1,
        limit_price=145.25,
        metadata={"market": "US", "venue": "NASD", "currency": "USD", "order_session": "regular"},
    )

    submit = adapter.submit_order(request)

    assert submit["ok"] is True
    assert submit["network_call_performed"] is True
    assert submit["broker_trace"]["market"] == "US"
    assert submit["broker_trace"]["symbol"] == "AAPL"
    assert submit["broker_trace"]["order_session"] == "regular"
    assert client.calls[0]["url"].endswith("/uapi/overseas-stock/v1/trading/order")
    assert client.calls[0]["headers"]["tr_id"] == "VTTT1002U"


def test_kis_paper_adapter_blocks_us_premarket_order_before_api_call(monkeypatch):
    _set_kis_env(monkeypatch)
    client = _FakeHttpClient([])
    adapter = KisPaperBrokerAdapter(
        config={**_enabled_config(), "market": "US", "venue": "NASD", "currency": "USD"},
        http_client=client,
        max_retries=0,
    )
    request = BrokerOrderRequest(
        symbol="AAPL",
        side="buy",
        qty=1,
        limit_price=145.25,
        metadata={"market": "US", "venue": "NASD", "currency": "USD", "order_session": "premarket"},
    )

    submit = adapter.submit_order(request)

    assert submit["ok"] is False
    assert submit["network_call_performed"] is False
    assert submit["reason_codes"] == [KIS_PAPER_US_DAYTIME_ORDER_UNSUPPORTED]
    assert submit["broker_message"] == KIS_PAPER_US_EXTENDED_SESSION_BLOCK_MESSAGE
    assert submit["broker_trace"]["tr_id"] == "VTTT1002U"
    assert submit["broker_trace"]["host"] == "openapivts.koreainvestment.com"
    assert submit["broker_trace"]["market"] == "US"
    assert submit["broker_trace"]["symbol"] == "AAPL"
    assert submit["broker_trace"]["order_session"] == "premarket"
    assert submit["broker_trace"]["rt_cd"] == "LOCAL_BLOCK"
    assert submit["broker_trace"]["msg_cd"] == KIS_PAPER_US_DAYTIME_ORDER_UNSUPPORTED
    assert submit["broker_trace"]["msg1"] == KIS_PAPER_US_EXTENDED_SESSION_BLOCK_MESSAGE
    assert client.calls == []


def test_kis_paper_adapter_blocks_us_daytime_order_before_api_call(monkeypatch):
    _set_kis_env(monkeypatch)
    client = _FakeHttpClient([])
    adapter = KisPaperBrokerAdapter(
        config={**_enabled_config(), "market": "US", "venue": "NASD", "currency": "USD"},
        http_client=client,
        max_retries=0,
    )
    request = BrokerOrderRequest(
        symbol="AAPL",
        side="buy",
        qty=1,
        limit_price=145.25,
        metadata={"market": "US", "venue": "NASD", "currency": "USD", "order_session": "daytime"},
    )

    submit = adapter.submit_order(request)

    assert submit["ok"] is False
    assert submit["network_call_performed"] is False
    assert submit["reason_codes"] == [KIS_PAPER_US_DAYTIME_ORDER_UNSUPPORTED]
    assert submit["broker_trace"]["order_session"] == "daytime"
    assert submit["broker_trace"]["msg_cd"] == KIS_PAPER_US_DAYTIME_ORDER_UNSUPPORTED
    assert submit["broker_trace"]["msg1"] == KIS_PAPER_US_EXTENDED_SESSION_BLOCK_MESSAGE
    assert client.calls == []


def test_kis_paper_adapter_blocks_us_aftermarket_order_before_api_call(monkeypatch):
    _set_kis_env(monkeypatch)
    client = _FakeHttpClient([])
    adapter = KisPaperBrokerAdapter(
        config={**_enabled_config(), "market": "US", "venue": "NASD", "currency": "USD"},
        http_client=client,
        max_retries=0,
    )
    request = BrokerOrderRequest(
        symbol="AAPL",
        side="buy",
        qty=1,
        limit_price=145.25,
        metadata={"market": "US", "venue": "NASD", "currency": "USD", "order_session": "aftermarket"},
    )

    submit = adapter.submit_order(request)

    assert submit["ok"] is False
    assert submit["network_call_performed"] is False
    assert submit["reason_codes"] == [KIS_PAPER_US_DAYTIME_ORDER_UNSUPPORTED]
    assert submit["broker_trace"]["market"] == "US"
    assert submit["broker_trace"]["symbol"] == "AAPL"
    assert submit["broker_trace"]["order_session"] == "aftermarket"
    assert submit["broker_trace"]["rt_cd"] == "LOCAL_BLOCK"
    assert submit["broker_trace"]["msg_cd"] == KIS_PAPER_US_DAYTIME_ORDER_UNSUPPORTED
    assert submit["broker_trace"]["msg1"] == KIS_PAPER_US_EXTENDED_SESSION_BLOCK_MESSAGE
    assert client.calls == []


def test_kis_capability_map_keeps_real_us_extended_sessions_enabled() -> None:
    assert kis_us_order_session_supported("paper", "regular") is True
    assert kis_us_order_session_supported("paper", "premarket") is False
    assert kis_us_order_session_supported("paper", "aftermarket") is False
    assert kis_us_order_session_supported("paper", "daytime") is False
    assert kis_us_order_session_supported("real", "premarket") is True
    assert kis_us_order_session_supported("real", "aftermarket") is True
    assert kis_us_order_session_supported("real", "daytime") is True


def test_kis_paper_adapter_blocks_live_base_url(monkeypatch):
    _set_kis_env(monkeypatch)
    monkeypatch.setenv("KIS_PAPER_BASE_URL", "https://openapi.koreainvestment.com:9443")
    adapter = KisPaperBrokerAdapter(config=_enabled_config(), http_client=_FakeHttpClient([]))

    result = adapter.submit_order(BrokerOrderRequest(symbol="005930", side="buy", qty=1, limit_price=70000))

    assert result["ok"] is False
    assert "KIS_LIVE_BASE_URL_BLOCKED" in result["reason_codes"]
    assert result["network_call_performed"] is False


def test_kis_paper_adapter_requires_paper_broker_mode_and_submit_flag(monkeypatch):
    _set_kis_env(monkeypatch)
    monkeypatch.delenv("BROKER_MODE", raising=False)
    monkeypatch.delenv("PAPER_ORDER_SUBMIT_ENABLED", raising=False)
    adapter = KisPaperBrokerAdapter(config={**_enabled_config(), "broker_mode": "", "paper_order_submit_enabled": False})

    result = adapter.submit_order(BrokerOrderRequest(symbol="005930", side="buy", qty=1, limit_price=70000))

    assert result["ok"] is False
    assert "BROKER_MODE_PAPER_KIS_REQUIRED" in result["reason_codes"]
    assert "PAPER_ORDER_SUBMIT_ENABLED_REQUIRED" in result["reason_codes"]
    assert result["network_call_performed"] is False


def test_kis_paper_adapter_redacts_and_surfaces_kis_error_message(monkeypatch):
    secret = "PHASE12C_SENTINEL_SECRET"
    _set_kis_env(monkeypatch, secret=secret)
    client = _FakeHttpClient(
        [
            _FakeResponse(
                {
                    "rt_cd": "1",
                    "msg_cd": "40580000",
                    "msg1": "mock paper order rejected",
                    "output": {"raw_account": secret},
                }
            )
        ]
    )
    adapter = KisPaperBrokerAdapter(config=_enabled_config(), http_client=client, max_retries=0)

    result = adapter.submit_order(BrokerOrderRequest(symbol="005930", side="buy", qty=1, limit_price=70000))

    assert result["ok"] is False
    assert result["status"] == "submit_failed"
    assert result["broker_message_code"] == "40580000"
    assert result["broker_message"] == "mock paper order rejected"
    assert result["broker_trace"]["broker_message_code"] == "40580000"
    assert result["broker_trace"]["broker_message"] == "mock paper order rejected"
    assert secret not in str(result)


def test_kis_paper_adapter_us_failure_trace_includes_order_context(monkeypatch):
    secret = "PHASE21_US_ERROR_SECRET"
    _set_kis_env(monkeypatch, secret=secret)
    client = _FakeHttpClient(
        [
            _FakeResponse(
                {
                    "rt_cd": "1",
                    "msg_cd": "40570000",
                    "msg1": "mock US paper order rejected",
                    "output": {"raw_account": secret},
                }
            )
        ]
    )
    adapter = KisPaperBrokerAdapter(
        config={**_enabled_config(), "market": "US", "venue": "NASD", "currency": "USD"},
        http_client=client,
        max_retries=0,
    )
    request = BrokerOrderRequest(
        symbol="AAPL",
        side="buy",
        qty=1,
        limit_price=145.25,
        metadata={"market": "US", "venue": "NASD", "currency": "USD", "order_session": "regular"},
    )

    result = adapter.submit_order(request)
    trace = result["broker_trace"]

    assert result["ok"] is False
    assert result["status"] == "submit_failed"
    assert trace["tr_id"] == "VTTT1002U"
    assert trace["host"] == "openapivts.koreainvestment.com"
    assert trace["market"] == "US"
    assert trace["symbol"] == "AAPL"
    assert trace["order_session"] == "regular"
    assert trace["rt_cd"] == "1"
    assert trace["msg_cd"] == "40570000"
    assert trace["msg1"] == "mock US paper order rejected"
    assert result["rt_cd"] == "1"
    assert result["msg_cd"] == "40570000"
    assert result["msg1"] == "mock US paper order rejected"
    assert secret not in str(result)


def test_kis_paper_adapter_surfaces_redacted_http_error_body(monkeypatch):
    secret = "PHASE21_HTTP_ERROR_SECRET"
    _set_kis_env(monkeypatch, secret=secret)
    client = _FakeHttpClient(
        [
            _FakeResponse(
                {
                    "rt_cd": "1",
                    "msg_cd": "50012345",
                    "msg1": "mock http body rejected",
                    "appsecret": secret,
                },
                status_code=500,
            )
        ]
    )
    adapter = KisPaperBrokerAdapter(config=_enabled_config(), http_client=client, max_retries=0)

    result = adapter.submit_order(BrokerOrderRequest(symbol="005930", side="buy", qty=1, limit_price=70000))

    assert result["ok"] is False
    assert result["status"] == "submit_failed"
    assert result["broker_message_code"] == "50012345"
    assert result["broker_message"] == "mock http body rejected"
    assert result["broker_trace"]["broker_message_code"] == "50012345"
    assert secret not in str(result)
