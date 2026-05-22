# Validation

## 최신 검증 결과

검증 시각: 2026-05-22

Checkpoint: `MVP v0.8 Phase 3F-3 KRX fixture source contract`

기준 브랜치: `main`

Status: Validated locally before commit/deploy

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase 3F-3 targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3f3_krx_fixture_contract.py backend/tests/test_phase3f_readonly_provider_contract.py -q`: 8 passed |
| Backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 73 passed |
| Frontend lint | 통과 | `npm.cmd run lint` |
| Frontend typecheck | 통과 | `npm.cmd exec tsc -- --noEmit` |
| Frontend production build | 통과 | `npm.cmd run build`: Next.js 16.2.6 production build |
| Frontend npm audit | 통과 | `npm.cmd audit --audit-level=moderate`: found 0 vulnerabilities |
| Safety invariant readback | 통과 | targeted/API test에서 orders/paper rows 0, token/cache/network/adapter flags false, KIS/paper mutation routes 404 확인 |

## Phase 3F-3 KRX Fixture Contract

- 신규 실행 endpoint 없음.
- DB schema 변경 없음.
- Alembic/migration 도입 없음.
- KRX/KIS 실제 network call 구현 없음.
- KRX fixture normalize 결과를 DB에 저장하는 runtime flow 없음.
- `GET /api/data/read-only/providers` 응답 필드는 추가/삭제하지 않음.
- KRX source 4종은 계속 `enabled=false`, `network_enabled=false`, `read_only_enabled=false`.

### Fixture schema

공통 top-level fields:

```text
fixture_version, source_id, provider_name, market, venue
```

Fixture별 entity fields:

| Fixture | Entity field | Row fields |
|---|---|---|
| `krx_index_sector_reference.json` | `indexes[]` | `trade_date`, `symbol`, `name`, `open`, `high`, `low`, `close`, `volume` |
| `krx_index_sector_reference.json` | `sectors[]` | `trade_date`, `sector`, `open`, `high`, `low`, `close`, `volume` |
| `krx_symbol_master_reference.json` | `symbols[]` | `symbol`, `name`, `asset_type`, `currency`, `market`, `exchange`, `sector`, `industry`, `is_active`, `list_date`, `delist_date` |
| `krx_trading_calendar_reference.json` | `dates[]` | `calendar_date`, `is_open`, `session`, `holiday_name` |
| `krx_corporate_actions_reference.json` | `actions[]` | `symbol`, `action_date`, `action_type`, `value`, `note` |

Fixtures do not contain `app_key`, `app_secret`, `secret`, `token`, `access_token`, `refresh_token`, `account`, `account_no`, `cano`, `authorization`, `headers`, or `raw_credentials`.

### Normalize output examples

`index_ohlcv` payload:

```json
{
  "trade_date": "2026-05-20",
  "symbol": "KOSPI",
  "open": 2725.1,
  "high": 2744.2,
  "low": 2718.35,
  "close": 2738.42,
  "volume": 483920000
}
```

`symbol_master` payload:

```json
{
  "symbol": "005930",
  "name": "Samsung Electronics",
  "asset_type": "stock",
  "currency": "KRW",
  "market": "KR",
  "exchange": "KRX",
  "sector": "Semiconductors",
  "industry": "Memory",
  "is_active": true,
  "list_date": "1975-06-11",
  "delist_date": null
}
```

`trading_calendar` payload:

```json
{
  "market": "KR",
  "calendar_date": "2026-05-20",
  "is_open": true,
  "source_id": "krx_trading_calendar",
  "note": "session=regular"
}
```

`corporate_actions` payload:

```json
{
  "symbol": "005930",
  "action_date": "2026-05-20",
  "action_type": "DIVIDEND",
  "value": 361.0,
  "source_id": "krx_corporate_actions",
  "note": "cash dividend fixture"
}
```

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

## 제외 범위

- 실제 KRX API 호출
- 실제 KIS API 호출
- token 발급/cache/credential 저장
- 신규 실행 endpoint
- DB schema 변경, Alembic/migration
- KRX normalize 결과 DB upsert API/service/runtime flow
- 주문/계좌/잔고/체결/cancel/websocket route
- `POST /api/paper/orders`
- paper fill simulator
- broker adapter network/order call
- live broker, 자동매매 scheduler

## 다음 Phase

- Phase 3F-4: data freshness/quality summary와 `/data` read-only summary panel 구현.
- Phase 3F-4에서도 실제 network call, token/cache, broker/order path는 별도 승인 전까지 금지.
