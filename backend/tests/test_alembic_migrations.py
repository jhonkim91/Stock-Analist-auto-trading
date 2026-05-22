from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from backend.app.core.database import Base
from backend.app.models import tables  # noqa: F401


def _alembic_config(database_url: str) -> Config:
    repo_root = Path(__file__).resolve().parents[2]
    config = Config(str(repo_root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_alembic_initial_migration_upgrade_and_downgrade(tmp_path: Path, monkeypatch) -> None:
    """초기 Alembic migration이 빈 SQLite DB에 적용되고 rollback 가능한지 확인한다."""
    database_path = tmp_path / "alembic_smoke.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    config = _alembic_config(database_url)
    command.upgrade(config, "head")

    engine = create_engine(database_url, future=True)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    assert {
        "alembic_version",
        "symbol_master",
        "daily_ohlcv",
        "import_runs",
        "orders",
        "paper_orders",
        "backtest_runs",
    }.issubset(table_names)
    with engine.connect() as connection:
        assert connection.scalar(text("select version_num from alembic_version")) == "da9ab5998e36"

    command.downgrade(config, "base")

    downgraded_tables = set(inspect(engine).get_table_names())
    assert "symbol_master" not in downgraded_tables
    assert "paper_orders" not in downgraded_tables
    engine.dispose()


def test_existing_create_all_sqlite_schema_can_be_stamped_as_head(tmp_path: Path, monkeypatch) -> None:
    """기존 create_all 기반 SQLite DB를 초기 Alembic baseline으로 stamp할 수 있는지 확인한다."""
    database_path = tmp_path / "existing_create_all.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(bind=engine)

    config = _alembic_config(database_url)
    command.stamp(config, "head")
    command.check(config)

    with engine.connect() as connection:
        assert connection.scalar(text("select version_num from alembic_version")) == "da9ab5998e36"
    engine.dispose()
