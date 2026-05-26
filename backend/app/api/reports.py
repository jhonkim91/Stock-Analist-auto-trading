from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.schemas import ReportNotifyRequest
from backend.app.services.report_service import ReportService

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/daily")
def generate_daily_report(report_date: date | None = None, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return ReportService(db).generate_daily_report(report_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/weekly")
def generate_weekly_report(report_date: date | None = None, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return ReportService(db).generate_weekly_report(report_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("")
def list_reports(
    limit: int = Query(default=20, ge=1, le=100),
    report_type: Literal["daily", "weekly"] | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return ReportService(db).list_reports(limit=limit, report_type=report_type)


@router.get("/latest")
def latest_report(db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return ReportService(db).latest_markdown()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{report_id}")
def report_detail(report_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return ReportService(db).get_report(report_id, include_markdown=True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{report_id}/markdown")
def report_markdown(report_id: str, db: Session = Depends(get_db)) -> Response:
    try:
        markdown = ReportService(db).get_markdown(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=markdown.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="report-{report_id}.md"'},
    )


@router.post("/{report_id}/notify")
def notify_report(report_id: str, payload: ReportNotifyRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return ReportService(db).notify_report(
            report_id,
            mode=payload.mode,
            channel_alias=payload.channel_alias,
            dry_run=payload.dry_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
