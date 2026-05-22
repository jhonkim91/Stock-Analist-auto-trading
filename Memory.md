# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `MVP v0.8 Phase 3F-1 read-only data provider contract`
- [x] Phase 1 Backend Core MVP 구현
- [x] Phase 2 MVP Web Flow 구현
- [x] Phase 3A CSV validate/confirm import 구현
- [x] Phase 3B provider-neutral external daily OHLCV preview/confirm 구현
- [x] Phase 3C KIS read-only foundation 구현
- [x] Phase 3D broker safety scaffold 구현
- [x] Phase 3E-1 paper preview safety scaffold 구현
- [x] Phase 3F-1 read-only data provider contract 구현
- [x] 단계별 계획 문서 `docs/plans/README.md`와 Phase 3F 상세 계획 문서 작성
- [x] 현재 브랜치: `main`

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, external daily OHLCV preview/confirm, KIS read-only foundation, broker safety scaffold, paper preview scaffold, Phase 3F-1 read-only provider contract.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/settings`.
- Data Quality: `/data`에서 CSV validate/confirm, External Daily OHLCV preview/confirm, KIS status, read-only provider contract 확인 가능.
- Plan docs: 전체 Phase 순서는 `docs/plans/README.md`, Phase 3F 상세 계획은 `docs/plans/phase-3f-readonly-data-reliability.md`에서 관리한다.
- 신규 Phase 3F-1 API: `GET /api/data/read-only/providers`.
- 신규 read-only sources: `krx_index_sector`, `krx_symbol_master`, `krx_trading_calendar`, `krx_corporate_actions`.
- KIS market data source: `kis_market_data`는 `provider_type=external_market_data`, `provider_name=kis`, `enabled=false`, `network_enabled=false`, `read_only_enabled=false`.
- KIS broker placeholder: `kis_openapi`는 `provider_type=broker_placeholder`, `enabled=false`, `network_enabled=false`, `paper_trading_enabled=false`, `live_trading_enabled=false`, `websocket_enabled=false`.
- Broker safety: `/api/broker/status`, `/api/broker/orders/preview`만 safety scaffold 상태를 반환한다.
- Paper safety: `/api/paper/status`, `/api/paper/orders/preview`만 disabled deny scaffold 상태를 반환한다.
- KIS execution routes: `/api/kis/orders/*`, `/api/kis/broker/*`, `/api/kis/websocket/*`는 미등록 404 상태를 유지한다.
- Frontend security: `postcss@8.5.15` override로 `npm audit` 0 vulnerabilities.

## Phase 3F-1 변경 파일/구조

- Config: `backend/config/data_sources.yaml`에 KIS/KRX read-only capability/status source 정의.
- Backend API: `backend/app/api/data.py`에 `GET /api/data/read-only/providers` 추가.
- Backend service: `backend/app/services/market_data_import_service.py`에 read-only provider status 계산 추가.
- Backend provider contract: `backend/app/services/data_providers.py`에 `ReadOnlyDataProvider` protocol 추가.
- Backend tests: `backend/tests/test_phase3f_readonly_provider_contract.py`.
- Frontend API type: `frontend/lib/api.ts` `ReadOnlyProviderStatus`.
- Frontend page: `frontend/app/data/page.tsx` read-only provider contract panel.
- Docs: `docs/VALIDATION.md`, `Memory.md`, `README.md`, `docs/plans/README.md`, `docs/plans/phase-3f-readonly-data-reliability.md`.

## 최신 검증 결과

- 2026-05-22 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3f_readonly_provider_contract.py -q`: 2 passed in 2.01s
- 2026-05-22 `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 62 passed in 116.53s
- 2026-05-22 `npm.cmd run lint`: 통과
- 2026-05-22 `npm.cmd exec tsc -- --noEmit`: 통과
- 2026-05-22 `npm.cmd run build`: Next.js 16.2.6 production build 통과, `/data` read-only panel 포함
- 2026-05-22 `npm.cmd audit --audit-level=moderate`: found 0 vulnerabilities
- 2026-05-22 browser smoke: fresh backend/frontend `8010/3010`, `/data`에서 `Read-only Provider Contract`, `kis_market_data`, `krx_index_sector`, `NETWORK_DISABLED_FAIL_CLOSED` 확인
- 2026-05-22 safety smoke: `orders_count == 0`, `paper_* == 0`, `token_issued=false`, `token_cache_enabled=false`, `network_call_performed=false`, adapter order/network call false
- 2026-05-22 plan docs check: `rg`로 `docs/plans` 링크와 Phase 순서 확인, `git diff --check` 통과

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

- `GET /api/data/read-only/providers`는 status/capability 조회만 수행하고 fetch 또는 DB mutation을 하지 않는다.
- CSV `validate-csv`와 external/KIS market-data preview는 `import_runs`와 `data_quality_checks`만 기록한다.
- Confirm 전에는 `daily_ohlcv`와 `symbol_master`를 변경하지 않는다.
- External provider는 반드시 `external_symbol_mapping`을 거친다.
- Mapping이 없으면 `SYMBOL_MAPPING_FAILED`를 기록하고 confirm 불가 상태가 된다.
- Broker preview는 safety scaffold only이며 `orders_count == 0`을 유지한다.
- Paper preview는 disabled deny scaffold only이며 `orders_count == 0`, `paper_* == 0`을 유지한다.
- Sell preview는 기존 long position 청산 검토 전용이고, 포지션 없음/수량 초과/short sell은 deny한다.

## 주의 사항

- 기본값은 `network_enabled=false`; 테스트와 smoke에서 실제 외부 네트워크를 호출하지 않는다.
- KIS 실제 API 호출, KIS app key/app secret 저장, KIS 계좌번호 저장, KIS token cache 생성 금지.
- KIS 주문/잔고/체결/계좌/websocket API 구현 금지.
- `POST /api/paper/orders`, fill simulator, paper order create, paper fill 생성, paper position 변경 금지.
- live broker, 실제 주문, cancel/fill/websocket 연결, 자동매매 스케줄러, AI 예측 모델 금지.
- API key, secret, token, password, account, header, raw credential 값을 저장하거나 Settings/API/docs/logs에 노출하지 않는다.
- yfinance/KIS/KRX 전용 UI write path를 만들지 말고 `source_id` 기반 provider-neutral API를 유지한다.
- `npm audit fix --force`, Next.js downgrade, main 강제 push 금지.
- `frontend/.env.local`은 local-only ignored file이다. backend 포트를 바꾸면 값을 맞춘 뒤 `npm.cmd run build`를 다시 실행한다.
- 현재 작업 전부터 `docs/research/검토결과.md`, `docs/research/제품설계문서.md`가 untracked 상태였고 이번 구현에서는 건드리지 않았다.

## 다음 작업

- [ ] Phase 3F-2: KIS read-only daily OHLCV adapter 구현. 주문/계좌/잔고/체결 API는 제외하고 기존 preview/confirm flow로만 연결.
- [ ] Phase 3F-3: KRX index/sector/symbol/calendar/corporate action source contract를 fixture/read-only 기반으로 설계.
- [ ] Phase 3F-4: data freshness/quality summary와 `/data` read-only summary panel 구현.
- [ ] Phase 3G: gap-aware stop, liquidity cap, partial fill, portfolio state 기반 백테스트 보강.
