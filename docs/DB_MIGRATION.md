# DB Migration

## 현재 정책

현재 DB 기준은 `MVP v0.11 / Phase 3G-2` 모델 스키마이며, Alembic revision `da9ab5998e36_initial_schema`가 초기 schema snapshot이다.

이 작업은 기존 SQLite 개발/test 환경을 유지하면서 migration 체계를 추가한 것이다.

- `backend/app/core/database.py`의 `init_db()`는 기존 테스트 fixture와 로컬 부트스트랩 호환을 위해 유지한다.
- 신규 schema 변경은 Alembic revision으로 작성한다.
- runtime SQLite schema patch는 기존 로컬 DB 호환용 legacy path로 남겨둔다.
- Postgres 전환은 현재 범위가 아니며 SQLite 기준으로 검증한다.

## 구조

| 경로 | 역할 |
|---|---|
| `alembic.ini` | repo root 기준 Alembic 설정 |
| `backend/alembic/env.py` | SQLAlchemy `Base.metadata`를 참조하는 Alembic environment |
| `backend/alembic/script.py.mako` | revision template |
| `backend/alembic/versions/` | migration revision 저장소 |
| `backend/alembic/versions/da9ab5998e36_initial_schema.py` | 현재 모델 기준 초기 migration |

## SQLite 개발 DB 명령

PowerShell 기준 repo root에서 실행한다.

빈 DB 또는 이미 Alembic version이 관리되는 DB에 migration 적용:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

특정 빈 SQLite 파일에 적용:

```powershell
$env:DATABASE_URL = "sqlite:///./backend/data/app.db"
.\.venv\Scripts\python.exe -m alembic upgrade head
```

기존 `create_all`로 이미 생성된 SQLite DB를 Alembic baseline으로 등록:

```powershell
# 먼저 DB 백업과 schema 검토를 끝낸 뒤 실행한다.
$env:DATABASE_URL = "sqlite:///./backend/data/app.db"
.\.venv\Scripts\python.exe -m alembic stamp head
.\.venv\Scripts\python.exe -m alembic check
```

초기 migration은 빈 DB 생성용이다. 기존 로컬 DB에 이미 같은 테이블이 있으면 `upgrade head`가 아니라 `stamp head`로 Alembic version만 맞춘다.

현재 revision 확인:

```powershell
.\.venv\Scripts\python.exe -m alembic current
```

history 확인:

```powershell
.\.venv\Scripts\python.exe -m alembic history
```

한 단계 rollback:

```powershell
.\.venv\Scripts\python.exe -m alembic downgrade -1
```

빈 SQLite smoke DB에 적용:

```powershell
$env:DATABASE_URL = "sqlite:///./backend/data/alembic_smoke.db"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

## 신규 migration 생성

모델 변경 후 빈 비교 DB 또는 현재 개발 DB 상태를 명확히 지정하고 autogenerate를 실행한다.

```powershell
$env:DATABASE_URL = "sqlite:///./backend/data/alembic_autogen.db"
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe schema change"
```

생성 후 반드시 확인한다.

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m pytest backend/tests/test_alembic_migrations.py
.\.venv\Scripts\python.exe -m pytest backend/tests
```

Autogenerate 결과는 그대로 신뢰하지 말고 다음을 확인한다.

- 테이블/컬럼 nullable 여부.
- unique constraint와 index 이름.
- SQLite batch migration 필요 여부.
- 데이터 보존이 필요한 `ALTER TABLE`인지 여부.
- 실주문, paper mutation, KIS credential/token 저장 경로가 추가되지 않았는지 여부.

## create_all/runtime patch와의 관계

`init_db()`는 기존 테스트가 `Base.metadata.drop_all(bind=engine)` 후 빠르게 schema를 만드는 경로라서 당장 제거하지 않는다.

현재 runtime patch `_ensure_sqlite_columns()`는 다음 legacy 컬럼 보강만 담당한다.

- `symbol_master.asset_type`
- `symbol_master.currency`
- `import_runs.source_config_snapshot_json`
- `import_runs.provider_metadata_json`

위 컬럼은 초기 migration에 포함되어 있다. 신규 DB는 Alembic migration만으로 같은 schema를 얻을 수 있으며, runtime patch는 오래된 로컬 SQLite 파일을 위한 호환 장치로만 유지한다.

기존 `create_all` 기반 DB가 현재 모델과 일치하는 경우에는 `alembic stamp head`로 baseline 등록한 뒤 이후 변경부터 revision을 적용한다.

## 향후 Postgres 전환 고려사항

- SQLite 전용 `connect_args`, batch migration, Boolean/DateTime 표현 차이를 확인한다.
- 운영 DB에는 destructive downgrade를 기본 절차로 사용하지 않는다.
- 데이터 보존 migration은 autogenerate 대신 수동 migration으로 작성한다.
- index/unique constraint 이름을 명시해 환경별 drift를 줄인다.
- migration 적용 전 백업, dry-run SQL 검토, rollback 방안을 별도 문서화한다.
- broker/KIS/live trading 관련 schema는 별도 승인 전까지 추가하지 않는다.
