# Validation

## 최신 검증 결과

검증 기준일: 2026-05-22

Checkpoint: `MVP v0.13 Phase 3H Strategy Extension`

기준 브랜치: `main`

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests`: 101 passed |
| Phase 3H strategy/API targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_strategies.py backend/tests/test_phase2_api.py backend/tests/test_api_smoke.py -q`: 12 passed |
| Phase 3G backtest targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_phase3g_backtest_execution_model.py -q`: 20 passed |
| Safety targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3c_kis_readonly.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_phase3g_backtest_execution_model.py -q`: 19 passed |
| Alembic migration smoke | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_alembic_migrations.py -q`: 2 passed |
| Frontend lint | 통과 | `npm.cmd run lint` |
| Frontend typecheck | 통과 | `npm.cmd exec tsc -- --noEmit` |
| Frontend production build | 통과 | `npm.cmd run build`: Next.js 16.2.6 production build |
| Secret/safety grep | 통과 | tracked backend/frontend code/config 대상 secret assignment scan: no matches |
| Backtest API contract | 통과 | `POST /api/backtest/run`, `GET /api/backtest/runs`, `GET /api/backtest/runs/{run_id}` contract 유지 |
| Screener explanation contract | 통과 | `triggered_conditions`, `score_breakdown`, `risk_flags`, `data_quality_flags`, `explanation`, `rationale` 응답 포함 |
| Safety invariant | 통과 | orders/paper rows 0, token/cache/network/adapter flags false, KIS/paper mutation routes 404, `.cache/kis/token.json` 미생성 |

## 표준 검증 명령

Backend full suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests
```

Phase 3H strategy targeted suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_strategies.py backend/tests/test_phase2_api.py backend/tests/test_api_smoke.py -q
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

`rg`는 매치가 없을 때 exit code 1을 반환하므로 위 wrapper는 no-match를 성공으로 처리한다.

Alembic migration smoke:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_alembic_migrations.py -q
```

## Phase 3H Strategy Extension

변경 범위:

- 기존 3개 전략 `trend_breakout`, `vcp_breakout`, `canslim_lite`의 기본 pass/fail 결과를 보존했다.
- `StrategyResult.metadata`에 공통 설명 필드 생성을 지원하는 helper를 추가했다.
- Screener result 응답에 `triggered_conditions`, `score_breakdown`, `risk_flags`, `data_quality_flags`, `explanation`, `rationale`를 추가했다.
- 새 optional strategy filter는 모두 기본 비활성이다.
- DB schema, backtest 수익률 산식, frontend 화면 구조, broker/paper/KIS safety contract는 변경하지 않았다.

Config:

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
```

Strategy explanation contract:

| 필드 | 의미 |
|---|---|
| `triggered_conditions` | `pass_flags` 중 true인 조건 목록 |
| `failed_conditions` | 기존 미충족 조건 목록 |
| `score_breakdown` | total score, grade, condition score, triggered/failed count |
| `risk_flags` | liquidity, reward/risk, position size, risk per share 확인 |
| `data_quality_flags` | parse 가능 여부와 주요 가격 필드 존재 여부 |
| `explanation` / `rationale` | 기존 `reason_summary` 기반 설명 |

Optional filter rule:

| 전략 | 옵션 | 기본값 | 활성화 시 처리 |
|---|---|---|---|
| `trend_breakout` | `atr_risk_filter_enabled` | `false` | `atr20_pct <= max_atr20_pct` 조건 추가 |
| `vcp_breakout` | `pivot_distance_limit_enabled` | `false` | breakout close와 pivot high 거리 제한 |
| `canslim_lite` | `earnings_quality_enabled` | `false` | `roe >= min_roe` 조건 추가 |

## Safety Contract

| 항목 | 상태 |
|---|---|
| Runtime table/column contract | 기존 모델 기준 유지, Alembic initial snapshot 유지 |
| provider fetch/network call | 없음 |
| token 발급/cache/refresh/storage | 없음 |
| KIS credential 저장 | 없음 |
| broker/order adapter import 또는 호출 | 없음 |
| paper order/fill/position/audit mutation | 없음 |
| `orders_count` | 0 유지 |
| `paper_orders_count` | 0 유지 |
| `paper_fills_count` | 0 유지 |
| `paper_positions_count` | 0 유지 |
| `paper_audit_events_count` | 0 유지 |
| `token_issued` | false 유지 |
| `token_cache_enabled` | false 유지 |
| `network_call_performed` | false 유지 |
| `adapter_order_call_performed` | false 유지 |
| `adapter_network_call_performed` | false 유지 |
| KIS order/broker/websocket routes | 404 유지 |
| `POST /api/paper/orders` | 404 유지 |
| `POST /api/paper/fill-simulator/run` | 404 유지 |
| `.cache/kis/token.json` | 미생성 |

## 제외 범위

- 실제 주문, paper order/fill/position/audit mutation, live broker.
- KIS/KRX/yfinance network call.
- token/cache/credential 저장.
- broker/order adapter import 또는 호출.
- DB table/column 변경.
- frontend 대규모 변경.
- backtest API breaking change.
- 기존 metrics key 제거/타입 변경.
- 기존 전략 기본 결과를 바꾸는 기본 활성 조건.
- portfolio cash/position state 구현.
- walk-forward 구현.

## 다음 Phase

- Phase 3I 제안: weekly review report를 검토한다.
- 권장 범위: 기존 safety contract를 유지하고 fixture 기반 리포트 생성/검증을 우선한다.
