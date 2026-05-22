# Project Status

## 현재 기준

| 항목 | 값 |
|---|---|
| Version | `MVP v0.13` |
| Phase | `Phase 3H Strategy Extension` |
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
- Phase 3G-1: backtest execution model hardening.
- Phase 3G-2: liquidity participation cap and partial fill model.
- Phase 3G-3: adjusted price option, delisted symbol forced exit, missing data forced exit metrics.
- Phase 3H: strategy explanation contract, conservative optional strategy filters, fixture tests.
- GitHub Actions CI: backend pytest, frontend lint/typecheck/build.
- Alembic migration scaffold: 초기 schema migration과 SQLite upgrade/downgrade smoke test.

## Phase 3H 변경 요약

- Screener result 응답에 `triggered_conditions`, `score_breakdown`, `risk_flags`, `data_quality_flags`, `explanation`, `rationale`를 추가했다.
- `trend_breakout`에 optional ATR risk filter를 추가했다.
- `vcp_breakout`에 optional pivot distance limit filter를 추가했다.
- `canslim_lite`에 optional ROE 기반 earnings quality filter를 추가했다.
- 모든 새 전략 조건은 기본값 `false`로 비활성화되어 기존 전략 기본 결과를 보존한다.
- DB schema, backtest 수익률 산식, broker/paper/KIS 기능은 변경하지 않았다.

## 미구현 항목

- 실제 주문, 주문 취소, 체결, 계좌, 잔고, websocket, live broker.
- paper order create, paper fill simulator, paper position mutation.
- KIS credential/token 저장, token 발급/refresh/cache, 실제 KIS API 호출.
- 실제 KRX/yfinance network fetch.
- 자동매매 scheduler, live broker adapter, AI prediction model.
- portfolio cash/position state, walk-forward validation.

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
.\.venv\Scripts\python.exe -m pytest backend/tests
```

Phase 3H strategy:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_strategies.py backend/tests/test_phase2_api.py backend/tests/test_api_smoke.py -q
```

Phase 3G backtest realism:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_phase3g_backtest_execution_model.py -q
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

Secret/safety grep:

```powershell
$matches = rg -n --hidden --glob '!docs/**' --glob '!frontend/package-lock.json' --glob '!frontend/node_modules/**' --glob '!backend/data/**' '(app_key|app_secret|access_token|refresh_token|account_no|password)\s*:\s*\x22[^*<][^\x22]{7,}\x22' backend frontend
if ($LASTEXITCODE -eq 1) { 'secret scan: no matches' } elseif ($LASTEXITCODE -eq 0) { $matches; exit 1 } else { exit $LASTEXITCODE }
```

Alembic migration:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_alembic_migrations.py -q
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

## 다음 권장 Phase

Phase 3I에서 weekly review report를 검토한다. 기존 API, safety contract, no real-order 정책을 유지하고 fixture 기반 검증을 우선한다.
