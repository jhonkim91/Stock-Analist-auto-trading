# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `MVP v0.5 Phase 3C KIS read-only foundation`
- [x] Phase 1 Backend Core MVP 구현
- [x] Phase 2 MVP Web Flow 구현
- [x] Phase 3A 데이터 품질/preview-confirm CSV import 구현
- [x] Phase 3A PR #1 merge 완료
- [x] Phase 3B provider-neutral external daily OHLCV flow 구현
- [x] Phase 3B PR #2 merge 완료: `754a139c24b3e3742f2060a9589d96d21a75d2b9`
- [x] Phase 3C KIS read-only foundation 구현
- [x] Phase 3C PR #3 merge 완료: `b696ce28603d0c7329e1f36f8bcb8b48db617710`
- [x] 현재 브랜치: `main`

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, provider-neutral external daily OHLCV preview/confirm, KIS read-only foundation, indicator recompute, screener, report, backtest, mock broker preview-only.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/settings`.
- Data Quality: `/data`에서 CSV validate/confirm, External Daily OHLCV fetch preview/confirm, KIS read-only status를 확인 가능.
- External provider: `external_yfinance`는 `provider_name=yfinance`, `network_enabled=false`, `manual_preview_only=true`.
- KIS market data source: `kis_market_data`는 `provider_type=external_market_data`, `provider_name=kis`, `enabled=false`, `network_enabled=false`, `read_only_enabled=false`.
- KIS broker placeholder: `kis_openapi`는 `provider_type=broker_placeholder`이며 Phase 3D 이후 broker adapter용이다.
- KIS provider: `KisMarketDataProvider` skeleton은 실제 network call을 금지하고, `MockKisMarketDataProvider`만 fixture preview/confirm 테스트에 사용한다.
- Settings/KIS API: secret 값은 반환하지 않고 configured boolean만 제공한다.
- Phase 3C post-merge: KIS secret 저장/노출 없음, KIS broker/order/websocket route 미구현.
- Frontend security: `postcss@8.5.15` override로 `npm audit` 0 vulnerabilities.

## Phase 3C 추가 파일/구조

- Config: `backend/config/data_sources.yaml`에 `kis_market_data` 추가, `kis_openapi`를 broker placeholder로 명확화.
- Backend services: `KisMarketDataProvider`, `MockKisMarketDataProvider`, `KisReadOnlyService`.
- Backend API: `/api/kis/status`, `/api/kis/config`, `/api/kis/config/validate`.
- Backend tests: `backend/tests/test_phase3c_kis_readonly.py`.
- Frontend route: `frontend/app/data/page.tsx` KIS read-only status panel.
- Docs: `README.md`, `docs/VALIDATION.md`, `.env.example`.

## 최신 검증 결과

- 2026-05-21 `.\.venv\Scripts\python.exe -m pytest backend/tests`: 50 passed in 261.06s
- 2026-05-21 `npm.cmd run lint`: 통과
- 2026-05-21 `npm.cmd exec tsc -- --noEmit`: 통과
- 2026-05-21 `npm.cmd run build`: Next.js 16.2.6 production build 통과, `/data` 포함
- 2026-05-21 `npm.cmd audit --audit-level=moderate`: found 0 vulnerabilities
- 2026-05-21 Browser/API smoke: backend `8002`, frontend `3010`, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/settings` 통과, route smoke console error/request failure/unexpected HTTP error 없음
- 2026-05-21 API smoke: `/api/kis/status`, `/api/kis/config`, `/api/kis/config/validate` 정상, KIS disabled preview HTTP 400 차단, KIS order/broker/websocket endpoint 404, sensitive value 노출 0
- 2026-05-21 Phase 3C 검증 후 `orders_count == 0`

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
- latest_trade_date: 2026-05-20
- latest_indicator_date: 2026-05-20
- latest_screen_date: 2026-05-20

## 불변식

- CSV `validate-csv`와 external/KIS preview는 `import_runs`와 `data_quality_checks`만 기록한다.
- Preview 전후 `symbol_master`, `daily_ohlcv`, `indicator_snapshot`, `screen_results`, `reports`, `backtest_runs`, `orders` count는 바뀌지 않아야 한다.
- Confirm 전에는 `daily_ohlcv`와 `symbol_master`가 변경되지 않아야 한다.
- Confirm 후에만 `daily_ohlcv` insert/update가 발생한다.
- External provider는 반드시 `external_symbol_mapping`을 거친다.
- Mapping이 없으면 `SYMBOL_MAPPING_FAILED`를 기록하고 confirm 불가 상태가 된다.
- Mock Broker는 preview-only이며 `orders_count == 0`을 유지한다.

## 주의 사항

- yfinance는 production-grade provider가 아니며 provider 구조 검증/manual preview/prototype 용도다.
- 기본값은 `network_enabled=false`; 테스트와 browser smoke에서 실제 외부 네트워크를 호출하지 않는다.
- KIS 실제 API 호출, KIS app key/app secret 저장, KIS 계좌번호 저장, KIS token cache 생성 금지.
- KIS 주문/잔고/체결/계좌/websocket API 구현 금지.
- paper/live broker, 실제 주문, 주문 row 생성, 자동매매 스케줄러, AI 예측 모델 금지.
- API key, secret, token, password, account 값을 저장하거나 Settings/API/docs/logs에 노출하지 않는다.
- yfinance/KIS 전용 DB/API/UI 하드코딩 금지. `source_id` 기반 provider-neutral API를 유지한다.
- `npm audit fix --force`, Next.js downgrade, main 강제 push 금지.
- `frontend/.env.local`은 local-only ignored file이다. backend 포트를 바꾸면 값을 맞춘 뒤 `npm.cmd run build`를 다시 실행한다.

## 다음 작업

- Phase 3D는 사용자 별도 승인 후 계획모드에서만 KIS broker adapter, token lifecycle, kill switch, order risk gate를 설계한다.
