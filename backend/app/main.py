from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    return app


app = create_app()
