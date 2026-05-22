# Validation

## 최신 검증 결과

검증 시각: 2026-05-22

Checkpoint: `MVP v0.8 Phase 3F-2 KIS read-only daily OHLCV fixture adapter`

기준 브랜치: `main`

Status: Validated locally before commit/deploy

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase 3F-2 targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3f2_kis_daily_ohlcv_adapter.py -q`: 5 passed |
| KIS/read-only safety regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3f_readonly_provider_contract.py backend/tests/test_phase3c_kis_readonly.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py -q`: 19 passed |
| Backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 67 passed |
| Frontend lint | 통과 | `npm.cmd run lint` |
| Frontend typecheck | 통과 | `npm.cmd exec tsc -- --noEmit` |
| Frontend production build | 통과 | `npm.cmd run build`: Next.js 16.2.6 production build |
| Frontend npm audit | 통과 | `npm.cmd audit --audit-level=moderate`: found 0 vulnerabilities |
| Safety invariant readback | 통과 | local DB/API readback: orders/paper rows 0, token/cache/network/adapter flags false, token cache file 없음 |

## Phase 3F-2 KIS Read-only Daily OHLCV Fixture Adapter

- 새 fixture: `backend/tests/fixtures/kis_daily_itemchartprice_response.json`.
- Canonical top-level fields: `rt_cd`, `msg_cd`, `msg1`, `output2`.
- Canonical `output2[]` row fields: `stck_bsop_date`, `stck_oprc`, `stck_hgpr`, `stck_lwpr`, `stck_clpr`, `acml_vol`, `acml_tr_pbmn`.
- Fixture에는 `app_key`, `app_secret`, `token`, `access_token`, `refresh_token`, `account`, `account_no`, `cano`, `hts_id`, `authorization`, `headers`, `raw_credentials` 계열 필드가 없다.
- `MockKisMarketDataProvider`는 `network_enabled=false` 경로에서만 canonical fixture schema 기반 deterministic raw rows를 생성한다.
- `KisMarketDataProvider.fetch_daily_ohlcv()`는 실제 KIS 호출 없이 계속 fail-closed 상태다.
- 기본 `backend/config/data_sources.yaml`의 `kis_market_data`는 `enabled=false`, `network_enabled=false`, `read_only_enabled=false`를 유지한다.

Normalized daily OHLCV 컬럼:

```text
trade_date, symbol, open, high, low, close, adj_close, volume, turnover_value, market, venue, provider
```

대표 normalized row:

```json
{
  "trade_date": "2026-05-19",
  "symbol": "KR001",
  "open": 50252.0,
  "high": 50452.0,
  "low": 50122.0,
  "close": 50302.0,
  "adj_close": 50302.0,
  "volume": 120000,
  "turnover_value": 6036240000.0,
  "market": "KR",
  "venue": "KRX",
  "provider": "external_market_data"
}
```

## Preview / Confirm 검증

- `source_id=kis_market_data` preview 검증은 test-only monkeypatch override로만 수행했다.
- Preview 응답은 `provider_name=kis`, `provider_mode=mock`, `data_origin=deterministic_kis_mock`, `network_enabled=false`를 반환했다.
- Preview 단계에서는 `daily_ohlcv` count가 변하지 않았다.
- Confirm 후에만 `daily_ohlcv`가 upsert됐다.
- 테스트 기준 `KR001`, `2026-05-19`~`2026-05-21` 범위에서 `inserted_count=1`, `updated_count=2`를 확인했다.
- 동일 run 중복 confirm은 기존 contract대로 `409`를 유지했다.
- 기존 `/api/data/external/preview-daily-ohlcv`, `/api/data/external/confirm-import`, `/api/data/read-only/providers` API contract 변경은 없다.
- Frontend API type과 DB schema 변경은 없다.

## Safety Contract

| 항목 | 상태 |
|---|---|
| `orders_count` | 0 |
| `paper_orders` | 0 |
| `paper_fills` | 0 |
| `paper_positions` | 0 |
| `paper_audit_events` | 0 |
| `token_issued` | false |
| `token_cache_enabled` | false |
| `network_call_performed` | false |
| `adapter_order_call_performed` | false |
| `adapter_network_call_performed` | false |
| `.cache/kis/token.json` | 없음 |
| KIS order/broker/websocket routes | 404 유지 |
| `POST /api/paper/orders` | 404 유지 |
| `POST /api/paper/fill-simulator/run` | 404 유지 |

Sentinel KIS env 값은 `/api/data/read-only/providers`, `/api/kis/status`, `/api/kis/config`, `/api/kis/config/validate` 응답에 노출되지 않았다.

## API Smoke 기준

| Check | Result |
|---|---|
| `/health` | 200 |
| `/api/data/status` | 200 |
| `/api/data/sources` | 200 |
| `/api/data/external/providers` | 200 |
| `/api/data/read-only/providers` | 200 |
| `/api/kis/status` | 200 |
| `/api/broker/status` | 200 |
| `/api/paper/status` | 200 |
| `/api/paper/orders/preview` | 200 |
| `/api/kis/orders/*` | 404 |
| `/api/kis/broker/*` | 404 |
| `/api/kis/websocket/*` | 404 |
| `/api/paper/orders` | 404 |
| `/api/paper/fill-simulator/run` | 404 |

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
- KIS token 발급, refresh, cache, DB 저장
- KIS credential 저장
- KIS 주문, 계좌, 잔고, 체결, cancel, websocket route
- broker adapter network/order call
- `POST /api/paper/orders`
- paper fill simulator
- paper order/fill/position/audit row mutation
- frontend API contract 변경
- DB schema 변경

## 다음 Phase

- Phase 3F-3: KRX index/sector/symbol/calendar/corporate action source contract를 fixture/read-only 기반으로 설계한다.
- DB schema 변경이 필요하면 Phase 3F-3 안에서 별도 승인 대상으로 분리한다.
