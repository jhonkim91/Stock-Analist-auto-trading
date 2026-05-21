# Stock Analyst Auto Trading

주식 분석과 자동매매 보조 흐름을 검증 가능한 MVP 형태로 구현한 FastAPI + Next.js 프로젝트입니다.

현재 checkpoint는 `MVP v0.3 Phase 3A data quality`입니다. 실제 주문, paper/live broker, 외부 데이터 API 호출, 실시간 websocket, AI 예측 모델은 구현하지 않습니다.

## Phase 3A 기능

- deterministic sample seed 유지
- legacy direct CSV import endpoint 유지
- 새 CSV preview/confirm import flow 추가
- DataProvider 계층 추가
  - `SampleDataProvider`
  - `CsvDataProvider`
  - `ExternalDataProvider` placeholder disabled
- 데이터 품질 검증 기록
  - `import_runs`
  - `data_quality_checks`
- 데이터 소스 설정
  - `backend/config/data_sources.yaml`
  - `sample_krx`
  - `csv_krx`
  - `external_placeholder_disabled`
- `/data` 화면 추가
  - Data Sources
  - CSV Validation Preview
  - Import History
  - Data Quality

## Data Import Flow

Frontend는 legacy direct import를 사용하지 않고 아래 flow만 사용합니다.

1. `POST /api/data/validate-csv`
2. `POST /api/data/import-csv-confirmed`

`validate-csv`는 market data table을 변경하지 않습니다. 허용되는 write는 `import_runs +1`, `data_quality_checks +N`뿐입니다.

`confirm`은 `run_id`만 받으며 파일을 다시 받지 않습니다. `import_runs.staged_rows_json`을 transaction으로 `daily_ohlcv`에 반영합니다.

```json
{
  "run_id": "imp-..."
}
```

## CSV 제한

| 항목 | 제한 |
|---|---:|
| 최대 row 수 | 10,000 |
| preview rows | 100 |
| 파일 크기 | 10MB 이하 |

Phase 3A에서는 `staged_rows_json`을 SQLite 호환 `Text` JSON으로 저장합니다. 대용량 파일은 Phase 3B 이후 staging table 분리를 검토합니다.

## CSV 컬럼

필수 컬럼:

| 컬럼 | 설명 |
|---|---|
| `symbol` | 종목 코드 |
| `trade_date` | 거래일 |
| `open` | 시가 |
| `high` | 고가 |
| `low` | 저가 |
| `close` | 종가 |
| `volume` | 거래량 |

선택 컬럼:

| 컬럼 | 기본 처리 |
|---|---|
| `adj_close` | 누락 시 `close` 사용, warning 기록 |
| `turnover_value` | 누락 시 `close * volume` 사용, warning 기록 |
| `market` | 누락 시 source config market 또는 `KRX` |
| `venue` | 누락 시 source config venue 또는 `KRX` |
| `provider` | 누락 시 source config provider_type |

## Data Quality Checks

대표 검증:

- 필수 컬럼 및 필수값
- 날짜 parse
- 숫자 parse
- 음수/0 이하 가격
- 음수 volume
- zero volume warning
- `high >= low`
- `high >= max(open, close)`
- `low <= min(open, close)`
- batch duplicate
- database duplicate
- unknown symbol warning
- provider mismatch
- weekend date
- calendar unknown date info

## 주요 API

| Method | Path | 설명 |
|---|---|---|
| `GET` | `/api/data/status` | 데이터 row count와 최신 기준일 |
| `GET` | `/api/data/sources` | data source 목록 |
| `GET` | `/api/data/import-runs` | import history |
| `GET` | `/api/data/import-runs/{run_id}` | import run 상세 |
| `POST` | `/api/data/validate-csv` | CSV validation preview |
| `POST` | `/api/data/import-csv-confirmed` | validated run confirm |
| `GET` | `/api/data/quality` | quality checks 필터 조회 |
| `GET` | `/api/data/quality/{run_id}` | run별 quality checks |
| `POST` | `/api/data/import/daily-ohlcv` | legacy direct import |

## 실행

Backend:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm.cmd install
npm.cmd run build
npm.cmd run start -- --hostname 127.0.0.1 --port 3000
```

포트 충돌 시 backend `8001`, frontend `3001`을 사용합니다. backend 포트를 바꾸면 `frontend/.env.local`의 `NEXT_PUBLIC_API_BASE_URL`을 맞춘 뒤 다시 build해야 합니다.

## 검증

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
npm.cmd audit --audit-level=moderate
```

상세 검증 결과는 `docs/VALIDATION.md`를 확인합니다.

## 안전 제약

- 외부 API 호출 없음
- API key/secret/token/password 저장 없음
- 실제 주문 없음
- 주문 row 생성 없음
- paper/live broker 없음
- 실시간 websocket 없음
- AI 예측 모델 없음
- Mock Broker는 preview-only
- Phase 3A 후에도 `orders_count == 0`
