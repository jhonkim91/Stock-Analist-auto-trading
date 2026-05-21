from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.core.config import get_config
from backend.app.core.paths import ensure_runtime_dirs


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


def _database_url() -> str:
    return get_config("app")["database"]["url"]


ensure_runtime_dirs()
engine = create_engine(
    _database_url(),
    connect_args={"check_same_thread": False} if _database_url().startswith("sqlite") else {},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """등록된 모델 기준으로 DB 테이블을 생성한다."""
    from backend.app.models import tables  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns() -> None:
    """기존 SQLite DB에 Phase 2 기본 컬럼을 안전하게 보강한다."""
    if not _database_url().startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "symbol_master" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("symbol_master")}
    statements: list[str] = []
    if "asset_type" not in existing:
        statements.append("ALTER TABLE symbol_master ADD COLUMN asset_type VARCHAR(32) DEFAULT 'stock'")
    if "currency" not in existing:
        statements.append("ALTER TABLE symbol_master ADD COLUMN currency VARCHAR(8) DEFAULT 'KRW'")
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency용 DB 세션을 제공한다."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
