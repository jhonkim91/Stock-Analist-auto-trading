# Validation

## 최신 검증 결과

검증 시각: 2026-05-22

Checkpoint: `MVP v0.11 Phase 3G-2 Liquidity and Partial Fill Model`

기준 브랜치: `main`

Status: 로컬 구현 및 검증 완료, commit/push 미수행

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase 3G-2 targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_phase3g_backtest_execution_model.py -q`: 17 passed |
| Backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests`: 93 passed |
| Frontend lint | 통과 | `npm.cmd run lint` |
| Frontend typecheck | 통과 | `npm.cmd exec tsc -- --noEmit` |
| Frontend production build | 통과 | `npm.cmd run build`: Next.js 16.2.6 production build |
| Frontend npm audit | 통과 | `npm.cmd audit --audit-level=moderate`: found 0 vulnerabilities |
| Backtest API contract | 통과 | `POST /api/backtest/run`, `GET /api/backtest/runs`, `GET /api/backtest/runs/{run_id}` smoke 유지 |
| Safety invariant | 통과 | orders/paper rows 0, token/cache/network/adapter flags false, KIS/paper mutation routes 404, `.cache/kis/token.json` 미생성 |

## Phase 3G-2 Backtest Liquidity Model

변경 범위:

- `BacktestService`의 long-only backtest 내부 simulation에만 liquidity participation limit과 partial fill을 추가.
- `risk.position_size`는 `planned_qty`로 유지하고, 실제 backtest 체결 수량만 `filled_qty`로 보수적으로 제한.
- `backtest.yaml.execution`에 `max_participation_rate`, `min_fill_ratio`, `allow_partial_fill` 추가.
- DB schema, migration/Alembic, frontend 화면/API client, broker, paper order/fill/position, KIS/KRX/yfinance network path 변경 없음.

Config:

```yaml
execution:
  max_participation_rate: 0.05
  min_fill_ratio: 0.25
  allow_partial_fill: true
```

Liquidity rule:

| 단계 | 처리 |
|---|---|
| planned quantity | 기존 `risk.position_size` 사용 |
| requested notional | `planned_qty * raw_entry_price` |
| liquidity notional | `turnover_value > 0`이면 우선 사용 |
| fallback | `turnover_value`가 0/누락이면 `volume * raw_entry_price` 사용 |
| missing liquidity | `turnover_value`와 `volume` 모두 0/누락이면 no-fill skip |
| cap notional | `liquidity_notional * max_participation_rate` |
| fill ratio | `min(1.0, cap_notional / requested_notional)` |
| partial disabled | `allow_partial_fill=false`이고 `fill_ratio < 1`이면 trade record 없이 skip |
| partial enabled | `filled_qty = floor(planned_qty * fill_ratio)` |
| minimum fill | `filled_qty == 0` 또는 `filled_qty / planned_qty < min_fill_ratio`이면 skip |
| generated trade | top-level `qty`, `pnl`, `estimated_cost`는 모두 `filled_qty` 기준 |

`trades[*].liquidity_detail` 예시:

```json
{
  "planned_qty": 1000,
  "filled_qty": 500,
  "unfilled_qty": 500,
  "requested_notional": 100000.0,
  "liquidity_notional": 1000000.0,
  "cap_notional": 50000.0,
  "fill_ratio": 0.5,
  "max_participation_rate": 0.05,
  "min_fill_ratio": 0.25,
  "allow_partial_fill": true,
  "liquidity_basis": "turnover_value",
  "position_size_cap_applied": true
}
```

Optional metrics 예시:

```json
{
  "partial_fill_count": 1,
  "no_fill_count": 0,
  "total_unfilled_qty": 500
}
```

기존 `trades[*].execution_detail`과 기존 metrics key는 삭제하거나 타입 변경하지 않는다.

## Safety Contract

| 항목 | 상태 |
|---|---|
| DB schema/migration | 변경 없음 |
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

- 실제 주문, paper order/fill/position/audit mutation, live broker
- KIS/KRX/yfinance network call
- token/cache/credential 저장
- broker/order adapter import 또는 호출
- DB schema 변경, Alembic/migration 도입
- frontend 대규모 변경
- backtest API breaking change
- 기존 metrics key 삭제/타입 변경
- strategy 조건 대규모 변경
- portfolio cash/position state 구현
- walk-forward 구현

## 다음 Phase

- Phase 3G-3 제안: backtest의 corporate action adjusted price와 delisted symbol handling을 보강한다.
- 권장 범위: split/dividend adjustment 기준 확정, 상장폐지/거래정지 row 처리, 마지막 가용 가격 청산 규칙, 기존 `daily_ohlcv.adj_close` 사용 여부 검증.
