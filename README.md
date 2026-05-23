# Stock Analyst Auto Trading

주식 분석, 스크리닝, 백테스트, 리포트 생성을 검증 가능한 MVP 형태로 구현한 FastAPI + Next.js 프로젝트입니다.

현재 기준선은 `MVP v0.14 / Phase C-3 new_high_breakout Strategy`입니다. 이 저장소는 실거래 자동매매 엔진이 아니라 자동매매 보조 MVP이며, 실주문, 주문 취소, 체결, 계좌, 잔고, websocket, live broker, KIS credential/token 저장, 실제 KIS/KRX/yfinance 호출은 구현하지 않습니다.

상태 요약은 [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md), 단계 계획은 [docs/plans/README.md](docs/plans/README.md), 최신 검증 기록은 [docs/VALIDATION.md](docs/VALIDATION.md), DB migration 절차는 [docs/DB_MIGRATION.md](docs/DB_MIGRATION.md)를 기준으로 봅니다.

## Current Baseline

| 항목 | 값 |
|---|---|
| Version | `MVP v0.14` |
| Phase | `Phase C-3 new_high_breakout Strategy` |
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
- Phase 3G-1: backtest execution realism hardening.
- Phase 3G-2: liquidity participation cap and partial fill model.
- Phase 3G-3: adjusted price option, delisted symbol forced exit, missing data forced exit metrics.
- Phase 3H: strategy explanation contract and conservative optional filters.
- Phase C-1: `momentum_rank` available-only strategy.
- Phase C-2: `relative_strength_leader` available-only strategy.
- Phase C-3: `new_high_breakout` default and available strategy.
- GitHub Actions CI scaffold: backend pytest, frontend lint/typecheck/build.
- Alembic migration scaffold: current SQLAlchemy model 기준 초기 SQLite migration.

## Strategy Behavior

Phase 3H 이후 전략 registry 기반 확장을 유지합니다.

- 기본 screener 전략은 `trend_breakout`, `vcp_breakout`, `canslim_lite`, `new_high_breakout` 4개입니다.
- `new_high_breakout`은 52주 신고가 또는 신고가 근접 돌파를 평가합니다.
- `momentum_rank`, `relative_strength_leader`는 available registry에 포함되며 명시 선택 시 screener/backtest에서 실행할 수 있습니다.
- screener result 응답에 `triggered_conditions`, `score_breakdown`, `risk_flags`, `data_quality_flags`, `explanation`, `rationale`을 추가합니다.
- 기존 `pass_flags`, `failed_conditions`, `reason_summary`, `score_details_json`, `risk_details_json`은 제거하지 않습니다.
- DB schema, backtest 수익률 산식, broker/paper/KIS safety contract는 변경하지 않습니다.

Strategy config options:

```yaml
trend_breakout:
  atr_risk_filter_enabled: false
  max_atr20_pct: 0.08

vcp_breakout:
  pivot_distance_limit_enabled: false
  max_pivot_distance_pct: 0.05

canslim_lite:
  earnings_quality_enabled: false
  min_roe: 0.15

new_high_breakout:
  new_high_threshold: 0.995
  volume_surge_multiple: 1.5
  rs_percentile_min: 80
```

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
| `GET` | `/api/screener/results` | screener result list with explanation contract |
| `POST` | `/api/backtest/run` | strategy backtest run |
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

backend 포트가 `8001` 등으로 바뀌면 `frontend/.env.local`의 `NEXT_PUBLIC_API_BASE_URL`을 맞춘 뒤 다시 build/start 해야 합니다. `NEXT_PUBLIC_*` 값은 production build에 포함됩니다.

## Verification Commands

Backend full suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests
```

Phase C strategy targeted suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_strategies.py backend/tests/test_backtest.py -q
```

Phase 3G backtest targeted suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_phase3g_backtest_execution_model.py -q
```

Broker/paper/KIS/backtest safety targeted suite:

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

Tracked code/config secret assignment scan:

```powershell
$matches = rg -n --hidden --glob '!docs/**' --glob '!frontend/package-lock.json' --glob '!frontend/node_modules/**' --glob '!backend/data/**' '(app_key|app_secret|access_token|refresh_token|account_no|password)\s*:\s*\x22[^*<][^\x22]{7,}\x22' backend frontend
if ($LASTEXITCODE -eq 1) { 'secret scan: no matches' } elseif ($LASTEXITCODE -eq 0) { $matches; exit 1 } else { exit $LASTEXITCODE }
```

Alembic migration smoke:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_alembic_migrations.py -q
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
