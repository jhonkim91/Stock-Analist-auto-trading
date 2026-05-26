from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.paths import REPORT_DIR
from backend.app.models.tables import Report, ScreenResult
from backend.app.repositories.report_repository import ReportRepository
from backend.app.services.regime_service import RegimeService
from backend.app.services.sector_service import SectorService


class ReportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ReportRepository(db)

    def generate_daily_report(self, report_date: date | None = None) -> dict[str, object]:
        """일간 Markdown 리포트를 생성하고 메타데이터를 저장한다."""
        target_date = report_date or self.db.scalar(
            select(ScreenResult.trade_date).order_by(ScreenResult.trade_date.desc()).limit(1)
        )
        if target_date is None:
            raise ValueError("screen_results 데이터가 없습니다.")

        results = list(
            self.db.scalars(
                select(ScreenResult)
                .where(ScreenResult.trade_date == target_date)
                .order_by(ScreenResult.passed.desc(), ScreenResult.total_score.desc())
            ).all()
        )
        regime = RegimeService(self.db).detect_market_regime()
        sectors = SectorService(self.db).latest_rotation()
        content = self._render(target_date, regime, sectors, results)
        path = REPORT_DIR / f"daily_report_{target_date.isoformat()}.md"
        path.write_text(content, encoding="utf-8")

        report = Report(
            report_id=f"daily-{target_date.isoformat()}",
            report_date=target_date,
            report_type="daily",
            version="0.1.0",
            path=str(path),
        )
        self.repo.save(report)
        return {"report_id": report.report_id, "path": str(path), "chars": len(content)}

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
        """전략별 validation summary를 JSON 산출물로 저장하고 API payload를 반환한다."""
        path = REPORT_DIR / f"strategy_validation_{int(lookback_days)}d.json"
        payload = {
            **summary,
            "generated_at": datetime.now(UTC).isoformat(),
            "report": {
                "format": "json",
                "path": str(path),
                "filename": path.name,
            },
            "validation_documentation_format": {
                "docs_file": "docs/VALIDATION.md",
                "required_fields": [
                    "checkpoint",
                    "command",
                    "result",
                    "summary_endpoint",
                    "report_path",
                    "baseline_status",
                    "safety_contract",
                ],
            },
        }
        content = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        path.write_text(content + "\n", encoding="utf-8")
        payload["report"] = {
            **payload["report"],  # type: ignore[arg-type]
            "bytes": len(content.encode("utf-8")),
        }
        return payload

    def list_reports(self, limit: int = 20) -> list[dict[str, object]]:
        """저장된 리포트 목록을 최신순으로 반환한다."""
        reports = list(self.db.scalars(select(Report).order_by(Report.created_at.desc()).limit(limit)).all())
        return [self._serialize_report(report, include_markdown=False) for report in reports]

    def get_report(self, report_id: str, include_markdown: bool = False) -> dict[str, object]:
        """리포트 메타데이터와 선택적으로 Markdown 본문을 반환한다."""
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

    def _serialize_report(self, report: Report, include_markdown: bool) -> dict[str, object]:
        markdown = self._read_markdown(report)
        metadata = self._extract_metadata(markdown, report)
        payload: dict[str, object] = {
            "id": report.report_id,
            "report_id": report.report_id,
            "report_date": report.report_date,
            "report_type": report.report_type,
            "title": metadata["title"],
            "model_version": metadata["model_version"],
            "strategy_version": metadata["strategy_version"],
            "data_timestamp": metadata["data_timestamp"],
            "created_at": report.created_at,
            "version": report.version,
            "path": report.path,
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
    def _extract_metadata(markdown: str, report: Report) -> dict[str, str]:
        title = next((line.removeprefix("#").strip() for line in markdown.splitlines() if line.startswith("# ")), report.report_id)
        metadata = {
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
        return metadata

    @staticmethod
    def _render(
        report_date: date,
        regime: dict[str, object],
        sectors: list[dict[str, object]],
        results: list[ScreenResult],
    ) -> str:
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
                f"{row.reward_risk_ratio:.2f} | {row.position_size} | {row.reason_summary} | {', '.join(json.loads(row.failed_conditions))} |"
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
            failed = ", ".join(json.loads(row.failed_conditions))
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

        lines.extend(
            [
                "",
                "## Audit Trail",
                f"- data_timestamp: {report_date.isoformat()}",
                "- model_version: 0.1.0",
                "- strategy_version: 0.1.0",
                "- backtest_version: 0.1.0",
                f"- report_generated_at: {datetime.now(UTC).isoformat()}",
                "- data_source: deterministic_sample_or_csv",
                "- broker_mode: mock_preview_only",
                "",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 0.8:
            return "A"
        if score >= 0.65:
            return "B"
        if score >= 0.5:
            return "C"
        return "D"
