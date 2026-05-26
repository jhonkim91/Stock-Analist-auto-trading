# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `Validate hardened strategy suite`
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
- [x] Phase C 전략 9개 등록 및 hardening foundation 구현
- [x] Frontend default/available strategy selector 구현
- [x] 현재 브랜치: `main`

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, external daily OHLCV preview/confirm, KIS read-only foundation, broker safety scaffold, paper preview scaffold, data quality summary, hardened backtest execution model, strategy explanation contract, strategy metadata endpoint.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/settings`; `/screener`, `/dashboard`, `/backtest`는 backend strategy metadata 기반 selector를 사용한다.
- Product state: 실주문 자동매매 엔진이 아니라 분석, 스크리닝, 백테스트, 리포트 중심 자동매매 보조 MVP.
- Strategy default: `trend_breakout`, `vcp_breakout`, `canslim_lite`, `new_high_breakout`, `pullback_20ema`.
- Strategy available: 기본 5개에 `momentum_rank`, `relative_strength_leader`, `darvas_box`, `stage_analysis_weekly`를 더해 명시 선택 시 screener/backtest 실행 가능.
- Phase C Strategy Hardening 검증 대상은 `trend_breakout`, `vcp_breakout`, `canslim_lite`, `new_high_breakout`, `pullback_20ema`, `momentum_rank`, `relative_strength_leader`, `darvas_box`, `stage_analysis_weekly` 9개다.
- `DEFAULT_STRATEGY_NAMES` 순서는 `trend_breakout`, `vcp_breakout`, `canslim_lite`, `new_high_breakout`, `pullback_20ema`로 유지한다.
- `AVAILABLE_STRATEGY_NAMES` 순서는 default 5개 뒤에 `momentum_rank`, `relative_strength_leader`, `darvas_box`, `stage_analysis_weekly`를 추가한 9개로 유지한다.
- 신규 optional filters는 config enable flag가 false이면 default pass surface를 과도하게 좁히지 않는다.
- 신규 required filters는 CANSLIM 기술 추세/거래량, pullback EMA/ATR, Darvas box/risk/long trend, weekly Stage 2 availability처럼 전략 의미상 필수인 경우에만 적용한다.
- `backend/config/strategies.yaml`의 `common.hardening`은 공통 optional hardening 기본값과 legacy enable flag를 보관한다. 기본 enable flag는 false라 기존 default 동작을 과도하게 바꾸지 않는다.
- `StrategyResult` 기존 필드인 `pass_flags`, `failed_conditions`, `reason_summary`, `metadata` contract를 유지한다.
- Screener explanation contract: `triggered_conditions`, `failed_conditions`, `score_breakdown`, `risk_flags`, `data_quality_flags`, `explanation`, `rationale`를 유지한다.
- API contract: `/api/screener/run`, `/api/backtest/run`, `/api/backtest/runs`, `/api/backtest/runs/{run_id}` 응답 shape와 metrics key/type을 유지한다.
- DB migration: root `alembic.ini`, initial revision `da9ab5998e36_initial_schema`, weekly column revision `c5b7d9a1e4f2_add_indicator_weekly_fields`, pullback EMA revision `f6d4a2c9e8b1_add_indicator_pullback_ema_fields`.

## 최근 변경 요약

- `docs/VALIDATION.md`: `Validate hardened strategy suite` 기준 검증 결과와 필수 contract 확인 결과로 갱신했다.
- `docs/PROJECT_STATUS.md`: `Phase C Strategy Hardening` 완료 항목과 suite validation 통과 상태를 추가했다.
- `README.md`: Strategy Behavior 섹션에 신규 optional filters 요약 표를 추가했다.
- 코드 변경 없이 기존 hardening suite의 contract, registry, screener/backtest, safety 테스트를 재검증했다.
- 제외 범위 유지: 실주문, paper order/fill/position mutation, KIS/KRX/yfinance network call, token/cache/credential 저장, DB migration, API breaking change 없음.

## 최신 검증 결과

- 2026-05-26 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_strategies.py -q`: 113 passed in 22.76s.
- 2026-05-26 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_indicators.py -q`: 3 passed in 2.45s.
- 2026-05-26 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3c_kis_readonly.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py -q`: 17 passed in 3.21s.
- 2026-05-26 `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 213 passed in 75.70s.
- 2026-05-26 registry probe: `DEFAULT_STRATEGY_NAMES`와 `AVAILABLE_STRATEGY_NAMES` 순서 유지 확인.
- 2026-05-26 `git diff --check`: 통과. CRLF 변환 경고만 출력.

## 불변 조건

- 실주문, 주문 취소, 체결, 계좌 이동, websocket, live broker 구현 금지.
- 실제 주문용 stop order 생성 금지.
- paper order/fill/position/audit mutation 구현 금지.
- KIS/KRX/yfinance network call, KIS token 발급/cache/credential 저장 금지.
- broker/order adapter import 또는 호출 금지.
- 신규 DB schema 변경은 Alembic revision과 검증 없이 금지.
- 기존 strategy registry 순서 변경 금지.
- 기존 `StrategyResult` 필드 제거 금지.
- 기존 screener/backtest API breaking change 금지.
- 기존 metrics key 제거, 타입 변경 금지.
- `orders_count == 0`, `paper_* == 0`, KIS/paper execution routes 404 유지.
- `npm audit fix --force`, Next.js downgrade, main 강제 push 금지.

## 다음 작업

- [ ] Phase 3I: weekly review report를 fixture 기반으로 검증한다.
- [ ] `stage_analysis_weekly` weekly risk metadata를 frontend에서 별도 표시할지 검토한다.
- [ ] Strategy explanation contract의 `risk_metadata`, leadership/ranking metadata 표시 범위를 별도 범위로 검토한다.
- [ ] Phase 4A/4B broker 또는 live gate는 별도 승인 전까지 구현하지 않는다.
- [ ] 현재 작업트리는 기존 미커밋 변경이 다수 포함되어 있으므로 publish/commit 시 파일 scope를 재확인한다.
