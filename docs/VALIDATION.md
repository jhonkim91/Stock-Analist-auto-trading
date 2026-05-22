# Validation

## 최신 검증 결과

검증 시각: 2026-05-22

Checkpoint: `MVP v0.10 Phase 3G-1 Backtest Execution Model Hardening`

기준 브랜치: `main`

Status: 로컬 구현 및 검증 완료, commit/push 미수행

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase 3G-1 targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_phase3g_backtest_execution_model.py -q`: 10 passed |
| Backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests`: 86 passed |
| Frontend lint | 통과 | `npm.cmd run lint` |
| Frontend typecheck | 통과 | `npm.cmd exec tsc -- --noEmit` |
| Frontend production build | 통과 | `npm.cmd run build`: Next.js 16.2.6 production build |
| Frontend npm audit | 통과 | `npm.cmd audit --audit-level=moderate`: found 0 vulnerabilities |
| Backtest API contract | 통과 | `POST /api/backtest/run`, `GET /api/backtest/runs`, `GET /api/backtest/runs/{run_id}` smoke 유지 |
| Safety invariant | 통과 | tests에서 orders/paper rows 0, token/cache/network/adapter flags false, KIS/paper mutation routes 404 확인 |

## Phase 3G-1 Backtest Execution Model

변경 범위:

- `BacktestService`의 long-only exit simulation만 보강.
- `next_open` entry, commission/slippage, max holding, 기존 metrics key, `backtest_runs.metrics_json` 저장 구조 유지.
- DB schema, migration/Alembic, frontend, broker, paper order/fill/position, KIS/KRX/yfinance network path 변경 없음.

Execution rule:

| 상황 | 최종 처리 |
|---|---|
| Entry | signal 다음 거래일 `open` 기준 진입 유지 |
| Entry gap below stop | skip하지 않고 next-open entry 후 같은 open 가격으로 즉시 `stop` exit |
| Holding day gap-down stop | `stop_price`가 아니라 해당 bar `open` 가격으로 exit |
| Intraday stop | gap이 아니면 `stop_price` 기준 exit |
| Target gap-up | `open >= target_price`이면 open fill 인정, intraday high 초과 이익은 반영하지 않음 |
| Intraday target | gap이 아니면 `target_price` 기준 exit |
| Same-bar stop/target | `backtest.yaml.execution.same_bar_stop_first` 설정을 따름 |
| Max holding | stop/target이 없으면 마지막 holding bar `close` 기준 exit 유지 |

`trades[*].execution_detail` 예시:

```json
{
  "entry_assumption": "next_open",
  "exit_assumption": "gap_down_stop_open_exit",
  "same_bar_stop_first": true,
  "stop_touched": true,
  "target_touched": false,
  "same_bar_both_touched": false,
  "gap_stop": true,
  "gap_target": false,
  "stop_price": 95.0,
  "target_price": 112.745,
  "commission_bps": 2.0,
  "slippage_bps": 5.0
}
```

## Safety Contract

| 항목 | 상태 |
|---|---|
| DB schema/migration | 변경 없음 |
| provider fetch/network call | 없음 |
| token 발급/cache/refresh/storage | 없음 |
| KIS credential 저장 | 없음 |
| broker adapter network/order call | 없음 |
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

## 제외 범위

- 실제 주문, paper order/fill/position mutation, live broker
- KIS/KRX/yfinance network call
- token/cache/credential 저장
- broker/order adapter import 또는 호출
- DB schema 변경, Alembic/migration 도입
- frontend 화면/API client 변경
- portfolio cash/open positions/overlapping trades 구현
- liquidity cap, partial fill, walk-forward validation 구현

## 다음 Phase

- Phase 3G-2: liquidity and partial fill model.
- 권장 범위: ADV/turnover participation limit, insufficient liquidity case, partial fill simulation, position size cap 보강.
