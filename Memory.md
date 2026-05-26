# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `Factor/Filter Attribution Minimal Integration`
- [x] 현재 version: `MVP v0.24.0`
- [x] 현재 브랜치: `main`
- [x] 최신 targeted backend pytest: `47 passed`
- [x] 최신 backend full pytest: `293 passed`
- [x] 최신 Alembic pytest: `미실행` (이번 변경은 DB schema 변경 없음)
- [x] 최신 diff check: `git diff --check` 통과, CRLF warning만 있음
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
- [x] Phase C strategy suite 및 hardening foundation 구현
- [x] Phase 3I Weekly Review Report 구현
- [x] Trade Ledger Foundation 구현
- [x] Portfolio Risk Guard v2 구현
- [x] Venue-aware session preview layer 구현
- [x] Indicator incremental + breadth-aware regime 구현
- [x] Data Reliability 2 구현
- [x] Validation Framework Scaffold 구현
- [x] Parameter Snapshot Foundation 구현
- [x] Walk-forward Minimal OOS Summary 구현
- [x] PBO/DSR Minimal Overfitting Validation 구현
- [x] Factor/Filter Attribution Minimal Integration 구현

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, external daily OHLCV preview/confirm, KIS read-only foundation, broker safety scaffold, paper preview scaffold, venue-aware session metadata, data quality summary, incremental indicator recompute, breadth-aware regime diagnostics, hardened backtest execution model, Data Reliability 2, strategy validation summary, validation scaffold, parameter snapshot foundation, portfolio risk guard, daily/weekly report generation.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/settings`.
- Local execution: `launcher.py`와 `start_stock_analyst.cmd`가 backend `127.0.0.1:8000` + frontend `127.0.0.1:3000`을 함께 실행한다.
- Product state: 실거래 자동매매 엔진이 아니라 분석, 스크리닝, 백테스트, 리포트 중심 자동매매 보조 MVP다.
- Strategy default: `trend_breakout`, `vcp_breakout`, `canslim_lite`, `new_high_breakout`, `pullback_20ema`.
- Strategy available: default 5개 + `momentum_rank`, `relative_strength_leader`, `darvas_box`, `stage_analysis_weekly`.
- `/api/backtest/strategy-summary?lookback_days=252`는 strategy별 screener pass rate, backtest metric subset, baseline delta, walk-forward OOS summary를 additive로 반환한다.
- `StrategyValidationService`는 validation summary 계산, `WalkForwardRunner`는 OOS test-window metric 집계, `ValidationBaselineComparator`는 baseline metric delta, `ValidationReportService`는 JSON artifact 저장을 담당한다.
- `OverfittingValidationCalculator`는 walk-forward window `total_return` 기반 CSCV-lite PBO와 multiple-testing/non-normal input shape 기반 Deflated Sharpe Ratio를 계산 가능한 표본에서만 산출한다.
- PBO/DSR 표본이 부족하면 `not_available_in_current_mvp`, `calculated=false`, 명확한 `reason`을 유지한다.
- `FactorFilterAttributionService`는 `backtest_trade_ledger.signal_date = screen_results.trade_date`, `symbol`, `strategy_name/strategy_tag`로 join 가능한 행만 연결하고, 불완전 join은 `not_available_in_current_mvp`로 남긴다.
- attribution은 realized PnL attribution과 screen filter failure counts를 분리한다. sector는 `symbol_master.sector`, market regime은 저장된 screen metadata에 있을 때만 사용한다.
- `StrategyParameterSnapshotService`는 현재 strategy config의 `common + strategy` payload를 `strategy_parameter_snapshots`에 저장하고, 기준일 이전 최신 snapshot과 현재 config diff를 계산한다.
- `strategy_parameter_snapshots` 최소 계약은 `strategy_name`, `config_hash`, `snapshot_date`, `effective_date`, `parameter_json`, `created_at`이다.
- Weekly review의 `Parameter Drift Check`는 snapshot이 있으면 `changed_keys`, `unchanged_keys_count`, snapshot/effective dates, config hash diff, parameter path diff를 표시하고, 없으면 `not_available_in_current_mvp`와 `strategy_parameter_snapshot_not_found`를 명시한다.
- Drift가 없으면 weekly Markdown과 detail metadata에 `no_drift_detected`를 명시한다.
- report detail API의 `metadata.parameter_drift`는 저장된 Markdown에서 추출해 Markdown과 모순되지 않게 유지한다.
- `/api/reports/daily`, `/api/reports/weekly`, `/api/reports?report_type=daily|weekly`, `/api/reports/{report_id}/markdown` contract는 유지된다.
- DB migration head: `f7a8b9c0d1e2_add_strategy_parameter_snapshots`.

## 최근 변경 요약

- `backend/app/services/validation_service.py`: `FactorFilterAttributionService` 추가, validation framework와 strategy별 validation payload에 attribution summary 연결.
- `backend/app/services/report_service.py`: weekly report의 `Factor/Filter Attribution` placeholder를 실제 realized PnL attribution table과 screen filter failure count table로 교체.
- `backend/tests/test_backtest.py`, `backend/tests/test_phase2_api.py`: attribution join 성공/불완전 join, weekly markdown table, strategy-summary artifact 저장 검증 추가.
- `backend/tests/test_report_quality.py`: weekly report quality expectation을 현재 parameter drift와 attribution table 출력 계약에 맞춤.
- `backend/reports/strategy_validation_252d.json`: top-level `validation_framework.attribution`과 strategy별 `validation.attribution` 결과 저장.
- `docs/PROJECT_STATUS.md`, `docs/VALIDATION.md`, `Memory.md`: `MVP v0.24.0 / Factor/Filter Attribution Minimal Integration` 기준으로 갱신.

## 최신 검증 결과

- 2026-05-26 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_phase2_api.py -q`: 47 passed in 225.71s.
- 2026-05-26 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_report_quality.py -q`: 4 passed in 27.29s.
- 2026-05-26 `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 293 passed in 282.75s.
- 2026-05-26 `git diff --check`: 통과, CRLF warning만 있음.
- Alembic pytest와 frontend lint/typecheck/build는 이번 backend report/test 변경에서 재실행하지 않았다.

## 불변 조건

- 실제 주문, 주문 취소, 체결, 계좌 이동, websocket, live broker 구현 금지.
- paper order/fill/position/audit mutation 구현 금지.
- KIS/KRX/yfinance network call, KIS token 발급/cache/credential 저장 금지.
- broker/order adapter import 또는 호출 금지.
- 기존 report/backtest/screener API breaking change 금지.
- strategy registry 순서와 기존 `StrategyResult` 필드 제거 금지.
- walk-forward는 actual local backtest OOS metric만 집계한다. PBO/Deflated Sharpe는 충분한 walk-forward 표본에서만 계산하고, factor/filter attribution은 저장된 ledger/screen join으로 확인되는 값만 계산한다.
- snapshot이 없을 때 parameter drift를 0이나 false normal 상태로 위장하지 않고 unavailable reason과 `comparison_available=false`를 명시한다.
- `orders_count == 0`, `paper_* == 0`, KIS/paper execution routes 404 유지.
- `npm audit fix --force`, Next.js downgrade, 강제 push 금지.

## 미구현 항목

- 실제 주문, 주문 취소, 체결, 계좌, 잔고, websocket, live broker.
- paper order create, paper fill simulator, paper position mutation.
- KIS credential/token 저장, token 발급/refresh/cache, 실제 KIS API 호출.
- 실제 KRX/yfinance network fetch.
- 자동매매 scheduler, live broker adapter, AI prediction model.
- broker-synced portfolio cash/position state, cash lock, open_positions state machine, realized exposure/drawdown.
- 저장된 parameter snapshot 기반 train-window 후보 선택과 OOS window persistence.
- walk-forward parameter optimization, multiple-testing 보정, 저장된 parameter snapshot 기반 후보 선택.
- parameter snapshot을 자동 생성하는 scheduler 또는 API route.

## 다음 작업

- [ ] Walk-forward 고도화: 저장된 parameter snapshot 기반 후보 선택, train-window parameter selection, OOS window persistence 정책을 정의한다.
- [ ] Factor/filter attribution 고도화: market_regime 저장 계약, sector as-of 계약, 더 긴 window별 attribution persistence를 검토한다.
- [ ] Monthly report extension은 daily/weekly 공통 persistence contract 위에 additive로만 검토한다.
- [ ] summary endpoint의 `baseline_snapshot` 입력을 파일 기반 import flow로 확장할지 별도 검토한다.
- [ ] frontend lint/typecheck/build는 frontend 변경이 포함될 때 재실행한다.
