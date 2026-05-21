# Stock Analyst Auto Trading

주식 분석과 자동매매 보조 흐름을 검증 가능한 MVP 형태로 구현한 FastAPI + Next.js 프로젝트입니다.

현재 checkpoint는 `MVP v0.5 Phase 3C KIS read-only foundation`입니다. 실제 주문, paper/live broker, KIS 실제 API 호출, 실시간 websocket, 자동매매 스케줄러, AI 예측 모델은 구현하지 않습니다.

## Phase 3C 기능

- Phase 3A CSV validate/confirm flow 유지
- Phase 3B provider-neutral external daily OHLCV preview/confirm flow 유지
- KIS read-only market data foundation 추가
  - `kis_market_data`: KIS market data 전용 source, 기본 disabled
  - `KisMarketDataProvider`: 실제 KIS 호출 금지 skeleton
  - `MockKisMarketDataProvider`: KIS 기간별시세 형태 fixture provider
  - `/api/kis/status`, `/api/kis/config`, `/api/kis/config/validate`
- KIS broker boundary 명확화
  - `kis_openapi`: Phase 3D 이후 broker adapter placeholder
  - Phase 3C에서는 broker DI/route/order/account/balance/fill/websocket 구현 없음
- `BaseExternalDataProvider` 기반 provider 구조 추가
  - `MockExternalDailyProvider`: 테스트/fixture 전용, 네트워크 호출 없음
  - `YFinanceDailyProvider`: 첫 external market data provider 구현체
  - `MockKisMarketDataProvider`: KIS read-only fixture 전용, 네트워크 호출 없음
- `external_yfinance` source 추가
  - `provider_type: external_market_data`
  - `provider_name: yfinance`
  - `network_enabled: false`
  - `manual_preview_only: true`
- `kis_market_data` source 추가
  - `provider_type: external_market_data`
  - `provider_name: kis`
  - `enabled: false`
  - `network_enabled: false`
  - `read_only_enabled: false`
  - `manual_preview_only: true`
  - secret/account/token 필드 없음
- `kis_openapi` broker placeholder 유지
  - `provider_type: broker_placeholder`
  - `enabled: false`
  - `network_enabled: false`
  - `paper_trading_enabled: false`
  - `live_trading_enabled: false`
  - `websocket_enabled: false`
  - secret/account/token/order 구현 없음
- `/data` 화면에 External Daily OHLCV Preview panel 추가
- `/data` 화면에 KIS read-only status panel 추가

## Import Flow

CSV flow:

1. `POST /api/data/validate-csv`
2. `POST /api/data/import-csv-confirmed`

External flow:

1. `POST /api/data/external/preview-daily-ohlcv`
2. `POST /api/data/external/confirm-import`

Preview 단계는 market data table을 직접 변경하지 않습니다. 허용되는 write는 `import_runs +1`, `data_quality_checks +N`뿐입니다.

Confirm은 `run_id`만 받으며 파일 또는 provider를 다시 조회하지 않습니다. `import_runs.staged_rows_json`을 transaction으로 `daily_ohlcv`에 반영합니다.

## External Provider 정책

`yfinance`는 production-grade 데이터 provider가 아닙니다. 자동매매용 최종 신뢰 데이터 소스로 사용하지 않고, provider-neutral 구조 검증과 manual preview/prototype 용도로만 사용합니다.

Phase 3B 기본 정책:

- 테스트와 browser smoke에서는 실제 네트워크 호출을 하지 않습니다.
- `network_enabled=false`가 기본값입니다.
- mock provider와 fixture 기반 테스트를 우선합니다.
- API key, secret, token, account 정보는 저장하지 않습니다.
- provider별 symbol mapping은 `external_symbol_mapping`을 반드시 거칩니다.

Symbol mapping 예:

| provider | internal_symbol | provider_symbol |
|---|---|---|
| yfinance | `005930` | `005930.KS` |
| kis | `005930` | `005930` |

매핑이 없으면 `SYMBOL_MAPPING_FAILED` quality check를 생성하고 `daily_ohlcv`에는 쓰지 않습니다.

## KIS 향후 확장 정책

KIS 확장은 단계별로 분리합니다.

- Phase 3C: KIS read-only foundation, 현재 checkpoint
- Phase 3D: KIS paper trading adapter
- Phase 3E: KIS live trading gate
- Phase 3F: KIS websocket/체결통보

KIS는 data provider와 broker adapter를 분리합니다.

- `KisMarketDataProvider`: read-only market data, 현재가/기간별시세/종목 기본정보 후보
- `KisBrokerAdapter`: 주문/잔고/체결/계좌, Phase 3D 이후

Phase 3C에서는 `KisMarketDataProvider` skeleton과 `MockKisMarketDataProvider` fixture만 구현합니다. `KisBrokerAdapter`는 DI와 route에 연결하지 않습니다.

KIS read-only API 후보는 fixture/schema/normalization 설계에만 사용합니다.

| 후보 | 용도 |
|---|---|
| `/uapi/domestic-stock/v1/quotations/inquire-price`, TR `FHKST01010100` | 국내주식 현재가 후보 |
| `/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice`, TR `FHKST03010100` | Phase 3C primary daily_ohlcv fixture |
| `/uapi/domestic-stock/v1/quotations/inquire-daily-price`, TR `FHKST01010400` | 일자별 시세 후보 |
| `/uapi/domestic-stock/v1/quotations/search-stock-info` | 종목 기본정보 후보 |
| 업종/지수 API | 문서 후보, Phase 3C import 연결 없음 |

## Secret 정책

- 실제 KIS app key/app secret/account/token은 저장하지 않습니다.
- `.env.example`에는 placeholder만 둡니다.
- `/api/kis/status`와 `/api/kis/config`는 configured boolean만 반환하며 secret 값을 반환하지 않습니다.
- `/api/kis/config/validate`는 환경변수 존재와 형식만 확인하고 KIS network call, 토큰 발급, token cache 생성을 하지 않습니다.
- Settings API와 logs에는 secret 값을 출력하지 않습니다.

## CSV 제한

| 항목 | 제한 |
|---|---:|
| 최대 row 수 | 10,000 |
| preview rows | 100 |
| 파일 크기 | 10MB 이하 |

Phase 3B에서도 `staged_rows_json`을 SQLite 호환 `Text` JSON으로 저장합니다. 대용량 import는 이후 staging table 분리를 검토합니다.

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
- `SYMBOL_MAPPING_FAILED`
- `PROVIDER_ROW_COUNT_MISMATCH`
- `DATE_RANGE_TOO_LARGE`
- `PROVIDER_RESPONSE_SCHEMA_MISMATCH`
- `PROVIDER_TIMEOUT`
- `PROVIDER_PARTIAL_RESPONSE`
- `RATE_LIMIT_EXCEEDED`
- `STALE_DATA`

## 주요 API

| Method | Path | 설명 |
|---|---|---|
| `GET` | `/api/data/status` | 데이터 row count와 최신 기준일 |
| `GET` | `/api/data/sources` | data source 목록 |
| `GET` | `/api/data/import-runs` | 전체 import history |
| `GET` | `/api/data/import-runs/{run_id}` | import run 상세 |
| `POST` | `/api/data/validate-csv` | CSV validation preview |
| `POST` | `/api/data/import-csv-confirmed` | validated CSV run confirm |
| `GET` | `/api/data/quality` | quality checks 필터 조회 |
| `GET` | `/api/data/quality/{run_id}` | run별 quality checks |
| `POST` | `/api/data/import/daily-ohlcv` | legacy direct import |
| `GET` | `/api/data/external/providers` | external-capable provider source 목록 |
| `POST` | `/api/data/external/preview-daily-ohlcv` | external daily OHLCV preview |
| `POST` | `/api/data/external/confirm-import` | external run confirm |
| `GET` | `/api/data/external/fetch-runs` | external fetch run 목록 |
| `GET` | `/api/data/external/fetch-runs/{run_id}` | external fetch run 상세 |
| `GET` | `/api/kis/status` | KIS read-only status |
| `GET` | `/api/kis/config` | KIS redacted config |
| `POST` | `/api/kis/config/validate` | KIS env configured boolean 검증 |

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

- KIS 실제 API 호출 없음
- KIS app key/app secret 저장 없음
- KIS 계좌번호 저장 없음
- KIS 주문 API 구현 없음
- KIS token cache 생성 없음
- API key/secret/token/password 저장 없음
- 실제 주문 없음
- 주문 row 생성 없음
- paper/live broker 없음
- 실시간 websocket 없음
- 자동매매 스케줄러 없음
- AI 예측 모델 없음
- yfinance 전용 DB/API/UI 하드코딩 없음
- Mock Broker는 preview-only
- Phase 3B 후에도 `orders_count == 0`
