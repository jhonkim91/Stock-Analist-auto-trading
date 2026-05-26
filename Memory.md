# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `KIS Paper Broker Phase 2 KIS Paper Broker Contract`
- [x] 현재 version: `MVP v0.24.0`
- [x] 현재 브랜치: `feature/kis-paper-goal-phases` (baseline: `main`)
- [x] 최신 targeted backend pytest: Phase 2 adapter/token/regression `22 passed`
- [x] 최신 backend full pytest: `293 passed`
- [x] 최신 frontend 검증: Node `v24.15.0`에서 `npm ci`, lint, typecheck, build 통과
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
- [x] KIS Paper Broker Phase 0 Baseline Audit 완료
- [x] KIS Paper Broker Phase 1 Notification Foundation 완료
- [x] KIS Paper Broker Phase 2 KIS Paper Broker Contract 완료

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
- KIS paper broker Phase 0 산출물: `docs/plans/phase-paper-broker-baseline-audit.md`, `docs/KIS_PAPER_API_MATRIX.md`.
- KIS paper broker Phase 1 산출물: `backend/config/notifications.yaml`, `/api/notifications/status`, `/api/notifications/test`, disabled/mock notification abstraction, Discord/Telegram adapter skeleton.
- KIS paper broker Phase 2 산출물: `backend/app/brokers/base.py`, `backend/app/brokers/kis_paper.py`, `backend/app/brokers/kis_live.py`, `backend/app/services/token_manager.py`.

## 최근 변경 요약

- `docs/plans/phase-paper-broker-baseline-audit.md`: 현재 `main` baseline, stale 문서 충돌, Phase 0 안전 결론 기록.
- `docs/KIS_PAPER_API_MATRIX.md`: KIS paper planned capability별 공식 문서 확인 상태와 `확인 필요` 항목 기록.
- `README.md`, `docs/plans/README.md`, `docs/DB_MIGRATION.md`: stale baseline과 Alembic head를 source-of-truth 기준으로 조정.
- `docs/PROJECT_STATUS.md`, `docs/VALIDATION.md`, `Memory.md`: KIS Paper Broker Phase 0 기준선과 safety 검증 결과 반영.
- `backend/app/services/notification_service.py`, `discord_notifier.py`, `telegram_notifier.py`: disabled/mock 기본 notification abstraction과 redacted status/test dispatch contract 추가.
- `backend/app/api/notifications.py`, `backend/config/notifications.yaml`, `.env.example`: `/api/notifications/status`, `/api/notifications/test`, placeholder-only env 변수 추가.
- `frontend/app/settings/page.tsx`, `frontend/lib/api.ts`: settings 화면에 redacted notification status 요약 추가.
- `backend/tests/test_notifications.py`, `backend/tests/test_notification_api.py`: redaction, disabled dry-run, mock mode, Discord mention safety, Telegram plain text 기본값 검증.
- `backend/app/brokers/*`, `backend/app/services/token_manager.py`: broker contract, KIS paper confirmation-required skeleton, live disabled placeholder, in-memory token metadata 추가.
- `backend/app/services/broker_service.py`, `backend/app/services/paper_trading_service.py`, `backend/app/services/kis_service.py`: 기존 fail-closed status에 adapter/token metadata를 additive로 연결.
- `backend/tests/test_kis_paper_adapter.py`, `backend/tests/test_token_manager.py`, `backend/tests/test_no_live_trading_regression.py`: Phase 2 contract와 no-live regression 검증.

## 최신 검증 결과

- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter.py backend/tests/test_token_manager.py backend/tests/test_no_live_trading_regression.py -q`: 9 passed in 0.54s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3c_kis_readonly.py backend/tests/test_phase3d_broker_safety.py -q`: 13 passed in 3.05s.
- 2026-05-27 Phase 2 secret exposure scan: `NO_PHASE2_SECRET_FINDINGS`.
- 2026-05-27 Phase 2 live trading enable static scan: `NO_PHASE2_LIVE_TRADING_ENABLE_FINDINGS`.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_notifications.py backend/tests/test_notification_api.py -q`: 8 passed in 0.49s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py -q`: 10 passed in 0.68s.
- 2026-05-27 frontend `npm.cmd run lint`, `npm.cmd exec tsc -- --noEmit`, `npm.cmd run build`: 통과.
- 2026-05-27 Phase 1 secret exposure scan: `NO_PHASE1_SECRET_FINDINGS`.
- 2026-05-27 Phase 1 live trading enable static scan: `NO_PHASE1_LIVE_TRADING_ENABLE_FINDINGS`.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3c_kis_readonly.py -q`: 7 passed in 2.70s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3d_broker_safety.py -q`: 6 passed in 0.54s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3e_paper_safety.py -q`: 4 passed in 0.55s.
- 2026-05-27 Phase 0 secret exposure scan: `NO_SECRET_FINDINGS`.
- 2026-05-27 live trading enable static scan: `NO_LIVE_TRADING_ENABLE_FINDINGS`.
- 2026-05-27 `git diff --check`: 통과, CRLF warning만 있음.
- 2026-05-26 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_phase2_api.py -q`: 47 passed in 225.71s.
- 2026-05-26 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_report_quality.py -q`: 4 passed in 27.29s.
- 2026-05-26 `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 293 passed in 282.75s.
- 2026-05-26 Node `v24.15.0`에서 `npm.cmd ci`, `npm.cmd run lint`, `npm.cmd exec tsc -- --noEmit`, `npm.cmd run build`: 통과.
- Phase 0는 DB schema/frontend/runtime 변경이 없으므로 Alembic pytest와 frontend 검증을 재실행하지 않았다.

## 불변 조건

- 실제 주문, 주문 취소, 체결, 계좌 이동, websocket, live broker 구현 금지.
- paper order/fill/position/audit mutation 구현 금지.
- KIS/KRX/yfinance network call, KIS token 발급/cache/credential 저장 금지.
- broker/order adapter import 또는 호출 금지.
- KIS paper endpoint/path/TR-ID/request field는 공식 문서에서 완전 확인 전까지 `확인 필요`로 남긴다.
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
- KIS paper broker submit/cancel/sync implementation, report notification, paper bot scheduler.

## 다음 작업

- [ ] KIS paper broker Phase 3 Paper Trading Persistence는 additive-only migration으로 진행한다.
- [ ] `docs/KIS_PAPER_API_MATRIX.md`의 `확인 필요` endpoint/path/TR-ID/request field를 공식 문서로 보강한다.
- [ ] Monthly report extension은 daily/weekly 공통 persistence contract 위에 additive로만 검토한다.
- [ ] summary endpoint의 `baseline_snapshot` 입력을 파일 기반 import flow로 확장할지 별도 검토한다.
- [ ] frontend lint/typecheck/build는 frontend 변경이 포함될 때 재실행한다.
