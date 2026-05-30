from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api import (
    account,
    backtest,
    bot,
    broker,
    data,
    indicators,
    instruments,
    kis,
    live,
    market,
    market_realtime,
    notifications,
    paper,
    portfolio,
    reports,
    screener,
    settings,
    stocks,
    telegram,
    trade_journal,
)
from backend.app.core.database import init_db
from backend.app.core.paths import ensure_runtime_dirs

LOCAL_FRONTEND_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3010",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3010",
)


def _frontend_export_dir() -> Path | None:
    """정적 export된 Next.js 산출물(frontend/out) 경로를 찾는다.

    - frozen(.exe): PyInstaller가 번들에 `frontend_out`으로 풀어둔 위치
    - 개발/일반 실행: 소스 트리의 `frontend/out`
    빌드가 아직 없으면 None을 반환해 API 전용으로 동작한다.
    """
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "frontend_out")
    candidates.append(Path(__file__).resolve().parents[2] / "frontend" / "out")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def create_app() -> FastAPI:
    """FastAPI 앱을 생성한다."""
    ensure_runtime_dirs()
    init_db()
    app = FastAPI(title="Stock Analyst Auto Trading API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(LOCAL_FRONTEND_ORIGINS),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"ok": True, "service": "backend", "version": "0.1.0"}

    app.include_router(data.router)
    app.include_router(indicators.router)
    app.include_router(market.router)
    app.include_router(market_realtime.router)
    app.include_router(instruments.router)
    app.include_router(account.router)
    app.include_router(screener.router)
    app.include_router(reports.router)
    app.include_router(backtest.router)
    app.include_router(bot.router)
    app.include_router(portfolio.router)
    app.include_router(broker.router)
    app.include_router(paper.router)
    app.include_router(kis.router)
    app.include_router(live.router)
    app.include_router(notifications.router)
    app.include_router(settings.router)
    app.include_router(stocks.router)
    app.include_router(telegram.router)
    app.include_router(trade_journal.router)

    # 정적 프론트엔드는 API 라우터 등록 이후 "/"에 마운트한다.
    # 라우트는 등록 순서대로 매칭되므로 /api/*, /health가 우선한다.
    # html=True + Next.js trailingSlash export로 /dashboard/ → dashboard/index.html 서빙.
    frontend_dir = _frontend_export_dir()
    if frontend_dir is not None:
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

    return app


app = create_app()
