from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api import (
    account,
    auth as auth_api,
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
from backend.app.core import auth as auth_core
from backend.app.core.database import init_db
from backend.app.core.paths import ensure_runtime_dirs
from backend.app.core.runtime_env import load_persisted_env

# 인증을 적용하지 않는 공개 경로 (로그인 화면이 동작하려면 필요)
_PUBLIC_API_PREFIXES = ("/api/auth/",)
_PUBLIC_PATHS = ("/health",)

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
    # 사용자가 프로그램 내에서 저장한 환경변수(자격증명/토글)를 먼저 반영한다.
    load_persisted_env()
    init_db()
    app = FastAPI(title="Stock Analyst Auto Trading API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(LOCAL_FRONTEND_ORIGINS),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _auth_guard(request: Request, call_next):
        """비밀번호가 설정된 경우에만 /api/* 호출에 유효 토큰을 요구한다.

        사용자가 없으면(테스트/초기 상태) 통과시켜 기존 동작과 호환된다.
        /api/auth/*, /health, 정적 파일은 항상 공개다.
        """
        path = request.url.path
        protected = (
            path.startswith("/api/")
            and not any(path.startswith(prefix) for prefix in _PUBLIC_API_PREFIXES)
            and path not in _PUBLIC_PATHS
        )
        if protected and auth_core.auth_configured():
            token = request.headers.get("authorization")
            if auth_core.verify_token(token) is None:
                return JSONResponse({"detail": "인증이 필요합니다.", "code": "UNAUTHORIZED"}, status_code=401)
        return await call_next(request)

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"ok": True, "service": "backend", "version": "0.1.0"}

    app.include_router(auth_api.router)
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
