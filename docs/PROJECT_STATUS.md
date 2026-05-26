# Project Status

## 현재 기준

| 항목 | 값 |
|---|---|
| Version | `MVP v0.16.4` |
| Phase | `Strategy Validation 252d Summary` |
| Branch | `main` |
| 상태 | 분석/스크리닝/백테스트/리포트 중심 자동매매 보조 MVP |
| 거래 상태 | 실거래 미구현, fail-closed, preview-only |
| 다음 권장 Phase | `Phase 3I Weekly Review Report` |

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
- Frontend strategy selector: `/api/screener/strategies` metadata와 `/screener`, `/dashboard`, `/backtest` selector 연동.
- GitHub Actions CI: backend pytest, frontend lint/typecheck/build.
- Alembic migration scaffold: initial schema, weekly indicator fields, pullback EMA fields, screen metadata JSON, pattern engine fields, earnings event table.

## BacktestService 상태

- `metrics.cost_bps`는 `backend/config/backtest.yaml`의 `execution.commission_bps + execution.slippage_bps` 합산값을 반영한다.
- trade-level `cost_bps`와 metrics-level `cost_bps`는 동일 execution 설정값을 사용한다.
- `run()`은 시작 시 `index_df` 기반 market regime cache를 1회 생성하고 signal date별로 조회한다.
- 기존 `/api/backtest/run`, `/api/backtest/runs`, `/api/backtest/runs/{run_id}` 응답 key는 제거하지 않는다.
- `/api/backtest/strategy-summary`는 최근 available trading window 기준 strategy별 screener pass rate와 backtest metric subset을 additive로 제공한다.
- summary endpoint는 저장형 `backtest_runs` row를 만들지 않고 JSON report artifact만 갱신한다.
- Metrics에는 `annualized_volatility`, `sharpe_ratio`, `sortino_ratio`, `calmar_ratio`, `turnover`, `regime_segment_return`을 additive로 제공한다.
- `regime_segment_return`은 현재 MVP 데이터/portfolio-state 부족으로 `not_available_in_current_mvp`를 반환한다.
- portfolio-state backtest, cash lock, open_positions 상태머신, walk-forward/PBO/Deflated Sharpe 계산은 구현하지 않았다.

## Phase C 전략 상태

- 기본 screener 전략은 `trend_breakout`, `vcp_breakout`, `canslim_lite`, `new_high_breakout`, `pullback_20ema` 5개다.
- available strategy는 기본 5개에 `momentum_rank`, `relative_strength_leader`, `darvas_box`, `stage_analysis_weekly` 4개를 더한 9개다.
- `/api/screener/strategies`는 frontend selector에 필요한 `name`, `display_name`, `description`, `is_default`, `is_available`, `required_fields`, `limitations`를 제공한다.
- `/screener`는 기본 전략 5개를 기본 선택하고, available-only 전략은 사용자가 명시 체크한 경우에만 실행 요청에 포함한다.
- `/dashboard`와 `/backtest`의 단일 전략 실행 UI는 backend metadata를 사용한다.
- `IndicatorService`는 EMA20, weekly fields, ATR, volume ratio, 52주 고점, pivot, RS/sector/market score를 `indicator_snapshot`에 저장한다.
- 최신 Alembic head는 `d9e3f0a1b2c4_add_earnings_events`다.
- Screener 응답은 기존 explanation contract 필드를 제거하지 않는다.

## Phase C Hardening Foundation

- `backend/config/strategies.yaml`의 `common.hardening`은 신규 조건 enable flag와 threshold를 관리한다.
- 기본 신규 조건 enable flag는 false다.
- 신규 조건 후보는 `market_regime_not_bear`, `sector_rs_score_min`, `market_score_min`, `atr20_pct_max`, `volume_ratio_50_min`, `near_high_52w_threshold`, `optional_fundamental_quality`, `optional_earnings_quality`다.
- `canslim_lite`는 `earnings_blackout_days`, `require_recent_new_high`, `require_institutional_proxy`를 strategy metadata에 남긴다.
- `new_high_breakout`은 `breakout_buffer_pct`와 `require_breakout_day_volume_ratio`를 분리 평가하고 `breakout_context` metadata를 남긴다.
- `pullback_20ema`는 `max_pullback_count`와 `require_volume_dry_up_vs_ma20` 기준으로 first/second pullback 및 volume dry-up context를 평가한다.
- 신규 조건은 `pass_flags`와 `failed_conditions`에 additive로만 추가한다.
- 신규 조건의 사용 가능 여부는 `metadata.data_quality_flags`에 남긴다.
- `metadata.risk_metadata`는 `suggested_stop_price`, `risk_per_share`, `risk_basis`, `entry_chase_warning`을 additive로 제공한다.
- strategy registry order, `DEFAULT_STRATEGY_NAMES`, `AVAILABLE_STRATEGY_NAMES`, `StrategyResult` 기존 필드는 변경하지 않는다.
- 2026-05-26 strategy validation summary 기준 `test_backtest.py` + `test_phase2_api.py` targeted suite 34 passed, full backend suite 252 passed, frontend lint/typecheck/build 통과를 확인했다.

## 미구현 항목

- 실제 주문, 주문 취소, 체결, 계좌, 잔고, websocket, live broker.
- paper order create, paper fill simulator, paper position mutation.
- KIS credential/token 저장, token 발급/refresh/cache, 실제 KIS API 호출.
- 실제 KRX/yfinance network fetch.
- 자동매매 scheduler, live broker adapter, AI prediction model.
- portfolio cash/position state, cash lock, open_positions state machine, walk-forward/PBO/Deflated Sharpe validation.

## 안전 제약사항

- broker/paper는 기본 deny, fail-closed, preview-only 정책을 유지한다.
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

Strategy validation summary:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_phase2_api.py -q
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

Phase 3I에서 weekly review report를 검토한다. 기존 API, safety contract, no real-order 정책은 유지하고 fixture 기반 검증을 우선한다.
