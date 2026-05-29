from __future__ import annotations

from datetime import date, datetime

from backend.app.services.market_session_service import KST, MarketSessionService


def _kst(year: int, month: int, day: int, hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=KST)


def test_krx_regular_and_after_hours_session_detection():
    service = MarketSessionService()

    regular = service.session_at(venue="KRX", as_of=_kst(2026, 5, 26, 10, 0))
    after_hours = service.session_at(venue="KRX", as_of=_kst(2026, 5, 26, 16, 10))
    windows = service.session_windows(venue="KRX", trade_date=date(2026, 5, 26))

    assert regular["venue"] == "KRX"
    assert regular["session"] == "regular"
    assert regular["session_kind"] == "regular"
    assert regular["is_trading_session"] is True
    assert regular["current_session_allows_preview"] is True

    assert after_hours["session"] == "after_hours"
    assert after_hours["session_kind"] == "after_hours"
    assert after_hours["current_session"]["trading_start"] == "15:40:00"
    assert after_hours["current_session_allows_preview"] is True

    assert {"pre_hours", "regular", "after_hours"}.issubset({str(window["name"]) for window in windows})


def test_nxt_pre_main_and_after_session_detection():
    service = MarketSessionService()

    pre_market = service.session_at(venue="NXT", as_of=_kst(2026, 5, 26, 8, 10))
    main_market = service.session_at(venue="NXT", as_of=_kst(2026, 5, 26, 9, 30))
    after_market = service.session_at(venue="NXT", as_of=_kst(2026, 5, 26, 16, 0))

    assert pre_market["session"] == "pre_market"
    assert pre_market["session_kind"] == "pre_market"
    assert pre_market["current_session_allows_preview"] is True

    assert main_market["session"] == "main"
    assert main_market["session_kind"] == "regular"
    assert main_market["current_session"]["order_acceptance_start"] == "09:00:30"

    assert after_market["session"] == "after_market"
    assert after_market["session_kind"] == "after_hours"
    assert after_market["current_session"]["trading_end"] == "20:00:00"


def test_holiday_and_outside_session_handling():
    service = MarketSessionService()

    weekend = service.session_at(venue="KRX", as_of=_kst(2026, 5, 23, 10, 0))
    outside_session = service.session_at(venue="KRX", as_of=_kst(2026, 5, 26, 6, 0))
    calendar = service.trading_calendar(
        venue="KRX",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 2),
    )

    assert weekend["is_trading_day"] is False
    assert weekend["session"] == "closed"
    assert "WEEKEND" in weekend["reason_codes"]
    assert weekend["current_session_allows_preview"] is False

    assert outside_session["is_trading_day"] is True
    assert outside_session["session"] == "closed"
    assert "OUTSIDE_SESSION_WINDOW" in outside_session["reason_codes"]
    assert outside_session["next_session"]["name"] == "pre_hours"

    assert calendar[0]["reason_code"] == "LABOR_DAY"
    assert calendar[0]["is_open"] is False
    assert calendar[1]["reason_code"] == "WEEKEND"
    assert calendar[1]["is_open"] is False


def test_preview_responses_include_session_metadata_and_keep_live_submit_disabled(client):
    broker_response = client.post(
        "/api/broker/orders/preview",
        json={
            "symbol": "KR009",
            "side": "buy",
            "qty": 10,
            "limit_price": 100.0,
            "stop_price": 90.0,
            "venue": "NXT",
            "as_of": "2026-05-26T08:10:00+09:00",
        },
    )
    paper_response = client.post(
        "/api/paper/orders/preview",
        json={
            "symbol": "KR009",
            "side": "buy",
            "qty": 10,
            "limit_price": 100.0,
            "stop_price": 90.0,
            "venue": "NXT",
            "as_of": "2026-05-26T16:00:00+09:00",
        },
    )

    assert broker_response.status_code == 200
    broker_payload = broker_response.json()
    assert broker_payload["can_submit"] is True
    assert broker_payload["paper_trading_enabled"] is True
    assert broker_payload["live_trading_enabled"] is False
    assert broker_payload["order_created"] is False
    assert broker_payload["venue"] == "NXT"
    assert broker_payload["session"] == "pre_market"
    assert broker_payload["session_metadata"]["current_session_allows_preview"] is True
    assert broker_payload["session_metadata"]["allowed_preview_sessions"]["pre_market"] is True
    assert broker_payload["session_metadata"]["operational_layer"]["live_submit_allowed"] is False
    assert broker_payload["session_metadata"]["operational_layer"]["network_call_allowed"] is False

    assert paper_response.status_code == 200
    paper_payload = paper_response.json()
    assert paper_payload["can_create"] is False
    assert paper_payload["paper_order_created"] is False
    assert paper_payload["live_order_created"] is False
    assert paper_payload["broker_order_created"] is False
    assert paper_payload["venue"] == "NXT"
    assert paper_payload["session"] == "after_market"
    assert paper_payload["session_metadata"]["current_session"]["trading_end"] == "20:00:00"
    assert paper_payload["session_metadata"]["operational_layer"]["paper_submit_allowed"] is False
