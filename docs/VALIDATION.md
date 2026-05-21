# Validation

## 최신 검증 결과

검증 시각: 2026-05-22

Checkpoint: `MVP v0.7 Phase 3E-1 paper preview safety scaffold`

기준 브랜치: `main`

Status: Completed

PR: #4

Merge commit: `2d5a146c8b89c355397eec458fd7343412e92c6e`

Post-merge docs commit: `127527ecec905227b15b5654dc3615f21fd244ec`

현재 HEAD: `8e503332c23875bd82754ffd29314b65e1235089`

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests`: 60 passed |
| Frontend lint | 통과 | `npm.cmd run lint` |
| Frontend typecheck | 통과 | `npm.cmd exec tsc -- --noEmit` |
| Frontend production build | 통과 | `npm.cmd run build` |
| Frontend npm audit | 통과 | `npm.cmd audit --audit-level=moderate` |
| API smoke | 통과 | FastAPI `TestClient` endpoint/status assertion |
| Browser route smoke | 통과 | `/dashboard` -> `/paper` nav, `/paper` desktop/mobile, preview deny |
| KIS execution routes | 통과 | `/api/kis/orders*`, `/api/kis/broker*`, `/api/kis/websocket*` 404 유지 |
| Broker/Paper safety assertions | 통과 | `orders_count == 0`, `paper_* == 0`, token/cache/network/adapter order call 미수행, sensitive value 미노출 |

## Phase 3E-1 Paper Preview Safety Scaffold

- `/api/paper/status`는 disabled/fail-closed 상태만 반환한다.
- `/api/paper/orders/preview`는 DB write 없이 deny preview만 반환한다.
- `POST /api/paper/orders`, `POST /api/paper/fill-simulator/run`, cancel API는 등록하지 않았다.
- paper fill 생성과 paper position 변경은 구현하지 않았다.
- `paper_orders`, `paper_fills`, `paper_positions`, `paper_audit_events` row는 disabled smoke 후에도 0이다.
- KIS execution routes는 계속 404다.

## Phase 3D Broker Safety Scaffold

- Phase 3D는 broker safety scaffold only다.
- 실주문, paper order, live order, cancel, fill, websocket 연결은 구현하지 않았다.
- `backend/config/broker.yaml`은 disabled/fail-closed 기본값만 담는다.
- `/api/settings`는 `broker.yaml` 원문과 broker summary를 모두 반환하지 않는다.
- broker 안전 상태 요약은 `/api/broker/status`에서만 반환한다.
- audit DB persistence는 비활성이다.
- `TokenLifecycleService`는 status-only이며 token 발급, refresh, cache, DB 저장, in-memory manager를 구현하지 않았다.
- sell preview는 기존 long position 청산 검토 전용이며, 포지션 없음/수량 초과/short sell은 deny한다.

## API Contract

| Method | Path | Phase 3D 결과 |
|---|---|---|
| `GET` | `/api/broker/status` | safety scaffold 상태 요약 |
| `POST` | `/api/broker/orders/preview` | dry-run preview only |
| `GET/POST` | `/api/kis/orders/*` | 404 유지 |
| `GET/POST` | `/api/kis/broker/*` | 404 유지 |
| `GET/POST` | `/api/kis/websocket/*` | 404 유지 |

`/api/broker/status` sample:

```json
{
  "mode": "safety_scaffold",
  "broker_mode": "disabled",
  "can_submit": false,
  "preview_only": true,
  "paper_trading_enabled": false,
  "live_trading_enabled": false,
  "token_issued": false,
  "network_call_performed": false,
  "adapter_selected": true,
  "adapter_name": "kis_openapi",
  "adapter_capability_checked": true,
  "adapter_order_call_performed": false,
  "adapter_network_call_performed": false,
  "audit_persistence_enabled": false
}
```

`/api/broker/orders/preview` sample:

```json
{
  "mode": "safety_scaffold",
  "broker_mode": "disabled",
  "can_submit": false,
  "preview_only": true,
  "order_created": false,
  "token_issued": false,
  "token_cache_enabled": false,
  "network_call_performed": false,
  "adapter_selected": true,
  "adapter_name": "kis_openapi",
  "adapter_capability_checked": true,
  "adapter_order_call_performed": false,
  "adapter_network_call_performed": false,
  "risk_gate": {
    "decision": "deny",
    "passed": false,
    "reason_codes": [
      "BROKER_DISABLED",
      "BROKER_SUBMIT_DISABLED",
      "BROKER_NETWORK_DISABLED",
      "PAPER_TRADING_DISABLED",
      "LIVE_TRADING_DISABLED",
      "KILL_SWITCH_ACTIVE",
      "TOKEN_DISABLED",
      "BROKER_SOURCE_DISABLED",
      "BROKER_SOURCE_NETWORK_DISABLED",
      "BROKER_SOURCE_PAPER_DISABLED",
      "BROKER_SOURCE_LIVE_DISABLED"
    ]
  }
}
```

## 명령 결과

### Backend pytest

```text
collected 60 items
60 passed in 120.89s
```

### Frontend lint

```text
eslint . --max-warnings=0
통과
```

### Frontend typecheck

```text
npm.cmd exec tsc -- --noEmit
통과
```

### Frontend build

```text
Next.js 16.2.6 (Turbopack)
Compiled successfully
Route (app): /, /dashboard, /data, /paper, /screener, /reports, /backtest, /portfolio, /settings
```

### Frontend audit

```text
found 0 vulnerabilities
```

## API Smoke

FastAPI `TestClient` 기준:

| Check | Result |
|---|---|
| `/health` | 200 |
| `/api/data/status` | 200 |
| `/api/data/sources` | 200 |
| `/api/broker/status` | 200 |
| `/api/broker/orders/preview` | 200 |
| `/api/paper/status` | 200 |
| `/api/paper/orders/preview` | 200 |
| `/api/kis/status` | 200 |
| `/api/kis/orders` | 404 |
| `/api/kis/orders/preview` | 404 |
| `/api/kis/broker/status` | 404 |
| `/api/kis/websocket/status` | 404 |
| sentinel secret exposure | false |
| token cache `.cache/kis/token.json` | 없음 |
| orders_count after preview | 0 |
| paper_orders after preview | 0 |
| paper_fills after preview | 0 |
| paper_positions after preview | 0 |
| paper_audit_events after preview | 0 |
| token_issued | false |
| network_call_performed | false |
| adapter_order_call_performed | false |
| adapter_network_call_performed | false |
| audit DB persistence | disabled |

## 최종 DB 상태

| table/status | count |
|---|---:|
| symbol_master | 15 |
| daily_ohlcv | 4,800 |
| index_ohlcv | 320 |
| sector_ohlcv | 2,880 |
| fundamentals_pti | 30 |
| indicator_snapshot | 4,800 |
| screen_results | 45 |
| reports | 1 |
| backtest_runs | 7 |
| orders | 0 |
| paper_orders | 0 |
| paper_fills | 0 |
| paper_positions | 0 |
| paper_audit_events | 0 |

| field | value |
|---|---|
| latest_trade_date | 2026-05-20 |
| latest_indicator_date | 2026-05-20 |
| latest_screen_date | 2026-05-20 |

## 제외 범위

- KIS 실제 API 호출
- KIS app key/app secret/account/token 저장
- token 발급, refresh, cache, DB 저장, in-memory token manager
- KIS 주문 API, cancel, fill, websocket
- KIS broker/order/websocket route 등록
- paper order create, fill, position 변경, live broker
- 실제 주문 또는 모의 주문 row 생성
- audit DB persistence
- 자동매매 스케줄러
