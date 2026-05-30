from __future__ import annotations

from pathlib import Path

from backend.app.main import app

ROOT = Path(__file__).resolve().parents[2]


def test_goal_documents_gated_live_policy():
    """goal.md는 실계좌 라이브 주문이 다중 게이트로 활성화됐음을 문서화한다(기본 차단)."""
    goal = (ROOT / "goal.md").read_text(encoding="utf-8")

    assert "| Phase 19 | 완료 |" in goal
    assert "Live Gate" in goal
    assert "실계좌" in goal
    assert "LIVE_TRADING_ENABLED" in goal
    assert "ENABLE_REAL_ORDER" in goal
    # 라이브 실행은 실제 KIS API로 미검증 — 최초 1건 최소 수량 확인을 문서가 명시해야 한다.
    assert "최소 수량" in goal


def test_live_public_routes_exist_and_are_gated_off_by_default(client):
    route_paths = {getattr(route, "path", "") for route in app.routes}

    assert "/api/reports/automation/status" in route_paths
    assert "/api/reports/automation/run-once" in route_paths
    assert "/api/live/status" in route_paths
    assert "/api/kis/orders/status" in route_paths
    assert "/api/kis/orders/submit" in route_paths
    assert not any(path.startswith("/api/kis/broker") for path in route_paths)
    assert not any(path.startswith("/api/kis/websocket") for path in route_paths)
    status = client.get("/api/live/status")
    submit = client.post("/api/kis/orders/submit", json={"symbol": "005930", "confirm": True})
    assert status.status_code == 200
    assert submit.status_code == 200
    assert status.json()["can_submit"] is False
    assert status.json()["reason_codes"]
    assert submit.json()["status"] == "submit_blocked"
    assert submit.json()["live_order_created"] is False
    assert submit.json()["network_call_performed"] is False


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
