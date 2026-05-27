from __future__ import annotations

import json
from datetime import date

from sqlalchemy import func, select

from backend.app.models.tables import PaperBotDecision, PaperBotRun, PaperOrder, ScreenResult
from backend.app.services.paper_bot_service import PaperBotService


def _write_bot_config(
    tmp_path,
    *,
    enabled: bool = True,
    auto_submit: bool = False,
    kill_switch: bool = False,
    max_auto_submit_orders: int = 1,
    max_order_qty: int = 1,
    max_order_notional: float = 100000.0,
) -> None:
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
  max_auto_submit_orders: {max_auto_submit_orders}
  max_order_qty: {max_order_qty}
  max_order_notional: {max_order_notional}
  default_strategy: trend_breakout
  sync_enabled: false
  notification_enabled: false
  report_generation_enabled: false
""",
        encoding="utf-8",
    )


def _write_paper_config(tmp_path) -> None:
    tmp_path.joinpath("paper.yaml").write_text(
        """
paper:
  mode: "paper"
  enabled: true
  can_create: true
  can_simulate_fills: false
  preview_only: false
  kill_switch_enabled: false
  network_enabled: false
  live_order_enabled: false
  broker_order_enabled: false
risk_gate:
  allow_buy_preview: true
  allow_sell_preview: true
  allow_short_sell: false
  max_order_qty: 20
  max_order_notional: 2000
audit:
  persistence_enabled: false
  sanitize_enabled: true
simulator:
  enabled: false
  auto_fill_on_create: false
""",
        encoding="utf-8",
    )


def _screen_result(symbol: str, *, total_score: float = 87.5) -> ScreenResult:
    return ScreenResult(
        trade_date=date(2026, 5, 27),
        symbol=symbol,
        strategy_tag="trend_breakout",
        passed=True,
        pass_flags='{"trend":true}',
        failed_conditions="[]",
        reason_summary="passed for bot preview",
        metadata_json="{}",
        risk_flags_json="{}",
        score_breakdown_json="{}",
        data_quality_flags_json="{}",
        total_score=total_score,
        entry_price=100.0,
        stop_price=94.0,
        target_price=118.0,
        risk_per_share=6.0,
        reward_risk_ratio=3.0,
        position_size=10,
        position_notional=1000.0,
    )


def _seed_passed_screen_result(db_session) -> None:
    db_session.add(_screen_result("KR009"))
    db_session.commit()


def _seed_two_passed_screen_results(db_session) -> None:
    db_session.add_all([_screen_result("KR009", total_score=90.0), _screen_result("KR010", total_score=80.0)])
    db_session.commit()


def _enable_local_paper_submit(monkeypatch) -> None:
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRADING_CAN_CREATE", "true")
    monkeypatch.setenv("PAPER_TRADING_KILL_SWITCH", "false")
    monkeypatch.delenv("PAPER_TRADING_NETWORK_ENABLED", raising=False)
    monkeypatch.setenv("ENABLE_REAL_ORDER", "false")


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


def test_paper_bot_auto_submit_is_capped_per_run(db_session, tmp_path, monkeypatch) -> None:
    _write_bot_config(
        tmp_path,
        enabled=True,
        auto_submit=True,
        kill_switch=False,
        max_auto_submit_orders=1,
        max_order_qty=20,
        max_order_notional=2000.0,
    )
    _write_paper_config(tmp_path)
    _seed_two_passed_screen_results(db_session)
    _enable_local_paper_submit(monkeypatch)
    monkeypatch.setenv("PAPER_BOT_AUTO_SUBMIT", "true")
    monkeypatch.setattr(
        PaperBotService,
        "_session_status",
        staticmethod(
            lambda: {
                "session_checked": True,
                "session_check_passed": True,
                "session_state": "open",
                "session": "regular",
                "trade_date": "2026-05-27",
                "reason_codes": [],
            }
        ),
    )
    service = PaperBotService(db_session, config_dir=tmp_path)

    result = service.run_once(auto_submit=True)
    paper_orders_count = int(db_session.scalar(select(func.count()).select_from(PaperOrder)) or 0)

    assert result["auto_submit_allowed"] is True
    assert result["decision_count"] == 2
    assert result["submitted_count"] == 1
    assert result["decisions"][0]["action"] == "submitted"
    assert result["decisions"][1]["action"] == "submit_blocked"
    assert "PAPER_BOT_MAX_SUBMITS_PER_RUN_REACHED" in result["decisions"][1]["reason_codes"]
    assert paper_orders_count == 1
