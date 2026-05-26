# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `Validation Framework Scaffold`
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
- [x] Strategy validation 252d summary endpoint 구현
- [x] Backtest integrity hardening 구현
- [x] Single PC Launcher v1 구현
- [x] Phase 3I Weekly Review Report 구현
- [x] Backtest trade ledger 저장 계약 구현
- [x] Portfolio Risk Guard v2 구현
- [x] Venue-aware session preview layer 구현
- [x] Indicator incremental + breadth-aware regime 구현
- [x] Data Reliability 2 구현
- [x] Validation Framework Scaffold 구현
- [x] 현재 브랜치: `main`

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, external daily OHLCV preview/confirm, KIS read-only foundation, broker safety scaffold, paper preview scaffold, venue-aware session metadata, data quality summary, incremental indicator recompute, breadth-aware regime diagnostics, hardened backtest execution model, Data Reliability 2 earnings/corporate-action as-of contract, strategy metadata endpoint, strategy validation summary endpoint, validation scaffold, portfolio risk guard, daily/weekly report generation.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/settings`.
- Local execution: `launcher.py`와 `start_stock_analyst.cmd`가 backend `127.0.0.1:8000` + frontend `127.0.0.1:3000`을 함께 실행한다.
- Product state: 실거래 자동매매 엔진이 아니라 분석, 스크리닝, 백테스트, 리포트 중심 자동매매 보조 MVP.
- Strategy default: `trend_breakout`, `vcp_breakout`, `canslim_lite`, `new_high_breakout`, `pullback_20ema`.
- Strategy available: default 5개 + `momentum_rank`, `relative_strength_leader`, `darvas_box`, `stage_analysis_weekly`.
- `/api/backtest/strategy-summary?lookback_days=252`는 strategy별 screener pass rate, backtest metric subset, baseline delta를 additive로 반환한다.
- strategy summary 계산은 `StrategyValidationService`, baseline 비교는 `ValidationBaselineComparator`, JSON artifact 저장은 `ValidationReportService`가 담당한다.
- `/api/backtest/strategy-summary`와 `/api/backtest/run`은 `validation_framework` scaffold를 additive로 반환한다.
- walk-forward, PBO, Deflated Sharpe Ratio, factor/filter attribution은 아직 계산하지 않고 `not_available_in_current_mvp`와 `calculated=false`로 명시한다.
- 저장형 `/api/backtest/run`은 `backtest_runs`와 함께 closed trade 전체를 `backtest_trade_ledger`에 저장한다.
- `/api/backtest/runs/{run_id}`는 기존 metric contract에 `trade_ledger_count`, `trade_ledger`, `trades`를 additive로 제공한다.
- `/api/backtest/runs/{run_id}/trades`는 저장된 ledger rows를 반환한다.
- `/api/reports/daily`와 `/api/reports/weekly`는 같은 Report persistence contract를 사용하며, `/api/reports?report_type=daily|weekly` 필터를 지원한다.
- Weekly review는 ledger가 있으면 realized PnL, realized return, win rate, average holding days, setup별 trade hit rate, failed trades review를 계산한다.
- ledger가 없거나 아직 계약이 없는 항목은 `not_available_in_current_mvp`로 표기하고 거짓 0 수치로 채우지 않는다.
- `/api/portfolio/risk`는 기존 필드를 유지하면서 `positions`와 최신 통과 `screen_results` 기반 gross/sector/symbol/strategy exposure, daily loss budget, gap risk preview, concentration warnings를 additive로 반환한다.
- `/api/market/session`, `/api/market/sessions`, `/api/market/calendar`는 KRX/NXT venue-aware session/calendar metadata를 network 없이 반환한다.
- `/api/broker/orders/preview`와 `/api/paper/orders/preview`는 기존 deny/fail-closed 계약을 유지하면서 `venue`, `session`, `session_metadata`를 additive로 반환한다.
- JSON 산출물: `backend/reports/strategy_validation_252d.json`.
- DB migration head: `e5f6a7b8c9d0_add_indicator_breadth_fields`.

## 최근 변경 요약

- `backend/app/services/validation_service.py`를 추가해 validation 계산, baseline 비교, JSON report 저장, placeholder scaffold를 분리했다.
- `BacktestService.strategy_summary()`와 `ReportService.write_strategy_validation_summary()`는 기존 호출 호환 wrapper로 유지했다.
- backtest metrics에 `walk_forward`, `pbo`, `probability_of_backtest_overfitting`, `deflated_sharpe_ratio`, `factor_filter_attribution` placeholder를 additive로 추가했다.
- minimal trade ledger schema metadata는 `backtest_and_report_analysis_only` 범위와 `orders`/`paper_orders`/broker/KIS/live trading 미연결을 명시한다.
- baseline_run_id, baseline_snapshot, unavailable placeholder, strategy-level payload 안정성 테스트를 추가했다.

## 최신 검증 결과

- 2026-05-26 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_phase2_api.py -q`: 41 passed in 99.84s.
- 2026-05-26 `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 287 passed in 249.61s.
- 2026-05-26 `git diff --check`: 통과, CRLF warning 외 whitespace error 없음.
- 2026-05-26 frontend lint/typecheck/build는 이번 backend-only 변경에서 재실행하지 않았다. 직전 동일일 검증은 통과 상태였다.

## 불변 조건

- 실제 주문, 주문 취소, 체결, 계좌 이동, websocket, live broker 구현 금지.
- 실제 주문용 stop order 생성 금지.
- paper order/fill/position/audit mutation 구현 금지.
- KIS/KRX/yfinance network call, KIS token 발급/cache/credential 저장 금지.
- earnings/corporate action 실데이터 fetch 추가 금지.
- adjusted price는 corporate action effective-date as-of row가 없으면 raw OHLC로 fail-closed 처리한다.
- broker/order adapter import 또는 호출 금지.
- strategy registry 순서 변경 금지.
- 기존 `StrategyResult` 필드 제거 금지.
- 기존 screener/backtest/report API breaking change 금지.
- 기존 metrics key 제거 또는 의미 변경 금지.
- walk-forward/PBO/Deflated Sharpe/factor attribution은 실제 계산 전까지 거짓 수치로 채우지 않는다.
- `orders_count == 0`, `paper_* == 0`, KIS/paper execution routes 404 유지.
- `backtest_trade_ledger`는 backtest/report 분석 산출물이며 `orders`, `paper_orders`, broker/KIS route와 연결하지 않는다.
- Portfolio Risk Guard v2는 synthetic/preview summary이며 broker position sync, paper/live order, paper position mutation과 연결하지 않는다.
- venue/session metadata는 preview 응답에만 추가하며 submit 가능 여부를 true로 바꾸지 않는다.
- `npm audit fix --force`, Next.js downgrade, main 강제 push 금지.

## 미구현 항목

- 실제 주문, 주문 취소, 체결, 계좌, 예수금, websocket, live broker.
- paper order create, paper fill simulator, paper position mutation.
- KIS credential/token 저장, token 발급/refresh/cache, 실제 KIS API 호출.
- 실제 KRX/yfinance network fetch.
- 자동매매 scheduler, live broker adapter, AI prediction model.
- 실제 거래소 holiday/calendar feed, KIS token lifecycle, 호출량 budget enforcement와 session service 연동.
- broker-synced portfolio cash/position state, cash lock, open_positions state machine, realized exposure/drawdown.
- walk-forward evaluation engine, PBO, Deflated Sharpe Ratio, factor/filter attribution 계산.
- weekly parameter drift 계산을 위한 historical strategy parameter snapshot.
- MAE/MFE, realized drawdown/exposure/open position risk, regime/factor별 realized PnL attribution 저장 계약.

## 다음 작업

- [ ] Parameter snapshot foundation: weekly `Parameter Drift Check`를 실제 이력 기반으로 계산할 수 있는 저장 계약을 검토한다.
- [ ] Walk-forward/PBO/DSR 계산 설계: train/test window, multiple-testing 보정 입력, 수익률 표본 계약을 먼저 정의한다.
- [ ] Factor/filter attribution: trade ledger와 pass_flags/failed_conditions/risk_flags를 연결할 저장/조회 계약을 검토한다.
- [ ] Monthly report extension을 daily/weekly 공통 persistence contract 위에 추가할지 검토한다.
- [ ] summary endpoint의 `baseline_snapshot` 입력을 파일 기반 import flow로 확장할지 별도 검토한다.
- [ ] rank portfolio trade detail을 `/backtest` 상세 화면에서 별도 표로 보여줄지 검토한다.
- [ ] 실제 trade ledger 또는 broker-synced position ledger가 생기면 Portfolio Risk Guard v2의 synthetic 계산을 ledger 기반 계산으로 확장한다.
- [ ] session service를 실제 거래소 holiday feed, KIS token lifecycle, 호출량 budget enforcement와 연결할지는 별도 운영 계층 범위에서 검토한다.
- [ ] launcher를 설치형 exe 또는 FastAPI static frontend 제공 방식으로 확장할지는 별도 v2 범위에서 검토한다.
- [ ] publish/commit 전에 기존 미커밋 파일과 이번 작업 파일 scope를 분리 확인한다.
