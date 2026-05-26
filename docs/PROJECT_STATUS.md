# Project Status

## 현재 기준

| 항목 | 값 |
|---|---|
| Version | `MVP v0.21.0` |
| Phase | `Validation Framework Scaffold` |
| Branch | `main` |
| 상태 | 분석/스크리닝/백테스트/리포트 중심 자동매매 보조 MVP |
| 거래 상태 | 실거래 미구현, fail-closed, preview-only |
| 최신 backend pytest | `287 passed` |
| 다음 권장 Phase | `Parameter Snapshot Foundation → Walk-forward/PBO/DSR` |

## 구현 완료 항목

- Phase 1: Backend Core MVP.
- Phase 2: MVP Web Flow.
- Phase 3A: CSV data quality validation and preview-confirm import.
- Phase 3B: provider-neutral external daily OHLCV preview-confirm flow.
- Phase 3C: KIS read-only foundation.
- Phase 3D: broker safety scaffold.
- Phase 3E-1: paper trading safety shell.
- Phase 3F: read-only data reliability, provider contract, KRX fixture contract, data quality summary.
- Phase 3G: hardened backtest execution model, gap-aware stop/target, liquidity and partial-fill simulation.
- Phase 3H: strategy explanation contract, conservative optional strategy filters, fixture tests, strategy registry.
- Phase C-1: `momentum_rank` available-only strategy.
- Phase C-2: `relative_strength_leader` available-only strategy.
- Phase C-3: `new_high_breakout` default and available strategy.
- Phase C-4: `darvas_box` available-only strategy.
- Phase C-5: `stage_analysis_weekly` available-only strategy and nullable weekly indicator fields.
- Phase C-6: `pullback_20ema` default and available strategy, nullable `low`/`ema20` indicator fields.
- Phase C hardening foundation: 9개 전략의 optional hardening 조건, `data_quality_flags`, additive `risk_metadata`.
- Phase C Strategy Hardening: 9개 전략 suite validation 완료.
- Phase C Growth Context Hardening: `canslim_lite` earnings blackout/recent high/institutional proxy, `new_high_breakout` breakout buffer/volume quality, `pullback_20ema` pullback count/volume dry-up context.
- Strategy validation summary: `/api/backtest/strategy-summary?lookback_days=252`, `backend/reports/strategy_validation_252d.json`, baseline 미지정 `unspecified/null delta` contract.
- Backtest integrity hardening: RR 목표가 의미, `rank_portfolio` realized-equity 회계, 평균 활성 포지션 range 집계 보강.
- Phase 3I Weekly Review Report: `POST /api/reports/weekly`, `report_type="weekly"` persistence, daily/weekly report filtering, unavailable trade-ledger fields 명시.
- Trade Ledger Foundation: `backtest_trade_ledger` 저장 계약, saved backtest trade 조회, weekly realized PnL/win rate/failed trades review 계산.
- Portfolio Risk Guard v2: `GET /api/portfolio/risk` additive exposure summary, sector/symbol/strategy concentration, daily loss budget, gap risk preview.
- Venue-aware session preview layer: `MarketSessionService`, `/api/market/session`, `/api/market/sessions`, `/api/market/calendar`, broker/paper preview `session_metadata`.
- Indicator incremental + breadth-aware regime: `IndicatorService.recompute(symbol/start_date/end_date)` 증분 경로, changed range snapshot 갱신, breadth proxy snapshot fields, `RegimeService` breadth diagnostics.
- Data Reliability 2: earnings event timestamp/session blackout, corporate action effective-date as-of lookup, adjusted/raw price 선택 계약.
- Validation Framework Scaffold: `StrategyValidationService`, `ValidationBaselineComparator`, `ValidationReportService`, walk-forward/PBO/Deflated Sharpe/factor attribution placeholder, minimal trade ledger schema metadata.
- Frontend strategy selector: `/api/screener/strategies` metadata와 `/screener`, `/dashboard`, `/backtest` selector 연동.
- GitHub Actions CI: backend pytest, frontend lint/typecheck/build.
- Alembic migration scaffold: initial schema, weekly indicator fields, pullback EMA fields, screen metadata JSON, pattern engine fields, earnings event table, backtest trade ledger table.

## Indicator / Regime 상태

- `IndicatorService`는 full recompute와 `symbol`, `start_date`, `end_date` 기반 증분 recompute를 모두 지원한다.
- 증분 recompute는 rolling/weekly/RS 계산을 위해 요청 시작일보다 앞선 warm-up window를 읽고, 쓰기 전 요청된 symbol/date changed range만 삭제 후 재삽입한다.
- weekly derived fields 계산은 helper로 분리했고, 현재는 별도 `weekly_ohlcv` 물리 테이블을 만들지 않는다. 주봉 값은 daily OHLCV에서 as-of 계산 가능하고, 현재 조회/전략 계약은 `indicator_snapshot` nullable fields로 충분하기 때문이다.
- `indicator_snapshot`에는 `breadth_advance_decline_ratio`, `breadth_52w_high_low_ratio`, `breadth_ma50_participation`, `breadth_score`와 각 availability flag가 추가됐다.
- `RegimeService`는 index/weekly 기반 `index_regime`을 먼저 계산한 뒤 breadth가 weak이면 bull을 neutral로 낮춘다. breadth 데이터가 없으면 `breadth_regime="not_available"`로 표기하고 최종 판정을 강제로 악화시키지 않는다.
- `momentum_rank`, `stage_analysis_weekly`는 breadth hardening을 optional config가 켜진 경우에만 적용하며, enabled 상태에서 breadth 입력이 없으면 fail-closed 처리한다.
- 최신 Alembic head는 `e5f6a7b8c9d0_add_indicator_breadth_fields`다.

## BacktestService 상태

- `metrics.cost_bps`는 `backend/config/backtest.yaml`의 `execution.commission_bps + execution.slippage_bps` 합산값을 반영한다.
- `execution.use_adjusted_price=true`라도 `corporate_actions.action_date <= trade_date` as-of row가 있는 bar에서만 `adj_close / close` factor를 적용한다.
- 유효한 corporate action이 없으면 raw OHLC로 실행하고 `price_detail`에 `corporate_action_status`와 effective-date 상태를 남긴다.
- trade-level `cost_bps`와 metrics-level `cost_bps`는 동일 execution 설정값을 사용한다.
- `run()`은 시작 시 `index_df` 기반 market regime cache를 1회 생성하고 signal date별로 조회한다.
- `RiskService.calculate()`는 명시 목표가가 있으면 해당 목표가 기준으로 `reward_risk_ratio`와 `rr_score`를 계산한다.
- `rr_score`는 실제 손익비를 설정 손익비로 나눈 clamp 점수이며, `rr_ok`는 실제 손익비가 설정 손익비 이상일 때만 true다.
- `rank_portfolio`는 `signal_date` 시작 시점에 `exit_date <= signal_date`인 PnL만 realized equity에 반영하고, 같은 rebalance batch는 동일 equity snapshot으로 sizing한다.
- `average_active_positions`는 entry/exit 양 끝점 sampling이 아니라 `entry_date..exit_date` inclusive range를 sweep-line 방식으로 계산한다.
- 2026-05-26 trade ledger targeted suite 10 passed를 확인했다.
- 기존 `/api/backtest/run`, `/api/backtest/runs`, `/api/backtest/runs/{run_id}` 응답 key는 제거하지 않는다.
- `/api/backtest/strategy-summary`는 최근 available trading window 기준 strategy별 screener pass rate와 backtest metric subset을 additive로 제공한다.
- summary endpoint는 저장형 `backtest_runs` row를 만들지 않고 JSON report artifact만 갱신한다.
- 저장형 `/api/backtest/run`은 `backtest_runs`와 함께 closed trade 전체를 `backtest_trade_ledger`에 저장한다.
- `GET /api/backtest/runs/{run_id}`는 `trade_ledger_count`, `trade_ledger`, `trades`를 additive로 제공한다.
- `GET /api/backtest/runs/{run_id}/trades`는 저장된 ledger rows를 반환한다.
- Metrics에는 `annualized_volatility`, `sharpe_ratio`, `sortino_ratio`, `calmar_ratio`, `turnover`, `regime_segment_return`을 additive로 제공한다.
- Metrics에는 `walk_forward`, `pbo`, `probability_of_backtest_overfitting`, `deflated_sharpe_ratio`, `factor_filter_attribution` placeholder도 additive로 제공한다.
- `regime_segment_return`과 상위 검증 placeholder는 현재 MVP 데이터/검증 엔진 부족으로 `not_available_in_current_mvp`를 반환한다.
- `/api/backtest/run`은 기존 key를 유지하면서 `validation_framework` scaffold를 additive로 반환한다.
- full portfolio-state backtest, cash lock, open_positions 상태머신, walk-forward/PBO/Deflated Sharpe 계산은 구현하지 않았다.

## Validation Framework 상태

- `backend/app/services/validation_service.py`가 strategy summary 계산, baseline 비교, JSON report 저장, placeholder scaffold를 분리한다.
- `StrategyValidationService`는 strategy별 screener pass rate, backtest metric subset, baseline delta payload를 계산한다.
- `ValidationBaselineComparator`는 `baseline_run_id`와 `baseline_snapshot`을 strategy별 metric map으로 정규화해 delta 계산을 재사용할 수 있게 한다.
- `ValidationReportService.write_json_report()`는 strategy summary뿐 아니라 향후 walk-forward 결과도 같은 `report`, `generated_at`, `validation_documentation_format` 포맷으로 저장할 수 있다.
- `GET /api/backtest/strategy-summary`는 기존 `strategies[].screener/backtest/delta` shape를 유지하고 `validation_framework`와 strategy별 `validation` placeholder를 additive로 반환한다.
- walk-forward evaluation, PBO, Deflated Sharpe Ratio, factor/filter attribution은 현재 계산하지 않는다. 모든 값은 `not_available_in_current_mvp`와 `calculated=false`로 명시한다.
- minimal trade ledger schema metadata는 `backtest_trade_ledger`를 `backtest_and_report_analysis_only` 범위로 제안/표기하며 `orders`, `paper_orders`, broker/KIS/live trading과 연결하지 않는다.

## ReportService 상태

- Daily report는 기존 `POST /api/reports/daily`, `report_type="daily"`, `daily_report_{date}.md` 계약을 유지한다.
- Weekly review는 `POST /api/reports/weekly`, `report_type="weekly"`, `weekly_strategy_review_{date}.md`로 저장한다.
- `GET /api/reports`는 기존 `limit`에 더해 `report_type=daily|weekly` 필터를 additive query로 지원한다.
- `GET /api/reports/{report_id}/markdown`는 daily와 weekly 모두 `text/markdown; charset=utf-8` 다운로드로 동작한다.
- Daily report는 단일 기준일의 market regime, sector rotation, triggered/rejected candidates, portfolio risk, mock order review를 보여준다.
- Weekly review는 최근 available `screen_results.trade_date` 최대 5개와 같은 기간의 `backtest_trade_ledger.exit_date`를 기준으로 performance/risk skeleton, setup별 screening/trade hit rate, regime diagnostics, filter failure counts를 보여준다.
- ledger가 있으면 `realized_trade_count`, `realized_pnl`, `realized_return`, `win_rate`, `average_holding_days`, setup별 PnL attribution, failed trades review를 계산한다.
- ledger가 없거나 아직 계약이 없는 `realized_drawdown`, `realized_exposure`, `open_position_risk`, `regime_segment_return`, realized factor/filter PnL attribution, `max_adverse_excursion_review`, parameter drift 항목은 `not_available_in_current_mvp`로 표기한다.

## PortfolioService 상태

- `GET /api/portfolio/risk`는 기존 `account_equity`, `risk_per_trade`, `max_daily_loss`, `open_positions_count`, `total_position_notional`, `available_risk_budget`, `warnings`, `latest_signal_date`, `proposed_positions`, `proposed_notional`, `broker_mode` 필드를 유지한다.
- v2 additive 필드는 `max_open_positions`, `gross_exposure_pct`, `proposed_gross_exposure`, `combined_gross_exposure`, `sector_exposure`, `symbol_exposure`, `strategy_exposure`, `daily_loss_budget`, `gap_risk_estimate`, `concentration_warnings`다.
- 노출 한도 철학은 포지션 수보다 gross/sector/symbol/strategy bucket 집중도를 먼저 확인하는 방식이다.
- 현재 계산은 실제 trade ledger가 아니라 `positions`와 최신 통과 `screen_results` 기반 synthetic/preview summary다.
- `positions`는 broker position sync가 아니며, `screen_results`는 실제 주문 후보가 아니라 조건검색 통과 후보라는 한계를 `warnings`에 남긴다.
- gap risk는 configured adverse gap fraction을 notional에 적용한 preview 추정치이며, notional 데이터가 없으면 `not_available`로 fail-closed 처리한다.
- broker/paper/live order 생성, paper position mutation, cash lock, open position state machine, realized exposure/drawdown 계산은 구현하지 않았다.

## Venue-Aware Session Preview 상태

- `MarketSessionService`는 KRX와 NXT의 session window를 로컬 정적 규칙으로 판정한다.
- KRX는 `pre_hours`, `regular`, `after_hours`를 표현하고, NXT는 `pre_market`, `main`, `after_market`을 표현한다.
- `/api/market/session`은 `venue`, `as_of` 기준 현재 session, trading day status, 다음 session window, preview 허용 metadata를 반환한다.
- `/api/market/sessions`는 venue별 주문 접수/거래 시간 목록을 반환한다.
- `/api/market/calendar`는 weekend, fixed holiday, 주입 holiday 기준의 정적 calendar preview를 반환한다.
- `/api/broker/orders/preview`와 `/api/paper/orders/preview`는 `venue`, `session`, `session_metadata`를 additive로 반환한다.
- `session_metadata.operational_layer`는 session/token/rate-limit/call-budget을 한 운영 계층에서 확장할 자리이며, 현재는 `token_issued=false`, `network_call_allowed=false`, `live_submit_allowed=false`, `paper_submit_allowed=false`만 명시한다.
- 실제 거래소 calendar feed, KIS token 발급/refresh/cache, 호출량 차감, websocket, live/paper submit은 구현하지 않았다.

## Phase C 전략 상태

- 기본 screener 전략은 `trend_breakout`, `vcp_breakout`, `canslim_lite`, `new_high_breakout`, `pullback_20ema` 5개다.
- available strategy는 기본 5개에 `momentum_rank`, `relative_strength_leader`, `darvas_box`, `stage_analysis_weekly` 4개를 더한 9개다.
- `/api/screener/strategies`는 frontend selector에 필요한 `name`, `display_name`, `description`, `is_default`, `is_available`, `required_fields`, `limitations`를 제공한다.
- `/screener`는 기본 전략 5개를 기본 선택하고, available-only 전략은 사용자가 명시 체크한 경우에만 실행 요청에 포함한다.
- `/dashboard`와 `/backtest`의 단일 전략 실행 UI는 backend metadata를 사용한다.
- `IndicatorService`는 EMA20, weekly fields, ATR, volume ratio, 52주 고점, pivot, RS/sector/market score, breadth proxy를 `indicator_snapshot`에 저장한다.
- 최신 Alembic head는 `e5f6a7b8c9d0_add_indicator_breadth_fields`다.
- Screener 응답은 기존 explanation contract 필드를 제거하지 않는다.

## Phase C Hardening Foundation

- `backend/config/strategies.yaml`의 `common.hardening`은 신규 조건 enable flag와 threshold를 관리한다.
- 기본 신규 조건 enable flag는 false다.
- 신규 조건 후보는 `market_regime_not_bear`, `sector_rs_score_min`, `market_score_min`, `atr20_pct_max`, `volume_ratio_50_min`, `near_high_52w_threshold`, `breadth_score_min`, `breadth_advance_decline_ratio_min`, `breadth_52w_high_low_ratio_min`, `breadth_ma50_participation_min`, `optional_fundamental_quality`, `optional_earnings_quality`다.
- `canslim_lite`는 `earnings_blackout_days`, `require_recent_new_high`, `require_institutional_proxy`를 strategy metadata에 남긴다.
- `new_high_breakout`은 `breakout_buffer_pct`와 `require_breakout_day_volume_ratio`를 분리 평가하고 `breakout_context` metadata를 남긴다.
- `pullback_20ema`는 `max_pullback_count`와 `require_volume_dry_up_vs_ma20` 기준으로 first/second pullback 및 volume dry-up context를 평가한다.
- 신규 조건은 `pass_flags`와 `failed_conditions`에 additive로만 추가한다.
- 신규 조건의 사용 가능 여부는 `metadata.data_quality_flags`에 남긴다.
- `metadata.risk_metadata`는 `suggested_stop_price`, `risk_per_share`, `risk_basis`, `entry_chase_warning`을 additive로 제공한다.
- strategy registry order, `DEFAULT_STRATEGY_NAMES`, `AVAILABLE_STRATEGY_NAMES`, `StrategyResult` 기존 필드는 변경하지 않는다.
- 2026-05-26 backend full pytest 287 passed를 확인했다. frontend lint/typecheck/build는 이번 backend-only 변경에서 재실행하지 않았으며 최신 검증 상태는 `docs/VALIDATION.md`를 기준으로 본다.

## Data Reliability 2 상태

- `canslim_lite`는 `earnings_events.earnings_date`, `release_ts`, `session`을 함께 사용해 blackout window를 계산한다.
- earnings event/date/timestamp/session 누락 또는 미인식 session은 `earnings_blackout_clear=false`로 fail-closed 처리하고 `data_quality_flags`에 원인을 남긴다.
- `MarketRepository.earnings_event_asof()`는 blackout용 event-calendar 조회라 예정 이벤트 lookahead를 허용하지만, fundamentals와 corporate action as-of 조회는 `effective_date/action_date <= trade_date`를 지킨다.
- `CorporateAction.effective_date`는 현재 DB column인 `action_date` alias이며, 별도 corporate action schema migration은 추가하지 않았다.
- CSV/external daily OHLCV preview는 `adj_close != close`인데 effective corporate action이 없으면 warning을 남기며, confirm 자체를 막지는 않는다.
- 별도 `weekly_ohlcv` table은 만들지 않는다. 현재 주봉 전략 요구사항은 daily OHLCV에서 as-of 파생해 `indicator_snapshot` nullable fields로 충족한다.

## 미구현 항목

- 실제 주문, 주문 취소, 체결, 계좌, 잔고, websocket, live broker.
- paper order create, paper fill simulator, paper position mutation.
- KIS credential/token 저장, token 발급/refresh/cache, 실제 KIS API 호출.
- 실제 KRX/yfinance network fetch.
- 자동매매 scheduler, live broker adapter, AI prediction model.
- broker-synced portfolio cash/position state, cash lock, open_positions state machine, realized exposure/drawdown.
- walk-forward evaluation engine, PBO, Deflated Sharpe Ratio, factor/filter attribution 계산.

## 안전 제약사항

- broker/paper는 기본 deny, fail-closed, preview-only 정책을 유지한다.
- venue/session metadata는 preview 응답에만 노출하며 submit 가능 여부를 true로 바꾸지 않는다.
- `orders_count == 0`을 유지한다.
- `paper_orders`, `paper_fills`, `paper_positions`, `paper_audit_events` row count는 0을 유지한다.
- `POST /api/paper/orders`, `POST /api/paper/fill-simulator/run`, `/api/kis/orders/*`, `/api/kis/broker/*`, `/api/kis/websocket/*`는 미등록 404 상태를 유지한다.
- KIS token cache 파일 `.cache/kis/token.json`은 생성하지 않는다.
- secret, token, account/header/raw credential 값을 코드, 문서, 로그, API 응답에 노출하지 않는다.

## 검증 명령

Backend:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

Backtest integrity:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_risk.py backend/tests/test_backtest.py backend/tests/test_phase3g_backtest_execution_model.py -q
```

Strategy validation summary:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_phase2_api.py -q
```

Latest validation framework scaffold result:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_phase2_api.py -q
# 41 passed in 99.84s
.\.venv\Scripts\python.exe -m pytest backend/tests -q
# 287 passed in 249.61s
git diff --check
# passed, CRLF warnings only
```

Strategy hardening:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_strategies.py -q
```

Broker/paper/KIS/backtest safety:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3c_kis_readonly.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_phase3g_backtest_execution_model.py -q
```

Frontend:

```powershell
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
```

Alembic migration:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_alembic_migrations.py -q
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

## 다음 권장 Phase

Parameter Snapshot Foundation을 먼저 검토한 뒤 Walk-forward/PBO/DSR 계산 설계로 확장한다. 다음 단계에서는 strategy parameter snapshot 저장 계약, train/test window 분할, multiple-testing 보정 입력, factor/filter attribution join 계약을 순서대로 정의해야 한다. 기존 API, safety contract, no real-order 정책은 유지한다.
