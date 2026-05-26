# Validation

## 최신 검증 결과

검증 기준일: 2026-05-26

Checkpoint: `Validation Framework Scaffold`

기준 브랜치: `main`

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Validation summary targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_phase2_api.py -q`: 41 passed in 99.84s |
| Backend full pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 287 passed in 249.61s |
| Frontend lint/typecheck/build | 미실행 | 이번 변경은 backend service/API/test/docs 범위이며 frontend 파일은 수정하지 않음 |
| Diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning 외 whitespace error 없음 |

## 검증 범위

- `indicator_snapshot` breadth fields SQLAlchemy model과 Alembic head `e5f6a7b8c9d0_add_indicator_breadth_fields`가 테스트 DB에 적용된다.
- `IndicatorService.recompute()`는 full recompute와 `symbol/start_date/end_date` 증분 recompute를 모두 지원하고, 증분 결과가 full recompute changed range와 일치한다.
- weekly derived field availability flags는 short-history 입력에서 false/not_available 계열로 fail-closed 처리된다.
- `RegimeService`는 breadth proxy를 제공하고, universe breadth 데이터가 없으면 `breadth_regime="not_available"`로 처리한다.
- `momentum_rank`, `stage_analysis_weekly` breadth hardening은 optional enabled 상태에서만 pass/fail에 적용된다.
- CANSLIM Lite earnings blackout은 `earnings_date`, `release_ts`, `session`을 함께 사용하며 release timestamp/session 누락 또는 미인식 session은 fail-closed로 처리된다.
- `MarketRepository.corporate_actions_asof()`는 `corporate_actions.action_date <= trade_date`만 반환하고 future corporate action을 제외한다.
- Backtest `execution.use_adjusted_price=true`는 유효한 corporate action as-of row가 있는 bar에서만 `adj_close / close` factor를 적용하고, 그 외에는 raw OHLC로 실행한다.
- CSV/external daily OHLCV preview는 `adj_close != close`인데 effective corporate action이 없으면 `ADJUSTED_CLOSE_WITHOUT_EFFECTIVE_CORPORATE_ACTION` warning을 남긴다.
- 별도 `weekly_ohlcv` table/migration은 추가하지 않았다. 주봉 파생값은 daily OHLCV 기반 as-of 계산과 `indicator_snapshot` nullable fields를 유지한다.
- `backtest_trade_ledger` SQLAlchemy model과 saved backtest trade ledger migration이 테스트 DB에 적용된다.
- 저장형 `POST /api/backtest/run`은 `backtest_runs`와 함께 closed trade ledger rows를 저장한다.
- `GET /api/backtest/runs/{run_id}`는 기존 metric contract를 유지하면서 `trade_ledger_count`, `trade_ledger`, `trades`를 additive로 반환한다.
- `GET /api/backtest/runs/{run_id}/trades`는 저장된 ledger rows를 조회한다.
- `POST /api/reports/daily` 기존 daily report 생성 계약을 유지한다.
- `POST /api/reports/weekly`는 `report_type="weekly"`로 Report 테이블을 재사용한다.
- `GET /api/reports?report_type=daily|weekly`는 기존 `limit` query에 additive filter로 동작한다.
- `GET /api/reports/{report_id}/markdown`는 daily/weekly 모두 Markdown 다운로드로 동작한다.
- Weekly Strategy Review는 ledger가 있으면 realized trade count, realized PnL, realized return, win rate, average holding days, setup별 trade hit rate, failed trades review를 계산한다.
- ledger가 없거나 현재 MVP에 저장 계약이 없는 realized drawdown/exposure/open position risk, regime segment return, realized factor/filter PnL attribution, MAE/MFE, parameter drift 항목은 `not_available_in_current_mvp`로 표기한다.
- `GET /api/portfolio/risk`는 기존 주요 응답 필드를 유지하면서 `max_open_positions`, gross/sector/symbol/strategy exposure, `daily_loss_budget`, `gap_risk_estimate`, `concentration_warnings`를 additive로 반환한다.
- portfolio risk summary는 `positions`와 최신 통과 `screen_results`를 함께 활용하되 synthetic/preview 한계를 `warnings`와 `gap_risk_estimate.status`에 남긴다.
- `MarketSessionService`는 KRX `regular`/`after_hours`, NXT `pre_market`/`main`/`after_market`, 휴장일 또는 세션 외 시간을 판정한다.
- `GET /api/market/session`, `GET /api/market/sessions`, `GET /api/market/calendar`는 network 없이 venue/session/calendar metadata를 반환한다.
- `/api/broker/orders/preview`와 `/api/paper/orders/preview`는 기존 deny/fail-closed 계약을 유지하면서 `venue`, `session`, `session_metadata`를 additive로 반환한다.
- 실제 주문, paper order, broker/KIS route, credential/token 저장 경로는 추가하지 않았다.
- `StrategyValidationService`는 strategy summary 계산을 담당하고, `ValidationReportService`는 JSON artifact 저장을 담당한다. 기존 `BacktestService.strategy_summary()`와 `ReportService.write_strategy_validation_summary()`는 호환 wrapper로 유지한다.
- baseline 비교는 `ValidationBaselineComparator`가 담당하며 `baseline_run_id`, `baseline_snapshot`, strategy list snapshot, 단일 strategy snapshot shape를 재사용 가능한 metric map으로 정규화한다.
- `GET /api/backtest/strategy-summary`는 기존 strategy-level `screener`, `backtest`, `delta` payload를 유지하면서 `validation_framework`와 strategy별 `validation` placeholder를 additive로 반환한다.
- `POST /api/backtest/run`은 기존 응답 key를 제거하지 않고 `validation_framework`를 additive로 반환한다.
- backtest metrics에는 `walk_forward`, `pbo`, `probability_of_backtest_overfitting`, `deflated_sharpe_ratio`, `factor_filter_attribution` placeholder가 추가됐다.
- walk-forward, PBO, Deflated Sharpe Ratio, factor/filter attribution은 아직 계산하지 않는다. 모든 unavailable 항목은 `not_available_in_current_mvp` 문자열과 `calculated=false` metadata로 반환한다.
- minimal trade ledger schema는 `validation_framework.trade_ledger_schema`에 문서화한다. 범위는 `backtest_and_report_analysis_only`이며 `orders`, `paper_orders`, broker adapter, KIS order route, live trading과 연결하지 않는다.

## 재현 명령

Backend:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

Frontend:

```powershell
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
cd ..
```

Diff:

```powershell
git diff --check
```

## Safety Contract

| 항목 | 상태 |
|---|---|
| 실제 주문/주문 취소/체결/계좌 이동 | 없음 |
| broker/paper adapter 호출 | 없음 |
| paper order/fill/position mutation | 없음 |
| KIS/KRX/yfinance network call | 없음 |
| credential/token 저장 | 없음 |
| earnings/corporate action 실데이터 fetch | 없음 |
| venue/session metadata가 submit 가능 상태로 전환 | 없음 |
| 기존 backtest run/list/detail 응답 필드 제거 | 없음 |
| 기존 portfolio risk 응답 주요 필드 제거 | 없음 |
| 실주문 관련 route 추가 | 없음 |
| walk-forward/PBO/Deflated Sharpe 추정 수치 생성 | 없음. `not_available_in_current_mvp` placeholder만 반환 |
| factor/filter attribution 추정 수치 생성 | 없음. `not_available_in_current_mvp` placeholder만 반환 |
| report schema 변경 | 기존 `reports` 테이블 재사용 |
| indicator schema 변경 | 이번 변경 없음. 기존 breadth proxy nullable fields와 availability flags 유지 |
| backtest/report schema 변경 | `backtest_trade_ledger` 유지 |
| trade ledger와 주문 테이블 연결 | 없음. validation scaffold에도 `not_connected_to`로 명시 |
| weekly_ohlcv migration 추가 | 없음 |
| `orders_count == 0` 정책 변경 | 없음 |

## 남은 검증

- frontend lint/typecheck/build는 이번 backend-only 변경에서 재실행하지 않았다.
- walk-forward/PBO/Deflated Sharpe Ratio/factor attribution은 이번 단계에서 scaffold만 검증했다. 실제 계산식, 표본 분할, multiple-testing 보정, attribution join 계약은 별도 단계에서 정의해야 한다.
