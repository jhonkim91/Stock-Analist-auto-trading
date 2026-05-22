# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `MVP v0.9 Phase 3F-4 Data Freshness/Quality Summary`
- [x] Phase 1 Backend Core MVP 구현
- [x] Phase 2 MVP Web Flow 구현
- [x] Phase 3A CSV validate/confirm import 구현
- [x] Phase 3B provider-neutral external daily OHLCV preview/confirm 구현
- [x] Phase 3C KIS read-only foundation 구현
- [x] Phase 3D broker safety scaffold 구현
- [x] Phase 3E-1 paper preview safety scaffold 구현
- [x] Phase 3F-1 read-only data provider contract 구현
- [x] Phase 3F-2 KIS daily OHLCV fixture adapter 구현
- [x] Phase 3F-3 KRX fixture source contract 구현
- [x] Phase 3F-4 data freshness/quality summary 구현
- [x] 현재 브랜치: `main`

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, external daily OHLCV preview/confirm, KIS read-only foundation, broker safety scaffold, paper preview scaffold, Phase 3F read-only data reliability API.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/settings`.
- `/data`: CSV validate/confirm, External Daily OHLCV preview/confirm, KIS status, read-only provider contract, freshness/quality summary panel을 표시한다.
- Phase 계획 문서: `docs/plans/README.md`, `docs/plans/phase-3f-readonly-data-reliability.md`.
- Frontend security: `postcss@8.5.15` override로 `npm audit` 0 vulnerabilities.

## Phase 3F-4 변경 파일/구조

- `backend/app/services/data_quality_summary_service.py`
  - `DataQualitySummaryService.summary()` 신규 추가.
  - SELECT 기반으로 `latest_trade_date`, row counts, source freshness, missing rows, duplicate summary, quality counts, safety counts를 계산한다.
  - service 내부에서 `add/delete/commit/rollback/provider fetch`를 호출하지 않는다.
- `backend/app/api/data.py`
  - `GET /api/data/quality-summary` 추가.
  - query: `market=KR`, `venue=KRX`, `lookback_trading_dates=30`, 범위 `1..252`.
- `frontend/lib/api.ts`
  - `DataQualitySummary`, `SourceFreshness` 타입 추가.
- `frontend/app/data/page.tsx`
  - `Freshness & Quality Summary` read-only panel 추가.
  - 기존 validate/confirm/read-only providers UI flow는 유지.
- `backend/tests/test_phase3f4_data_quality_summary.py`
  - response contract, calendar fallback, calendar 기준 coverage, duplicate code count, no mutation, safety/route invariant, 기존 provider contract regression 검증.
- 문서: `docs/VALIDATION.md`, `Memory.md`, `docs/plans/phase-3f-readonly-data-reliability.md`, `README.md`.

## Phase 3F-4 계산 규칙

- `latest_trade_date`: `daily_ohlcv.trade_date` max, `venue` 필터 적용.
- `source_freshness`: CSV/external/read-only source 기준.
  - disabled source: `freshness_status=DISABLED`
  - enabled daily OHLCV source confirmed run 없음: `NO_CONFIRMED_RUN`
  - enabled read-only reference source confirmed run 없음: `NOT_APPLICABLE`
  - confirmed trade date가 latest trade date와 같으면 `CURRENT`, 뒤처지면 `STALE`
- `missing_rows`: `trading_calendar` open date가 있으면 calendar 기준, 없으면 observed `daily_ohlcv` date 기준.
- latest trade date missing symbol sample은 최대 20개.
- `duplicate_summary`: physical duplicate와 `DUPLICATE_IN_BATCH`/`DUPLICATE_IN_DATABASE` quality code 집계를 분리.
- `quality_counts`: severity별 count와 top check code 집계.
- `safety_counts`: orders/paper row count는 DB 조회, token/network/adapter flags는 false.

## 최신 검증 결과

- 2026-05-22 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3f4_data_quality_summary.py -q`: 6 passed in 4.98s
- 2026-05-22 `.\.venv\Scripts\python.exe -m pytest backend/tests`: 79 passed in 123.38s
- 2026-05-22 `npm.cmd run lint`: 통과
- 2026-05-22 `npm.cmd exec tsc -- --noEmit`: 통과
- 2026-05-22 `npm.cmd run build`: Next.js 16.2.6 production build 통과
- 2026-05-22 `npm.cmd audit --audit-level=moderate`: found 0 vulnerabilities
- 2026-05-22 API sample: seeded DB `GET /api/data/quality-summary` 200, `latest_trade_date=2026-05-20`, `daily_ohlcv=4800`, safety counts 0/false.
- 2026-05-22 `/data` smoke: fresh backend/frontend `8010/3010`, Playwright CLI screenshot selector `Freshness & Quality Summary` 확인.

## 최신 DB count

- symbol_master: 15
- daily_ohlcv: 4,800
- index_ohlcv: 320
- sector_ohlcv: 2,880
- fundamentals_pti: 30
- indicator_snapshot: 4,800
- screen_results: 45
- reports: 1
- backtest_runs: 7
- orders_count: 0
- paper_orders: 0
- paper_fills: 0
- paper_positions: 0
- paper_audit_events: 0
- latest_trade_date: 2026-05-20
- latest_indicator_date: 2026-05-20
- latest_screen_date: 2026-05-20

## 불변 조건

- `GET /api/data/quality-summary`는 SELECT 기반 read-only 조회만 수행한다.
- `GET /api/data/read-only/providers`는 status/capability 조회만 수행하고 fetch 또는 DB mutation을 하지 않는다.
- CSV `validate-csv`와 external/KIS market-data preview는 `import_runs`와 `data_quality_checks`만 기록한다.
- Confirm 전에는 `daily_ohlcv`와 `symbol_master`를 변경하지 않는다.
- Confirm은 `run_id`만 받아 staged rows를 transaction으로 `daily_ohlcv`에 반영한다.
- KRX source 4종은 기본 `enabled=false`, `network_enabled=false`, `read_only_enabled=false`.
- Broker preview는 safety scaffold only이며 `orders_count == 0`을 유지한다.
- Paper preview는 disabled deny scaffold only이며 `orders_count == 0`, `paper_* == 0`을 유지한다.

## 주의 사항

- 기본값은 `network_enabled=false`; 테스트나 smoke에서 실제 외부 네트워크를 호출하지 않는다.
- KRX 실제 API 호출, KIS 실제 API 호출, KIS app key/app secret 저장, KIS 계좌번호 저장, KIS token cache 생성 금지.
- KIS 주문/계좌/잔고/체결/cancel/websocket API 구현 금지.
- `POST /api/paper/orders`, fill simulator, paper order create, paper fill 생성, paper position 변경 금지.
- live broker, 실제 주문, cancel/fill/websocket 연결, 자동매매 scheduler, AI 예측 모델 금지.
- API key, secret, token, password, account, header, raw credential 값을 저장하거나 Settings/API/docs/logs에 노출하지 않는다.
- yfinance/KIS/KRX 전용 UI write path를 만들지 말고 `source_id` 기반 provider-neutral API를 유지한다.
- `npm audit fix --force`, Next.js downgrade, main 강제 push 금지.
- `frontend/.env.local`은 local-only ignored file이다. backend 포트를 바꾸면 값을 맞춘 뒤 `npm.cmd run build`를 다시 실행한다.

## 다음 작업

- [ ] Phase 3G: gap-aware stop, liquidity cap, partial fill, portfolio state 기반 백테스트 보강.
- [ ] Phase 3F 후속: quality-summary 기간/시장 필터 UI, source freshness 상세 drilldown, calendar load flow는 별도 승인 후 진행.
