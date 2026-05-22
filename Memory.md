# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `MVP v0.8 Phase 3F-2 KIS read-only daily OHLCV fixture adapter`
- [x] Phase 1 Backend Core MVP 구현
- [x] Phase 2 MVP Web Flow 구현
- [x] Phase 3A CSV validate/confirm import 구현
- [x] Phase 3B provider-neutral external daily OHLCV preview/confirm 구현
- [x] Phase 3C KIS read-only foundation 구현
- [x] Phase 3D broker safety scaffold 구현
- [x] Phase 3E-1 paper preview safety scaffold 구현
- [x] Phase 3F-1 read-only data provider contract 구현
- [x] Phase 3F-2 KIS daily OHLCV fixture adapter 구현
- [x] 현재 브랜치: `main`

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, external daily OHLCV preview/confirm, KIS read-only foundation, broker safety scaffold, paper preview scaffold, Phase 3F read-only data provider contract.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/settings`.
- Data Quality: `/data`에서 CSV validate/confirm, External Daily OHLCV preview/confirm, KIS status, read-only provider contract 확인 가능.
- Plan docs: 전체 Phase 순서는 `docs/plans/README.md`, Phase 3F 상세 계획은 `docs/plans/phase-3f-readonly-data-reliability.md`에서 관리한다.
- KIS market data source: `kis_market_data`는 `provider_type=external_market_data`, `provider_name=kis`, `enabled=false`, `network_enabled=false`, `read_only_enabled=false`.
- KIS broker placeholder: `kis_openapi`는 `provider_type=broker_placeholder`, `enabled=false`, `network_enabled=false`, `paper_trading_enabled=false`, `live_trading_enabled=false`, `websocket_enabled=false`.
- KIS execution routes: `/api/kis/orders/*`, `/api/kis/broker/*`, `/api/kis/websocket/*`는 미등록 404 상태를 유지한다.
- Paper safety: `/api/paper/status`, `/api/paper/orders/preview`만 disabled deny scaffold 상태를 반환한다.
- Frontend security: `postcss@8.5.15` override로 `npm audit` 0 vulnerabilities.

## Phase 3F-2 변경 파일/구조

- Backend provider: `backend/app/services/data_providers.py`
  - KIS itemchart canonical fixture schema constants 추가.
  - `validate_kis_daily_itemchart_fixture()`와 `normalize_kis_daily_itemchart_rows()` 추가.
  - `MockKisMarketDataProvider`는 `network_enabled=false` 경로에서 canonical fixture schema 기반 deterministic rows를 생성한다.
  - `KisMarketDataProvider.fetch_daily_ohlcv()`는 계속 fail-closed 상태다.
- Fixture: `backend/tests/fixtures/kis_daily_itemchartprice_response.json`
  - Top-level fields: `rt_cd`, `msg_cd`, `msg1`, `output2`.
  - Row fields: `stck_bsop_date`, `stck_oprc`, `stck_hgpr`, `stck_lwpr`, `stck_clpr`, `acml_vol`, `acml_tr_pbmn`.
  - secret/account/token/header 계열 필드 없음.
- Backend tests: `backend/tests/test_phase3f2_kis_daily_ohlcv_adapter.py`
  - fixture schema, raw-to-normalized 변환, `kis_market_data` mock preview/confirm, read-only provider contract, KIS execution route 404를 검증한다.
- Docs: `docs/VALIDATION.md`, `Memory.md`, `README.md`.

## 최신 검증 결과

- 2026-05-22 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3f2_kis_daily_ohlcv_adapter.py -q`: 5 passed in 1.76s
- 2026-05-22 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3f_readonly_provider_contract.py backend/tests/test_phase3c_kis_readonly.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py -q`: 19 passed in 10.27s
- 2026-05-22 `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 67 passed in 119.71s
- 2026-05-22 `npm.cmd run lint`: 통과
- 2026-05-22 `npm.cmd exec tsc -- --noEmit`: 통과
- 2026-05-22 `npm.cmd run build`: Next.js 16.2.6 production build 통과
- 2026-05-22 `npm.cmd audit --audit-level=moderate`: found 0 vulnerabilities
- 2026-05-22 safety readback: `orders_count == 0`, `paper_* == 0`, token/cache/network/adapter order call false, KIS execution routes 미등록, paper mutation routes 미등록, token cache file 없음.

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
- Confirm은 `run_id`만 받아 staged rows를 transaction으로 `daily_ohlcv`에 반영한다.
- External provider는 반드시 `external_symbol_mapping`을 거친다.
- Mapping이 없으면 `SYMBOL_MAPPING_FAILED`를 기록하고 confirm 불가 상태가 된다.
- Broker preview는 safety scaffold only이며 `orders_count == 0`을 유지한다.
- Paper preview는 disabled deny scaffold only이며 `orders_count == 0`, `paper_* == 0`을 유지한다.
- Sell preview는 기존 long position 청산 검토 전용이고, 포지션 없음/수량 초과/short sell은 deny한다.

## 주의 사항

- 기본값은 `network_enabled=false`; 테스트와 smoke에서 실제 외부 네트워크를 호출하지 않는다.
- KIS 실제 API 호출, KIS app key/app secret 저장, KIS 계좌번호 저장, KIS token cache 생성 금지.
- KIS 주문/계좌/잔고/체결/cancel/websocket API 구현 금지.
- `POST /api/paper/orders`, fill simulator, paper order create, paper fill 생성, paper position 변경 금지.
- live broker, 실제 주문, cancel/fill/websocket 연결, 자동매매 스케줄러, AI 예측 모델 금지.
- API key, secret, token, password, account, header, raw credential 값을 저장하거나 Settings/API/docs/logs에 노출하지 않는다.
- yfinance/KIS/KRX 전용 UI write path를 만들지 말고 `source_id` 기반 provider-neutral API를 유지한다.
- `npm audit fix --force`, Next.js downgrade, main 강제 push 금지.
- `frontend/.env.local`은 local-only ignored file이다. backend 포트를 바꾸면 값을 맞춘 뒤 `npm.cmd run build`를 다시 실행한다.
- 현재 작업 전부터 `docs/research/검색결과.md`, `docs/research/제품설계문서.md`가 untracked 상태일 수 있으므로 이번 구현에서는 건드리지 않는다.

## 다음 작업

- [ ] Phase 3F-3: KRX index/sector/symbol/calendar/corporate action source contract를 fixture/read-only 기반으로 설계한다.
- [ ] Phase 3F-4: data freshness/quality summary와 `/data` read-only summary panel 구현.
- [ ] Phase 3G: gap-aware stop, liquidity cap, partial fill, portfolio state 기반 백테스트 보강.
