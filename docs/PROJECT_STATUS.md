# Project Status

## 현재 기준

| 항목 | 값 |
|---|---|
| Version | `MVP v0.26.0` |
| Phase | `KIS Paper Balance Inquiry Read-only` |
| Goal.md Phase 0 | `docs/research/kis-paper-baseline-audit.md`에서 main 기준선과 현재 작업 브랜치 차이를 분리 감사 |
| Branch | `feature/kis-paper-goal-phases` (baseline: `main`) |
| 상태 | 분석/스크리닝/백테스트/리포트 중심 자동매매 보조 MVP |
| 거래 상태 | paper-only local submit gated by `confirm=true`, idempotency, kill-switch; KIS paper balance read-only 조건부 지원; live/real order disabled |
| 최신 backend pytest | full backend `342 passed`, KIS balance/no-live/secret targeted suites 통과 |
| 다음 권장 Phase | KIS paper submit/cancel/sync network 구현은 보류. balance 조회는 read-only 조건부 경로만 허용 |

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
- Validation Framework Scaffold: `StrategyValidationService`, `ValidationBaselineComparator`, `ValidationReportService`, PBO/Deflated Sharpe/factor attribution scaffold, minimal trade ledger schema metadata.
- Parameter Snapshot Foundation: `strategy_parameter_snapshots` 저장 계약, `StrategyParameterSnapshotService` 저장/조회/diff, weekly `Parameter Drift Check` snapshot 기반 diff/unavailable/no-drift 상태 표기.
- Walk-forward Minimal OOS Summary: train/test/step trading-day window와 rebalance frequency 입력 기반 `WalkForwardRunner`, strategy별 OOS metric summary, insufficient data fail-closed, `strategy_validation_252d.json` artifact 저장.
- PBO/DSR Minimal Overfitting Validation: walk-forward window total_return 기반 CSCV-lite PBO, multiple-testing 및 non-normal input shape 기반 Deflated Sharpe Ratio, insufficient sample fail-closed unavailable.
- Factor/Filter Attribution Minimal Integration: `backtest_trade_ledger`와 `screen_results`를 signal date/symbol/strategy 기준으로 join해 realized PnL attribution과 screen filter failure counts를 분리 계산.
- KIS Paper Broker Phase 0 Baseline Audit: 현재 fail-closed 기준선, stale 문서 충돌, 공식 문서 확인 필요 matrix를 문서화.
- KIS Paper Broker Phase 1 Notification Foundation: `backend/config/notifications.yaml`, `/api/notifications/status`, `/api/notifications/test`, disabled/mock 기본값, Discord/Telegram adapter skeleton, settings redacted summary.
- KIS Paper Broker Phase 2 KIS Paper Broker Contract: `BrokerAdapter` contract, KIS paper/live adapter skeleton, in-memory-only token manager, no-live regression tests.
- KIS Paper Broker Phase 3 Paper Trading Persistence: `paper_*` table additive extension, `paper_portfolio_snapshots`, `broker_audit_events`, `notification_events`, `notification_delivery_logs`, `kis_token_status_metadata`.
- KIS Paper Broker Phase 4 Paper Order Preview/Submit/Cancel: local `paper_orders` submit/list lifecycle, explicit `confirm=true`, required idempotency key + canonical request hash, kill-switch/config gate, cancel disabled until official KIS cancel payload is confirmed.
- KIS Paper Broker Phase 5 Fill/Position/Portfolio Sync: `paper_fills`, `paper_positions`, `paper_portfolio_snapshots` read APIs and fail-closed/idempotent `POST /api/paper/sync`; synthetic `positions` remains separate.
- KIS Paper Broker Phase 6 Report Notification: saved report notification endpoint, channel-safe summary splitting, optional attachment metadata, sanitized notification event/delivery logs, delivery failure isolation.
- KIS Paper Broker Phase 7 Bot Scheduler: disabled-by-default bot config, safe once/loop CLI runner, bot status/run API, launcher check-only integration, explicit auto-submit gate.
- KIS Paper Broker Phase 8 Frontend Integration: `/paper`, `/portfolio`, `/reports`, `/settings`에 paper-only banner와 backend-gated submit/cancel/sync/notify controls를 추가하고 live readiness copy를 배제.
- KIS Paper Broker Phase 9 Validation & Hardening: repo secret scan 도구, CI secret scan, settings key-name redaction hardening, operation doc, full backend/frontend acceptance 검증.
- KIS Paper Balance Inquiry Read-only: `/api/paper/portfolio`에서 paper mode와 env credential 조건이 모두 맞을 때만 KIS `주식잔고조회` paper TR `VTTC8434R`를 호출하고, 기본 disabled/mock 상태는 local snapshot fallback을 유지.
- Goal.md Phase 0 Baseline Audit Refresh: `docs/research/kis-paper-baseline-audit.md`에 main ref `bfcb1691e56dbdbbfc18b043bc65ec447acafa3e`와 현재 작업 브랜치 `ffd7f52a4745df2b99c8dae694796eab5e8f024d`를 분리 기록하고, Phase 0 범위가 문서 감사뿐임을 확정.
- Frontend strategy selector: `/api/screener/strategies` metadata와 `/screener`, `/dashboard`, `/backtest` selector 연동.
- GitHub Actions CI: backend pytest, frontend lint/typecheck/build.
- Alembic migration scaffold: initial schema, weekly indicator fields, pullback EMA fields, screen metadata JSON, pattern engine fields, earnings event table, backtest trade ledger table, strategy parameter snapshot table.

## Indicator / Regime 상태

- `IndicatorService`는 full recompute와 `symbol`, `start_date`, `end_date` 기반 증분 recompute를 모두 지원한다.
- 증분 recompute는 rolling/weekly/RS 계산을 위해 요청 시작일보다 앞선 warm-up window를 읽고, 쓰기 전 요청된 symbol/date changed range만 삭제 후 재삽입한다.
- weekly derived fields 계산은 helper로 분리했고, 현재는 별도 `weekly_ohlcv` 물리 테이블을 만들지 않는다. 주봉 값은 daily OHLCV에서 as-of 계산 가능하고, 현재 조회/전략 계약은 `indicator_snapshot` nullable fields로 충분하기 때문이다.
- `indicator_snapshot`에는 `breadth_advance_decline_ratio`, `breadth_52w_high_low_ratio`, `breadth_ma50_participation`, `breadth_score`와 각 availability flag가 추가됐다.
- `RegimeService`는 index/weekly 기반 `index_regime`을 먼저 계산한 뒤 breadth가 weak이면 bull을 neutral로 낮춘다. breadth 데이터가 없으면 `breadth_regime="not_available"`로 표기하고 최종 판정을 강제로 악화시키지 않는다.
- `momentum_rank`, `stage_analysis_weekly`는 breadth hardening을 optional config가 켜진 경우에만 적용하며, enabled 상태에서 breadth 입력이 없으면 fail-closed 처리한다.
- 최신 Alembic head는 `a8b9c0d1e2f3_paper_trading_persistence`다.

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
- `/api/backtest/strategy-summary`는 최근 available trading window 기준 strategy별 screener pass rate, backtest metric subset, walk-forward OOS summary를 additive로 제공한다.
- summary endpoint는 저장형 `backtest_runs` row를 만들지 않고 JSON report artifact만 갱신한다.
- 저장형 `/api/backtest/run`은 `backtest_runs`와 함께 closed trade 전체를 `backtest_trade_ledger`에 저장한다.
- `GET /api/backtest/runs/{run_id}`는 `trade_ledger_count`, `trade_ledger`, `trades`를 additive로 제공한다.
- `GET /api/backtest/runs/{run_id}/trades`는 저장된 ledger rows를 반환한다.
- Metrics에는 `annualized_volatility`, `sharpe_ratio`, `sortino_ratio`, `calmar_ratio`, `turnover`, `regime_segment_return`을 additive로 제공한다.
- 저장형 backtest run metrics에는 `walk_forward`, `pbo`, `probability_of_backtest_overfitting`, `deflated_sharpe_ratio`, `factor_filter_attribution` placeholder도 additive로 제공한다.
- `regime_segment_return`과 상위 검증 placeholder는 현재 MVP 데이터/검증 엔진 부족으로 `not_available_in_current_mvp`를 반환한다.
- `/api/backtest/run`은 기존 key를 유지하면서 `validation_framework` scaffold를 additive로 반환한다.
- full portfolio-state backtest, cash lock, open_positions 상태머신은 구현하지 않았다. factor/filter attribution은 저장된 ledger/screen join으로 확인되는 최소 범위만 계산한다. PBO/Deflated Sharpe는 walk-forward 표본이 충분할 때만 계산한다.

## Validation Framework 상태

- `backend/app/services/validation_service.py`가 strategy summary 계산, baseline 비교, JSON report 저장, placeholder scaffold를 분리한다.
- `StrategyValidationService`는 strategy별 screener pass rate, backtest metric subset, baseline delta payload를 계산한다.
- `ValidationBaselineComparator`는 `baseline_run_id`와 `baseline_snapshot`을 strategy별 metric map으로 정규화해 delta 계산을 재사용할 수 있게 한다.
- `StrategyParameterSnapshotService`는 현재 `backend/config/strategies.yaml`의 `common + strategy` parameter payload를 strategy별 snapshot으로 저장하고, 기준일 이전 최신 snapshot과 현재 config를 비교한다.
- snapshot row는 `strategy_name`, `config_hash`, `snapshot_date`, `effective_date`, `parameter_json`, `created_at`을 저장한다.
- snapshot이 없으면 drift를 만들지 않고 `not_available_in_current_mvp`, `strategy_parameter_snapshot_not_found`, `drifted_parameter_count=0`을 반환한다.
- `WalkForwardRunner`는 train window를 window metadata로 고정하고 test window만 `BacktestService.run(save=False)`로 실행해 OOS 수치를 만든다. 기본값은 train 126 trading days, test 21 trading days, step 63 trading days, backtest config의 rebalance frequency다.
- walk-forward 데이터가 부족하면 `calculated=false`, `reason="insufficient_indicator_trading_days"`, `summary=null`, `windows=[]`로 fail-closed 처리한다.
- `ValidationReportService.write_json_report()`는 strategy summary뿐 아니라 향후 walk-forward 결과도 같은 `report`, `generated_at`, `validation_documentation_format` 포맷으로 저장할 수 있다.
- `GET /api/backtest/strategy-summary`는 기존 `strategies[].screener/backtest/delta` shape를 유지하고 `validation_framework.walk_forward`와 strategy별 `validation.walk_forward`에 최소 OOS summary를 additive로 반환한다.
- PBO는 walk-forward window `total_return` 행렬이 strategy 2개 이상, 비교 가능 window 2개 이상일 때 CSCV-lite leave-one-window-out 방식으로 계산한다.
- Deflated Sharpe Ratio는 strategy 2개 이상과 strategy별 OOS return sample 4개 이상, return variance가 있을 때 multiple-testing expected-max Sharpe와 skewness/kurtosis input shape를 포함해 계산한다.
- 표본이 부족하면 PBO/DSR 모두 `not_available_in_current_mvp`, `calculated=false`, 명확한 `reason`을 유지한다.
- `FactorFilterAttributionService`는 `backtest_trade_ledger.signal_date = screen_results.trade_date`, `symbol`, `strategy_name/strategy_tag`로 join 가능한 row만 attribution에 사용한다.
- `validation_framework.attribution`과 strategy별 `validation.attribution`은 realized PnL attribution과 screen filter failure counts를 분리해 반환한다.
- join 불가능한 row, 저장되지 않은 market regime 등은 추정하지 않고 `not_available_in_current_mvp`로 남긴다.
- minimal trade ledger schema metadata는 `backtest_trade_ledger`를 `backtest_and_report_analysis_only` 범위로 제안/표기하며 `orders`, `paper_orders`, broker/KIS/live trading과 연결하지 않는다.

## ReportService 상태

- Daily report는 기존 `POST /api/reports/daily`, `report_type="daily"`, `daily_report_{date}.md` 계약을 유지한다.
- Weekly review는 `POST /api/reports/weekly`, `report_type="weekly"`, `weekly_strategy_review_{date}.md`로 저장한다.
- `GET /api/reports`는 기존 `limit`에 더해 `report_type=daily|weekly` 필터를 additive query로 지원한다.
- `GET /api/reports/{report_id}/markdown`는 daily와 weekly 모두 `text/markdown; charset=utf-8` 다운로드로 동작한다.
- Daily report는 단일 기준일의 market regime, sector rotation, triggered/rejected candidates, portfolio risk, mock order review를 보여준다.
- Weekly review는 최근 available `screen_results.trade_date` 최대 5개와 같은 기간의 `backtest_trade_ledger.exit_date`를 기준으로 performance/risk skeleton, setup별 screening/trade hit rate, regime diagnostics, factor/filter attribution, filter failure counts를 보여준다.
- ledger가 있으면 `realized_trade_count`, `realized_pnl`, `realized_return`, `win_rate`, `average_holding_days`, setup별 PnL attribution, failed trades review를 계산한다.
- `Parameter Drift Check`는 현재 config와 기준일 이전 최신 strategy parameter snapshot을 비교해 `drift_detected`, `no_drift`, `partial_snapshot_history`, `not_available_in_current_mvp` 중 하나로 표기한다.
- Markdown에는 `changed_keys`, `unchanged_keys_count`, `snapshot_dates`, `effective_dates`, `config_hash_diff`를 표시하고, 전체 비교 결과 drift가 없으면 `no_drift_detected`를 명시한다.
- snapshot이 없으면 `parameter_snapshot_status: not_available_in_current_mvp`, `comparison_available: false`, `unavailable_reason: strategy_parameter_snapshot_not_found`를 표시하며 거짓 diff를 만들지 않는다.
- report detail API의 `metadata.parameter_drift`는 저장된 Markdown의 `Parameter Drift Check` 섹션에서 추출해 Markdown과 서로 모순되지 않게 유지한다.
- `Factor/Filter Attribution`은 placeholder bullet 대신 realized PnL attribution table과 screen filter failure counts table을 출력한다.
- ledger가 없거나 아직 계약이 없는 `realized_drawdown`, `realized_exposure`, `open_position_risk`, `regime_segment_return`, `max_adverse_excursion_review` 항목은 `not_available_in_current_mvp`로 표기한다.

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
- 최신 Alembic head는 `a8b9c0d1e2f3_paper_trading_persistence`다.
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
- frontend lint/typecheck/build와 backend full pytest는 이번 targeted backend 변경에서 재실행하지 않았으며 최신 검증 상태는 `docs/VALIDATION.md`를 기준으로 본다.

## Data Reliability 2 상태

- `canslim_lite`는 `earnings_events.earnings_date`, `release_ts`, `session`을 함께 사용해 blackout window를 계산한다.
- earnings event/date/timestamp/session 누락 또는 미인식 session은 `earnings_blackout_clear=false`로 fail-closed 처리하고 `data_quality_flags`에 원인을 남긴다.
- `MarketRepository.earnings_event_asof()`는 blackout용 event-calendar 조회라 예정 이벤트 lookahead를 허용하지만, fundamentals와 corporate action as-of 조회는 `effective_date/action_date <= trade_date`를 지킨다.
- `CorporateAction.effective_date`는 현재 DB column인 `action_date` alias이며, 별도 corporate action schema migration은 추가하지 않았다.
- CSV/external daily OHLCV preview는 `adj_close != close`인데 effective corporate action이 없으면 warning을 남기며, confirm 자체를 막지는 않는다.
- 별도 `weekly_ohlcv` table은 만들지 않는다. 현재 주봉 전략 요구사항은 daily OHLCV에서 as-of 파생해 `indicator_snapshot` nullable fields로 충족한다.

## 미구현 항목

- 실제 주문, 주문 취소, 체결, 계좌 자금 이동, websocket, live broker.
- KIS/broker paper order create, paper fill simulator, paper position mutation.
- KIS credential/token 저장, token 발급/refresh/cache, KIS 주문/실전 API 호출.
- KIS paper broker submit/cancel/sync network implementation.
- 실제 KRX/yfinance network fetch.
- 자동매매 scheduler, live broker adapter, AI prediction model.
- broker-synced portfolio cash/position state, cash lock, open_positions state machine, realized exposure/drawdown.
- attribution persistence, market_regime 저장 계약, sector as-of attribution contract.
- 저장된 parameter snapshot 기반 train-window 후보 선택과 OOS window persistence.
- walk-forward parameter optimization, multiple-testing 보정, 저장된 parameter snapshot 기반 후보 선택.

## 안전 제약사항

- broker/paper는 기본 deny, fail-closed, preview-only 정책을 유지한다.
- venue/session metadata는 preview 응답에만 노출하며 submit 가능 여부를 true로 바꾸지 않는다.
- `orders_count == 0`을 유지한다.
- 기본 config에서 `paper_orders`, `paper_fills`, `paper_positions`, `paper_audit_events` row count는 0을 유지한다. local `paper_orders`는 confirm/idempotency/kill-switch gate 통과 시에만 생성된다.
- `POST /api/paper/orders`, `POST /api/paper/fill-simulator/run`, `/api/kis/orders/*`, `/api/kis/broker/*`, `/api/kis/websocket/*`는 미등록 404 상태를 유지한다.
- KIS token cache 파일 `.cache/kis/token.json`은 생성하지 않는다.
- secret, token, account/header/raw credential 값을 코드, 문서, 로그, API 응답에 노출하지 않는다.

## KIS Paper Broker Phase 0 상태

- `docs/plans/phase-paper-broker-baseline-audit.md`와 `docs/KIS_PAPER_API_MATRIX.md`를 Phase 0 산출물로 추가했다.
- `README.md`, `docs/plans/README.md`, `docs/DB_MIGRATION.md`의 stale 기준선은 `docs/PROJECT_STATUS.md`와 `docs/VALIDATION.md` 기준으로 조정했다.
- 공식 문서에서 endpoint/path/TR-ID/request field가 완전 확인되지 않은 KIS paper capability는 `확인 필요`로 남겼다.
- Phase 1 Notification Foundation은 완료했다. 실제 Discord/Telegram delivery는 config/env opt-in이며 기본 runtime은 disabled/dry-run이다.
- Phase 2 KIS Paper Broker Contract는 완료했다. KIS paper/live adapter는 모두 fail-closed skeleton이며 endpoint/TR-ID/request field 추정 구현은 없다.
- Phase 3 Paper Trading Persistence는 완료했다. schema 변경은 additive-only이며 raw token/account/webhook/chat_id column을 만들지 않았다.
- Phase 4 Paper Order Preview/Submit/Cancel은 완료했다. local paper order submit/list만 추가됐고 KIS/live submit/cancel은 여전히 비활성이다.
- Phase 5 Fill/Position/Portfolio Sync는 완료했다. KIS sync endpoint는 공식 확인 전 disabled no-op이고, views는 paper_* tables만 조회한다.
- Phase 6 Report Notification은 완료했다. notification failure는 report row/markdown을 rollback하지 않고 sanitized delivery log로 기록한다.
- Phase 7 Bot Scheduler는 완료했다. scheduler/auto-submit은 기본 disabled이고 runner/API는 주문 없이 safe no-op을 반환한다.
- Phase 8 Frontend Integration은 완료했다. `/paper`, `/portfolio`, `/reports`, `/settings`는 `모의투자`, `실거래 아님`, `paper only`를 명시하고 backend safety API만 호출한다.
- Phase 9 Validation & Hardening은 완료했다. `tools/secret_scan.py`와 `backend/tests/test_secret_redaction.py`가 secret 원문과 민감 key-name 노출을 검증하며 CI에도 secret scan을 추가했다.

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
.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase2_api.py backend/tests/test_backtest.py -q
```

Latest validation framework scaffold result:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase2_api.py backend/tests/test_backtest.py -q
# 47 passed in 225.71s
.\.venv\Scripts\python.exe -m pytest backend/tests/test_alembic_migrations.py -q
# 2 passed in 3.79s
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

`goal.md` 기준 KIS paper broker phase는 완료됐다. 이후 작업은 공식 KIS paper endpoint/TR-ID/request field 확인 또는 운영 절차 고도화를 별도 승인 범위로 진행한다.
