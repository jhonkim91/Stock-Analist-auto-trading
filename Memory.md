# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `Phase C-6 pullback_20ema Strategy`
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
- [x] Phase C-3 `new_high_breakout` 전략 구현
- [x] Phase C-4 `darvas_box` 전략 구현
- [x] Phase C-5 `stage_analysis_weekly` 전략 구현
- [x] Phase C-6 `pullback_20ema` 전략 구현
- [x] Alembic migration scaffold와 strategy indicator migrations 추가
- [x] 현재 브랜치: `main`

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, external daily OHLCV preview/confirm, KIS read-only foundation, broker safety scaffold, paper preview scaffold, data quality summary, hardened backtest execution model, strategy explanation contract.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/settings`.
- Product state: 실주문 자동매매 엔진이 아닌 분석, 스크리닝, 백테스트, 리포트 중심 자동매매 보조 MVP.
- Strategy default: `trend_breakout`, `vcp_breakout`, `canslim_lite`, `new_high_breakout`, `pullback_20ema`.
- Strategy available: 기본 5개에 더해 `momentum_rank`, `relative_strength_leader`, `darvas_box`, `stage_analysis_weekly`를 명시 선택 시 screener/backtest에서 실행 가능.
- `pullback_20ema`: 상승 추세 정배열, `ema20` 존재, `low <= ema20 * 1.01`, `close >= ema20`, `rs_percentile >= 70`, `volume_ratio_50 <= 1.2`, `atr20_pct <= 0.08` 조건을 사용한다.
- `IndicatorService`: daily OHLCV 기반 SMA/EMA/ATR/volume/weekly/as-of 지표를 계산해 `indicator_snapshot`에 저장한다. EMA20은 `close.ewm(span=20, adjust=False, min_periods=20).mean()`으로 계산한다.
- DB migration: root `alembic.ini`, initial revision `da9ab5998e36_initial_schema`, weekly column revision `c5b7d9a1e4f2_add_indicator_weekly_fields`, pullback EMA revision `f6d4a2c9e8b1_add_indicator_pullback_ema_fields`.
- Screener explanation contract: `triggered_conditions`, `failed_conditions`, `score_breakdown`, `risk_flags`, `data_quality_flags`, `explanation`, `rationale`를 유지한다.
- API contract: `/api/screener/run`, `/api/backtest/run`, `/api/backtest/runs`, `/api/backtest/runs/{run_id}` 응답 shape와 metrics key/type은 유지한다.

## 최근 변경 요약

- `backend/app/strategies/pullback_20ema.py`: 20EMA 눌림목 후 재상승 후보 전략 추가.
- `backend/app/services/indicator_service.py`: `ema20` 계산과 `low` snapshot 저장 추가.
- `backend/app/models/tables.py`: `IndicatorSnapshot.low`, `IndicatorSnapshot.ema20` nullable 컬럼 추가.
- `backend/alembic/versions/f6d4a2c9e8b1_add_indicator_pullback_ema_fields.py`: `low`, `ema20` upgrade/downgrade migration 추가.
- `backend/app/strategies/registry.py`, `backend/config/strategies.yaml`, `backend/app/services/screener_service.py`: `pullback_20ema` 기본 전략 등록, 설정, screener metadata 연결.
- `backend/tests/test_indicators.py`, `backend/tests/test_strategies.py`, `backend/tests/test_alembic_migrations.py`: EMA20/low, 전략 pass/fail, registry/default, screener/backtest 실행, migration smoke 검증 추가.
- `docs/VALIDATION.md`, `Memory.md`: Phase C-6 최신 검증 결과로 압축 갱신.

## 기준 문서

- `README.md`: 실행, API, 검증 명령, 안전 불변 조건.
- `docs/PROJECT_STATUS.md`: 다음 작업자가 먼저 볼 단일 상태 요약.
- `docs/VALIDATION.md`: 최신 검증 결과와 검증 명령.
- `docs/plans/README.md`: Phase index와 다음 권장 Phase.
- `docs/DB_MIGRATION.md`: Alembic migration 생성, 적용, 롤백 절차.

## 최신 검증 결과

- 2026-05-24 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_indicators.py backend/tests/test_strategies.py backend/tests/test_alembic_migrations.py -q`: 51 passed.
- 2026-05-24 `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 144 passed.
- 2026-05-24 `git diff --check`: 통과.
- 2026-05-24 `.\.venv\Scripts\python.exe -m alembic heads`: `f6d4a2c9e8b1 (head)`.
- 2026-05-24 frontend lint/typecheck/build: frontend 파일 변경 없음으로 미실행.

## 불변 조건

- 실주문, 주문 취소, 체결, 계좌 이동, websocket, live broker 구현 금지.
- paper order/fill/position/audit mutation 구현 금지.
- KIS/KRX/yfinance network call, KIS token 발급/cache/credential 저장 금지.
- broker/order adapter import 또는 호출 금지.
- 신규 DB schema 변경은 Alembic revision과 검증 없이 금지.
- 기존 backtest API breaking change 금지.
- 기존 metrics key 제거, 타입 변경 금지.
- portfolio cash/position state와 walk-forward 구현은 현재 범위 밖.
- `orders_count == 0`, `paper_* == 0`, KIS/paper execution routes 404 유지.
- `npm audit fix --force`, Next.js downgrade, main 강제 push 금지.

## 다음 작업

- [ ] Phase 3I: weekly review report를 fixture 기반으로 검토한다.
- [ ] Strategy explanation contract를 frontend에서 표시할지 별도 범위로 검토한다.
- [ ] `new_high_breakout`, `relative_strength_leader`, `darvas_box`, `stage_analysis_weekly`, `pullback_20ema`를 frontend strategy selector에 추가할지 별도 범위로 결정한다.
- [ ] Phase 4A/4B broker 또는 live gate는 별도 승인 전까지 구현하지 않는다.
