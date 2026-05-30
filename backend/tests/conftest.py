from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "test_app.db"
EMPTY_DB_SNAPSHOT_PATH = TEST_DB_PATH.with_name("test_app_empty_snapshot.db")
SEEDED_DB_SNAPSHOT_PATH = TEST_DB_PATH.with_name("test_app_seeded_snapshot.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
TEST_ISOLATED_ENV_VARS = (
    "BROKER_MODE",
    "DISCORD_OPS_WEBHOOK_URL",
    "ENABLE_REAL_ORDER",
    "EXECUTION_MODE",
    "KIS_ACCESS_TOKEN",
    "KIS_ACCOUNT_NO",
    "KIS_APP_KEY",
    "KIS_APP_SECRET",
    "KIS_ENV",
    "KIS_MARKET_QUOTE_ENABLED",
    "KIS_PAPER_BASE_URL",
    "KIS_PRODUCT_CODE",
    "KIS_REFRESH_TOKEN",
    "KIS_TOKEN_CACHE_ENABLED",
    "KIS_TOKEN_CACHE_PATH",
    "KIS_TOKEN_ISSUE_ENABLED",
    "KIS_WEBSOCKET_APPROVAL_ENABLED",
    "KIS_LIVE_ACCESS_TOKEN",
    "KIS_LIVE_ACCOUNT_NO",
    "KIS_LIVE_APP_KEY",
    "KIS_LIVE_APP_SECRET",
    "KIS_LIVE_BASE_URL",
    "KIS_LIVE_BUY_TR_ID",
    "KIS_LIVE_CANCEL_TR_ID",
    "KIS_LIVE_PRODUCT_CODE",
    "KIS_LIVE_SELL_TR_ID",
    "LIVE_KILL_SWITCH",
    "LIVE_MAX_ORDER_NOTIONAL",
    "LIVE_ORDER_CONFIRM_REQUIRED",
    "LIVE_ORDER_SUBMIT_ENABLED",
    "LIVE_TRADING_ENABLED",
    "NOTIFICATIONS_DEFAULT_DRY_RUN",
    "NOTIFICATIONS_ENABLED",
    "PAPER_BOT_CONFIRM",
    "PAPER_BOT_ENABLED",
    "PAPER_BOT_KILL_SWITCH",
    "PAPER_BOT_MAX_ITERATIONS",
    "PAPER_BOT_MAX_ITERATIONS_CAP",
    "PAPER_BOT_STOP_FILE",
    "PAPER_FILL_SIMULATOR_ENABLED",
    "PAPER_ORDER_COOLDOWN_SECONDS",
    "PAPER_ORDER_SUBMIT_ENABLED",
    "PAPER_REALTIME_ENABLED",
    "PAPER_SYMBOL_BLACKLIST",
    "PAPER_TRADING_CAN_CREATE",
    "PAPER_TRADING_CAN_SIMULATE_FILLS",
    "PAPER_TRADING_ENABLED",
    "PAPER_TRADING_KILL_SWITCH",
    "PAPER_TRADING_MARKET",
    "PAPER_TRADING_NETWORK_ENABLED",
    "PAPER_SYNC_WORKER_ENABLED",
    "PAPER_SYNC_WORKER_INTERVAL_SECONDS",
    "PAPER_SYNC_WORKER_MAX_ITERATIONS",
    "PAPER_SYNC_WORKER_MAX_ITERATIONS_CAP",
    "TELEGRAM_BOT_ENABLED",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_API_BASE_URL",
    "TELEGRAM_PAPER_TRADE_CONFIRM",
    "TELEGRAM_POLLING_DRY_RUN",
    "TELEGRAM_POLLING_ENABLED",
    "TELEGRAM_POLLING_SEND_REPLIES",
    "TELEGRAM_POST_MARKET_REPORT_ENABLED",
    "TELEGRAM_POST_MARKET_REPORT_TIME",
    "TELEGRAM_PRE_MARKET_REPORT_ENABLED",
    "TELEGRAM_PRE_MARKET_REPORT_TIME",
    "TELEGRAM_REPORT_DRY_RUN",
    "TELEGRAM_REPORT_SCHEDULER_ENABLED",
    "TELEGRAM_WEBHOOK_ENABLED",
    "TELEGRAM_WEEKLY_REPORT_ENABLED",
    "TELEGRAM_WEEKLY_REPORT_TIME",
)

from backend.app.core.database import SessionLocal, engine, init_db
from backend.app.main import app
from backend.app.services.indicator_service import IndicatorService
from backend.app.services.market_data_service import MarketDataService


@pytest.fixture(autouse=True)
def isolated_runtime_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """테스트는 로컬 KIS/Telegram/Paper env가 있어도 기본 fail-closed 상태로 시작한다.

    추가로 로그인/런타임 env 영속 파일(users.json, auth_secret.key, runtime_env.json)을
    테스트별 임시 경로로 격리한다. 이렇게 하면:
      - 실제 backend/data가 테스트 부작용(자격증명/토글 파일)으로 오염되지 않고,
      - 인증 미들웨어가 항상 "사용자 없음 = 비인증" 상태에서 시작한다(테스트 결정성).
    """
    from backend.app.core import auth as auth_core
    from backend.app.core import runtime_env as runtime_env_core
    from backend.app.services.settings_service import (
        RUNTIME_ENV_PRESET_SPECS,
        RUNTIME_ENV_TOGGLE_SPECS,
    )

    for name in TEST_ISOLATED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    # UI 토글/프리셋이 설정할 수 있는 모든 런타임 env 키도 비운다.
    # (영속 runtime_env.json 또는 이전 테스트가 os.environ에 남긴 값이 누수되지 않도록)
    runtime_env_keys = {spec.name for spec in RUNTIME_ENV_TOGGLE_SPECS}
    for preset in RUNTIME_ENV_PRESET_SPECS:
        runtime_env_keys.update(key for key, _ in preset.values)
    for name in runtime_env_keys:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(auth_core, "AUTH_FILE", tmp_path / "users.json", raising=False)
    monkeypatch.setattr(auth_core, "AUTH_SECRET_FILE", tmp_path / "auth_secret.key", raising=False)
    monkeypatch.setattr(runtime_env_core, "RUNTIME_ENV_FILE", tmp_path / "runtime_env.json", raising=False)
    yield


def _recreate_database() -> None:
    """현재 테스트 DB 파일을 schema-only 상태로 새로 만든다."""
    engine.dispose()
    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    init_db()
    engine.dispose()


def _restore_database(snapshot_path: Path) -> None:
    """SQLite snapshot을 테스트 DB로 복사해 테스트 간 상태를 격리한다."""
    engine.dispose()
    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snapshot_path, TEST_DB_PATH)
    engine.dispose()


@pytest.fixture(scope="session")
def empty_db_snapshot() -> Path:
    _recreate_database()
    shutil.copy2(TEST_DB_PATH, EMPTY_DB_SNAPSHOT_PATH)
    return EMPTY_DB_SNAPSHOT_PATH


@pytest.fixture(scope="session")
def seeded_db_snapshot(empty_db_snapshot: Path) -> Path:
    _restore_database(empty_db_snapshot)
    db = SessionLocal()
    try:
        MarketDataService(db).seed_sample_data()
        IndicatorService(db).recompute()
    finally:
        db.close()
        engine.dispose()
    shutil.copy2(TEST_DB_PATH, SEEDED_DB_SNAPSHOT_PATH)
    return SEEDED_DB_SNAPSHOT_PATH


@pytest.fixture()
def db_session(empty_db_snapshot: Path):
    _restore_database(empty_db_snapshot)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def seeded_db(seeded_db_snapshot: Path):
    _restore_database(seeded_db_snapshot)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(empty_db_snapshot: Path):
    _restore_database(empty_db_snapshot)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def seeded_client(seeded_db_snapshot: Path):
    _restore_database(seeded_db_snapshot)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def full_flow_client(seeded_db_snapshot: Path):
    _restore_database(seeded_db_snapshot)
    with TestClient(app) as test_client:
        assert test_client.post("/api/screener/run", json={}).status_code == 200
        assert test_client.post("/api/reports/daily").status_code == 200
        assert test_client.post("/api/backtest/run", json={"strategy_name": "trend_breakout"}).status_code == 200
        yield test_client
