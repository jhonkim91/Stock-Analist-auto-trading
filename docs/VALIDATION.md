# Validation

## 최신 검증 결과

검증 시각: 2026-05-22

Checkpoint: `MVP v0.8 Phase 3F-1 read-only data provider contract`

기준 브랜치: `main`

Status: Validated locally before commit/deploy

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase 3F-1 targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3f_readonly_provider_contract.py -q`: 2 passed |
| Backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 62 passed |
| Frontend lint | 통과 | `npm.cmd run lint` |
| Frontend typecheck | 통과 | `npm.cmd exec tsc -- --noEmit` |
| Frontend production build | 통과 | `npm.cmd run build` |
| Frontend npm audit | 통과 | `npm.cmd audit --audit-level=moderate`: found 0 vulnerabilities |
| Browser smoke | 통과 | fresh backend/frontend `8010/3010`, `/data` read-only provider contract 표시 |
| Safety assertions | 통과 | `orders_count == 0`, `paper_* == 0`, token/cache/network/adapter order call 미수행 |
| Plan docs check | 통과 | `rg -n "Phase Plan Index|Phase 3F: Read-only Data Reliability|Phase 4B" docs/plans README.md Memory.md`; `git diff --check` |

## Phase 3F-1 Read-only Data Provider Contract

- 신규 endpoint: `GET /api/data/read-only/providers`.
- 반환 필드: `source_id`, `provider_name`, `asset_scope`, `capabilities`, `enabled`, `network_enabled`, `read_only_enabled`, `status`, `blocked_reason`, `reason_codes`.
- KIS/KRX provider contract는 capability/status만 반환하며 fetch 실행 endpoint를 만들지 않았다.
- `network_call_performed=false`, `token_issued=false`, `token_cache_enabled=false`, `adapter_order_call_performed=false`, `adapter_network_call_performed=false`를 명시한다.
- `kis_market_data`는 `daily_ohlcv` read-only candidate로 유지하되 `enabled=false`, `network_enabled=false`, `read_only_enabled=false` fail-closed 상태다.
- KRX contract source는 `krx_index_sector`, `krx_symbol_master`, `krx_trading_calendar`, `krx_corporate_actions`로 등록했다.
- 기존 `/api/data/external/providers`, `/api/data/external/preview-daily-ohlcv`, `/api/data/external/confirm-import` flow는 유지한다.
- `/data` 화면은 read-only provider contract panel을 표시한다.

## Phase Plan Docs

- 전체 Phase 인덱스: `docs/plans/README.md`.
- Phase 3F 상세 계획: `docs/plans/phase-3f-readonly-data-reliability.md`.
- README의 오래된 Phase 3F/3G 후보 문구를 현재 흐름인 Phase 3F-2, 3F-3, 3F-4, 3G, 3H, 3I, 3J, 4A, 4B 순서로 정리했다.
- 계획 문서는 승인 경계와 안전 불변 조건을 유지한다.

## Safety Contract

| 항목 | 상태 |
|---|---|
| `/api/paper/status` | 유지 |
| `/api/paper/orders/preview` | 유지 |
| `POST /api/paper/orders` | 404 유지 |
| `POST /api/paper/fill-simulator/run` | 404 유지 |
| KIS order/broker/websocket routes | 404 유지 |
| KIS token 발급/cache/DB 저장 | 없음 |
| KIS credential 노출 | 없음 |
| broker network/order call | 없음 |
| live broker/order/cancel/fill/websocket | 없음 |

## API Smoke

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
| `/api/paper/orders` | 404 |
| `/api/paper/fill-simulator/run` | 404 |

## Browser Smoke

```text
backend: http://127.0.0.1:8010
frontend: http://127.0.0.1:3010
result: /data read-only provider contract visible, API safety flags false
visible contracts: kis_market_data, krx_index_sector, NETWORK_DISABLED_FAIL_CLOSED
```

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
- token 발급, refresh, cache, DB 저장
- KIS 주문 API, cancel, fill, websocket
- KIS broker/order/websocket route 등록
- paper order create, fill, position 변경
- live broker
- 실제 주문 또는 모의 주문 row 생성
- 자동매매 스케줄러
