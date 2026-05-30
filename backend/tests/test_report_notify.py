from __future__ import annotations

import json
from datetime import date
from textwrap import dedent

from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.models.tables import NotificationDeliveryLog, NotificationEvent, PaperPortfolioSnapshot, PaperPosition, Report, utc_now
from backend.app.services.notification_service import NotificationService
from backend.app.services.report_notification_service import ReportNotificationService
from backend.app.services.report_service import REPORT_DIR, ReportService


def _create_report(report_id: str, markdown: str, report_type: str = "daily") -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{report_id}.md"
    path.write_text(markdown, encoding="utf-8")
    with SessionLocal() as db:
        db.add(
            Report(
                report_id=report_id,
                report_date=date(2026, 5, 27),
                report_type=report_type,
                version="test",
                path=str(path),
            )
        )
        db.commit()


def _notification_rows() -> tuple[list[NotificationEvent], list[NotificationDeliveryLog]]:
    with SessionLocal() as db:
        events = list(db.scalars(select(NotificationEvent).order_by(NotificationEvent.created_at)).all())
        logs = list(db.scalars(select(NotificationDeliveryLog).order_by(NotificationDeliveryLog.created_at)).all())
        return events, logs


def _write_mock_config(tmp_path, *, channel_type: str = "discord", mode: str = "mock") -> None:
    tmp_path.joinpath("notifications.yaml").write_text(
        dedent(
            f"""
            notifications:
              enabled: true
              default_dry_run: false
              channels:
                discord_ops:
                  type: {channel_type}
                  enabled: true
                  mode: {mode}
                  webhook_env: PHASE6_DISCORD_WEBHOOK_URL
                  bot_token_env: PHASE6_TELEGRAM_BOT_TOKEN
                  chat_id_env: PHASE6_TELEGRAM_CHAT_ID
                  dry_run: false
                  allowed_mentions:
                    parse: []
                  parse_mode: null
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _seed_portfolio_snapshot(db_session) -> None:
    now = utc_now()
    db_session.add_all(
        [
            PaperPortfolioSnapshot(
                snapshot_id="phase8-portfolio-snapshot",
                snapshot_ts=now,
                account_alias="paper-demo",
                cash_balance=1000.0,
                buying_power=900.0,
                market_value=330.0,
                total_equity=1330.0,
                unrealized_pnl=30.0,
                realized_pnl=0.0,
                metadata_json='{"raw_account_marker":"PHASE8_ACCOUNT_SHOULD_NOT_LEAK"}',
            ),
            PaperPosition(
                symbol="KR009",
                strategy_tag="phase8",
                qty=3,
                avg_price=100.0,
                last_price=110.0,
                market_value=330.0,
                unrealized_pnl=30.0,
                account_alias="paper-demo",
            ),
        ]
    )
    db_session.commit()


def test_report_notify_endpoint_logs_dry_run_delivery_without_secret_leak(client):
    report_id = "phase6-disabled-report"
    secret_marker = "PHASE6_SECRET_SHOULD_NOT_LEAK"
    _create_report(
        report_id,
        f"# Daily Market Report\n\n- KIS_APP_SECRET={secret_marker}\n- normal summary line",
    )

    response = client.post(f"/api/reports/{report_id}/notify", json={"mode": "summary"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "dry_run"
    assert payload["ok"] is True
    assert payload["report_preserved"] is True
    assert payload["secrets_redacted"] is True
    assert all(length <= payload["max_message_length"] for length in payload["message_lengths"])
    serialized = json.dumps(payload, ensure_ascii=False)
    assert secret_marker not in serialized

    events, logs = _notification_rows()
    assert len(events) == 1
    assert len(logs) == 1
    assert events[0].event_type == "report_notify"
    assert events[0].status == "dry_run"
    assert logs[0].status == "dry_run"
    assert logs[0].attempt_count == 0
    assert secret_marker not in events[0].payload_summary_json


def test_long_report_is_split_and_summary_file_metadata_is_channel_safe(db_session, tmp_path):
    report_id = "phase6-long-report"
    long_body = "\n".join(f"- row {idx}: {'x' * 120}" for idx in range(120))
    _create_report(report_id, f"# Weekly Strategy Review\n\n{long_body}", report_type="weekly")
    _seed_portfolio_snapshot(db_session)
    _write_mock_config(tmp_path, channel_type="discord", mode="mock")

    result = ReportNotificationService(db_session, config_dir=tmp_path).notify(
        report_id=report_id,
        mode="summary_and_file",
        channel_alias="discord_ops",
        dry_run=False,
    )

    assert result["status"] == "mock_sent"
    assert result["delivered"] is True
    assert result["message_count"] > 1
    assert all(length <= 1900 for length in result["message_lengths"])
    assert result["payload_shape"]["allowed_mentions_parse"] == []
    assert result["payload_shape"]["attachment_method"] == "file"
    assert result["attachment"]["included"] is True
    assert result["attachment"]["filename"] == f"{report_id}.md"
    assert result["portfolio_snapshot"]["source"] == "paper_portfolio_snapshots"
    assert result["portfolio_snapshot"]["snapshot_id"] == "phase8-portfolio-snapshot"
    assert result["portfolio_snapshot"]["total_equity"] == 1330.0
    assert result["portfolio_snapshot"]["positions_count"] == 1
    assert result["portfolio_snapshot"]["network_call_performed"] is False

    events, logs = _notification_rows()
    assert events[-1].status == "mock_sent"
    assert "phase8-portfolio-snapshot" in events[-1].payload_summary_json
    assert "PHASE8_ACCOUNT_SHOULD_NOT_LEAK" not in events[-1].payload_summary_json
    assert logs[-1].status == "mock_sent"
    assert logs[-1].delivered_at is not None


def test_delivery_failure_is_logged_without_corrupting_report(db_session, tmp_path, monkeypatch):
    report_id = "phase6-failure-report"
    _create_report(report_id, "# Daily Market Report\n\n- delivery failure should not corrupt report")
    _write_mock_config(tmp_path, channel_type="discord", mode="live")
    monkeypatch.setenv("PHASE6_DISCORD_WEBHOOK_URL", "configured-but-not-used")

    def _raise_delivery(self, raw, message):
        raise RuntimeError("forced delivery failure")

    monkeypatch.setattr(NotificationService, "dispatch", _raise_delivery)

    result = ReportNotificationService(db_session, config_dir=tmp_path).notify(
        report_id=report_id,
        mode="summary",
        channel_alias="discord_ops",
        dry_run=False,
    )
    preserved = ReportService(db_session).get_report(report_id, include_markdown=True)
    delivery_logs_count = int(db_session.scalar(select(func.count()).select_from(NotificationDeliveryLog)) or 0)

    assert result["status"] == "failed"
    assert result["ok"] is False
    assert "DELIVERY_FAILED" in result["reason_codes"]
    assert preserved["report_id"] == report_id
    assert "delivery failure should not corrupt report" in preserved["markdown"]
    assert delivery_logs_count == 1
    log = db_session.scalar(select(NotificationDeliveryLog))
    assert log is not None
    assert log.status == "failed"
    assert log.last_error_code == "DELIVERY_FAILED"
