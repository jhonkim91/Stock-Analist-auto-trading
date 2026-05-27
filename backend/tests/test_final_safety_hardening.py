from __future__ import annotations

from pathlib import Path

from backend.app.main import app

ROOT = Path(__file__).resolve().parents[2]


def test_goal_live_phases_remain_approval_gated():
    goal = (ROOT / "goal.md").read_text(encoding="utf-8")

    assert "| Phase 19 | 완료 |" in goal
    assert "| Phase 20 | preflight 차단 |" in goal
    assert "실계좌 주문" in goal
    assert "별도 명시 승인" in goal
    assert "live submit 가능 상태, live endpoint 호출, 실계좌 주문/취소/체결은 금지한다" in goal


def test_no_live_public_routes_exist_after_report_automation_addition(client):
    route_paths = {getattr(route, "path", "") for route in app.routes}

    assert "/api/reports/automation/status" in route_paths
    assert "/api/reports/automation/run-once" in route_paths
    assert not any(path.startswith("/api/live") for path in route_paths)
    assert not any(path.startswith("/api/kis/orders") for path in route_paths)
    assert not any(path.startswith("/api/kis/broker") for path in route_paths)
    assert not any(path.startswith("/api/kis/websocket") for path in route_paths)
    assert client.get("/api/live/status").status_code == 404
    assert client.post("/api/kis/orders/submit", json={"symbol": "005930"}).status_code == 404


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
