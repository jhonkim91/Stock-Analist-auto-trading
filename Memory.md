# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `Strategy validation 252d summary`
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
- [x] 현재 브랜치: `main`

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, external daily OHLCV preview/confirm, KIS read-only foundation, broker safety scaffold, paper preview scaffold, data quality summary, hardened backtest execution model, strategy metadata endpoint, strategy validation summary endpoint.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/settings`; `/backtest`는 252D validation summary를 읽어 최소 표로 표시한다.
- Product state: 실제 주문 자동매매 엔진이 아니라 분석, 스크리닝, 백테스트, 리포트 중심 자동매매 보조 MVP.
- Strategy default: `trend_breakout`, `vcp_breakout`, `canslim_lite`, `new_high_breakout`, `pullback_20ema`.
- Strategy available: default 5개에 `momentum_rank`, `relative_strength_leader`, `darvas_box`, `stage_analysis_weekly`를 더한 9개.
- `/api/backtest/strategy-summary?lookback_days=252`는 strategy별 screener pass rate, backtest metric subset, baseline delta를 additive로 반환한다.
- baseline이 없으면 `baseline.status="unspecified"`이고 `trade_count_delta`, `win_rate_delta`, `total_return_delta`, `max_drawdown_delta`는 `null`이다.
- JSON 산출물: `backend/reports/strategy_validation_252d.json`.
- DB migration head: `d9e3f0a1b2c4_add_earnings_events`.

## 최근 변경 요약

- `ScreenerService.strategy_pass_rate_summary()`가 최근 available `screen_results.trade_date` 기준 strategy별 pass rate를 계산한다.
- `BacktestService.strategy_summary()`가 최근 available `indicator_snapshot.trade_date` 기준 strategy별 `trade_count`, `win_rate`, `total_return`, `max_drawdown`을 저장 없이 계산한다.
- `GET /api/backtest/strategy-summary` endpoint와 `ReportService.write_strategy_validation_summary()`를 추가했다.
- `frontend/lib/api.ts`에 strategy validation summary 타입을 추가하고 `/backtest`에 최소 summary 표를 추가했다.
- 252일 미만 available window와 baseline 미지정 `unspecified/null delta` 회귀 테스트를 추가했다.
- `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md`, `README.md`를 최신 검증 상태로 갱신했다.

## 최신 검증 결과

- 2026-05-26 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_phase2_api.py -q`: 34 passed in 78.72s.
- 2026-05-26 `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 252 passed in 192.44s.
- 2026-05-26 `cd frontend; npm.cmd run lint`: passed.
- 2026-05-26 `cd frontend; npm.cmd exec tsc -- --noEmit`: passed.
- 2026-05-26 `cd frontend; npm.cmd run build`: passed, `/backtest` route included.

## 불변 조건

- 실제 주문, 주문 취소, 체결, 계좌 이동, websocket, live broker 구현 금지.
- 실제 주문용 stop order 생성 금지.
- paper order/fill/position/audit mutation 구현 금지.
- KIS/KRX/yfinance network call, KIS token 발급/cache/credential 저장 금지.
- broker/order adapter import 또는 호출 금지.
- strategy registry 순서 변경 금지.
- 기존 `StrategyResult` 필드 제거 금지.
- 기존 screener/backtest API breaking change 금지.
- 기존 metrics key 제거 또는 의미 변경 금지.
- `orders_count == 0`, `paper_* == 0`, KIS/paper execution routes 404 유지.
- `npm audit fix --force`, Next.js downgrade, main 강제 push 금지.

## 다음 작업

- [ ] Phase 3I: weekly review report를 fixture 기반으로 검증한다.
- [ ] summary endpoint의 `baseline_snapshot` 입력을 파일 기반 import flow로 확장할지 별도 검토한다.
- [ ] rank portfolio trade detail을 `/backtest` 상세 화면에서 별도 표로 보여줄지 검토한다.
- [ ] Strategy selector metadata의 required fields를 earnings/pattern context 신규 필드까지 확장할지 검토한다.
- [ ] Phase 4A/4B broker 또는 live gate는 별도 승인 전까지 구현하지 않는다.
- [ ] publish/commit 전에 기존 미커밋 파일과 이번 작업 파일 scope를 분리 확인한다.
