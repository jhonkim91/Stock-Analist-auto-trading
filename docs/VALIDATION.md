# Validation

## 최신 검증 결과

검증 시각: 2026-05-22

Checkpoint: `MVP v0.9 Phase 3F-4 Data Freshness/Quality Summary`

기준 브랜치: `main`

Status: 로컬 구현 및 검증 완료, commit/push 미수행

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase 3F-4 targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3f4_data_quality_summary.py -q`: 6 passed |
| Backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests`: 79 passed |
| Frontend lint | 통과 | `npm.cmd run lint` |
| Frontend typecheck | 통과 | `npm.cmd exec tsc -- --noEmit` |
| Frontend production build | 통과 | `npm.cmd run build`: Next.js 16.2.6 production build |
| Frontend npm audit | 통과 | `npm.cmd audit --audit-level=moderate`: found 0 vulnerabilities |
| API sample | 통과 | seeded DB에서 `GET /api/data/quality-summary` 200, `latest_trade_date=2026-05-20`, `daily_ohlcv=4800`, safety counts 0/false |
| `/data` browser smoke | 통과 | fresh backend/frontend `8010/3010`, Playwright CLI screenshot, `Freshness & Quality Summary` selector 확인 |
| Safety invariant | 통과 | tests에서 orders/paper rows 0, token/cache/network/adapter flags false, KIS/paper mutation routes 404 확인 |

## Phase 3F-4 Data Quality Summary

신규 API:

```http
GET /api/data/quality-summary?market=KR&venue=KRX&lookback_trading_dates=30
```

Query 기본값:

| query | 기본값 | 범위 |
|---|---:|---:|
| `market` | `KR` | length 1..16 |
| `venue` | `KRX` | length 1..32 |
| `lookback_trading_dates` | `30` | 1..252 |

대표 응답 예시:

```json
{
  "market": "KR",
  "venue": "KRX",
  "latest_trade_date": "2026-05-20",
  "row_counts": {
    "daily_ohlcv": 4800,
    "symbol_master": 15,
    "active_symbols": 15,
    "trading_calendar": 0,
    "import_runs": 0,
    "confirmed_import_runs": 0,
    "data_quality_checks": 0
  },
  "missing_rows": {
    "basis": "observed_daily_ohlcv",
    "lookback_trading_dates": 30,
    "date_count": 30,
    "active_symbol_count": 15,
    "expected_rows": 450,
    "actual_rows": 450,
    "missing_rows_estimate": 0,
    "coverage_ratio": 1.0,
    "latest_trade_date_missing_symbol_count": 0,
    "missing_symbol_sample": []
  },
  "duplicate_summary": {
    "physical_duplicate_groups": 0,
    "physical_duplicate_rows": 0,
    "physical_duplicate_sample": [],
    "quality_duplicate_code_counts": {
      "DUPLICATE_IN_BATCH": 0,
      "DUPLICATE_IN_DATABASE": 0
    }
  },
  "safety_counts": {
    "orders_count": 0,
    "paper_orders_count": 0,
    "paper_fills_count": 0,
    "paper_positions_count": 0,
    "paper_audit_events_count": 0,
    "token_issued": false,
    "token_cache_enabled": false,
    "network_call_performed": false,
    "adapter_order_call_performed": false,
    "adapter_network_call_performed": false
  }
}
```

계산 규칙:

- `latest_trade_date`: `daily_ohlcv.trade_date` max, `venue` 필터 적용.
- `source_freshness`: `data_sources.yaml`의 CSV/external/read-only source 기준. disabled source는 `DISABLED`, enabled daily OHLCV source의 confirmed run 없음은 `NO_CONFIRMED_RUN`, enabled read-only reference source의 confirmed run 없음은 `NOT_APPLICABLE`.
- `missing_rows`: `trading_calendar` open date가 있으면 calendar 기준, 없으면 observed `daily_ohlcv` date 기준. latest trade date missing symbol sample은 최대 20개.
- `duplicate_summary`: physical duplicate group/row count와 `data_quality_checks` duplicate code count를 분리.
- `quality_counts`: severity별 count와 top check code를 집계.
- `safety_counts`: execution/paper row count는 DB에서 조회하고 token/network/adapter flags는 false로 반환.

## Safety Contract

| 항목 | 상태 |
|---|---|
| DB schema/migration | 변경 없음 |
| provider fetch/network call | 없음 |
| token 발급/cache/refresh/storage | 없음 |
| KIS credential 저장 | 없음 |
| broker adapter network/order call | 없음 |
| `orders_count` | 0 |
| `paper_orders_count` | 0 |
| `paper_fills_count` | 0 |
| `paper_positions_count` | 0 |
| `paper_audit_events_count` | 0 |
| `token_issued` | false |
| `token_cache_enabled` | false |
| `network_call_performed` | false |
| `adapter_order_call_performed` | false |
| `adapter_network_call_performed` | false |
| KIS order/broker/websocket routes | 404 유지 |
| `POST /api/paper/orders` | 404 유지 |
| `POST /api/paper/fill-simulator/run` | 404 유지 |

## 제외 범위

- 실제 KIS/KRX/yfinance network call
- provider fetch 실행
- token 발급/cache/credential 저장
- 주문/계좌/잔고/체결/cancel/websocket route
- `POST /api/paper/orders`
- paper fill simulator
- paper order/fill/position/audit mutation
- DB schema 변경, Alembic/migration 도입
- 기존 preview/confirm flow 변경
- 기존 `GET /api/data/read-only/providers` contract 변경

## 다음 Phase

- Phase 3G: backtest/execution realism 보강 후보. gap-aware stop, liquidity participation cap, partial fill, delisted symbol, corporate action adjusted price, portfolio cash/position state, overlapping trades control.
