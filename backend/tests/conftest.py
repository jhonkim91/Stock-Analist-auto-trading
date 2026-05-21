from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "test_app.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"

from backend.app.core.database import Base, SessionLocal, engine, init_db
from backend.app.main import app
from backend.app.services.indicator_service import IndicatorService
from backend.app.services.market_data_service import MarketDataService


@pytest.fixture()
def db_session():
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def seeded_db(db_session):
    MarketDataService(db_session).seed_sample_data()
    IndicatorService(db_session).recompute()
    return db_session


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    init_db()
    return TestClient(app)
