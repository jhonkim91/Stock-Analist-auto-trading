# Stock Analyst Auto Trading

주식 분석, 스크리닝, 백테스트, 리포트 생성을 검증 가능한 MVP 형태로 구현한 FastAPI + Next.js 프로젝트입니다.

현재 기준선은 `Strategy Validation 252d Summary`입니다. 이 저장소는 실거래 자동매매 엔진이 아니라 자동매매 보조 MVP이며, 실주문, 주문 취소, 체결, 계좌, 잔고, websocket, live broker, KIS credential/token 저장, 실제 KIS/KRX/yfinance 호출은 구현하지 않습니다.

상태 요약은 [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md), 단계 계획은 [docs/plans/README.md](docs/plans/README.md), 최신 검증 기록은 [docs/VALIDATION.md](docs/VALIDATION.md), DB migration 절차는 [docs/DB_MIGRATION.md](docs/DB_MIGRATION.md)를 기준으로 봅니다.

## Current Baseline

| 항목 | 값 |
|---|---|
| Version | `MVP v0.16.4` |
| Phase | `Strategy Validation 252d Summary` |
| Branch | `main` |
| Product state | 분석/스크리닝/백테스트/리포트 중심 자동매매 보조 MVP |
| Trading state | fail-closed, preview-only, real order 미구현 |
| Next recommended phase | `Phase 3I Weekly Review Report` |

## Implemented Scope

- Phase 1: FastAPI backend core MVP.
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
- Frontend strategy selector: backend default/available strategy metadata endpoint and screener/dashboard/backtest selector integration.
- Alembic migration scaffold: current SQLAlchemy model 기준 initial schema, weekly indicator migration, pullback EMA migration.

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
| `momentum_rank` | ATR risk, volume confirmation | RS percentile, RS score, trend score, sector/market score |
| `relative_strength_leader` | market score, ATR risk, fundamentals quality | RS leadership, sector RS, near-high 52w, market regime |
| `darvas_box` | sector RS, ATR risk | box range, close above box, risk per share, long trend |
| `stage_analysis_weekly` | sector RS, market score, fundamentals quality | weekly close/SMA30/slope availability, Stage 2 trend, market regime |

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
    optional_fundamental_quality_enabled: false
    optional_earnings_quality_enabled: false
```

전략별 핵심 설정은 같은 파일의 각 strategy key에서 관리합니다.

## Strategy Validation Summary

`GET /api/backtest/strategy-summary?lookback_days=252`는 strategy별 validation summary를 반환합니다.

| 항목 | 내용 |
|---|---|
| Screener | 최근 available `screen_results.trade_date` 기준 `pass_rate`, `pass_count`, `evaluated_count` |
| Backtest | 최근 available `indicator_snapshot.trade_date` 기준 `trade_count`, `win_rate`, `total_return`, `max_drawdown` |
| Baseline | `baseline_run_id` 또는 JSON `baseline_snapshot`이 없으면 `baseline.status="unspecified"`, delta는 `null` |
| Artifact | `backend/reports/strategy_validation_252d.json` |

기존 `/api/backtest/run`, `/api/backtest/runs`, `/api/backtest/runs/{run_id}` contract는 변경하지 않습니다.

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
| `GET` | `/api/broker/status` | broker safety status |
| `POST` | `/api/broker/orders/preview` | dry-run preview only |
| `GET` | `/api/paper/status` | paper disabled safety status |
| `POST` | `/api/paper/orders/preview` | paper deny preview only |
| `POST` | `/api/screener/run` | rule-based screener run |
| `GET` | `/api/screener/strategies` | frontend strategy selector metadata |
| `GET` | `/api/screener/results` | screener result list with explanation contract |
| `POST` | `/api/backtest/run` | strategy backtest run |
| `GET` | `/api/backtest/strategy-summary` | 최근 252 trading days strategy validation summary |
| `GET` | `/api/backtest/runs` | backtest run 목록 |
| `GET` | `/api/backtest/runs/{run_id}` | backtest run 상세 |

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

Backend full suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
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
- `paper_orders`, `paper_fills`, `paper_positions`, `paper_audit_events` row count 0 유지.
- `/api/broker/status`는 `can_submit=false`, `preview_only=true`, `token_issued=false`, `network_call_performed=false`를 반환.
- `/api/broker/orders/preview`는 실제 주문, token 발급, network call, adapter order call 없이 deny preview만 반환.
- `/api/paper/status`는 `enabled=false`, `can_create=false`, `can_simulate_fills=false`, `preview_only=true`를 반환.
- `/api/paper/orders/preview`는 paper order/fill/position/audit mutation 없이 deny preview만 반환.
- `POST /api/paper/orders`, `POST /api/paper/fill-simulator/run`, `/api/kis/orders/*`, `/api/kis/broker/*`, `/api/kis/websocket/*` route는 미등록 404 상태를 유지.
- `.cache/kis/token.json`은 생성하지 않음.
- API key, secret, token, password, account/header/raw credential 값을 저장하거나 출력하지 않음.

## Not Implemented

- 실제 주문, 주문 취소, 체결, 계좌, 잔고, websocket, live broker.
- paper order create, paper fill simulator, paper position mutation.
- KIS credential/token 저장, KIS token 발급/refresh/cache, 실제 KIS API 호출.
- KRX/yfinance 실제 network fetch.
- 자동매매 scheduler, live broker adapter, AI prediction model.
- portfolio cash/position state, walk-forward validation.

## CI

GitHub Actions workflow는 `.github/workflows/ci.yml`에 정의합니다.

- backend job: Python 3.12, `requirements.txt` 설치, `python -m pytest backend/tests`.
- frontend job: Node 22, `npm ci`, lint, typecheck, build.
- CI는 KIS credential/token secret을 요구하지 않으며 실제 외부 API 호출 없이 fail-closed 테스트만 실행합니다.
