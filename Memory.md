# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `MVP v0.10 Phase 3G-1 Backtest Execution Model Hardening`
- [x] Phase 1 Backend Core MVP 구현
- [x] Phase 2 MVP Web Flow 구현
- [x] Phase 3A CSV validate/confirm import 구현
- [x] Phase 3B provider-neutral external daily OHLCV preview/confirm 구현
- [x] Phase 3C KIS read-only foundation 구현
- [x] Phase 3D broker safety scaffold 구현
- [x] Phase 3E-1 paper preview safety scaffold 구현
- [x] Phase 3F read-only data reliability 구현
- [x] Phase 3G-1 backtest execution model hardening 구현
- [x] 현재 브랜치: `main`

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, external daily OHLCV preview/confirm, KIS read-only foundation, broker safety scaffold, paper preview scaffold, data quality summary, hardened backtest execution model.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/settings`.
- Backtest: long-only exit simulation에서 gap-aware stop/target, config 기반 same-bar priority, optional `trades[*].execution_detail`을 제공한다.
- `POST /api/backtest/run`, `GET /api/backtest/runs`, `GET /api/backtest/runs/{run_id}` contract와 기존 metrics key는 유지한다.
- `backtest_runs.metrics_json` 저장 구조는 유지한다.
- Frontend security: `postcss@8.5.15` override로 `npm audit` 0 vulnerabilities.

## Phase 3G-1 변경 파일/구조

- `backend/app/services/backtest_service.py`
  - `_exit_decision()` helper 추가.
  - entry gap below stop은 skip하지 않고 next-open entry 후 open stop exit 처리.
  - holding day gap-down stop은 `stop_price`가 아니라 bar open 가격으로 손실 반영.
  - target gap-up은 open fill만 인정하고 intraday high 초과 이익은 반영하지 않음.
  - same-bar stop/target은 `backtest.yaml.execution.same_bar_stop_first`를 따름.
  - `execution_detail` optional trade field 추가.
- `backend/tests/test_backtest.py`
  - gap-down entry/holding, gap-up target, same-bar true/false, max holding, cost regression 테스트 보강.
- `backend/tests/test_phase3g_backtest_execution_model.py`
  - backtest API smoke, metrics contract, execution safety invariant 테스트 추가.
- `docs/VALIDATION.md`
  - Phase 3G-1 최신 검증 결과와 safety contract로 갱신.

## 최신 검증 결과

- 2026-05-22 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_phase3g_backtest_execution_model.py -q`: 10 passed in 42.07s
- 2026-05-22 `.\.venv\Scripts\python.exe -m pytest backend/tests`: 86 passed in 154.65s
- 2026-05-22 `npm.cmd run lint`: 통과
- 2026-05-22 `npm.cmd exec tsc -- --noEmit`: 통과
- 2026-05-22 `npm.cmd run build`: Next.js 16.2.6 production build 통과
- 2026-05-22 `npm.cmd audit --audit-level=moderate`: found 0 vulnerabilities
- Safety invariant: orders/paper rows 0, token/cache/network/adapter flags false, KIS execution routes 404, `POST /api/paper/orders` 404, `POST /api/paper/fill-simulator/run` 404.

## 최신 DB count

- symbol_master: 15
- daily_ohlcv: 4,800
- index_ohlcv: 320
- sector_ohlcv: 2,880
- fundamentals_pti: 30
- indicator_snapshot: 4,800
- screen_results: 45
- reports: 1
- backtest_runs: local test DB에서 backtest smoke마다 증가 가능
- orders_count: 0
- paper_orders: 0
- paper_fills: 0
- paper_positions: 0
- paper_audit_events: 0
- latest_trade_date: 2026-05-20
- latest_indicator_date: 2026-05-20
- latest_screen_date: 2026-05-20

## 불변 조건

- 실제 주문, paper order/fill/position mutation, live broker 구현 금지.
- KIS/KRX/yfinance network call, token 발급/cache/credential 저장 금지.
- broker/order adapter import 또는 호출 금지.
- DB schema 변경, Alembic/migration 도입 금지.
- 기존 backtest API breaking change 금지.
- 기존 metrics key 삭제/타입 변경 금지.
- Frontend API client와 화면 변경은 Phase 3G-1 범위 밖.
- `orders_count == 0`, `paper_* == 0`, KIS/paper execution routes 404 유지.
- `npm audit fix --force`, Next.js downgrade, main 강제 push 금지.

## 다음 작업

- [ ] Phase 3G-2: Liquidity and partial fill model.
- [ ] ADV/turnover participation limit와 insufficient liquidity case 설계.
- [ ] partial fill simulation은 DB mutation 없이 backtest 내부 trade simulation field로만 시작.
- [ ] position size cap 보강은 risk sizing contract와 기존 screener/backtest 결과 영향을 먼저 분리 검토.
