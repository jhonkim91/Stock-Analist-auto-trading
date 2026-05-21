# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `MVP v0.7 Phase 3E-1 paper preview safety scaffold`
- [x] Phase 1 Backend Core MVP 구현
- [x] Phase 2 MVP Web Flow 구현
- [x] Phase 3A 데이터 검증/preview-confirm CSV import 구현
- [x] Phase 3A PR #1 merge 완료
- [x] Phase 3B provider-neutral external daily OHLCV flow 구현
- [x] Phase 3B PR #2 merge 완료: `754a139c24b3e3742f2060a9589d96d21a75d2b9`
- [x] Phase 3C KIS read-only foundation 구현
- [x] Phase 3C PR #3 merge 완료: `b696ce28603d0c7329e1f36f8bcb8b48db617710`
- [x] Phase 3D broker safety scaffold 구현
- [x] Phase 3D PR #4 merge 완료: `2d5a146c8b89c355397eec458fd7343412e92c6e`
- [x] Phase 3D post-merge docs commit: `127527ecec905227b15b5654dc3615f21fd244ec`
- [x] Phase 3E-1 paper preview safety scaffold 구현
- [x] 현재 브랜치: `main`
- [x] 현재 HEAD: `8e503332c23875bd82754ffd29314b65e1235089`

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, provider-neutral external daily OHLCV preview/confirm, KIS read-only foundation, Phase 3D broker safety scaffold, Phase 3E-1 paper preview scaffold, indicator recompute, screener, report, backtest.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/settings`.
- Data Quality: `/data`에서 CSV validate/confirm, External Daily OHLCV preview/confirm, KIS read-only status 확인 가능.
- External provider: `external_yfinance`는 `provider_name=yfinance`, `network_enabled=false`, `manual_preview_only=true`.
- KIS market data source: `kis_market_data`는 `provider_type=external_market_data`, `provider_name=kis`, `enabled=false`, `network_enabled=false`, `read_only_enabled=false`.
- KIS broker placeholder: `kis_openapi`는 `provider_type=broker_placeholder`, `enabled=false`, `network_enabled=false`, `paper_trading_enabled=false`, `live_trading_enabled=false`, `websocket_enabled=false`.
- Broker safety: `/api/broker/status`, `/api/broker/orders/preview`만 safety scaffold 상태를 반환한다.
- Paper safety: `/api/paper/status`, `/api/paper/orders/preview`만 disabled deny scaffold 상태를 반환한다.
- KIS execution routes: `/api/kis/orders/*`, `/api/kis/broker/*`, `/api/kis/websocket/*`는 미등록 404 상태를 유지한다.
- Settings: `/api/settings`는 `broker.yaml` 원문과 broker summary를 반환하지 않는다.
- Frontend security: `postcss@8.5.15` override로 `npm audit` 0 vulnerabilities.

## Phase 3D/3E-1 추가 파일/구조

- Config: `backend/config/broker.yaml` disabled/fail-closed broker safety 기본값.
- Config: `backend/config/paper.yaml` disabled/fail-closed paper safety 기본값.
- Backend API: `backend/app/api/broker.py` preview endpoint에 DB session 주입.
- Backend API: `backend/app/api/paper.py` status/preview endpoint.
- Backend service: `backend/app/services/broker_service.py`에 `BrokerConfigService`, `TokenLifecycleService`, `BrokerAuditService`, `OrderRiskGate`, `BrokerService`.
- Backend service: `backend/app/services/paper_trading_service.py`에 `PaperTradingService`, `LocalPaperSimulator` skeleton.
- Backend tests: `backend/tests/test_phase3d_broker_safety.py`.
- Backend tests: `backend/tests/test_phase3e_paper_safety.py`.
- Frontend API type: `frontend/lib/api.ts` `BrokerStatus`, `PaperStatus`, `PaperPreviewResponse` safety scaffold fields.
- Frontend page: `frontend/app/paper/page.tsx`.
- Docs: `README.md`, `docs/VALIDATION.md`, `Memory.md`.

## 최신 검증 결과

- 2026-05-22 `.\.venv\Scripts\python.exe -m pytest backend/tests`: 60 passed in 120.89s
- 2026-05-22 `npm.cmd run lint`: 통과
- 2026-05-22 `npm.cmd exec tsc -- --noEmit`: 통과
- 2026-05-22 `npm.cmd run build`: Next.js 16.2.6 production build 통과, `/paper` 포함
- 2026-05-22 `npm.cmd audit --audit-level=moderate`: found 0 vulnerabilities
- 2026-05-22 API smoke: `/health`, `/api/data/status`, `/api/data/sources`, `/api/broker/status`, `/api/broker/orders/preview`, `/api/paper/status`, `/api/paper/orders/preview`, `/api/kis/status` 정상
- 2026-05-22 browser smoke: `http://127.0.0.1:3010/dashboard` -> `/paper`, desktop/mobile `/paper`, preview deny 통과
- 2026-05-22 KIS execution route smoke: `/api/kis/orders`, `/api/kis/orders/preview`, `/api/kis/broker/status`, `/api/kis/websocket/status` 모두 404
- 2026-05-22 broker/paper safety smoke: `orders_count == 0`, `paper_* == 0`, `token_issued=false`, `network_call_performed=false`, adapter order/network call false, sentinel secret 노출 false
- 2026-05-22 token cache `.cache/kis/token.json` 없음

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

- CSV `validate-csv`와 external/KIS market-data preview는 `import_runs`와 `data_quality_checks`만 기록한다.
- Preview 전후 `symbol_master`, `daily_ohlcv`, `indicator_snapshot`, `screen_results`, `reports`, `backtest_runs`, `orders` count는 바뀌지 않아야 한다.
- Confirm 전에만 `daily_ohlcv`와 `symbol_master`가 바뀌지 않아야 한다.
- External provider는 반드시 `external_symbol_mapping`을 거친다.
- Mapping이 없으면 `SYMBOL_MAPPING_FAILED`를 기록하고 confirm 불가 상태가 된다.
- Broker preview는 safety scaffold only이며 `orders_count == 0`을 유지한다.
- Paper preview는 disabled deny scaffold only이며 `orders_count == 0`, `paper_* == 0`을 유지한다.
- Sell preview는 기존 long position 청산 검토 전용이고, 포지션 없음/수량 초과/short sell은 deny한다.

## 주의 사항

- 기본값은 `network_enabled=false`; 테스트와 smoke에서 실제 외부 네트워크를 호출하지 않는다.
- KIS 실제 API 호출, KIS app key/app secret 저장, KIS 계좌번호 저장, KIS token cache 생성 금지.
- KIS 주문/잔고/체결/계좌/websocket API 구현 금지.
- paper order create, paper fill 생성, paper position 변경, live broker, 실제 주문, cancel/fill/websocket 연결, 자동매매 스케줄러, AI 예측 모델 금지.
- API key, secret, token, password, account, header, raw credential 값을 저장하거나 Settings/API/docs/logs에 노출하지 않는다.
- `backend/config/broker.yaml`은 `/api/settings`에 노출하지 않는다.
- yfinance/KIS 전용 DB/API/UI 하드코딩 금지. `source_id` 기반 provider-neutral API를 유지한다.
- `npm audit fix --force`, Next.js downgrade, main 강제 push 금지.
- `frontend/.env.local`은 local-only ignored file이다. backend 포트를 바꾸면 값을 맞춘 뒤 `npm.cmd run build`를 다시 실행한다.

## 다음 작업

- Phase 3E-2는 별도 승인 전까지 paper order create, fill simulator 실행, paper position 변경을 구현하지 않는다.
- 실제 KIS token 발급, 주문, cancel, fill, websocket은 Phase 3D 이후에도 별도 승인 전까지 구현하지 않는다.
