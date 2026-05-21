# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `MVP v0.3 Phase 3A data quality`
- [x] Phase 1 Backend Core MVP 구현
- [x] Phase 2 MVP Web Flow 구현
- [x] Phase 2 마감 QA 완료
- [x] Phase 3A 데이터 품질/preview-confirm import 구현
- [x] Phase 3A 마감 QA 완료
- [x] GitHub 초기 publish 완료: `jhonkim91/Stock-Analist-auto-trading`
- [x] 작업 브랜치: `phase-3a-data-quality`

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, indicator recompute, screener, report, backtest, mock broker preview-only.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/settings`.
- Data Quality: `/data`에서 source 선택, CSV validate, preview rows, quality checks, confirm import, import history/detail 확인.
- Legacy endpoint: `POST /api/data/import/daily-ohlcv` 유지. 내부는 `MarketDataImportService` 사용.
- New flow: `POST /api/data/validate-csv` 후 `POST /api/data/import-csv-confirmed`.
- Settings: `backend/config/*.yaml` read-only 표시, 민감 키 redaction 유지, `data_sources.yaml` 포함.
- Frontend security: `postcss@8.5.15` override로 `npm audit` 0 vulnerabilities.

## Phase 3A 추가 파일/구조

- Config: `backend/config/data_sources.yaml`
- Backend services: `data_providers.py`, `market_data_import_service.py`
- Backend tables: `data_sources`, `import_runs`, `data_quality_checks`, `external_symbol_mapping`, `corporate_actions`, `trading_calendar`
- Backend tests: `backend/tests/test_phase3a_data_quality.py`
- Frontend route: `frontend/app/data/page.tsx`

## 최신 검증 결과

- 2026-05-21 `.\.venv\Scripts\python.exe -m pytest backend/tests`: 37 passed in 119.24s
- 2026-05-21 `npm.cmd run lint`: 통과
- 2026-05-21 `npm.cmd exec tsc -- --noEmit`: 통과
- 2026-05-21 `npm.cmd run build`: Next.js 16.2.6 production build 통과, `/data` 포함
- 2026-05-21 `npm.cmd audit --audit-level=moderate`: found 0 vulnerabilities
- 2026-05-21 Browser smoke: `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/settings` 통과
- 2026-05-21 Browser smoke: CSV validate success/failure, Confirm 버튼 상태, Import History/Detail/Quality Checks 표시 통과
- 2026-05-21 Dashboard flow: seed -> indicators -> screener -> report -> backtest -> mock preview 통과
- 2026-05-21 Phase 3A 후 `orders_count == 0`

## 최신 DB count

- symbol_master: 15
- daily_ohlcv: 4,800
- index_ohlcv: 320
- sector_ohlcv: 2,880
- fundamentals_pti: 30
- indicator_snapshot: 4,800
- screen_results: 45
- reports: 1
- backtest_runs: 3
- import_runs: 15
- data_quality_checks: 74
- orders_count: 0
- latest_trade_date: 2026-05-20
- latest_indicator_date: 2026-05-20
- latest_screen_date: 2026-05-20

## Phase 3A 불변식

- `validate-csv`는 `import_runs`와 `data_quality_checks`만 기록한다.
- `validate-csv` 전후 `symbol_master`, `daily_ohlcv`, `index_ohlcv`, `sector_ohlcv`, `fundamentals_pti`, `indicator_snapshot`, `screen_results`, `reports`, `backtest_runs`, `orders` count는 바뀌지 않아야 한다.
- confirm 전에는 `daily_ohlcv`와 `symbol_master`가 변경되지 않아야 한다.
- confirm 후에만 insert/update count가 확정된다.
- unknown symbol은 validate 단계에서 `UNKNOWN_SYMBOL` warning만 기록하고, confirm 단계에서 기본 `symbol_master` row를 생성할 수 있다.
- zero volume은 `ZERO_VOLUME` warning만 기록한다. `daily_ohlcv`에 trading status 컬럼은 추가하지 않는다.

## 주의 사항

- 외부 API 연동, 실제 주문, 주문 row 생성, paper/live broker, 실시간 websocket, AI 예측 모델은 구현하지 않는다.
- Mock Broker는 preview-only이며 `orders_count == 0`을 유지한다.
- API key, secret, token, password를 저장하거나 Settings에 노출하지 않는다.
- `npm audit fix --force`, Next.js downgrade, main 강제 push 금지.
- `frontend/.env.local`은 local-only ignored file이다. backend 포트를 바꾸면 값을 맞춘 뒤 `npm.cmd run build`를 다시 실행한다.
- Browser smoke 전용으로 8010/3010을 사용할 수 있으며 backend CORS allowlist에 포함되어 있다.

## 다음 작업

- Phase 3B 진입 전 PR 생성과 리뷰를 완료한다.
- Phase 3B에서는 external provider 실제 연동 전 secret 저장 방식, rate limit, staging table, market calendar/corporate action 적용 정책을 별도 설계한다.
