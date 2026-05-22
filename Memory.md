# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `MVP v0.11 Phase 3G-2 Liquidity and Partial Fill Model`
- [x] Phase 1 Backend Core MVP 구현
- [x] Phase 2 MVP Web Flow 구현
- [x] Phase 3A CSV validate/confirm import 구현
- [x] Phase 3B provider-neutral external daily OHLCV preview/confirm 구현
- [x] Phase 3C KIS read-only foundation 구현
- [x] Phase 3D broker safety scaffold 구현
- [x] Phase 3E-1 paper preview safety scaffold 구현
- [x] Phase 3F read-only data reliability 구현
- [x] Phase 3G-1 backtest execution model hardening 구현
- [x] Phase 3G-2 liquidity and partial fill model 구현
- [x] 현재 브랜치: `main`

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, external daily OHLCV preview/confirm, KIS read-only foundation, broker safety scaffold, paper preview scaffold, data quality summary, hardened backtest execution model.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/settings`.
- Backtest: long-only exit simulation에서 gap-aware stop/target, config 기반 same-bar priority, optional `trades[*].execution_detail`, optional `trades[*].liquidity_detail`을 제공한다.
- Liquidity model: `risk.position_size`를 `planned_qty`로 유지하고 `turnover_value` 또는 `volume * raw_entry_price` 기준 participation cap으로 backtest 체결 수량만 제한한다.
- `POST /api/backtest/run`, `GET /api/backtest/runs`, `GET /api/backtest/runs/{run_id}` contract와 기존 metrics key/type은 유지한다.
- Optional metrics: `partial_fill_count`, `no_fill_count`, `total_unfilled_qty`.
- `backtest_runs.metrics_json` 저장 구조는 유지한다.
- Frontend security: `postcss@8.5.15` override로 `npm audit` 0 vulnerabilities.

## Phase 3G-2 변경 파일/구조

- `backend/config/backtest.yaml`
  - `execution.max_participation_rate: 0.05`
  - `execution.min_fill_ratio: 0.25`
  - `execution.allow_partial_fill: true`
- `backend/app/services/backtest_service.py`
  - `planned_qty = risk.position_size`
  - `requested_notional = planned_qty * raw_entry_price`
  - `liquidity_notional`은 `turnover_value` 우선, 없거나 0이면 `volume * raw_entry_price` fallback.
  - `cap_notional = liquidity_notional * max_participation_rate`
  - `fill_ratio = min(1.0, cap_notional / requested_notional)`
  - partial fill 허용 시 `filled_qty = floor(planned_qty * fill_ratio)`.
  - no-fill/insufficient liquidity는 `qty=0` trade record를 남기지 않고 skip.
  - generated trade의 top-level `qty`, `pnl`, `estimated_cost`는 `filled_qty` 기준.
- `backend/tests/test_backtest.py`
  - 충분한 유동성, partial fill, min fill 미달 skip, partial disabled skip, volume fallback, zero liquidity skip, optional metrics 테스트 추가.
- `backend/tests/test_phase3g_backtest_execution_model.py`
  - 기존 backtest API smoke에 optional metrics와 `liquidity_detail` contract 확인 추가.
- `docs/VALIDATION.md`
  - Phase 3G-2 최신 검증 결과와 safety contract로 갱신.

## 최신 검증 결과

- 2026-05-22 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_phase3g_backtest_execution_model.py -q`: 17 passed in 55.95s
- 2026-05-22 `.\.venv\Scripts\python.exe -m pytest backend/tests`: 93 passed in 188.86s
- 2026-05-22 `npm.cmd run lint`: 통과
- 2026-05-22 `npm.cmd exec tsc -- --noEmit`: 통과
- 2026-05-22 `npm.cmd run build`: Next.js 16.2.6 production build 통과
- 2026-05-22 `npm.cmd audit --audit-level=moderate`: found 0 vulnerabilities
- Safety invariant: `orders_count == 0`, `paper_orders/fills/positions/audit_events == 0`, KIS execution routes 404, `POST /api/paper/orders` 404, `POST /api/paper/fill-simulator/run` 404, provider network/token/adapter flags false, `.cache/kis/token.json` 미생성.

## 최신 DB count

- symbol_master: 15
- daily_ohlcv: 4,800
- index_ohlcv: 320
- sector_ohlcv: 2,880
- fundamentals_pti: 30
- indicator_snapshot: 4,800
- screen_results: 45
- reports: 1
- backtest_runs: local DB에서 backtest smoke마다 증가 가능
- orders_count: 0
- paper_orders: 0
- paper_fills: 0
- paper_positions: 0
- paper_audit_events: 0
- latest_trade_date: 2026-05-20
- latest_indicator_date: 2026-05-20
- latest_screen_date: 2026-05-20

## 불변 조건

- 실제 주문, paper order/fill/position/audit mutation, live broker 구현 금지.
- KIS/KRX/yfinance network call, token 발급/cache/credential 저장 금지.
- broker/order adapter import 또는 호출 금지.
- DB schema 변경, Alembic/migration 도입 금지.
- 기존 backtest API breaking change 금지.
- 기존 metrics key 삭제/타입 변경 금지.
- strategy 조건 대규모 변경 금지.
- portfolio cash/position state와 walk-forward 구현은 Phase 3G-2 범위 밖.
- `orders_count == 0`, `paper_* == 0`, KIS/paper execution routes 404 유지.
- `npm audit fix --force`, Next.js downgrade, main 강제 push 금지.

## 다음 작업

- [ ] Phase 3G-3: corporate action adjusted price와 delisted symbol handling 보강.
- [ ] `daily_ohlcv.adj_close` 사용 기준과 split/dividend adjustment 범위 확정.
- [ ] 상장폐지/거래정지/마지막 가용 가격 청산 규칙 설계.
