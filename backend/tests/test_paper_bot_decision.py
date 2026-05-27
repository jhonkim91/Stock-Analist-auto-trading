from __future__ import annotations

import json
from datetime import date

from sqlalchemy import func, select

from backend.app.models.tables import PaperBotDecision, PaperBotRun, PaperOrder, ScreenResult
from backend.app.services.paper_bot_service import PaperBotService


def _write_bot_config(tmp_path, *, enabled: bool = True, auto_submit: bool = False, kill_switch: bool = False) -> None:
    tmp_path.joinpath("bot.yaml").write_text(
        f"""
bot:
  enabled: {str(enabled).lower()}
  scheduler_enabled: false
  auto_submit: {str(auto_submit).lower()}
  kill_switch_enabled: {str(kill_switch).lower()}
  mode: run_once
  loop_interval_seconds: 300
  max_candidates: 5
  default_strategy: trend_breakout
  sync_enabled: false
  notification_enabled: false
  report_generation_enabled: false
""",
        encoding="utf-8",
    )


def _seed_passed_screen_result(db_session) -> None:
    db_session.add(
        ScreenResult(
            trade_date=date(2026, 5, 27),
            symbol="KR009",
            strategy_tag="trend_breakout",
            passed=True,
            pass_flags='{"trend":true}',
            failed_conditions="[]",
            reason_summary="passed for bot preview",
            metadata_json="{}",
            risk_flags_json="{}",
            score_breakdown_json="{}",
            data_quality_flags_json="{}",
            total_score=87.5,
            entry_price=100.0,
            stop_price=94.0,
            target_price=118.0,
            risk_per_share=6.0,
            reward_risk_ratio=3.0,
            position_size=10,
            position_notional=1000.0,
        )
    )
    db_session.commit()


def test_paper_bot_run_once_creates_preview_decision_without_submit(db_session, tmp_path, monkeypatch) -> None:
    _write_bot_config(tmp_path, enabled=True, auto_submit=False, kill_switch=False)
    _seed_passed_screen_result(db_session)
    monkeypatch.delenv("PAPER_BOT_AUTO_SUBMIT", raising=False)
    service = PaperBotService(db_session, config_dir=tmp_path)

    result = service.run_once(auto_submit=False)

    run = db_session.scalar(select(PaperBotRun).where(PaperBotRun.run_id == result["run_id"]))
    decision = db_session.scalar(select(PaperBotDecision).where(PaperBotDecision.run_id == result["run_id"]))
    paper_orders_count = int(db_session.scalar(select(func.count()).select_from(PaperOrder)) or 0)

    assert result["status"] == "completed_safely"
    assert result["mode"] == "run_once"
    assert result["decision_count"] == 1
    assert result["submitted_count"] == 0
    assert result["paper_order_submitted"] is False
    assert result["auto_submit_allowed"] is False
    assert result["decisions"][0]["action"] == "preview"
    assert result["decisions"][0]["symbol"] == "KR009"
    assert result["decisions"][0]["risk_passed"] is True
    assert run.decision_count == 1
    assert run.submitted_count == 0
    assert decision.action == "preview"
    assert decision.paper_order_id is None
    assert paper_orders_count == 0


def test_paper_bot_auto_submit_requires_config_request_and_session(db_session, tmp_path, monkeypatch) -> None:
    _write_bot_config(tmp_path, enabled=True, auto_submit=False, kill_switch=False)
    _seed_passed_screen_result(db_session)
    monkeypatch.setenv("PAPER_BOT_AUTO_SUBMIT", "false")
    service = PaperBotService(db_session, config_dir=tmp_path)

    result = service.run_once(auto_submit=True)
    serialized = json.dumps(result, ensure_ascii=False)

    assert result["auto_submit_requested"] is True
    assert result["auto_submit_allowed"] is False
    assert result["submitted_count"] == 0
    assert result["paper_order_submitted"] is False
    assert "PAPER_BOT_AUTO_SUBMIT_DISABLED" in serialized


def test_paper_bot_kill_switch_blocks_decisions(db_session, tmp_path) -> None:
    _write_bot_config(tmp_path, enabled=True, auto_submit=True, kill_switch=True)
    _seed_passed_screen_result(db_session)
    service = PaperBotService(db_session, config_dir=tmp_path)

    result = service.run_once(auto_submit=True)

    assert result["status"] == "blocked"
    assert result["decision_count"] == 0
    assert result["auto_submit_allowed"] is False
    assert "PAPER_BOT_KILL_SWITCH_ACTIVE" in result["reason_codes"]
