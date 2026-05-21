# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `MVP v0.4 Phase 3B provider-neutral external data`
- [x] Phase 1 Backend Core MVP 구현
- [x] Phase 2 MVP Web Flow 구현
- [x] Phase 3A 데이터 품질/preview-confirm CSV import 구현
- [x] Phase 3A PR #1 merge 완료
- [x] Phase 3B provider-neutral external daily OHLCV flow 구현
- [x] 작업 브랜치: `phase-3b-external-data-provider`

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, provider-neutral external daily OHLCV preview/confirm, indicator recompute, screener, report, backtest, mock broker preview-only.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/settings`.
- Data Quality: `/data`에서 CSV validate/confirm과 External Daily OHLCV fetch preview/confirm을 모두 확인 가능.
- External provider: `external_yfinance`는 `provider_name=yfinance`, `network_enabled=false`, `manual_preview_only=true`.
- External provider policy: `external_yfinance`는 `unknown_symbol_policy=warn_and_create_on_confirm`, mock metadata `provider_mode=mock`, `data_origin=deterministic_mock`.
- KIS placeholder: `kis_openapi`는 disabled이며 secret/account/token/order/websocket 필드와 구현이 없다.
- KIS placeholder policy: `kis_openapi`는 `unknown_symbol_policy=reject`를 유지한다.
- Settings: `backend/config/*.yaml` read-only 표시, 민감 키 redaction 유지, `data_sources.yaml` 포함.
- Frontend security: `postcss@8.5.15` override로 `npm audit` 0 vulnerabilities.

## Phase 3B 추가 파일/구조

- Config: `backend/config/data_sources.yaml`에 `external_yfinance`, `kis_openapi` 추가.
- Backend services: `BaseExternalDataProvider`, `MockExternalDailyProvider`, `YFinanceDailyProvider`, `KisOpenApiProvider` placeholder.
- Backend flow: `import_runs.provider_metadata_json`, `import_runs.source_config_snapshot_json` 추가.
- Backend API: `/api/data/external/providers`, `/preview-daily-ohlcv`, `/confirm-import`, `/fetch-runs`.
- Backend tests: `backend/tests/test_phase3b_external_provider.py`.
- Frontend route: `frontend/app/data/page.tsx` external provider panel.

## 최신 검증 결과

- 2026-05-21 `.\.venv\Scripts\python.exe -m pytest backend/tests`: 43 passed in 101.54s
- 2026-05-21 `npm.cmd run lint`: 통과
- 2026-05-21 `npm.cmd exec tsc -- --noEmit`: 통과
- 2026-05-21 `npm.cmd run build`: Next.js 16.2.6 production build 통과, `/data` 포함
- 2026-05-21 `npm.cmd audit --audit-level=moderate`: found 0 vulnerabilities
- 2026-05-21 Browser smoke: `/data` external preview/confirm 통과, API request failure 없음
- 2026-05-21 Browser smoke: mock/fixture 안내 문구, provider metadata `provider_mode=mock`, `data_origin=deterministic_mock`, Import History confirmed 표시 통과
- 2026-05-21 Phase 3B 후 `orders_count == 0`

## 최신 DB count

- symbol_master: 16
- daily_ohlcv: 4,803
- index_ohlcv: 320
- sector_ohlcv: 2,880
- fundamentals_pti: 30
- indicator_snapshot: 4,800
- screen_results: 45
- reports: 1
- backtest_runs: 3
- import_runs: 23
- data_quality_checks: 122
- external_symbol_mapping: 32
- orders_count: 0
- latest_trade_date: 2026-05-21
- latest_indicator_date: 2026-05-20
- latest_screen_date: 2026-05-20

## 불변식

- CSV `validate-csv`와 external preview는 `import_runs`와 `data_quality_checks`만 기록한다.
- Preview 전후 `symbol_master`, `daily_ohlcv`, `indicator_snapshot`, `screen_results`, `reports`, `backtest_runs`, `orders` count는 바뀌지 않아야 한다.
- Confirm 전에는 `daily_ohlcv`와 `symbol_master`가 변경되지 않아야 한다.
- Confirm 후에만 `daily_ohlcv` insert/update가 발생한다.
- External provider는 반드시 `external_symbol_mapping`을 거친다.
- Mapping이 없으면 `SYMBOL_MAPPING_FAILED`를 기록하고 confirm 불가 상태가 된다.
- Mock Broker는 preview-only이며 `orders_count == 0`을 유지한다.

## 주의 사항

- yfinance는 production-grade provider가 아니며 provider 구조 검증/manual preview/prototype 용도다.
- 기본값은 `network_enabled=false`; 테스트와 browser smoke에서 실제 외부 네트워크를 호출하지 않는다.
- KIS 실제 API 호출, KIS app key/app secret 저장, KIS 계좌번호 저장, KIS 주문 API 구현 금지.
- paper/live broker, 실제 주문, 주문 row 생성, websocket, 자동매매 스케줄러, AI 예측 모델 금지.
- API key, secret, token, password를 저장하거나 Settings에 노출하지 않는다.
- yfinance 전용 DB/API/UI 하드코딩 금지. `source_id` 기반 provider-neutral API를 유지한다.
- `npm audit fix --force`, Next.js downgrade, main 강제 push 금지.
- `frontend/.env.local`은 local-only ignored file이다. backend 포트를 바꾸면 값을 맞춘 뒤 `npm.cmd run build`를 다시 실행한다.

## 다음 작업

- Phase 3B PR 생성 전 `git diff` 확인과 필요 시 브라우저 smoke 재실행.
- Phase 3C에서만 KIS read-only foundation을 별도 설계한다.
- KIS 확장 시 `KisMarketDataProvider`와 `KisBrokerAdapter`를 분리하고, broker/order/websocket은 Phase 3D 이후로 유지한다.
