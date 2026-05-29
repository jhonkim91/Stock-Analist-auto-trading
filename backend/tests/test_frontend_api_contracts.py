from __future__ import annotations

import json
import re
from pathlib import Path

from backend.app.main import app

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_FILES = [
    "frontend/lib/api.ts",
    "frontend/lib/paperApi.ts",
    "frontend/lib/notificationApi.ts",
    "frontend/components/paper-mode-banner.tsx",
    "frontend/app/paper/page.tsx",
    "frontend/app/bot/page.tsx",
    "frontend/app/portfolio/page.tsx",
    "frontend/app/reports/page.tsx",
    "frontend/app/settings/page.tsx",
]

SECRET_PATTERN = re.compile(
    r"https://discord\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]{20,}"
    r"|\b[0-9]{8,10}:[A-Za-z0-9_-]{30,}\b"
    r"|(KIS_(APP_KEY|APP_SECRET|ACCESS_TOKEN|REFRESH_TOKEN)\s*[:=]\s*[\"']?"
    r"(?!\*|<|your|placeholder|env|None|null)[A-Za-z0-9._\-]{12,})"
    r"|(access_token|refresh_token)\s*[\"']?\s*:\s*[\"']"
    r"(?!\*\*\*REDACTED\*\*\*)[A-Za-z0-9._\-]{16,}[\"']"
    r"|(account(_no|_number)?|cano|chat_id)\s*[:=]\s*[\"']?-?[0-9]{6,}",
    re.IGNORECASE,
)
FORBIDDEN_LIVE_COPY = re.compile(
    r"실거래\s*(가능|준비|주문|체결)|live[- ]?trading ready|live submit|live order button",
    re.IGNORECASE,
)


def _frontend_text(relative_path: str) -> str:
    return ROOT.joinpath(relative_path).read_text(encoding="utf-8")


def test_frontend_static_contracts_are_paper_only_and_redacted():
    combined = "\n".join(_frontend_text(path) for path in FRONTEND_FILES)
    paper_page = _frontend_text("frontend/app/paper/page.tsx")

    for endpoint in (
        "/api/paper/status",
        "/api/paper/orders/preview",
        "/api/paper/orders/submit",
        "/api/paper/orders/cancel",
        "/api/paper/orders",
        "/api/paper/fills",
        "/api/paper/positions",
        "/api/paper/portfolio",
        "/api/paper/sync",
        "/api/bot/status",
        "/api/bot/run-once",
        "/api/bot/stop",
        "/api/notifications/status",
        "/api/notifications/test",
        "/api/settings/runtime-env",
        "/api/settings/runtime-env/toggle",
        "/api/settings/runtime-env/preset",
    ):
        assert endpoint in combined

    assert "/api/reports/${encodeURIComponent(reportId)}/notify" in combined
    assert "모의투자" in combined
    assert "즉시 반영" in combined
    assert "실거래 아님" in combined
    assert "paper only" in combined
    assert "confirm" in combined
    assert "idempotency_key" in combined
    assert "data-tooltip" in combined
    assert "클릭하면" in combined
    assert "실계좌 주문은 이 화면에서 켤 수 없습니다" in combined
    assert "fallbackEnvPresets" in combined
    assert "dry-run으로 검증" in combined
    assert not SECRET_PATTERN.search(combined)
    assert not FORBIDDEN_LIVE_COPY.search(combined)
    assert "/api/kis/orders" not in combined
    assert "/api/broker/orders" not in combined


def test_frontend_referenced_api_contracts_are_fail_closed(client):
    route_paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/reports/{report_id}/notify" in route_paths
    assert "/api/settings/runtime-env/preset" in route_paths

    status = client.get("/api/paper/status")
    submit = client.post(
        "/api/paper/orders/submit",
        json={
            "symbol": "KR009",
            "side": "buy",
            "qty": 1,
            "confirm": False,
            "idempotency_key": "frontend-contract-submit",
        },
    )
    cancel = client.post(
        "/api/paper/orders/cancel",
        json={
            "paper_order_id": "frontend-contract-order",
            "confirm": True,
            "idempotency_key": "frontend-contract-cancel",
        },
    )
    sync = client.post("/api/paper/sync", json={"scope": "all"})
    orders = client.get("/api/paper/orders")
    fills = client.get("/api/paper/fills")
    portfolio = client.get("/api/paper/portfolio")

    for response in (status, submit, cancel, sync, orders, fills, portfolio):
        assert response.status_code == 200
        serialized = json.dumps(response.json(), ensure_ascii=False)
        assert not SECRET_PATTERN.search(serialized)

    status_payload = status.json()
    submit_payload = submit.json()
    cancel_payload = cancel.json()
    sync_payload = sync.json()
    orders_payload = orders.json()
    fills_payload = fills.json()
    portfolio_payload = portfolio.json()

    assert status_payload["live_order_created"] is False
    assert submit_payload["paper_order_created"] is False
    assert submit_payload["live_order_created"] is False
    assert submit_payload["broker_order_created"] is False
    assert submit_payload["network_call_performed"] is False
    assert "PAPER_CONFIRM_TRUE_REQUIRED" in submit_payload["reason_codes"]
    assert cancel_payload["cancel_supported"] is False
    assert cancel_payload["order_cancelled"] is False
    assert "PAPER_ORDER_NOT_FOUND" in cancel_payload["reason_codes"]
    assert sync_payload["sync_performed"] is False
    assert sync_payload["synthetic_positions_touched"] is False
    assert orders_payload["live_order_created"] is False
    assert fills_payload["network_call_performed"] is False
    assert portfolio_payload["separation_contract"]["mixed"] is False
