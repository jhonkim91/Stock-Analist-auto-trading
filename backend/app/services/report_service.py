from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.paths import REPORT_DIR
from backend.app.models.tables import BacktestTradeLedger, Report, ScreenResult
from backend.app.repositories.report_repository import ReportRepository
from backend.app.services.regime_service import RegimeService
from backend.app.services.sector_service import SectorService
from backend.app.services.validation_service import (
    FactorFilterAttributionService,
    StrategyParameterSnapshotService,
    ValidationReportService,
)


ReportType = Literal["daily", "weekly"]
REPORT_VERSION = "0.1.0"
WEEKLY_REVIEW_TRADING_DAYS = 5
NOT_AVAILABLE = "not_available_in_current_mvp"


@dataclass(frozen=True)
class _ReportContext:
    report_date: date
    target_results: list[ScreenResult]
    window_dates: list[date]
    window_results: list[ScreenResult]
    trade_ledger: list[BacktestTradeLedger]
    regime: dict[str, object]
    sectors: list[dict[str, object]]
    parameter_drift: dict[str, object]
    attribution: dict[str, object]


class ReportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ReportRepository(db)

    def generate_daily_report(self, report_date: date | None = None) -> dict[str, object]:
        """일간 Markdown 리포트를 생성하고 동일한 Report 저장 계약으로 보관한다."""
        return self._generate_markdown_report("daily", report_date)

    def generate_weekly_report(self, report_date: date | None = None) -> dict[str, object]:
        """주간 전략 리뷰 Markdown 리포트를 생성하고 Report 테이블에 저장한다."""
        return self._generate_markdown_report("weekly", report_date)

    def latest_markdown(self) -> dict[str, object]:
        """최신 Markdown 리포트 본문을 반환한다."""
        report = self.db.scalar(select(Report).order_by(Report.created_at.desc()).limit(1))
        if report is None:
            raise ValueError("생성된 리포트가 없습니다.")
        return self.get_report(report.report_id, include_markdown=True)

    def write_strategy_validation_summary(
        self,
        summary: dict[str, object],
        lookback_days: int = 252,
    ) -> dict[str, object]:
        """전략 validation summary를 JSON 산출물로 저장하고 API payload를 반환한다."""
        return ValidationReportService().write_strategy_validation_summary(summary, lookback_days=lookback_days)

    def list_reports(self, limit: int = 20, report_type: ReportType | None = None) -> list[dict[str, object]]:
        """저장된 리포트 목록을 최신순으로 반환하고 선택적으로 유형을 필터링한다."""
        stmt = select(Report)
        if report_type is not None:
            stmt = stmt.where(Report.report_type == report_type)
        reports = list(self.db.scalars(stmt.order_by(Report.created_at.desc()).limit(limit)).all())
        return [self._serialize_report(report, include_markdown=False) for report in reports]

    def get_report(self, report_id: str, include_markdown: bool = False) -> dict[str, object]:
        """리포트 메타데이터와 선택적 Markdown 본문을 반환한다."""
        report = self.db.get(Report, report_id)
        if report is None:
            raise ValueError("리포트를 찾을 수 없습니다.")
        return self._serialize_report(report, include_markdown=include_markdown)

    def get_markdown(self, report_id: str) -> str:
        """리포트 Markdown 본문을 UTF-8 문자열로 반환한다."""
        report = self.db.get(Report, report_id)
        if report is None:
            raise ValueError("리포트를 찾을 수 없습니다.")
        return self._read_markdown(report)

    def notify_report(
        self,
        report_id: str,
        *,
        mode: Literal["summary", "summary_and_file"] = "summary",
        channel_alias: str | None = None,
        dry_run: bool | None = None,
    ) -> dict[str, object]:
        """저장된 report를 notification channel로 전달하고 delivery log를 남긴다."""
        from backend.app.services.report_notification_service import ReportNotificationService

        return ReportNotificationService(self.db).notify(
            report_id=report_id,
            mode=mode,
            channel_alias=channel_alias,
            dry_run=dry_run,
        )

    def _generate_markdown_report(self, report_type: ReportType, report_date: date | None) -> dict[str, object]:
        target_date = self._resolve_report_date(report_date)
        context = self._build_context(target_date)
        content = self._render_report(report_type, context)
        report = self._persist_markdown_report(report_type, target_date, content)
        metadata = self._extract_metadata(content, report)
        return {
            "report_id": report.report_id,
            "report_type": report.report_type,
            "path": str(report.path),
            "chars": len(content),
            "metadata": metadata,
        }

    def _resolve_report_date(self, report_date: date | None) -> date:
        if report_date is not None:
            return report_date
        latest_date = self.db.scalar(select(ScreenResult.trade_date).order_by(ScreenResult.trade_date.desc()).limit(1))
        if latest_date is None:
            raise ValueError("screen_results 데이터가 없습니다.")
        return latest_date

    def _build_context(self, target_date: date) -> _ReportContext:
        target_results = self._results_for_date(target_date)
        window_dates = self._latest_screen_dates(target_date, WEEKLY_REVIEW_TRADING_DAYS) or [target_date]
        window_results = self._results_for_dates(window_dates)
        trade_ledger = self._trade_ledger_for_window(window_dates, target_date)
        return _ReportContext(
            report_date=target_date,
            target_results=target_results,
            window_dates=window_dates,
            window_results=window_results,
            trade_ledger=trade_ledger,
            regime=RegimeService(self.db).detect_market_regime(as_of=target_date),
            sectors=SectorService(self.db).latest_rotation(),
            parameter_drift=StrategyParameterSnapshotService(self.db).parameter_drift_check(as_of=target_date),
            attribution=FactorFilterAttributionService(self.db).calculate(
                start_date=window_dates[0] if window_dates else target_date,
                end_date=window_dates[-1] if window_dates else target_date,
                trades=trade_ledger,
                screen_results=window_results,
            ),
        )

    def _render_report(self, report_type: ReportType, context: _ReportContext) -> str:
        if report_type == "daily":
            return self._render_daily(context)
        if report_type == "weekly":
            return self._render_weekly(context)
        raise ValueError(f"지원하지 않는 리포트 유형입니다: {report_type}")

    def _persist_markdown_report(self, report_type: ReportType, report_date: date, content: str) -> Report:
        path = self._write_markdown(report_type, report_date, content)
        report = Report(
            report_id=self._report_id(report_type, report_date),
            report_date=report_date,
            report_type=report_type,
            version=REPORT_VERSION,
            path=str(path),
        )
        self.repo.save(report)
        return report

    @staticmethod
    def _write_markdown(report_type: ReportType, report_date: date, content: str) -> Path:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        path = REPORT_DIR / ReportService._report_filename(report_type, report_date)
        path.write_text(content, encoding="utf-8")
        return path

    @staticmethod
    def _report_id(report_type: ReportType, report_date: date) -> str:
        return f"{report_type}-{report_date.isoformat()}"

    @staticmethod
    def _report_filename(report_type: ReportType, report_date: date) -> str:
        prefix = "daily_report" if report_type == "daily" else "weekly_strategy_review"
        return f"{prefix}_{report_date.isoformat()}.md"

    def _results_for_date(self, target_date: date) -> list[ScreenResult]:
        return list(
            self.db.scalars(
                select(ScreenResult)
                .where(ScreenResult.trade_date == target_date)
                .order_by(ScreenResult.passed.desc(), ScreenResult.total_score.desc())
            ).all()
        )

    def _results_for_dates(self, dates: list[date]) -> list[ScreenResult]:
        if not dates:
            return []
        return list(
            self.db.scalars(
                select(ScreenResult)
                .where(ScreenResult.trade_date.in_(dates))
                .order_by(ScreenResult.trade_date.desc(), ScreenResult.passed.desc(), ScreenResult.total_score.desc())
            ).all()
        )

    def _latest_screen_dates(self, target_date: date, limit: int) -> list[date]:
        dates_desc = list(
            self.db.scalars(
                select(ScreenResult.trade_date)
                .distinct()
                .where(ScreenResult.trade_date <= target_date)
                .order_by(ScreenResult.trade_date.desc())
                .limit(limit)
            ).all()
        )
        return sorted(dates_desc)

    def _trade_ledger_for_window(self, window_dates: list[date], target_date: date) -> list[BacktestTradeLedger]:
        window_start = window_dates[0] if window_dates else target_date
        window_end = window_dates[-1] if window_dates else target_date
        return list(
            self.db.scalars(
                select(BacktestTradeLedger)
                .where(BacktestTradeLedger.exit_date >= window_start)
                .where(BacktestTradeLedger.exit_date <= window_end)
                .order_by(BacktestTradeLedger.exit_date, BacktestTradeLedger.run_id, BacktestTradeLedger.trade_index)
            ).all()
        )

    def _serialize_report(self, report: Report, include_markdown: bool) -> dict[str, object]:
        markdown = self._read_markdown(report)
        metadata = self._extract_metadata(markdown, report)
        payload: dict[str, object] = {
            "id": report.report_id,
            "report_id": report.report_id,
            "report_date": report.report_date,
            "report_type": report.report_type,
            "title": str(metadata["title"]),
            "model_version": str(metadata["model_version"]),
            "strategy_version": str(metadata["strategy_version"]),
            "data_timestamp": str(metadata["data_timestamp"]),
            "created_at": report.created_at,
            "version": report.version,
            "path": report.path,
            "metadata": metadata,
        }
        if include_markdown:
            payload["markdown"] = markdown
        return payload

    @staticmethod
    def _read_markdown(report: Report) -> str:
        path = REPORT_DIR / Path(report.path).name
        if not path.exists():
            raise ValueError("리포트 파일을 찾을 수 없습니다.")
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _extract_metadata(markdown: str, report: Report) -> dict[str, object]:
        title = next((line.removeprefix("#").strip() for line in markdown.splitlines() if line.startswith("# ")), report.report_id)
        metadata: dict[str, object] = {
            "title": title,
            "model_version": report.version,
            "strategy_version": report.version,
            "data_timestamp": report.report_date.isoformat(),
        }
        for line in markdown.splitlines():
            if line.startswith("- model_version:"):
                metadata["model_version"] = line.split(":", 1)[1].strip()
            elif line.startswith("- strategy_version:"):
                metadata["strategy_version"] = line.split(":", 1)[1].strip()
            elif line.startswith("- data_timestamp:"):
                metadata["data_timestamp"] = line.split(":", 1)[1].strip()
        parameter_drift = ReportService._extract_parameter_drift_metadata(markdown)
        if parameter_drift:
            metadata["parameter_drift"] = parameter_drift
        return metadata

    @staticmethod
    def _extract_parameter_drift_metadata(markdown: str) -> dict[str, object]:
        in_section = False
        table_headers: list[str] | None = None
        metadata: dict[str, object] = {}
        strategy_rows: list[dict[str, str]] = []
        for line in markdown.splitlines():
            if line == "## Parameter Drift Check":
                in_section = True
                continue
            if in_section and line.startswith("## "):
                break
            if not in_section:
                continue
            if line.startswith("- ") and ":" in line:
                key, value = line[2:].split(":", 1)
                metadata[key.strip()] = ReportService._parse_metadata_scalar(value.strip())
                continue
            if not (line.startswith("|") and line.endswith("|")):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if all(cell and set(cell) <= {"-", ":"} for cell in cells):
                continue
            if table_headers is None:
                table_headers = cells
                continue
            if len(cells) == len(table_headers):
                strategy_rows.append(dict(zip(table_headers, cells, strict=True)))
        if strategy_rows:
            metadata["strategies"] = strategy_rows
        return metadata

    @staticmethod
    def _parse_metadata_scalar(value: str) -> object:
        if value == "true":
            return True
        if value == "false":
            return False
        if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
            return int(value)
        return value

    @staticmethod
    def _render_daily(context: _ReportContext) -> str:
        report_date = context.report_date
        results = context.target_results
        regime = context.regime
        sectors = context.sectors
        triggered = [row for row in results if row.passed]
        rejected = [row for row in results if not row.passed][:10]
        lines: list[str] = [f"# Daily Market Report - {report_date.isoformat()}", ""]
        lines.extend(
            [
                "## Market Regime",
                f"- benchmark: {regime['benchmark']}",
                f"- regime: {regime['regime']}",
                f"- market_score: {regime['market_score']}",
                f"- close_vs_200dma: {regime['close_vs_200dma']}",
                f"- sma50_vs_200dma: {regime['sma50_vs_200dma']}",
                f"- weekly_close: {regime['weekly_close']}",
                f"- weekly_sma30: {regime['weekly_sma30']}",
                f"- weekly_sma30_slope: {regime['weekly_sma30_slope']}",
                f"- breadth_regime: {regime.get('breadth_regime')}",
                f"- breadth_score: {regime.get('breadth_score')}",
                f"- breadth_advance_decline_ratio: {regime.get('breadth_advance_decline_ratio')}",
                f"- breadth_52w_high_low_ratio: {regime.get('breadth_52w_high_low_ratio')}",
                f"- breadth_ma50_participation: {regime.get('breadth_ma50_participation')}",
                "",
                "## Sector Rotation",
                "| sector | rs_rank | trend_ok | note |",
                "|---|---:|---|---|",
            ]
        )
        for sector in sectors:
            lines.append(f"| {sector['sector']} | {sector['rs_rank']} | {sector['trend_ok']} | {sector['note']} |")

        lines.extend(
            [
                "",
                "## Triggered Candidates",
                "| symbol | strategy_tag | total_score | grade | entry_price | stop_price | target_price | risk_per_share | reward_risk_ratio | position_size | reason_summary | failed_conditions |",
                "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|---|",
            ]
        )
        for row in triggered:
            lines.append(
                f"| {row.symbol} | {row.strategy_tag} | {row.total_score:.4f} | {ReportService._grade(row.total_score)} | {row.entry_price:.2f} | "
                f"{row.stop_price:.2f} | {row.target_price:.2f} | {row.risk_per_share:.2f} | "
                f"{row.reward_risk_ratio:.2f} | {row.position_size} | {row.reason_summary} | {', '.join(ReportService._json_list(row.failed_conditions))} |"
            )

        lines.extend(
            [
                "",
                "## Rejected But Close",
                "| symbol | strategy_tag | total_score | grade | entry_price | stop_price | target_price | risk_per_share | reward_risk_ratio | position_size | reason_summary | failed_conditions |",
                "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|---|",
            ]
        )
        for row in rejected:
            failed = ", ".join(ReportService._json_list(row.failed_conditions))
            lines.append(
                f"| {row.symbol} | {row.strategy_tag} | {row.total_score:.4f} | {ReportService._grade(row.total_score)} | "
                f"{row.entry_price:.2f} | {row.stop_price:.2f} | {row.target_price:.2f} | {row.risk_per_share:.2f} | "
                f"{row.reward_risk_ratio:.2f} | {row.position_size} | {row.reason_summary} | {failed} |"
            )

        total_notional = sum(float(row.position_notional or 0) for row in triggered)
        avg_initial_risk = (
            sum(float(row.risk_per_share or 0) * int(row.position_size or 0) for row in triggered) / max(len(triggered), 1)
        )
        lines.extend(
            [
                "",
                "## Portfolio Risk",
                f"- triggered_candidates: {len(triggered)}",
                f"- proposed_notional: {round(total_notional, 2)}",
                f"- avg_initial_risk: {round(avg_initial_risk, 2)}",
                "- worst_gap_risk: not_modelled_in_phase_1",
                "- upcoming_event_risk: sample_data_only",
                "",
                "## Mock Orders For Review",
                "| symbol | side | qty | entry_type | limit_price | stop_price | comment |",
                "|---|---|---:|---|---:|---:|---|",
            ]
        )
        for row in triggered:
            lines.append(
                f"| {row.symbol} | buy | {row.position_size} | next_open_preview | {row.entry_price:.2f} | "
                f"{row.stop_price:.2f} | mock preview only, no live order |"
            )

        lines.extend(ReportService._audit_trail(report_date))
        return "\n".join(lines)

    @staticmethod
    def _render_weekly(context: _ReportContext) -> str:
        report_date = context.report_date
        window_start = context.window_dates[0] if context.window_dates else report_date
        window_end = context.window_dates[-1] if context.window_dates else report_date
        rows = context.window_results
        triggered = [row for row in rows if row.passed]
        rejected_count = len([row for row in rows if not row.passed])
        total_count = len(rows)
        screen_pass_rate = ReportService._ratio(len(triggered), total_count)
        trade_summary = ReportService._trade_ledger_summary(context.trade_ledger)
        proposed_notional = round(sum(float(row.position_notional or 0) for row in triggered), 2)
        proposed_initial_risk = round(
            sum(float(row.risk_per_share or 0) * int(row.position_size or 0) for row in triggered),
            2,
        )

        lines: list[str] = [f"# Weekly Strategy Review - {report_date.isoformat()}", ""]
        lines.extend(
            [
                "## Performance Summary",
                f"- review_window_start: {window_start.isoformat()}",
                f"- review_window_end: {window_end.isoformat()}",
                f"- review_window_basis: screen_results.trade_date",
                f"- screened_candidates: {total_count}",
                f"- passed_screen_candidates: {len(triggered)}",
                f"- screen_pass_rate: {screen_pass_rate}",
                f"- realized_trade_count: {trade_summary['trade_count']}",
                f"- realized_pnl: {trade_summary['realized_pnl']}",
                f"- realized_return: {trade_summary['realized_return']}",
                f"- win_rate: {trade_summary['win_rate']}",
                f"- average_holding_days: {trade_summary['average_holding_days']}",
                "",
                "## Risk Summary",
                f"- proposed_notional_from_screen: {proposed_notional}",
                f"- proposed_initial_risk_from_screen: {proposed_initial_risk}",
                f"- proposed_position_count: {len(triggered)}",
                f"- realized_drawdown: {NOT_AVAILABLE}",
                f"- realized_exposure: {NOT_AVAILABLE}",
                f"- open_position_risk: {NOT_AVAILABLE}",
                f"- trade_ledger_source: {trade_summary['source']}",
                "",
                "## Hit Rate By Setup",
                "| setup | screened | screen_passed | screen_pass_rate | trade_hit_rate |",
                "|---|---:|---:|---:|---|",
            ]
        )
        for row in ReportService._hit_rate_rows(rows, context.trade_ledger):
            lines.append(
                f"| {row['setup']} | {row['screened']} | {row['screen_passed']} | {row['screen_pass_rate']} | {row['trade_hit_rate']} |"
            )
        if not rows:
            lines.append(f"| {NOT_AVAILABLE} | 0 | 0 | {NOT_AVAILABLE} | {NOT_AVAILABLE} |")

        regime = context.regime
        lines.extend(
            [
                "",
                "## Regime Diagnostics",
                f"- benchmark: {regime['benchmark']}",
                f"- regime: {regime['regime']}",
                f"- market_score: {regime['market_score']}",
                f"- close_vs_200dma: {regime['close_vs_200dma']}",
                f"- sma50_vs_200dma: {regime['sma50_vs_200dma']}",
                f"- weekly_close: {regime['weekly_close']}",
                f"- weekly_sma30: {regime['weekly_sma30']}",
                f"- weekly_sma30_slope: {regime['weekly_sma30_slope']}",
                f"- breadth_regime: {regime.get('breadth_regime')}",
                f"- breadth_score: {regime.get('breadth_score')}",
                f"- breadth_advance_decline_ratio: {regime.get('breadth_advance_decline_ratio')}",
                f"- breadth_52w_high_low_ratio: {regime.get('breadth_52w_high_low_ratio')}",
                f"- breadth_ma50_participation: {regime.get('breadth_ma50_participation')}",
                f"- regime_segment_return: {NOT_AVAILABLE}",
                "",
                "## Factor/Filter Attribution",
                f"- attribution_status: {context.attribution.get('status', NOT_AVAILABLE)}",
                f"- attribution_reason: {context.attribution.get('reason') or 'none'}",
                f"- attribution_scope: {ReportService._attribution_basis_value(context.attribution, 'scope')}",
                f"- attribution_join_keys: {ReportService._attribution_join_keys(context.attribution)}",
                f"- joined_trade_count: {context.attribution.get('joined_trade_count', 0)}",
                f"- unjoined_trade_count: {context.attribution.get('unjoined_trade_count', 0)}",
                "### Realized PnL Attribution",
                "| attribution_type | dimension | value | trade_count | pnl | win_rate | avg_return | joined_trade_count | unavailable_count | status |",
                "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
            ]
        )
        for row in ReportService._attribution_pnl_rows(context.attribution):
            lines.append(
                f"| {row['attribution_type']} | {row['dimension']} | {row['value']} | {row['trade_count']} | "
                f"{row['pnl']} | {row['win_rate']} | {row['avg_return']} | {row['joined_trade_count']} | "
                f"{row['unavailable_count']} | {row['status']} |"
            )

        lines.extend(
            [
                "### Screen Filter Failure Counts",
                "| attribution_type | strategy | filter | failed_count | screened_count | status |",
                "|---|---|---|---:|---:|---|",
            ]
        )
        for row in ReportService._attribution_failure_rows(context.attribution):
            lines.append(
                f"| {row['attribution_type']} | {row['strategy_name']} | {row['filter']} | "
                f"{row['failed_count']} | {row['screened_count']} | {row['status']} |"
            )

        lines.extend(
            [
                "",
                "## Failed Trades Review",
                f"- failed_trade_count: {trade_summary['failed_trade_count']}",
                f"- loss_reason_breakdown: {trade_summary['loss_reason_breakdown']}",
                f"- stop_loss_review: {trade_summary['stop_loss_review']}",
                f"- max_adverse_excursion_review: {NOT_AVAILABLE}",
                f"- screen_rejected_candidate_count: {rejected_count}",
                "| symbol | setup | exit_date | exit_reason | pnl | return_pct | holding_days |",
                "|---|---|---|---|---:|---:|---:|",
            ]
        )
        for row in trade_summary["failed_rows"]:
            if isinstance(row, dict):
                lines.append(
                    f"| {row['symbol']} | {row['setup']} | {row['exit_date']} | {row['exit_reason']} | "
                    f"{row['pnl']} | {row['return_pct']} | {row['holding_days']} |"
                )
        if not trade_summary["failed_rows"]:
            lines.append(f"| {NOT_AVAILABLE} | {NOT_AVAILABLE} | {NOT_AVAILABLE} | {NOT_AVAILABLE} | 0 | 0 | 0 |")

        lines.extend(
            ReportService._parameter_drift_lines(
                context.parameter_drift,
                len({row.strategy_tag for row in rows}),
            )
        )

        lines.extend(ReportService._audit_trail(report_date))
        return "\n".join(lines)

    @staticmethod
    def _audit_trail(report_date: date) -> list[str]:
        return [
            "",
            "## Audit Trail",
            f"- data_timestamp: {report_date.isoformat()}",
            f"- model_version: {REPORT_VERSION}",
            f"- strategy_version: {REPORT_VERSION}",
            f"- backtest_version: {REPORT_VERSION}",
            f"- report_generated_at: {datetime.now(UTC).isoformat()}",
            "- data_source: deterministic_sample_or_csv",
            "- broker_mode: mock_preview_only",
            "",
        ]

    @staticmethod
    def _trade_ledger_summary(trades: list[BacktestTradeLedger]) -> dict[str, object]:
        if not trades:
            return {
                "source": NOT_AVAILABLE,
                "trade_count": NOT_AVAILABLE,
                "realized_pnl": NOT_AVAILABLE,
                "realized_return": NOT_AVAILABLE,
                "win_rate": NOT_AVAILABLE,
                "average_holding_days": NOT_AVAILABLE,
                "failed_trade_count": NOT_AVAILABLE,
                "loss_reason_breakdown": NOT_AVAILABLE,
                "stop_loss_review": NOT_AVAILABLE,
                "setup_rows": [],
                "failed_rows": [],
            }

        trade_count = len(trades)
        wins = [trade for trade in trades if float(trade.pnl or 0) > 0]
        failed = [trade for trade in trades if float(trade.pnl or 0) < 0]
        realized_pnl = round(sum(float(trade.pnl or 0) for trade in trades), 2)
        entry_notional = sum(float(trade.entry_price or 0) * int(trade.qty or 0) for trade in trades)
        reason_counts: dict[str, int] = {}
        for trade in failed:
            reason_counts[trade.exit_reason] = reason_counts.get(trade.exit_reason, 0) + 1
        stop_count = reason_counts.get("stop", 0)

        return {
            "source": "backtest_trade_ledger",
            "trade_count": trade_count,
            "realized_pnl": realized_pnl,
            "realized_return": ReportService._ratio_float(realized_pnl, entry_notional),
            "win_rate": ReportService._ratio(len(wins), trade_count),
            "average_holding_days": round(sum(int(trade.holding_days or 0) for trade in trades) / trade_count, 4),
            "failed_trade_count": len(failed),
            "loss_reason_breakdown": ReportService._reason_breakdown(reason_counts),
            "stop_loss_review": f"{stop_count}_stop_exits" if stop_count else "no_stop_loss_failures_in_ledger_window",
            "setup_rows": ReportService._setup_pnl_rows(trades),
            "failed_rows": ReportService._failed_trade_rows(failed),
        }

    @staticmethod
    def _attribution_basis_value(attribution: dict[str, object], key: str) -> object:
        basis = attribution.get("basis")
        if not isinstance(basis, dict):
            return NOT_AVAILABLE
        return basis.get(key, NOT_AVAILABLE)

    @staticmethod
    def _attribution_join_keys(attribution: dict[str, object]) -> str:
        return ReportService._format_metadata_list(ReportService._attribution_basis_value(attribution, "join_keys"))

    @staticmethod
    def _attribution_pnl_rows(attribution: dict[str, object]) -> list[dict[str, object]]:
        section = attribution.get("realized_pnl_attribution")
        rows = section.get("rows") if isinstance(section, dict) else None
        parsed_rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
        if not parsed_rows:
            parsed_rows = [
                {
                    "attribution_type": "realized_pnl",
                    "dimension": "strategy_name",
                    "value": NOT_AVAILABLE,
                    "trade_count": 0,
                    "pnl": NOT_AVAILABLE,
                    "win_rate": NOT_AVAILABLE,
                    "avg_return": NOT_AVAILABLE,
                    "joined_trade_count": 0,
                    "unavailable_count": 0,
                    "status": NOT_AVAILABLE,
                }
            ]
        return [ReportService._normalize_attribution_pnl_row(row) for row in parsed_rows[:50]]

    @staticmethod
    def _normalize_attribution_pnl_row(row: dict[str, object]) -> dict[str, object]:
        return {
            "attribution_type": row.get("attribution_type", "realized_pnl"),
            "dimension": row.get("dimension", NOT_AVAILABLE),
            "value": row.get("value", NOT_AVAILABLE),
            "trade_count": row.get("trade_count", 0),
            "pnl": row.get("pnl", NOT_AVAILABLE),
            "win_rate": row.get("win_rate", NOT_AVAILABLE),
            "avg_return": row.get("avg_return", NOT_AVAILABLE),
            "joined_trade_count": row.get("joined_trade_count", 0),
            "unavailable_count": row.get("unavailable_count", 0),
            "status": row.get("status", NOT_AVAILABLE),
        }

    @staticmethod
    def _attribution_failure_rows(attribution: dict[str, object]) -> list[dict[str, object]]:
        section = attribution.get("screen_filter_failure_counts")
        rows = section.get("rows") if isinstance(section, dict) else None
        parsed_rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
        if not parsed_rows:
            parsed_rows = [
                {
                    "attribution_type": "screen_filter_failure",
                    "strategy_name": NOT_AVAILABLE,
                    "filter": NOT_AVAILABLE,
                    "failed_count": 0,
                    "screened_count": 0,
                    "status": NOT_AVAILABLE,
                }
            ]
        return [ReportService._normalize_attribution_failure_row(row) for row in parsed_rows[:50]]

    @staticmethod
    def _normalize_attribution_failure_row(row: dict[str, object]) -> dict[str, object]:
        return {
            "attribution_type": row.get("attribution_type", "screen_filter_failure"),
            "strategy_name": row.get("strategy_name", NOT_AVAILABLE),
            "filter": row.get("filter", NOT_AVAILABLE),
            "failed_count": row.get("failed_count", 0),
            "screened_count": row.get("screened_count", 0),
            "status": row.get("status", NOT_AVAILABLE),
        }

    @staticmethod
    def _parameter_drift_lines(parameter_drift: dict[str, object], active_setup_count: int) -> list[str]:
        status = str(parameter_drift.get("status", NOT_AVAILABLE))
        reason = parameter_drift.get("reason")
        no_drift_detected = status == "no_drift"
        lines = [
            "",
            "## Parameter Drift Check",
            f"- parameter_history_source: {parameter_drift.get('history_source', NOT_AVAILABLE)}",
            f"- parameter_snapshot_status: {status}",
            f"- parameter_snapshot_as_of: {parameter_drift.get('as_of', NOT_AVAILABLE)}",
            f"- comparison_available: {ReportService._bool_text(parameter_drift.get('comparison_available', False))}",
            f"- compared_strategy_count: {parameter_drift.get('compared_strategy_count', 0)}",
            f"- missing_snapshot_count: {parameter_drift.get('missing_snapshot_count', 0)}",
            f"- drifted_strategy_count: {parameter_drift.get('drifted_strategy_count', 0)}",
            f"- drifted_parameter_count: {parameter_drift.get('drifted_parameter_count', 0)}",
            f"- changed_keys: {ReportService._format_changed_keys(parameter_drift)}",
            f"- unchanged_keys_count: {parameter_drift.get('unchanged_keys_count', 0)}",
            f"- snapshot_dates: {ReportService._format_metadata_list(parameter_drift.get('snapshot_dates'))}",
            f"- effective_dates: {ReportService._format_metadata_list(parameter_drift.get('effective_dates'))}",
            f"- current_config_hash: {parameter_drift.get('current_config_hash', NOT_AVAILABLE)}",
            f"- config_hash_diff: {ReportService._format_config_hash_diff(parameter_drift.get('config_hash_diff'))}",
            f"- active_setup_count_in_window: {active_setup_count}",
        ]
        if no_drift_detected:
            lines.append("- no_drift_detected: true")
        if reason:
            lines.append(f"- unavailable_reason: {reason}")
        lines.extend(
            [
                "| strategy | status | snapshot_date | effective_date | config_hash_diff | current_config_hash | snapshot_config_hash | changed_keys | unchanged_keys_count | change_detail |",
                "|---|---|---|---|---|---|---|---|---:|---|",
            ]
        )
        strategy_rows = parameter_drift.get("strategies")
        if not isinstance(strategy_rows, list) or not strategy_rows:
            lines.append(
                f"| {NOT_AVAILABLE} | {status} | {NOT_AVAILABLE} | {NOT_AVAILABLE} | "
                f"{NOT_AVAILABLE} | {NOT_AVAILABLE} | {NOT_AVAILABLE} | {NOT_AVAILABLE} | 0 | {NOT_AVAILABLE} |"
            )
            return lines
        for row in strategy_rows:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"| {row.get('strategy_name', NOT_AVAILABLE)} | {row.get('status', NOT_AVAILABLE)} | "
                f"{row.get('snapshot_date') or NOT_AVAILABLE} | {row.get('effective_date') or NOT_AVAILABLE} | "
                f"{row.get('config_hash_diff') or NOT_AVAILABLE} | "
                f"{row.get('current_config_hash') or NOT_AVAILABLE} | {row.get('snapshot_config_hash') or NOT_AVAILABLE} | "
                f"{ReportService._format_changed_keys(row)} | {row.get('unchanged_keys_count', 0)} | "
                f"{ReportService._format_drifted_parameters(row)} |"
            )
        return lines

    @staticmethod
    def _format_drifted_parameters(row: dict[str, object]) -> str:
        diffs = row.get("drifted_parameters")
        if not isinstance(diffs, list) or not diffs:
            if row.get("status") == NOT_AVAILABLE:
                return NOT_AVAILABLE
            if row.get("status") == "no_drift":
                return "no_drift_detected"
            return "none"
        formatted: list[str] = []
        for diff in diffs[:10]:
            if not isinstance(diff, dict):
                continue
            formatted.append(
                f"{diff.get('parameter')}:{ReportService._markdown_value(diff.get('snapshot'))}"
                f"->{ReportService._markdown_value(diff.get('current'))}"
            )
        extra_count = len(diffs) - len(formatted)
        if extra_count > 0:
            formatted.append(f"+{extra_count}_more")
        return "; ".join(formatted) if formatted else "none"

    @staticmethod
    def _format_changed_keys(row: dict[str, object]) -> str:
        keys = row.get("changed_keys")
        if isinstance(keys, list) and keys:
            return ", ".join(str(key) for key in keys)
        if row.get("status") == "no_drift":
            return "no_drift_detected"
        if row.get("comparison_available") is False or row.get("status") == NOT_AVAILABLE:
            return NOT_AVAILABLE
        return "none"

    @staticmethod
    def _format_metadata_list(value: object) -> str:
        if isinstance(value, (list, tuple, set)) and value:
            return ", ".join(str(item) for item in value)
        return NOT_AVAILABLE

    @staticmethod
    def _format_config_hash_diff(value: object) -> str:
        if not isinstance(value, dict):
            return NOT_AVAILABLE
        return (
            f"changed:{value.get('changed_count', 0)}, "
            f"unchanged:{value.get('unchanged_count', 0)}, "
            f"unavailable:{value.get('unavailable_count', 0)}"
        )

    @staticmethod
    def _bool_text(value: object) -> str:
        return "true" if bool(value) else "false"

    @staticmethod
    def _markdown_value(value: object) -> str:
        if value is None:
            return "null"
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        return str(value)

    @staticmethod
    def _hit_rate_rows(rows: list[ScreenResult], trades: list[BacktestTradeLedger]) -> list[dict[str, object]]:
        grouped: dict[str, dict[str, int]] = {}
        for row in rows:
            bucket = grouped.setdefault(row.strategy_tag, {"screened": 0, "screen_passed": 0})
            bucket["screened"] += 1
            bucket["screen_passed"] += 1 if row.passed else 0
        trade_grouped: dict[str, dict[str, int]] = {}
        for trade in trades:
            bucket = trade_grouped.setdefault(trade.strategy_name, {"trade_count": 0, "wins": 0})
            bucket["trade_count"] += 1
            bucket["wins"] += 1 if float(trade.pnl or 0) > 0 else 0
        for setup in trade_grouped:
            grouped.setdefault(setup, {"screened": 0, "screen_passed": 0})
        return [
            {
                "setup": setup,
                "screened": counts["screened"],
                "screen_passed": counts["screen_passed"],
                "screen_pass_rate": ReportService._ratio(counts["screen_passed"], counts["screened"]),
                "trade_hit_rate": ReportService._trade_hit_rate(setup, trade_grouped),
            }
            for setup, counts in sorted(grouped.items())
        ]

    @staticmethod
    def _trade_hit_rate(setup: str, grouped: dict[str, dict[str, int]]) -> float | str:
        counts = grouped.get(setup)
        if not counts:
            return NOT_AVAILABLE
        return ReportService._ratio(counts["wins"], counts["trade_count"])

    @staticmethod
    def _setup_pnl_rows(trades: list[BacktestTradeLedger]) -> list[dict[str, object]]:
        grouped: dict[str, list[BacktestTradeLedger]] = {}
        for trade in trades:
            grouped.setdefault(trade.strategy_name, []).append(trade)
        rows: list[dict[str, object]] = []
        for setup, setup_trades in sorted(grouped.items()):
            trade_count = len(setup_trades)
            pnl = round(sum(float(trade.pnl or 0) for trade in setup_trades), 2)
            avg_return = sum(float(trade.return_pct or 0) for trade in setup_trades) / trade_count
            rows.append(
                {
                    "setup": setup,
                    "trade_count": trade_count,
                    "pnl": pnl,
                    "win_rate": ReportService._ratio(
                        len([trade for trade in setup_trades if float(trade.pnl or 0) > 0]),
                        trade_count,
                    ),
                    "avg_return": round(avg_return, 6),
                }
            )
        return rows

    @staticmethod
    def _failed_trade_rows(trades: list[BacktestTradeLedger]) -> list[dict[str, object]]:
        return [
            {
                "symbol": trade.symbol,
                "setup": trade.strategy_name,
                "exit_date": trade.exit_date.isoformat(),
                "exit_reason": trade.exit_reason,
                "pnl": round(float(trade.pnl or 0), 2),
                "return_pct": round(float(trade.return_pct or 0), 6),
                "holding_days": trade.holding_days,
            }
            for trade in sorted(trades, key=lambda row: float(row.pnl or 0))[:10]
        ]

    @staticmethod
    def _reason_breakdown(reason_counts: dict[str, int]) -> str:
        if not reason_counts:
            return "no_failed_trades_in_ledger_window"
        return ", ".join(f"{reason}:{count}" for reason, count in sorted(reason_counts.items()))

    @staticmethod
    def _failed_condition_counts(rows: list[ScreenResult]) -> list[tuple[str, int]]:
        counts: dict[str, int] = {}
        for row in rows:
            for condition in ReportService._json_list(row.failed_conditions):
                counts[condition] = counts.get(condition, 0) + 1
        return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:20]

    @staticmethod
    def _ratio(numerator: int, denominator: int) -> float | str:
        if denominator <= 0:
            return NOT_AVAILABLE
        return round(numerator / denominator, 6)

    @staticmethod
    def _ratio_float(numerator: float, denominator: float) -> float | str:
        if denominator <= 0:
            return NOT_AVAILABLE
        return round(numerator / denominator, 6)

    @staticmethod
    def _json_list(value: str | None) -> list[str]:
        if not value:
            return []
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return [str(item) for item in parsed]

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 0.8:
            return "A"
        if score >= 0.65:
            return "B"
        if score >= 0.5:
            return "C"
        return "D"
