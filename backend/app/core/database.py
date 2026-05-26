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
    """등록된 모델 기준으로 DB 테이블을 생성한다.

    Alembic 도입 후에도 기존 SQLite 개발/test fixture 호환을 위해 create_all 경로를 유지한다.
    운영성 schema 변경은 신규 Alembic revision으로 관리하고, 이 함수는 로컬 부트스트랩과 테스트 초기화 용도로만 사용한다.
    """
    from backend.app.models import tables  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns() -> None:
    """기존 SQLite DB에 누락된 호환 컬럼을 안전하게 보강한다.

    TODO: Phase 3 이전 로컬 SQLite DB 호환용 runtime patch다. 신규 schema 변경은 Alembic migration으로 작성하고,
    이 보강 로직은 기존 로컬 DB를 더 이상 지원하지 않아도 되는 시점에 deprecate한다.
    현재 대체 가능한 migration 기준은 `da9ab5998e36_initial_schema`의 `symbol_master` 및 `import_runs` 컬럼 정의다.
    """
    if not _database_url().startswith("sqlite"):
        return
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "symbol_master" not in table_names:
        return
    statements: list[str] = []
    existing = {column["name"] for column in inspector.get_columns("symbol_master")}
    if "asset_type" not in existing:
        statements.append("ALTER TABLE symbol_master ADD COLUMN asset_type VARCHAR(32) DEFAULT 'stock'")
    if "currency" not in existing:
        statements.append("ALTER TABLE symbol_master ADD COLUMN currency VARCHAR(8) DEFAULT 'KRW'")
    if "import_runs" in table_names:
        import_run_columns = {column["name"] for column in inspector.get_columns("import_runs")}
        if "source_config_snapshot_json" not in import_run_columns:
            statements.append("ALTER TABLE import_runs ADD COLUMN source_config_snapshot_json TEXT DEFAULT '{}'")
        if "provider_metadata_json" not in import_run_columns:
            statements.append("ALTER TABLE import_runs ADD COLUMN provider_metadata_json TEXT DEFAULT '{}'")
    if "screen_results" in table_names:
        screen_result_columns = {column["name"] for column in inspector.get_columns("screen_results")}
        for column_name in (
            "metadata_json",
            "risk_flags_json",
            "score_breakdown_json",
            "data_quality_flags_json",
        ):
            if column_name not in screen_result_columns:
                statements.append(f"ALTER TABLE screen_results ADD COLUMN {column_name} TEXT DEFAULT '{{}}'")
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
