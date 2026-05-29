from __future__ import annotations

from pathlib import Path

from backend.app.main import app

ROOT = Path(__file__).resolve().parents[2]


def test_goal_live_phases_remain_approval_gated():
    goal = (ROOT / "goal.md").read_text(encoding="utf-8")

    assert "| Phase 19 | 완료 |" in goal
    assert "| Phase 20 | route scaffold 차단 |" in goal
    assert "실계좌 주문" in goal
    assert "별도 명시 승인" in goal
    assert "live public route scaffold는 등록됐지만 network call, live submit 가능 상태, 실계좌 주문/취소/체결은 금지한다" in goal


def test_live_public_routes_exist_but_are_disabled_after_approval(client):
    route_paths = {getattr(route, "path", "") for route in app.routes}

    assert "/api/reports/automation/status" in route_paths
    assert "/api/reports/automation/run-once" in route_paths
    assert "/api/live/status" in route_paths
    assert "/api/kis/orders" in route_paths
    assert "/api/kis/orders/submit" in route_paths
    assert not any(path.startswith("/api/kis/broker") for path in route_paths)
    assert not any(path.startswith("/api/kis/websocket") for path in route_paths)
    status = client.get("/api/live/status")
    submit = client.post("/api/kis/orders/submit", json={"symbol": "005930"})
    assert status.status_code == 200
    assert submit.status_code == 200
    for payload in (status.json(), submit.json()):
        assert payload["status"] == "live_disabled"
        assert payload["live_order_created"] is False
        assert payload["network_call_performed"] is False
        assert payload["endpoint_called"] is False


def test_phase12c_redacted_record_has_no_raw_secret_and_no_live_order():
    record_path = ROOT / "docs" / "research" / "kis-paper-phase12c-redacted-record.json"
    payload = record_path.read_text(encoding="utf-8")

    assert '"paper_only": true' in payload
    assert '"live_order_created": false' in payload
    assert "***REDACTED***" in payload
    assert "KIS_ACCESS_TOKEN" in payload
    assert '"configured": true' in payload
    assert "appsecret" not in payload.lower()
    assert "authorization" not in payload.lower()
