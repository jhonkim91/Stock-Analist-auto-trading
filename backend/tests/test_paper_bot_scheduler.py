from __future__ import annotations

import json

from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.jobs import paper_bot_runner
from backend.app.models.tables import Order, PaperOrder
from backend.app.services.paper_bot_service import PaperBotService


def _counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "orders": int(db.scalar(select(func.count()).select_from(Order)) or 0),
            "paper_orders": int(db.scalar(select(func.count()).select_from(PaperOrder)) or 0),
        }


def test_paper_bot_defaults_disabled_without_scheduler_loop(db_session, monkeypatch):
    monkeypatch.delenv("PAPER_BOT_AUTO_SUBMIT", raising=False)
    monkeypatch.delenv("PAPER_BOT_SCHEDULER_ENABLED", raising=False)
    service = PaperBotService(db_session)

    status = service.status()
    result = service.run_once(auto_submit=True)

    assert status["enabled"] is False
    assert status["scheduler_enabled"] is False
    assert status["auto_submit"] is False
    assert status["loop_allowed"] is False
    assert status["auto_submit_allowed"] is False
    assert "PAPER_BOT_DISABLED" in status["reason_codes"]
    assert "PAPER_BOT_SCHEDULER_DISABLED" in status["reason_codes"]
    assert result["paper_order_submitted"] is False
    assert result["auto_submit_requested"] is True
    assert result["auto_submit_allowed"] is False
    assert result["live_order_created"] is False
    assert result["broker_order_created"] is False
    assert result["network_call_performed"] is False
    assert {step["name"] for step in result["steps"]} == {
        "candidate_screening",
        "signal_selection",
        "risk_guard",
        "order_preview",
        "paper_submit",
        "polling_sync",
        "notification",
        "report_generation",
    }
    assert _counts() == {"orders": 0, "paper_orders": 0}


def test_paper_bot_api_and_settings_are_disabled_by_default(client):
    before = _counts()

    status = client.get("/api/paper/bot/status")
    run = client.post("/api/paper/bot/run", json={"auto_submit": True})
    settings = client.get("/api/settings")

    assert status.status_code == 200
    assert status.json()["scheduler_enabled"] is False
    assert status.json()["auto_submit_allowed"] is False
    assert run.status_code == 200
    assert run.json()["paper_order_submitted"] is False
    assert run.json()["network_call_performed"] is False
    assert settings.status_code == 200
    assert settings.json()["bot"]["bot"]["enabled"] is False
    assert settings.json()["bot"]["bot"]["auto_submit"] is False
    assert settings.json()["bot"]["bot"]["scheduler_enabled"] is False
    assert _counts() == before


def test_bot_api_routes_are_disabled_by_default(client):
    before = _counts()

    status = client.get("/api/bot/status")
    run = client.post("/api/bot/run-once", json={"auto_submit": True})
    stop = client.post("/api/bot/stop")

    assert status.status_code == 200
    assert status.json()["supported_modes"] == ["manual", "run_once", "scheduled"]
    assert status.json()["auto_submit_allowed"] is False
    assert run.status_code == 200
    assert run.json()["paper_order_submitted"] is False
    assert run.json()["network_call_performed"] is False
    assert stop.status_code == 200
    assert stop.json()["status"] == "stopped"
    assert stop.json()["loop_allowed"] is False
    assert _counts() == before


def test_paper_bot_runner_once_and_loop_are_gated(capsys):
    before = _counts()

    once_code = paper_bot_runner.main(["--once"])
    once_output = json.loads(capsys.readouterr().out)
    loop_code = paper_bot_runner.main(["--loop", "--max-iterations", "1"])
    loop_output = json.loads(capsys.readouterr().out)

    assert once_code == 0
    assert once_output["paper_order_submitted"] is False
    assert once_output["network_call_performed"] is False
    assert loop_code == 0
    assert loop_output["status"] == "loop_disabled"
    assert loop_output["loop_allowed"] is False
    assert loop_output["network_call_performed"] is False
    assert _counts() == before
