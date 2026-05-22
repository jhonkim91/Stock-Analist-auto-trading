# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `MVP v0.13 Phase 3H Strategy Extension`
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
- [x] Phase 3G-3 adjusted price and delisted/missing data handling 구현
- [x] Phase 3H strategy explanation and optional filters 구현
- [x] GitHub Actions CI scaffold 추가
- [x] Alembic migration scaffold 및 initial schema migration 추가
- [x] 현재 브랜치: `main`

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, external daily OHLCV preview/confirm, KIS read-only foundation, broker safety scaffold, paper preview scaffold, data quality summary, hardened backtest execution model, strategy explanation contract.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/settings`.
- Product state: 실주문 자동매매 엔진이 아니라 분석/스크리닝/백테스트/리포트 중심 자동매매 보조 MVP.
- Strategy: `trend_breakout`, `vcp_breakout`, `canslim_lite` 기본 결과를 보존하고 screener response에 `triggered_conditions`, `score_breakdown`, `risk_flags`, `data_quality_flags`, `explanation`, `rationale`를 제공한다.
- Strategy options: `atr_risk_filter_enabled=false`, `pivot_distance_limit_enabled=false`, `earnings_quality_enabled=false` 기본값으로 기존 결과를 보존한다.
- Backtest: gap-aware stop/target, same-bar priority, liquidity participation cap, partial fill, adjusted price, delisted/missing data forced exit를 옵션 기반으로 제공한다.
- `POST /api/backtest/run`, `GET /api/backtest/runs`, `GET /api/backtest/runs/{run_id}` contract와 기존 metrics key/type은 유지한다.
- DB migration: root `alembic.ini`, `backend/alembic`, initial revision `da9ab5998e36_initial_schema`, SQLite upgrade/downgrade smoke test.

## 기준 문서

- `README.md`: 실행, API, 검증 명령, 안전 불변조건.
- `docs/PROJECT_STATUS.md`: 다음 작업자가 가장 먼저 볼 단일 상태 요약.
- `docs/VALIDATION.md`: 최신 검증 결과와 검증 명령.
- `docs/plans/README.md`: Phase index와 다음 권장 Phase.
- `docs/DB_MIGRATION.md`: Alembic migration 생성/적용/롤백 절차.

## 최신 검증 결과

- 2026-05-22 `.\.venv\Scripts\python.exe -m pytest backend/tests`: 101 passed.
- 2026-05-22 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_strategies.py backend/tests/test_phase2_api.py backend/tests/test_api_smoke.py -q`: 12 passed.
- 2026-05-22 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_phase3g_backtest_execution_model.py -q`: 20 passed.
- 2026-05-22 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3c_kis_readonly.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_phase3g_backtest_execution_model.py -q`: 19 passed.
- 2026-05-22 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_alembic_migrations.py -q`: 2 passed.
- 2026-05-22 frontend lint/typecheck/build: 통과.
- 2026-05-22 tracked backend/frontend code/config secret assignment scan: no matches.
- Safety invariant: `orders_count == 0`, `paper_orders/fills/positions/audit_events == 0`, KIS execution routes 404, `POST /api/paper/orders` 404, `POST /api/paper/fill-simulator/run` 404, provider network/token/adapter flags false, `.cache/kis/token.json` 미생성.

## 불변 조건

- 실제 주문, 주문 취소, 체결, 계좌, 잔고, websocket, live broker 구현 금지.
- paper order/fill/position/audit mutation 구현 금지.
- KIS/KRX/yfinance network call, KIS token 발급/cache/credential 저장 금지.
- broker/order adapter import 또는 호출 금지.
- 신규 DB schema 변경은 Alembic revision과 검증 없이 금지.
- 기존 backtest API breaking change 금지.
- 기존 metrics key 제거/타입 변경 금지.
- 기존 전략 기본 결과를 변경하는 새 조건은 기본 비활성으로 둔다.
- portfolio cash/position state와 walk-forward 구현은 현재 범위 밖.
- `orders_count == 0`, `paper_* == 0`, KIS/paper execution routes 404 유지.
- `npm audit fix --force`, Next.js downgrade, main 강제 push 금지.

## 다음 작업

- [ ] Phase 3I: weekly review report를 fixture 기반으로 검토.
- [ ] Strategy explanation contract를 frontend에서 표시할지 별도 범위로 검토.
- [ ] adjusted price factor/corporate action fixture를 실제 데이터 계약 수준으로 정교화.
- [ ] Phase 4A/4B broker 또는 live gate는 별도 승인 전까지 구현하지 않는다.
