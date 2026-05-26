from __future__ import annotations

import json
import logging

import httpx

from backend.app.services.kis_paper_balance import (
    KIS_PAPER_BALANCE_PATH,
    KIS_PAPER_BALANCE_TR_ID,
    KisPaperBalanceClient,
)
from backend.app.services.paper_sync_service import PaperConfigService


def _set_kis_balance_env(monkeypatch, secret: str = "PAPER_BALANCE_SECRET_SENTINEL") -> None:
    monkeypatch.setenv("ENABLE_REAL_ORDER", "false")
    monkeypatch.setenv("KIS_APP_KEY", secret)
    monkeypatch.setenv("KIS_APP_SECRET", secret)
    monkeypatch.setenv("KIS_ACCESS_TOKEN", secret)
    monkeypatch.setenv("KIS_ACCOUNT_NO", "12345678")
    monkeypatch.setenv("KIS_PRODUCT_CODE", "01")
    monkeypatch.setenv("KIS_PAPER_BASE_URL", "https://openapivts.koreainvestment.com:29443")


def _enabled_paper_config() -> dict[str, object]:
    return {
        "mode": "paper",
        "enabled": True,
        "network_enabled": True,
        "balance_inquiry_enabled": True,
        "broker_adapter_name": "kis_paper",
        "broker_adapter_enabled": True,
        "official_balance_endpoint_confirmed": True,
        "live_order_enabled": False,
        "live_fallback_enabled": False,
        "broker_order_enabled": False,
    }


def _fake_balance_payload() -> dict[str, object]:
    return {
        "ok": True,
        "source": "kis_paper_balance",
        "snapshot": {
            "snapshot_id": "kis-paper-balance-test",
            "snapshot_ts": "2026-05-27T00:00:00+00:00",
            "account_alias": "kis_paper",
            "cash_balance": 100000.0,
            "buying_power": 100000.0,
            "market_value": 50000.0,
            "total_equity": 150000.0,
            "unrealized_pnl": 5000.0,
            "realized_pnl": 0.0,
            "source": "kis_paper_balance",
            "status": "ok",
            "created_at": "2026-05-27T00:00:00+00:00",
        },
        "positions_summary": {
            "source": "kis_paper_balance",
            "count": 1,
            "total_qty": 2,
            "market_value": 50000.0,
            "unrealized_pnl": 5000.0,
        },
        "holdings": [
            {
                "symbol": "005930",
                "name": "Samsung",
                "quantity": 2,
                "orderable_quantity": 2,
                "average_price": 22500.0,
                "purchase_amount": 45000.0,
                "current_price": 25000.0,
                "evaluation_amount": 50000.0,
                "profit_loss_amount": 5000.0,
                "profit_loss_rate": 11.11,
            }
        ],
        "account_summary": {
            "cash_total": 100000.0,
            "securities_evaluation_amount": 50000.0,
            "total_evaluation_amount": 150000.0,
            "net_asset_amount": 150000.0,
            "total_purchase_amount": 45000.0,
            "total_stock_evaluation_amount": 50000.0,
            "total_profit_loss_amount": 5000.0,
            "previous_total_asset_amount": 145000.0,
            "asset_change_amount": 5000.0,
            "asset_change_rate": 3.45,
        },
        "kis_balance": {
            "enabled": True,
            "status": "ok",
            "endpoint_path": KIS_PAPER_BALANCE_PATH,
            "tr_id": KIS_PAPER_BALANCE_TR_ID,
            "secrets_redacted": True,
            "read_only": True,
            "real_order_enabled": False,
        },
        "reason": None,
        "live_order_created": False,
        "broker_order_created": False,
        "network_call_performed": True,
    }


def test_kis_paper_balance_client_uses_required_get_headers_params_and_maps_response(monkeypatch):
    _set_kis_balance_env(monkeypatch)
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["query"] = dict(request.url.params)
        seen["headers"] = {
            "authorization": request.headers.get("authorization"),
            "appkey": request.headers.get("appkey"),
            "appsecret": request.headers.get("appsecret"),
            "tr_id": request.headers.get("tr_id"),
            "custtype": request.headers.get("custtype"),
        }
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "output1": [
                    {
                        "pdno": "005930",
                        "prdt_name": "Samsung",
                        "hldg_qty": "2",
                        "ord_psbl_qty": "1",
                        "pchs_avg_pric": "70000",
                        "pchs_amt": "140000",
                        "prpr": "75000",
                        "evlu_amt": "150000",
                        "evlu_pfls_amt": "10000",
                        "evlu_pfls_rt": "7.14",
                    }
                ],
                "output2": [
                    {
                        "dnca_tot_amt": "100000",
                        "scts_evlu_amt": "150000",
                        "tot_evlu_amt": "250000",
                        "nass_amt": "250000",
                        "pchs_amt_smtl_amt": "140000",
                        "evlu_amt_smtl_amt": "150000",
                        "evlu_pfls_smtl_amt": "10000",
                        "bfdy_tot_asst_evlu_amt": "240000",
                        "asst_icdc_amt": "10000",
                        "asst_icdc_erng_rt": "4.16",
                    }
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        payload = KisPaperBalanceClient(http_client=http_client).fetch_balance()

    assert seen["method"] == "GET"
    assert seen["path"] == KIS_PAPER_BALANCE_PATH
    assert seen["headers"]["tr_id"] == KIS_PAPER_BALANCE_TR_ID
    assert seen["headers"]["custtype"] == "P"
    assert str(seen["headers"]["authorization"]).startswith("Bearer ")
    assert seen["query"] == {
        "CANO": "12345678",
        "ACNT_PRDT_CD": "01",
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "01",
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "00",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }
    assert payload["source"] == "kis_paper_balance"
    assert payload["holdings"][0]["symbol"] == "005930"
    assert payload["holdings"][0]["quantity"] == 2
    assert payload["account_summary"]["cash_total"] == 100000.0
    assert payload["snapshot"]["total_equity"] == 250000.0
    assert payload["network_call_performed"] is True


def test_paper_portfolio_default_disabled_uses_local_snapshot_fallback(client, monkeypatch):
    def fail_fetch(self):
        raise AssertionError("KIS balance client must not be called while disabled")

    monkeypatch.setattr(KisPaperBalanceClient, "fetch_balance", fail_fetch)

    response = client.get("/api/paper/portfolio")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "paper_portfolio_snapshots"
    assert payload["network_call_performed"] is False
    assert payload["kis_balance"]["status"] == "fallback"
    assert "KIS_PAPER_BALANCE_DISABLED" in payload["kis_balance"]["reason_codes"]


def test_paper_portfolio_enabled_paper_mode_calls_kis_balance_client_without_secret_logs(
    client,
    monkeypatch,
    caplog,
):
    secret = "PHASE10_" + "SECRET_" + "SENTINEL_" + "VALUE"
    _set_kis_balance_env(monkeypatch, secret=secret)
    calls: list[str] = []

    def fake_load(self):
        return _enabled_paper_config(), []

    def fake_fetch(self):
        calls.append("called")
        return _fake_balance_payload()

    monkeypatch.setattr(PaperConfigService, "load", fake_load)
    monkeypatch.setattr(KisPaperBalanceClient, "fetch_balance", fake_fetch)

    with caplog.at_level(logging.INFO):
        response = client.get("/api/paper/portfolio")

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, ensure_ascii=False)
    assert calls == ["called"]
    assert payload["source"] == "kis_paper_balance"
    assert payload["network_call_performed"] is True
    assert payload["live_order_created"] is False
    assert payload["broker_order_created"] is False
    assert payload["kis_balance"]["tr_id"] == KIS_PAPER_BALANCE_TR_ID
    assert secret not in serialized
    assert secret not in caplog.text


def test_paper_portfolio_blocks_kis_balance_when_real_order_flag_is_true(client, monkeypatch):
    _set_kis_balance_env(monkeypatch)
    monkeypatch.setenv("ENABLE_REAL_ORDER", "true")

    def fake_load(self):
        return _enabled_paper_config(), []

    def fail_fetch(self):
        raise AssertionError("KIS balance client must not be called when real order flag is true")

    monkeypatch.setattr(PaperConfigService, "load", fake_load)
    monkeypatch.setattr(KisPaperBalanceClient, "fetch_balance", fail_fetch)

    response = client.get("/api/paper/portfolio")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "paper_portfolio_snapshots"
    assert payload["network_call_performed"] is False
    assert "ENABLE_REAL_ORDER_MUST_BE_FALSE" in payload["kis_balance"]["reason_codes"]
