# Stock Analyst Auto Trading

주식 분석, 스크리닝, 백테스트, 텔레그램 리포트, KIS 모의투자 자동매매봇을 단계적으로 구현하는 FastAPI + Next.js 프로젝트입니다.

현재 기준선은 `Project Reset: Telegram + KIS Paper Trading Bot`입니다. 기존 분석/스크리너/백테스트/리포트/포트폴리오 기능은 보존하고, 주문/체결/잔고/포지션 갱신은 KIS paper 모의투자 계좌에서만 허용합니다. 실계좌 live 자동매매, live fallback, secret 하드코딩은 계속 비활성화합니다.

상태 요약은 [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md), 단계 계획은 [docs/plans/README.md](docs/plans/README.md), 최신 검증 기록은 [docs/VALIDATION.md](docs/VALIDATION.md), DB migration 절차는 [docs/DB_MIGRATION.md](docs/DB_MIGRATION.md)를 기준으로 봅니다.

## Current Baseline

| 항목 | 값 |
|---|---|
| Version | `Project Reset` |
| Phase | `Telegram + KIS Paper Trading Bot skeleton` |
| Branch | `feature/kis-paper-goal-phases` (baseline: `main`) |
| Product state | 분석 엔진 + Telegram command/webhook/polling/report scheduler + KIS paper bot 전환 진행 |
| Trading state | `analysis_only`, `telegram_report`, `paper_kis`, `live_disabled` 실행 모드 분리 |
| Latest backend pytest | `.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider --basetemp $env:TEMP\stock_reset_full_after_sync_loop` -> `531 passed in 775.81s`; sync worker loop API `19 passed` |
| Latest secret scan | `.\.venv\Scripts\python.exe tools\secret_scan.py` -> `NO_SECRET_FINDINGS` |
| Latest frontend validation | `npm.cmd run lint`, `npm.cmd exec tsc -- --noEmit`, `npm.cmd run build` 통과 |
| Next recommended phase | KIS 포털/운영 문서 또는 paper host 기준 국내 정정취소가능/매도가능수량조회 paper TR ID 확인 |

## Execution Modes

| 모드 | 설명 |
|---|---|
| `analysis_only` | 로컬 DB 기반 분석, 스크리너, 백테스트, 리포트 |
| `telegram_report` | Telegram 명령과 daily/weekly 리포트 전송 |
| `paper_kis` | KIS 모의투자 API 기반 주문, 체결 동기화, 포지션 갱신 |
| `live_disabled` | 실계좌 live 주문/취소/체결 차단 |

## Telegram + KIS Paper Reset Surface

- `GET /api/stocks/search`, `GET /api/stocks/{symbol}`: KIS paper quote 우선, 실패/비활성 시 DB 최신 OHLCV fallback.
- `GET /api/telegram/status`, `POST /api/telegram/command`: `/start`, `/help`, `/status`, `/search`, `/report`, `/portfolio`, `/rank`, `/bot`, `/stop`, `/buy`, `/sell`, `/orders`, `/cancel`. `/report daily|weekly`와 `/report type=daily|weekly`는 해당 Markdown 리포트를 생성한 뒤 Telegram reply-safe 요약 메시지를 반환하고, `/cancel paper_order_id confirm`은 paper-only 주문 취소를 수행한다.
- `POST /api/telegram/webhook`: Telegram webhook update를 command dispatcher에 연결한다.
- `GET /api/telegram/polling/status`, `POST /api/telegram/polling/run-once`: Telegram `getUpdates` bounded polling runner다. 기본은 OFF이며 `confirm=true`, `TELEGRAM_BOT_ENABLED=true`, `TELEGRAM_POLLING_ENABLED=true`, token 설정이 모두 필요하다.
- `GET /api/telegram/scheduler/status`, `POST /api/telegram/scheduler/run-once`: 장 시작 전/장 종료 후/주간 report scheduler 구조를 제공한다. 기본은 OFF이며 `confirm=true`와 dry-run gate 뒤에서만 실행된다.
- `/buy`, `/sell`: `confirm` 또는 `TELEGRAM_PAPER_TRADE_CONFIRM=true` 없이는 preview만 수행. `/buy`는 `amount`/`notional` 금액 기반 수량 계산을 지원하고, `/sell 종목 all`은 현재 `paper_positions` 보유 수량을 전량 매도 수량으로 사용한다.
- `GET /api/paper/sync-worker/status`, `POST /api/paper/sync-worker/run-once`, `POST /api/paper/sync-worker/run-loop`: KIS paper 주문/체결/잔고 sync worker wrapper다. 기본은 OFF이며 `confirm=true`와 paper network gate를 통과해야 조회 동기화를 시도한다. loop는 `PAPER_SYNC_WORKER_MAX_ITERATIONS_CAP` 안에서만 bounded 실행된다.
- KIS token cache: `KIS_TOKEN_CACHE_ENABLED=true`일 때만 `.cache/kis/token.json`에 local cache 저장.
- Paper risk gate: `kill_switch`, `max_order_notional`, `max_order_qty`, `max_open_positions`, `blacklist`, `cooldown_seconds`, `idempotency_key`.
- Paper bot 자동매매: 기본 OFF(`enabled=false`, `auto_submit=false`, scheduler false). Telegram 또는 설정에서 명시적으로 켜야 동작.
- Paper bot runner: 자동 시작은 없고, loop는 `PAPER_BOT_MAX_ITERATIONS`, `PAPER_BOT_MAX_ITERATIONS_CAP`, `PAPER_BOT_STOP_FILE`로 제한된 bounded runner만 허용한다.
- Telegram `/bot status|enable|disable|auto|run|stop`: paper bot을 process env 기준으로 명시 제어한다. `enable`, `disable`, `auto`, `run`은 `confirm`이 필요하다.
- Settings runtime env 버튼: 개별 gate ON/OFF와 `모의 주문 준비`, `자동매매 ON`, `텔레그램 리포트 ON`, `봇/주문 정지` preset을 현재 backend 프로세스에 즉시 반영한다. 모든 버튼은 hover/focus 시 한국어 설명을 표시하고, `ENABLE_REAL_ORDER`는 클릭해도 `false`로 강제 적용한다.
- KIS paper API matrix: 공식 `koreainvestment/open-trading-api` sample commit `33e0e1e65cd1c8c8b639531483ec0b327087bab1` 기준 국내/해외 regular paper endpoint/TR ID와 현재 adapter 상수를 재확인했다. 국내 정정취소가능/매도가능수량조회는 샘플상 real `TTTC0084R`/`TTTC8408R` only라 paper 구현은 계속 보류한다.

## Implemented Scope

- Phase 1: FastAPI backend core MVP.
- Goal Read/Report Phase 1: `/api/market-realtime/*`, `/api/account/*`, `/api/trade-journal/*`와 frontend `/market` 화면으로 종목 상세 검색, 계좌/포트폴리오 리포트, 보유 종목 조회, 랭킹, 차트, CSV 매매일지를 local read-only surface로 제공한다.
- Phase 2: Next.js MVP web flow.
- Phase 3A: CSV data quality validation and preview-confirm import.
- Phase 3B: provider-neutral external daily OHLCV preview-confirm flow.
- Phase 3C: KIS read-only foundation.
- Phase 3D: broker safety scaffold.
- Phase 3E-1: paper trading safety shell.
- Phase 3F: read-only data reliability, provider contract, KRX fixture contract, data quality summary.
- Phase 3G: hardened backtest execution model, gap/stop realism, liquidity and partial-fill simulation.
- Phase 3H: strategy explanation contract, conservative optional filters, strategy registry.
- Phase C-1 to C-6: `momentum_rank`, `relative_strength_leader`, `new_high_breakout`, `darvas_box`, `stage_analysis_weekly`, `pullback_20ema`.
- Phase C Strategy Hardening Foundation: 9개 전략의 optional hardening 조건 기반, `data_quality_flags`, additive `risk_metadata`.
- Strategy validation summary: 최근 252 trading days 기준 strategy별 screener/backtest 요약과 baseline delta contract.
- Backtest integrity hardening: RR 목표가 의미, `rank_portfolio` realized-equity 회계, 평균 활성 포지션 range 집계 보강.
- Phase 3I Weekly Review Report: `POST /api/reports/weekly`, `report_type="weekly"` persistence, daily/weekly report filtering, ledger-backed realized metrics.
- Trade Ledger Foundation: `backtest_trade_ledger` table, `GET /api/backtest/runs/{run_id}/trades`, weekly realized PnL/win rate/failed trades review.
- Portfolio Risk Guard v2: `GET /api/portfolio/risk` additive gross/sector/symbol/strategy exposure, daily loss budget, gap risk preview.
- Venue-aware session preview layer: KRX/NXT session window service, `/api/market/session`, `/api/market/sessions`, `/api/market/calendar`, broker/paper preview `session_metadata`.
- Indicator incremental + breadth-aware regime: `/api/indicators/recompute`는 full recompute와 `symbol`, `start_date`, `end_date` 범위 recompute를 지원하고, `RegimeService`는 advance/decline, 52-week high/low, MA50 participation breadth proxy를 함께 반환한다.
- Data Reliability 2: earnings event timestamp/session 기반 blackout 판단, corporate action effective-date as-of 조회, adjusted/raw price 선택 계약을 보강했다.
- Validation Framework Scaffold: `StrategyValidationService`, `ValidationBaselineComparator`, `ValidationReportService`, walk-forward/PBO/Deflated Sharpe/factor attribution placeholder, minimal trade ledger schema metadata.
- Parameter Snapshot Foundation: strategy parameter snapshot 저장/조회/diff와 weekly `Parameter Drift Check`.
- Walk-forward Minimal OOS Summary: train/test/step trading-day window 기반 strategy별 OOS metric summary.
- PBO/DSR Minimal Overfitting Validation: 충분한 walk-forward 표본에서만 PBO/Deflated Sharpe Ratio 산출.
- Factor/Filter Attribution Minimal Integration: 저장된 `backtest_trade_ledger`와 `screen_results` join 기반 realized PnL attribution과 filter failure counts.
- KIS Paper Broker Phase 0 Baseline Audit: 현재 fail-closed baseline과 KIS paper API 확인 matrix 문서화.
- KIS Paper Broker Phase 1 Notification Foundation: disabled/mock 기본 notification abstraction, redacted status/test API, Discord/Telegram adapter skeleton.
- KIS Paper Broker Phase 2 KIS Paper Broker Contract: `BrokerAdapter` contract, disabled `KisPaperBrokerAdapter`, disabled `KisLiveBrokerAdapter`, in-memory-only `KisTokenManager`.
- KIS Paper Broker Phase 3 Paper Trading Persistence: additive paper table extension, portfolio snapshot, broker audit, notification outbox/delivery log, KIS token status metadata tables.
- KIS Paper Broker Phase 4 Paper Order Preview/Submit/Cancel: `POST /api/paper/orders/submit`, `POST /api/paper/orders/cancel`, `GET /api/paper/orders`, confirm/idempotency/kill-switch gated local paper order lifecycle.
- KIS Paper Broker Phase 5 Fill/Position/Portfolio Sync: `GET /api/paper/fills`, `GET /api/paper/positions`, `GET /api/paper/portfolio`, `POST /api/paper/sync`는 paper-only table을 사용하며, credentials/confirm/gate가 없으면 network 없이 차단된다.
- KIS Paper Broker Phase 6 Report Notification: `POST /api/reports/{report_id}/notify`, channel-safe summary splitting, optional attachment metadata, sanitized notification event/delivery logs.
- KIS Paper Broker Phase 7 Bot Scheduler: disabled-by-default paper bot config, safe once/loop runner, `/api/bot/status`, `/api/bot/run-once`, `/api/bot/stop`, launcher check integration without automatic scheduler start.
- KIS Paper Broker Phase 8 Frontend Integration: `/paper`, `/portfolio`, `/reports`, `/settings`에 `모의투자`, `실거래 아님`, `paper only` boundary를 표시하고 paper submit/history/snapshot/sync/report notify controls를 backend safety API로만 연결.
- KIS Paper Broker Phase 9 Validation & Hardening: `tools/secret_scan.py`, `backend/tests/test_secret_redaction.py`, CI secret scan, key-name redaction hardening, `docs/PAPER_TRADING_OPERATION.md`, full backend/frontend acceptance 검증.
- Goal.md Phase 10 Frontend Integration: `/bot` 화면, paper/notification API wrapper, `/paper` bot/kill-switch indicator, `/settings` notification dry-run test, `/reports` report notify action을 paper-only UI로 연결.
- Goal.md Phase 11 End-to-End Mock Validation: `backend/tests/test_e2e_paper_mock_flow.py`로 preview, local paper submit, order poll, mock fill/position/portfolio, notification outbox, report notify를 KIS credential 없이 검증.
- KIS Paper Balance Inquiry Read-only: `/api/paper/portfolio`에서 공식 `주식잔고조회[v1_국내주식-006]` paper TR `VTTC8434R`를 조건부 호출하고, disabled/mock 상태는 기존 local snapshot fallback 유지.
- Goal.md Phase 12B KIS Paper Network Adapter: `KisPaperBrokerAdapter`가 공식 paper endpoint/TR ID 기반 submit/cancel/daily order-fill/balance/sync를 mock HTTP client로 검증하며, `BROKER_MODE=paper_kis`, runtime flags, kill switch, idempotency, duplicate guard, risk cap, `ENABLE_REAL_ORDER=false` 조건 없이는 network submit을 차단한다.
- docs/goal.md Phase 5-6 KIS Paper Bot Executor/Dashboard: `PaperBotExecutor`, `/api/paper/bot/preview`, `/api/paper/bot/run`, `/api/paper/bot/runs/{run_id}`, `/api/paper/dashboard`, daily/weekly `Paper Trading` report section, paper operational metrics를 추가했다.
- Frontend strategy selector: backend default/available strategy metadata endpoint and screener/dashboard/backtest selector integration.
- Alembic migration scaffold: current SQLAlchemy model 기준 initial schema, weekly indicator migration, pullback EMA migration, screen metadata/pattern/earnings migrations, backtest trade ledger migration, indicator breadth fields migration, strategy parameter snapshot migration, paper trading persistence migration.

## Strategy Behavior

- Default strategy order: `trend_breakout`, `vcp_breakout`, `canslim_lite`, `new_high_breakout`, `pullback_20ema`.
- Available strategy order: default 5개 + `momentum_rank`, `relative_strength_leader`, `darvas_box`, `stage_analysis_weekly`.
- `GET /api/screener/strategies`는 `name`, `display_name`, `description`, `is_default`, `is_available`, `required_fields`, `limitations`를 반환합니다.
- `/screener`는 기본 전략 5개를 기본 선택하고, available-only 전략은 사용자가 체크한 경우에만 `POST /api/screener/run`의 `strategies`에 포함합니다.
- StrategyResult 기존 필드인 `strategy_tag`, `passed`, `pass_flags`, `failed_conditions`, `reason_summary`, `metadata`는 제거하지 않습니다.
- 신규 hardening 조건은 config-gated optional 방식입니다. 기본 enable flag는 false이며 기존 default 동작을 과도하게 바꾸지 않습니다.
- 신규 조건은 `metadata.data_quality_flags`에 사용 가능 여부를 남깁니다.
- `metadata.risk_metadata`는 `suggested_stop_price`, `risk_per_share`, `risk_basis`, `entry_chase_warning`을 additive로 제공합니다.
- Screener result 응답은 `triggered_conditions`, `score_breakdown`, `risk_flags`, `data_quality_flags`, `explanation`, `rationale`를 유지합니다.

신규 optional filters 요약:

| 전략 | 기본 off optional filters | 기본 on 또는 필수 의미 조건 |
|---|---|---|
| `trend_breakout` | sector RS, ATR risk | market regime, trend, 52주 고점, volume surge |
| `vcp_breakout` | sector RS, pivot distance limit, ATR risk | trend, contraction, dry-up, breakout, volume surge |
| `canslim_lite` | sector RS, earnings quality | technical trend, volume confirmation |
| `new_high_breakout` | common hardening 기반 sector RS, ATR risk | 52주 고점/근접 고점, breakout, volume surge |
| `pullback_20ema` | sector RS, near-high 52w, fundamentals quality | EMA20 touch/reclaim, ATR cap, market regime |
| `momentum_rank` | ATR risk, volume confirmation, breadth score | RS percentile, RS score, trend score, sector/market score |
| `relative_strength_leader` | market score, ATR risk, fundamentals quality | RS leadership, sector RS, near-high 52w, market regime |
| `darvas_box` | sector RS, ATR risk | box range, close above box, risk per share, long trend |
| `stage_analysis_weekly` | sector RS, market score, fundamentals quality, breadth score | weekly close/SMA30/slope availability, Stage 2 trend, market regime |

## Strategy Config

공통 hardening key는 `backend/config/strategies.yaml`의 `common.hardening`에서 관리합니다.

```yaml
common:
  hardening:
    risk_metadata_enabled: true
    market_regime_not_bear_enabled: false
    sector_rs_score_min_enabled: false
    market_score_min_enabled: false
    atr20_pct_max_enabled: false
    volume_ratio_50_min_enabled: false
    near_high_52w_threshold_enabled: false
    breadth_score_filter_enabled: false
    breadth_advance_decline_filter_enabled: false
    breadth_52w_high_low_filter_enabled: false
    breadth_ma50_participation_filter_enabled: false
    optional_fundamental_quality_enabled: false
    optional_earnings_quality_enabled: false
```

전략별 핵심 설정은 같은 파일의 각 strategy key에서 관리합니다.

## Indicators And Regime

- `IndicatorService.recompute()`는 기본 전체 재계산을 유지하면서 `symbol`, `start_date`, `end_date`를 받는 증분 경로를 제공합니다.
- 증분 경로는 요청 시작일보다 앞선 warm-up 윈도우를 읽어 rolling/weekly/RS 파생값을 계산하고, snapshot 쓰기 전 요청된 symbol/date 범위만 삭제 후 재삽입합니다.
- 주봉 파생값은 기존 `indicator_snapshot` nullable fields 패턴을 유지하며 helper로 분리했습니다. 별도 `weekly_ohlcv` 물리 테이블은 만들지 않았습니다. 현재 필요한 값은 daily OHLCV에서 as-of로 재계산 가능하고, 저장 계약을 늘리면 migration/운영 부담이 커지기 때문입니다.
- breadth proxy는 `indicator_snapshot`에 날짜별 동일 값으로 저장합니다: `breadth_advance_decline_ratio`, `breadth_52w_high_low_ratio`, `breadth_ma50_participation`, `breadth_score`.
- `RegimeService`는 기존 index/weekly 조건에 breadth 진단을 더합니다. breadth가 약하면 bull 판정을 neutral로 낮추고, breadth 입력이 없으면 `breadth_regime="not_available"` 및 availability flag false로 처리합니다.
- `momentum_rank`, `stage_analysis_weekly`는 breadth hardening을 optional config flag가 켜진 경우에만 적용합니다. 데이터가 없고 filter가 켜져 있으면 fail-closed로 탈락합니다.

## Data Reliability Rules

| 영역 | 규약 |
|---|---|
| Earnings event | `earnings_events.earnings_date`, `release_ts`, `session`을 함께 사용한다. CANSLIM Lite는 `release_ts.date()` 기준 blackout window를 계산하고, event/date/timestamp/session이 없거나 session이 미인식이면 `earnings_blackout_clear=false`로 fail-closed 처리한다. |
| Earnings lookup | `MarketRepository.earnings_event_asof()`는 blackout 판단용 event-calendar 조회다. 예정 이벤트도 위험 요인이므로 lookahead window를 허용하지만, timestamp/session 품질 판단은 strategy metadata와 `data_quality_flags`에 남긴다. |
| Corporate action effective-date | 현재 DB의 `corporate_actions.action_date`를 effective-date로 해석한다. `MarketRepository.corporate_actions_asof()`는 항상 `action_date <= trade_date` row만 반환하며 future action은 조정가 계산에 사용하지 않는다. |
| Adjusted/raw price | daily import는 raw OHLCV와 `adj_close`를 저장할 뿐 가격 선택을 결정하지 않는다. Backtest execution의 `use_adjusted_price=true`일 때도 해당 bar의 `trade_date`까지 유효한 corporate action이 있어야 `adj_close / close` factor를 적용한다. 조건이 없으면 raw OHLC로 실행하고 `price_detail`에 사유를 남긴다. |
| Import warning | CSV/external daily OHLCV preview에서 `adj_close != close`인데 effective corporate action이 없으면 `ADJUSTED_CLOSE_WITHOUT_EFFECTIVE_CORPORATE_ACTION` warning을 남긴다. 이는 preview 품질 신호이며 confirm 자체를 막는 error는 아니다. |
| Weekly OHLCV | 별도 `weekly_ohlcv` migration은 추가하지 않는다. 현재 전략이 필요한 주봉 파생값은 daily OHLCV에서 as-of로 계산해 `indicator_snapshot` nullable fields와 availability flags에 저장한다. |
| Fixture scope | KRX corporate action fixture는 schema/normalize contract와 as-of 규칙을 검증한다. 실제 KIS/KRX/yfinance network fetch, live corporate action loader, earnings calendar 실데이터 연동은 구현하지 않는다. |

## Strategy Validation Summary

`GET /api/backtest/strategy-summary?lookback_days=252`는 strategy별 validation summary를 반환합니다.

| 항목 | 내용 |
|---|---|
| Screener | 최근 available `screen_results.trade_date` 기준 `pass_rate`, `pass_count`, `evaluated_count` |
| Backtest | 최근 available `indicator_snapshot.trade_date` 기준 `trade_count`, `win_rate`, `total_return`, `max_drawdown` |
| Baseline | `baseline_run_id` 또는 JSON `baseline_snapshot`이 없으면 `baseline.status="unspecified"`, delta는 `null` |
| Artifact | `backend/reports/strategy_validation_252d.json` |

기존 `/api/backtest/run`, `/api/backtest/runs`, `/api/backtest/runs/{run_id}` contract는 변경하지 않습니다.

## Reports

`ReportService`는 daily와 weekly Markdown report를 같은 저장 계약으로 관리합니다. 두 report 모두 `reports` 테이블, `backend/reports/*.md`, `GET /api/reports/{report_id}`, `GET /api/reports/{report_id}/markdown`을 재사용합니다.

| 구분 | 생성 API | `report_type` | 목적 | 계산 기준 |
|---|---|---|---|---|
| Daily Market Report | `POST /api/reports/daily` | `daily` | 당일 screener 결과, market regime, sector rotation, mock order review | `screen_results.trade_date` 단일 기준일 |
| Weekly Strategy Review | `POST /api/reports/weekly` | `weekly` | 주간 성과/리스크 리뷰, setup별 screening/trade hit rate, regime/filter diagnostics | 최근 available `screen_results.trade_date` 최대 5개 + `backtest_trade_ledger.exit_date` |

목록 API는 기존 계약을 유지하면서 유형 필터를 추가로 지원합니다.

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/reports?report_type=daily&limit=20"
Invoke-RestMethod "http://127.0.0.1:8000/api/reports?report_type=weekly&limit=20"
```

Weekly review는 `backtest_trade_ledger`가 있으면 `realized_trade_count`, `realized_pnl`, `realized_return`, `win_rate`, `average_holding_days`, setup별 trade hit rate, failed trades review를 계산합니다. ledger가 없거나 현재 MVP에 데이터 계약이 없는 항목은 거짓 수치로 채우지 않고 `not_available_in_current_mvp`로 표기합니다.

| 항목 | 사유 |
|---|---|
| `realized_drawdown`, `realized_exposure`, `open_position_risk` | portfolio state와 position ledger 미구현 |
| `regime_segment_return`, realized factor/filter PnL attribution | regime/factor별 성과 연결 계약 미구현 |
| `max_adverse_excursion_review` | MAE/MFE 경로별 adverse excursion 저장 계약 미구현 |
| `parameter_snapshot_diff`, `drifted_parameters` | historical strategy parameter snapshot 미저장 |

## Portfolio Risk Guard v2

`GET /api/portfolio/risk`는 기존 Phase 2 응답 필드를 제거하지 않고, 현재 `positions`와 최신 통과 `screen_results`를 함께 읽어 노출 구조를 additive로 반환합니다. 핵심 원칙은 포지션 개수보다 총 노출, 섹터, 종목, 전략별 집중도를 먼저 보는 것입니다.

| 항목 | 계산 기준 |
|---|---|
| `max_open_positions` | `backend/config/risk.yaml`의 `portfolio.max_open_positions` |
| `gross_exposure`, `combined_gross_exposure` | 현재 position notional, 현재+제안 notional |
| `sector_exposure`, `symbol_exposure`, `strategy_exposure` | current/proposed/combined bucket별 notional, equity 대비 비중, symbol 목록 |
| `daily_loss_budget` | `equity * max_daily_loss_fraction`, 현재/제안 open risk 차감 후 잔여 예산 |
| `gap_risk_estimate` | configured adverse gap fraction을 notional에 적용한 preview 추정치 |
| `concentration_warnings` | symbol/sector/strategy 한도와 `max_open_positions` 초과 경고 |

현재 summary는 synthetic/preview 성격입니다. `positions` 테이블은 실제 broker position sync가 아니며, `screen_results`는 주문 의사가 아니라 조건검색 통과 후보입니다. 따라서 실제 trade ledger 기반 계산처럼 체결가, 부분체결, 현금 잠금, 실현/미실현 PnL, 포지션 상태 전이를 완전히 반영하지 않습니다. 데이터가 부족한 gap risk는 거짓 0으로 채우지 않고 `not_available` 또는 warning으로 남깁니다.

아직 구현하지 않은 항목은 broker position sync, paper/live position mutation, cash lock, open position state machine, realized exposure/drawdown, MAE/MFE, 실제 event risk hold입니다. 이 기능은 `orders`, `paper_orders`, broker/KIS route와 연결되지 않으며 preview-only 안전 경계를 유지합니다.

## Venue-Aware Execution Assumptions

`MarketSessionService`는 KRX와 NXT를 단일 한국 주식 세션으로 보지 않고 venue별 세션 window를 로컬 정적 규칙으로 판정합니다. 이 계층은 future order preview와 paper simulator가 같은 기준을 재사용하도록 만든 운영 메타데이터 계층이며, 실제 주문, token 발급, 호출량 차감, websocket 연결은 수행하지 않습니다.

| Venue | 세션 | 주문 접수 | 거래 시간 | 현재 처리 |
|---|---|---|---|---|
| KRX | `pre_hours` | 07:30-09:00 | 07:30-09:00 | preview metadata only |
| KRX | `regular` | 08:00-15:30 | 09:00-15:30 | preview metadata only |
| KRX | `after_hours` | 15:30-18:00 | 15:40-18:00 | preview metadata only |
| NXT | `pre_market` | 08:00-08:50 | 08:00-08:50 | preview metadata only |
| NXT | `main` | 09:00:30-15:20 | 09:00:30-15:20 | preview metadata only |
| NXT | `after_market` | 15:30-20:00 | 15:40-20:00 | preview metadata only |

단일 `next_open` 또는 단일 정규장 가정만으로는 부족합니다. KRX와 NXT는 세션 이름, 주문 접수 시작, 실제 거래 시작, 마감 시간이 다르고, NXT는 KRX 정규장 전후로 더 긴 pre/after market을 제공합니다. 따라서 future order engine은 venue, session, 현재 세션 허용 여부, 다음 order window, token lifecycle, 호출량 예산을 하나의 운영 계층에서 함께 확인해야 합니다.

현재 구현은 `session_metadata`를 `/api/broker/orders/preview`와 `/api/paper/orders/preview`에 additive로 노출할 뿐입니다. `operational_layer.live_submit_allowed=false`, `paper_submit_allowed=false`, `network_call_allowed=false`, `token_issued=false`를 유지하며, broker/paper preview는 계속 deny/fail-closed입니다.

## Backtest Trade Ledger

저장형 backtest run은 closed trade 전체를 `backtest_trade_ledger`에 저장합니다. 이 ledger는 backtest/report 분석용 산출물이며 실제 주문, paper order, broker adapter와 연결되지 않습니다.

| 계약 | 내용 |
|---|---|
| 생성 | `POST /api/backtest/run`에서 `save=True` 기본값일 때 `backtest_runs`와 함께 저장 |
| 식별 | `run_id + trade_index` unique |
| 핵심 필드 | `strategy_name`, `symbol`, `signal_date`, `entry_date`, `exit_date`, `qty`, `entry_price`, `exit_price`, `pnl`, `return_pct`, `exit_reason` |
| 상세 JSON | `execution_detail_json`, `liquidity_detail_json`, `price_detail_json`, `portfolio_detail_json` |
| 조회 | `GET /api/backtest/runs/{run_id}`의 `trades`, `GET /api/backtest/runs/{run_id}/trades` |
| 안전 경계 | `orders`, `paper_orders`, broker/KIS route를 생성하거나 호출하지 않음 |

## Backtest Accounting Rules

- `RiskService.calculate()`는 명시적 `suggested_target_price`/`target_price` 계열 값이 있으면 해당 목표가로 `reward_risk_ratio`를 계산한다.
- `rr_score`는 `actual_reward_risk_ratio / configured_target_rr`를 1.0으로 clamp한 값이다.
- `rr_ok`는 `actual_reward_risk_ratio >= configured_target_rr`일 때만 true이며, 정상 trade라도 목표가가 낮으면 false가 될 수 있다.
- `rank_portfolio`는 각 `signal_date` 시작 시 `exit_date <= signal_date`인 trade PnL만 realized equity에 반영한다.
- 같은 `rebalance_date`의 선택 종목은 모두 동일한 rebalance equity snapshot으로 sizing하며, future PnL은 exit_date 전 sizing에 반영하지 않는다.
- `average_active_positions`는 `entry_date..exit_date` inclusive holding range를 sweep-line 방식으로 집계한다.

## Main APIs

| Method | Path | 목적 |
|---|---|---|
| `GET` | `/api/data/status` | 데이터 row count와 최신 기준일 |
| `GET` | `/api/data/sources` | data source 목록 |
| `POST` | `/api/data/validate-csv` | CSV validation preview |
| `POST` | `/api/data/import-csv-confirmed` | validated CSV run confirm |
| `GET` | `/api/data/external/providers` | external-capable provider source 목록 |
| `POST` | `/api/data/external/preview-daily-ohlcv` | external daily OHLCV preview |
| `POST` | `/api/data/external/confirm-import` | external run confirm |
| `GET` | `/api/data/read-only/providers` | KIS/KRX read-only provider contract |
| `GET` | `/api/data/quality-summary` | data freshness/quality/safety summary |
| `GET` | `/api/kis/status` | KIS read-only status |
| `GET` | `/api/kis/config` | KIS redacted config |
| `POST` | `/api/kis/config/validate` | KIS env configured boolean 검증 |
| `GET` | `/api/market/session` | venue/as_of 기준 현재 세션과 다음 window |
| `GET` | `/api/market/sessions` | venue별 session window 목록 |
| `GET` | `/api/market/calendar` | 정적 거래일 calendar preview |
| `GET` | `/api/market-realtime/search` | local symbol master 기반 종목 검색 |
| `GET` | `/api/market-realtime/symbols/{symbol}` | 종목 master, 최신 OHLCV quote, 지표, screener, 재무 as-of 상세 |
| `GET` | `/api/market-realtime/symbols/{symbol}/chart` | frontend chart용 OHLCV/이동평균 series |
| `GET` | `/api/market-realtime/rankings` | screener score 또는 OHLCV 기반 랭킹 |
| `GET` | `/api/account/summary`, `/api/account/holdings`, `/api/account/report` | paper table 기반 계좌/보유/포트폴리오 리포트 조회 |
| `GET` | `/api/trade-journal/entries`, `/api/trade-journal/csv` | backtest ledger와 paper fill/order 기반 매매일지 조회/CSV export |
| `GET` | `/api/broker/status` | broker safety status |
| `POST` | `/api/broker/orders/preview` | venue/session metadata 포함 dry-run preview only |
| `GET` | `/api/paper/status` | paper_kis safety status |
| `POST` | `/api/paper/orders/preview` | venue/session metadata 포함 paper deny preview only |
| `POST` | `/api/paper/orders/submit`, `/api/paper/orders` | local/KIS paper submit alias, `KIS_ENV=paper`, `PAPER_TRADING_ENABLED=true`, `PAPER_BOT_CONFIRM=true`, `confirm=true`, idempotency, kill-switch off 필요 |
| `POST` | `/api/paper/orders/cancel`, `/api/paper/orders/{order_id}/cancel` | local paper order는 confirm/idempotency gate 뒤 취소, KIS broker order cancel은 KIS paper network gate 필요 |
| `GET` | `/api/paper/orders`, `/api/paper/orders/open`, `/api/paper/orders/{order_id}`, `/api/paper/fills`, `/api/paper/positions`, `/api/paper/portfolio`, `/api/paper/account` | paper_* table 전용 조회, `/api/paper/portfolio`는 KIS paper balance 조건부 read-only 호출 후 local fallback |
| `POST` | `/api/paper/fill-simulator/run` | simulator gate와 confirm/idempotency 통과 시 local paper fill 생성 및 `paper_positions` 갱신 |
| `POST` | `/api/paper/risk/exit-check` | stop-loss/trailing-stop/이동평균 하향 교차 trigger 시 local sell order/fill 생성 및 position 감소 |
| `POST` | `/api/paper/sync` | KIS paper sync gate 통과 시만 조회 동기화, 기본은 credentials/gate 미충족으로 no-network block |
| `GET` | `/api/paper/sync-worker/status` | KIS paper sync worker 상태, 기본 OFF/auto-start false |
| `POST` | `/api/paper/sync-worker/run-once` | `PAPER_SYNC_WORKER_ENABLED=true`와 `confirm=true` 뒤에서 paper sync 1회 실행 |
| `POST` | `/api/paper/sync-worker/run-loop` | `confirm=true` 뒤에서 bounded sync loop 실행. `PAPER_SYNC_WORKER_MAX_ITERATIONS_CAP` 초과 반복은 잘라냄 |
| `GET` | `/api/paper/realtime/status` | polling quote cache/heartbeat/stale quote gate 상태 |
| `GET` | `/api/paper/dashboard` | account, positions, open orders, fills, PnL, risk, worker status, metrics |
| `POST` | `/api/paper/bot/preview` | screener 결과 또는 `watchlist_symbols` 기반 dry-run bot candidate/risk gate preview, paper order 생성 없음 |
| `POST` | `/api/paper/bot/run` | screener/watchlist 후보에서 `dry_run=false`와 모든 paper gate 통과 시에만 paper submit 시도 |
| `GET` | `/api/paper/bot/runs/{run_id}` | 저장된 bot run/decision, submitted/skipped/rejected reason code 조회 |
| `GET` | `/api/bot/status` | paper-only bot runtime status, kill-switch/session/auto-submit gate 표시 |
| `POST` | `/api/bot/run-once` | paper-only preview decision loop, auto-submit은 명시 opt-in과 backend gate 통과 시에만 허용 |
| `POST` | `/api/bot/stop` | paper-only scheduler stop marker, live/order side effect 없음 |
| `GET` | `/api/telegram/polling/status` | Telegram getUpdates polling 상태, 기본 OFF/auto-start false |
| `POST` | `/api/telegram/polling/run-once` | confirm-gated getUpdates 1회 조회, command dispatch, 선택적 reply send |
| `GET` | `/api/telegram/scheduler/status` | Telegram report scheduler 상태, 기본 OFF/auto-start false |
| `POST` | `/api/telegram/scheduler/run-once` | confirm 뒤 daily/weekly report 생성 및 Telegram summary dry-run/send |
| `POST` | `/api/telegram/webhook` | Telegram webhook update를 command dispatcher로 연결 |
| `GET` | `/api/settings/runtime-env` | process-only runtime gate와 Settings preset 목록, secret redacted |
| `POST` | `/api/settings/runtime-env/toggle` | allowlist boolean env gate 1개를 현재 backend 프로세스에 반영 |
| `POST` | `/api/settings/runtime-env/preset` | paper_kis/Telegram/paper bot gate 묶음을 현재 backend 프로세스에 일괄 반영, live lock은 false 유지 |
| `POST` | `/api/screener/run` | rule-based screener run |
| `GET` | `/api/screener/strategies` | frontend strategy selector metadata |
| `GET` | `/api/screener/results` | screener result list with explanation contract |
| `GET` | `/api/portfolio/risk` | Portfolio Risk Guard v2 synthetic exposure summary |
| `POST` | `/api/backtest/run` | strategy backtest run |
| `GET` | `/api/backtest/strategy-summary` | 최근 252 trading days strategy validation summary |
| `GET` | `/api/backtest/runs` | backtest run 목록 |
| `GET` | `/api/backtest/runs/{run_id}` | backtest run 상세 |
| `GET` | `/api/backtest/runs/{run_id}/trades` | 저장된 backtest trade ledger |
| `POST` | `/api/reports/daily` | daily market report 생성 |
| `POST` | `/api/reports/weekly` | weekly strategy review 생성 |
| `GET` | `/api/reports?report_type=daily` 또는 `/api/reports?report_type=weekly` | report 목록과 유형 필터 |
| `GET` | `/api/reports/{report_id}/markdown` | daily/weekly Markdown 다운로드 |

## Single PC Launcher

Windows 단일 PC 실행은 기존 FastAPI backend와 Next.js frontend 구조를 유지한 채 launcher가 두 프로세스를 함께 관리한다.

```powershell
py launcher.py check
py launcher.py setup
py launcher.py run
```

더블클릭 실행은 프로젝트 루트의 `start_stock_analyst.cmd`를 사용한다. 실행이 완료되면 `http://127.0.0.1:3000/dashboard`가 기본 화면이며, backend는 `http://127.0.0.1:8000`에서 동작한다.

종료:

```powershell
py launcher.py stop
```

주의 사항:

- launcher는 기본 포트 `8000`과 `3000`만 사용한다.
- 해당 포트가 launcher가 띄운 프로세스가 아닌 다른 프로세스에 의해 점유되어 있으면 stale server 위험 때문에 실행을 중단한다.
- `setup`은 `.env.local`을 수정하지 않고 `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000` 환경 변수로 Next.js production build를 수행한다.
- 실주문, 실계좌 체결, live broker/order route는 추가하지 않는다. local paper fill/position mutation은 simulator gate와 confirm/idempotency 조건에서만 허용한다.

## Run Locally

Backend:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm.cmd install
npm.cmd run build
npm.cmd run start -- --hostname 127.0.0.1 --port 3000
```

backend 포트가 `8001` 등으로 바뀌면 `frontend/.env.local`의 `NEXT_PUBLIC_API_BASE_URL`을 맞춘 뒤 다시 build/start 해야 합니다.

## Verification Commands

Launcher:

```powershell
py launcher.py check
py launcher.py setup
.\.venv\Scripts\python.exe -m pytest backend/tests/test_local_launcher.py -q
py launcher.py run --no-browser
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/data/status
Invoke-WebRequest http://127.0.0.1:3000/dashboard -UseBasicParsing
py launcher.py stop
```

Backtest integrity targeted suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_risk.py backend/tests/test_backtest.py backend/tests/test_phase3g_backtest_execution_model.py -q
```

Backend full suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

Secret scan:

```powershell
.\.venv\Scripts\python.exe tools\secret_scan.py
```

Strategy hardening targeted suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_strategies.py -q
```

Strategy validation summary targeted suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_phase2_api.py -q
```

Diff check:

```powershell
git diff --check
```

Frontend:

```powershell
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
```

## Safety Invariants

- `orders_count == 0` 유지.
- 기본 config에서는 실계좌 live 주문/취소/체결이 계속 0건이다. `paper_orders`는 confirm/idempotency/risk/quote/KIS paper gate를 통과한 경우, `paper_fills`/`paper_positions`는 simulator/sync gate를 통과한 경우에만 증가한다.
- `/api/broker/status`는 `live_trading_enabled=false`, `token_issued=false`, `network_call_performed=false`를 반환하고, paper adapter는 credentials 미충족 시 `can_submit=false`다.
- `/api/broker/orders/preview`는 실제 주문, token 발급, network call, adapter order call 없이 deny preview만 반환하며, `session_metadata`는 additive metadata다.
- `/api/paper/status`는 `paper_kis` runtime/config gate를 반영하되 live submit과 live fallback은 계속 false로 유지한다.
- `/api/paper/orders/preview`는 paper order/fill/position/audit mutation 없이 preview만 반환한다. `/api/paper/orders/submit`은 backend confirm/idempotency/kill-switch gate 없이는 생성하지 않는다.
- `/api/paper/fill-simulator/run`과 `/api/paper/risk/exit-check`는 `can_simulate_fills`, simulator enabled, confirm, idempotency, kill-switch, no-live gate 없이는 fill/position을 생성하지 않는다.
- KRX/NXT session window 판정은 로컬 정적 metadata이며 실제 거래소, KIS token, 호출량 API와 통신하지 않는다.
- `/api/live/status`, `/api/kis/orders/*` route는 disabled scaffold로만 등록되어 `live_order_created=false`, `network_call_performed=false`를 유지한다.
- `/api/kis/broker/*`, `/api/kis/websocket/*` route는 미등록 404 상태를 유지.
- `.cache/kis/token.json`은 `KIS_TOKEN_CACHE_ENABLED=true`에서만 생성되며 Git에는 포함하지 않음.
- API key, secret, token, password, account/header/raw credential 값을 저장하거나 출력하지 않음.

## Not Implemented

- 실계좌 실제 주문, 주문 취소, 체결, 계좌 자금 이동, live broker.
- live broker order create, live fill, live position mutation.
- Telegram 장시간 상주 운영 scheduler auto-start. Polling/webhook run-once 구조는 구현됨.
- KRX/yfinance 실제 network fetch.
- 완전 자동매매 운영 loop, live broker adapter, AI prediction model.
- portfolio cash/position state, walk-forward validation.

## CI

GitHub Actions workflow는 `.github/workflows/ci.yml`에 정의합니다.

- backend job: Python 3.12, `requirements.txt` 설치, `python -m pytest backend/tests`.
- frontend job: Node 22, `npm ci`, lint, typecheck, build.
- CI는 KIS credential/token secret을 요구하지 않으며 실제 외부 API 호출 없이 fail-closed 테스트만 실행합니다.
