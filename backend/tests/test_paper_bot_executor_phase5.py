from __future__ import annotations

import json
from datetime import date

from sqlalchemy import func, select

from backend.app.models.tables import PaperBotDecision, PaperBotRun, PaperOrder, PaperPosition, ScreenResult, SymbolMaster, utc_now
from backend.app.services.paper_bot_executor import PaperBotExecutor
from backend.app.workers.realtime_market_worker import realtime_market_worker


class _OpenSessionService:
    def session_at(self):
        return {
            "session": "regular",
            "session_state": "open",
            "trade_date": "2026-05-27",
            "current_session_allows_preview": True,
            "reason_codes": [],
        }


def _write_bot_config(tmp_path, *, max_auto_submit_orders: int = 3) -> None:
    tmp_path.joinpath("bot.yaml").write_text(
        f"""
bot:
  enabled: true
  scheduler_enabled: false
  auto_submit: false
  kill_switch_enabled: false
  mode: run_once
  loop_interval_seconds: 300
  max_candidates: 5
  max_auto_submit_orders: {max_auto_submit_orders}
  max_order_qty: 100
  max_order_notional: 1000000
  default_strategy: trend_breakout
  sync_enabled: false
  notification_enabled: false
  report_generation_enabled: false
""",
        encoding="utf-8",
    )


def _write_paper_config(tmp_path, *, realtime_enabled: bool = False) -> None:
    tmp_path.joinpath("paper.yaml").write_text(
        f"""
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
  max_order_qty: 1000000
  max_order_notional: 100000000
audit:
  persistence_enabled: false
  sanitize_enabled: true
simulator:
  enabled: false
  auto_fill_on_create: false
realtime:
  enabled: {str(realtime_enabled).lower()}
  mode: "polling"
  require_fresh_quote_for_orders: true
  stale_quote_threshold_seconds: 30
  heartbeat_timeout_seconds: 60
""",
        encoding="utf-8",
    )


def _enable_paper_env(monkeypatch, *, realtime_enabled: bool = False) -> None:
    monkeypatch.setenv("KIS_ENV", "paper")
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRADING_CAN_CREATE", "true")
    monkeypatch.setenv("PAPER_TRADING_KILL_SWITCH", "false")
    monkeypatch.setenv("PAPER_BOT_CONFIRM", "true")
    monkeypatch.setenv("ENABLE_REAL_ORDER", "false")
    monkeypatch.delenv("PAPER_TRADING_NETWORK_ENABLED", raising=False)
    if realtime_enabled:
        monkeypatch.setenv("PAPER_REALTIME_ENABLED", "true")
        monkeypatch.setenv("PAPER_REALTIME_REQUIRE_FRESH_QUOTES", "true")
    else:
        monkeypatch.delenv("PAPER_REALTIME_ENABLED", raising=False)
        monkeypatch.delenv("PAPER_REALTIME_REQUIRE_FRESH_QUOTES", raising=False)


def _seed_symbol_and_screen(db_session, *, metadata: dict[str, object] | None = None) -> None:
    db_session.add(
        SymbolMaster(
            symbol="KR009",
            name="KR Test",
            sector="Technology",
            industry="Software",
        )
    )
    metadata_payload = metadata or {
        "risk_metadata": {"risk_basis": "fixture", "suggested_stop_price": 94.0},
        "data_quality_flags": {"price_ok": True, "risk_ok": True},
    }
    db_session.add(
        ScreenResult(
            trade_date=date(2026, 5, 27),
            symbol="KR009",
            strategy_tag="trend_breakout",
            passed=True,
            pass_flags='{"trend":true}',
            failed_conditions="[]",
            reason_summary="passed",
            metadata_json=json.dumps(metadata_payload, ensure_ascii=False),
            risk_flags_json="{}",
            score_breakdown_json="{}",
            data_quality_flags_json='{"price_ok":true,"risk_ok":true}',
            total_score=95.0,
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


def _order_count(db_session) -> int:
    return int(db_session.scalar(select(func.count()).select_from(PaperOrder)) or 0)


def test_bot_executor_preview_dry_run_stores_skipped_without_order(db_session, tmp_path, monkeypatch) -> None:
    _write_bot_config(tmp_path)
    _write_paper_config(tmp_path)
    _enable_paper_env(monkeypatch)
    _seed_symbol_and_screen(db_session)
    service = PaperBotExecutor(db_session, config_dir=tmp_path, market_session_service=_OpenSessionService())

    result = service.preview(
        trade_date=date(2026, 5, 27),
        strategies=["trend_breakout"],
        max_candidates=3,
    )

    run = db_session.get(PaperBotRun, result["run_id"])
    decision = db_session.scalar(select(PaperBotDecision).where(PaperBotDecision.run_id == result["run_id"]))

    assert result["dry_run"] is True
    assert result["submitted_count"] == 0
    assert result["skipped_count"] == 1
    assert result["decisions"][0]["action"] == "skipped"
    assert "PAPER_BOT_DRY_RUN" in result["decisions"][0]["reason_codes"]
    assert decision is not None
    assert decision.qty == 10
    assert run is not None
    assert run.request_json
    assert _order_count(db_session) == 0


def test_bot_executor_run_submits_local_paper_order_when_all_gates_pass(db_session, tmp_path, monkeypatch) -> None:
    _write_bot_config(tmp_path)
    _write_paper_config(tmp_path)
    _enable_paper_env(monkeypatch)
    _seed_symbol_and_screen(db_session)
    service = PaperBotExecutor(db_session, config_dir=tmp_path, market_session_service=_OpenSessionService())

    result = service.run(
        trade_date=date(2026, 5, 27),
        strategies=["trend_breakout"],
        max_candidates=3,
        dry_run=False,
    )
    detail = service.get_run(run_id=result["run_id"])

    assert result["submitted_count"] == 1
    assert result["rejected_count"] == 0
    assert result["decisions"][0]["action"] == "submitted"
    assert result["paper_order_submitted"] is True
    assert result["live_order_created"] is False
    assert result["network_call_performed"] is False
    assert detail["submitted_count"] == 1
    assert _order_count(db_session) == 1


def test_bot_executor_rejects_stale_quote_before_order(db_session, tmp_path, monkeypatch) -> None:
    realtime_market_worker.quote_cache.clear()
    _write_bot_config(tmp_path)
    _write_paper_config(tmp_path, realtime_enabled=True)
    _enable_paper_env(monkeypatch, realtime_enabled=True)
    _seed_symbol_and_screen(db_session)
    service = PaperBotExecutor(db_session, config_dir=tmp_path, market_session_service=_OpenSessionService())

    result = service.run(
        trade_date=date(2026, 5, 27),
        strategies=["trend_breakout"],
        max_candidates=3,
        dry_run=False,
    )

    assert result["submitted_count"] == 0
    assert result["rejected_count"] == 1
    assert result["decisions"][0]["action"] == "rejected"
    assert "PAPER_REALTIME_STALE_QUOTE" in result["decisions"][0]["reason_codes"]
    assert _order_count(db_session) == 0


def test_bot_executor_skips_invalid_risk_metadata(db_session, tmp_path, monkeypatch) -> None:
    _write_bot_config(tmp_path)
    _write_paper_config(tmp_path)
    _enable_paper_env(monkeypatch)
    _seed_symbol_and_screen(db_session, metadata={"data_quality_flags": {"price_ok": True}})
    service = PaperBotExecutor(db_session, config_dir=tmp_path, market_session_service=_OpenSessionService())

    result = service.run(
        trade_date=date(2026, 5, 27),
        strategies=["trend_breakout"],
        max_candidates=3,
        dry_run=False,
    )

    assert result["submitted_count"] == 0
    assert result["skipped_count"] == 1
    assert result["decisions"][0]["action"] == "skipped"
    assert "RISK_METADATA_INVALID" in result["decisions"][0]["reason_codes"]
    assert _order_count(db_session) == 0


def test_bot_executor_rejects_duplicate_open_order(db_session, tmp_path, monkeypatch) -> None:
    _write_bot_config(tmp_path)
    _write_paper_config(tmp_path)
    _enable_paper_env(monkeypatch)
    _seed_symbol_and_screen(db_session)
    now = utc_now()
    db_session.add(
        PaperOrder(
            paper_order_id="paper-duplicate-open",
            created_ts=now,
            updated_ts=now,
            symbol="KR009",
            side="buy",
            qty=10,
            filled_qty=0,
            remaining_qty=10,
            order_type="limit",
            limit_price=100.0,
            stop_price=94.0,
            status="submitted",
            idempotency_key="duplicate-open",
            request_hash="hash",
            strategy_tag="trend_breakout",
            reason_codes_json="[]",
            risk_gate_json="{}",
        )
    )
    db_session.commit()
    service = PaperBotExecutor(db_session, config_dir=tmp_path, market_session_service=_OpenSessionService())

    result = service.run(
        trade_date=date(2026, 5, 27),
        strategies=["trend_breakout"],
        max_candidates=3,
        dry_run=False,
    )

    assert result["submitted_count"] == 0
    assert result["rejected_count"] == 1
    assert "PAPER_DUPLICATE_OPEN_ORDER" in result["decisions"][0]["reason_codes"]
    assert _order_count(db_session) == 1


def test_bot_executor_rejects_daily_loss_limit(db_session, tmp_path, monkeypatch) -> None:
    _write_bot_config(tmp_path)
    _write_paper_config(tmp_path)
    _enable_paper_env(monkeypatch)
    _seed_symbol_and_screen(db_session)
    db_session.add(
        PaperPosition(
            symbol="KRLOSS",
            strategy_tag="trend_breakout",
            qty=1,
            avg_price=100.0,
            realized_pnl=-3000000.0,
        )
    )
    db_session.commit()
    service = PaperBotExecutor(db_session, config_dir=tmp_path, market_session_service=_OpenSessionService())

    result = service.run(
        trade_date=date(2026, 5, 27),
        strategies=["trend_breakout"],
        max_candidates=3,
        dry_run=False,
    )

    assert result["submitted_count"] == 0
    assert result["rejected_count"] == 1
    assert "PAPER_BOT_DAILY_LOSS_LIMIT_EXCEEDED" in result["decisions"][0]["reason_codes"]
    assert _order_count(db_session) == 0
