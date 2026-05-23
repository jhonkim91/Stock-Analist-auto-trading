# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `Phase C-2 relative_strength_leader Strategy`
- [x] Phase 1 Backend Core MVP 구현
- [x] Phase 2 MVP Web Flow 구현
- [x] Phase 3A CSV validate/confirm import 구현
- [x] Phase 3B provider-neutral external daily OHLCV preview/confirm 구현
- [x] Phase 3C KIS read-only foundation 구현
- [x] Phase 3D broker safety scaffold 구현
- [x] Phase 3E-1 paper preview safety scaffold 구현
- [x] Phase 3F read-only data reliability 구현
- [x] Phase 3G hardened backtest execution model 구현
- [x] Phase 3H strategy explanation, optional filters, strategy registry 구현
- [x] Phase C-1 `momentum_rank` 전략 구현
- [x] Phase C-2 `relative_strength_leader` 전략 구현
- [x] GitHub Actions CI scaffold 추가
- [x] Alembic migration scaffold 및 initial schema migration 추가
- [x] 현재 브랜치: `main`

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, external daily OHLCV preview/confirm, KIS read-only foundation, broker safety scaffold, paper preview scaffold, data quality summary, hardened backtest execution model, strategy explanation contract.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/settings`.
- Product state: 실주문 자동매매 엔진이 아닌 분석, 스크리닝, 백테스트, 리포트 중심 자동매매 보조 MVP.
- Strategy default: `trend_breakout`, `vcp_breakout`, `canslim_lite` 3개 기본 실행을 유지한다.
- Strategy available: `momentum_rank`, `relative_strength_leader`는 available registry에 등록되어 명시 선택 시 screener/backtest에서 실행 가능하다.
- `relative_strength_leader`: `indicator_snapshot` 기존 필드만 사용하며 DB schema 변경이 없다.
- Screener explanation contract: `triggered_conditions`, `failed_conditions`, `score_breakdown`, `risk_flags`, `data_quality_flags`, `explanation`, `rationale`를 유지한다.
- API contract: `/api/screener/run`, `/api/backtest/run`, `/api/backtest/runs`, `/api/backtest/runs/{run_id}` 응답 shape와 metrics key/type을 유지한다.
- DB migration: root `alembic.ini`, `backend/alembic`, initial revision `da9ab5998e36_initial_schema`, SQLite upgrade/downgrade smoke test.

## 최근 변경 요약

- `backend/app/strategies/relative_strength_leader.py`: market/sector relative strength leadership 전략 추가.
- `backend/app/strategies/registry.py`: `relative_strength_leader`를 available-only 전략으로 등록.
- `backend/config/strategies.yaml`: `relative_strength_leader` 기본 threshold 추가.
- `backend/app/services/screener_service.py`: `relative_strength_leader` Screener 응답에 strategy별 `data_quality_flags` 병합.
- `backend/tests/test_strategies.py`: C-2 pass/fail fixture, registry, Screener/Backtest 명시 실행 테스트 추가.
- `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md`, `Memory.md`: Phase C-2 기준으로 최신 상태 갱신.

## 기준 문서

- `README.md`: 실행, API, 검증 명령, 안전 불변조건.
- `docs/PROJECT_STATUS.md`: 다음 작업자가 먼저 볼 단일 상태 요약.
- `docs/VALIDATION.md`: 최신 검증 결과와 검증 명령.
- `docs/plans/README.md`: Phase index와 다음 권장 Phase.
- `docs/DB_MIGRATION.md`: Alembic migration 생성, 적용, 롤백 절차.

## 최신 검증 결과

- 2026-05-23 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_strategies.py backend/tests/test_backtest.py -q`: 37 passed.
- 2026-05-23 `.\.venv\Scripts\python.exe -m pytest backend/tests`: 115 passed.
- 2026-05-23 `cd frontend && npm.cmd run lint`: 통과.
- 2026-05-23 `cd frontend && npm.cmd exec tsc -- --noEmit`: 통과.
- 2026-05-23 `cd frontend && npm.cmd run build`: 통과, Next.js 16.2.6 production build.

## 불변 조건

- 실주문, 주문 취소, 체결, 계좌, 예수금, websocket, live broker 구현 금지.
- paper order/fill/position/audit mutation 구현 금지.
- KIS/KRX/yfinance network call, KIS token 발급/cache/credential 저장 금지.
- broker/order adapter import 또는 호출 금지.
- 신규 DB schema 변경은 Alembic revision과 검증 없이 금지.
- 기존 backtest API breaking change 금지.
- 기존 metrics key 제거, 타입 변경 금지.
- 기존 전략 기본 실행 목록 변경 금지.
- 기존 전략 기본 결과를 바꾸는 조건은 기본 비활성화로 둔다.
- portfolio cash/position state와 walk-forward 구현은 현재 범위 밖.
- `orders_count == 0`, `paper_* == 0`, KIS/paper execution routes 404 유지.
- `npm audit fix --force`, Next.js downgrade, main 강제 push 금지.

## 다음 작업

- [ ] README와 phase plan 문서에 Phase C-2 상태를 반영할지 별도 범위로 검토한다.
- [ ] Phase 3I: weekly review report를 fixture 기반으로 검토한다.
- [ ] Strategy explanation contract를 frontend에서 표시할지 별도 범위로 검토한다.
- [ ] `relative_strength_leader`를 frontend strategy selector에 추가할지 별도 범위로 결정한다.
- [ ] Phase 4A/4B broker 또는 live gate는 별도 승인 전까지 구현하지 않는다.
