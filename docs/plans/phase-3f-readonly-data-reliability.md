# Phase 3F: Read-only Data Reliability

Phase 3F는 전략 확장이나 주문 기능보다 먼저 실데이터 read-only adapter 기반의 데이터 신뢰성을 보강하는 단계다.

## 기준

- Phase 3E-1 Paper trading safety shell은 완료 상태로 유지한다.
- 유지: `/api/paper/status`, `/api/paper/orders/preview`, `/paper`.
- 미구현 유지: `POST /api/paper/orders`, fill simulator, paper mutation.
- 금지: 실주문, KIS 주문, cancel, fill, websocket, live broker, token 발급/cache, KIS credential 저장, broker network call.
- 안전 기준: `orders_count == 0`, `paper_orders/fills/positions/audit_events == 0`.

## Phase 3F 목표

- KIS/KRX read-only adapter의 공통 계약을 먼저 고정한다.
- 실제 외부 네트워크 호출은 명시 승인 전까지 기본 disabled/fail-closed로 둔다.
- 기존 `/api/data/external/preview-daily-ohlcv`와 confirm flow를 유지한다.
- read-only provider 상태, 데이터 freshness, import 품질 정보를 `/data`에서 확인 가능하게 만든다.

## Phase 3F-1: Read-only Data Provider Contract

상태: 완료

목표:

- KIS/KRX read-only adapter의 공통 인터페이스와 상태 계약을 고정한다.
- provider별 capability/status 구조를 정의한다.
- network call은 기본 disabled/fail-closed로 유지한다.
- 기존 external preview/confirm flow와 충돌하지 않게 설계한다.

구현 파일:

- `backend/app/services/data_providers.py`
- `backend/app/services/market_data_import_service.py`
- `backend/app/api/data.py`
- `backend/config/data_sources.yaml`
- `backend/tests/test_phase3f_readonly_provider_contract.py`
- `frontend/lib/api.ts`
- `frontend/app/data/page.tsx`
- `docs/VALIDATION.md`
- `Memory.md`

API contract:

| Method | Path | 설명 |
|---|---|---|
| `GET` | `/api/data/read-only/providers` | provider별 capability/status 조회 |

응답 필드:

- `source_id`
- `provider_name`
- `asset_scope`
- `capabilities`
- `enabled`
- `network_enabled`
- `read_only_enabled`
- `status`
- `blocked_reason`
- `network_call_performed`
- `token_issued`
- `token_cache_enabled`
- `adapter_order_call_performed`
- `adapter_network_call_performed`
- `credential_fields_exposed`

완료 기준:

- KIS/KRX provider가 capability만 노출하고 네트워크 호출은 하지 않는다.
- provider status가 secret 없이 redacted/fail-closed로 반환된다.
- 신규 fetch 실행 endpoint는 만들지 않는다.
- backend tests, frontend lint/typecheck/build/audit 통과.
- `orders_count == 0`, `paper_* == 0` 유지.

## Phase 3F-2: KIS Read-only Daily OHLCV Adapter

상태: 대기

목표:

- KIS 국내주식 일봉 OHLCV 조회 후보 adapter를 구현한다.
- 주문/계좌/잔고/체결 API와 분리한다.
- `network_enabled=false` 기본값을 유지한다.
- 명시 config와 환경변수 조건이 없으면 실제 호출을 차단한다.

범위:

- `KisMarketDataProvider`의 daily OHLCV raw response normalize.
- fixture 기반 normalize 테스트.
- normalize 결과를 기존 external preview/confirm flow로만 연결.
- preview 단계에서는 import run과 quality check만 생성.
- confirm 후에만 `daily_ohlcv` upsert.

제외 범위:

- KIS 주문 API.
- 계좌, 잔고, 체결 API.
- token 발급, token refresh, token cache 저장.
- websocket, live broker, broker network call.

테스트 계획:

- disabled 상태에서 network call 미수행.
- fixture raw response에서 normalized daily OHLCV 변환.
- preview는 `import_runs`와 `data_quality_checks`만 생성.
- confirm 전 market table mutation 없음.
- confirm 후에만 `daily_ohlcv` upsert.
- `orders_count == 0`, `paper_* == 0` 유지.

## Phase 3F-3: KRX Index/Sector/Symbol/Calendar/Corporate Action Source

상태: 대기

목표:

- KRX 계열 데이터를 주문과 무관한 read-only source로 분리한다.
- 우선 mock/fixture + read-only contract부터 시작한다.

범위:

- KRX index/sector data adapter contract.
- symbol master sync contract.
- trading calendar sync contract.
- corporate action loader contract.
- source별 freshness 기준과 `source_id` 정책 정의.

DB 변경 원칙:

- 설계 단계에서는 기존 테이블을 우선 사용한다.
- 부족한 컬럼/테이블이 필요하면 별도 migration 계획으로 분리한다.
- Alembic 도입은 Phase 3F-3 내부 구현이 아니라 별도 backlog로 관리한다.

테스트 계획:

- fixture 기반 symbol normalize.
- fixture 기반 trading calendar normalize.
- fixture 기반 corporate action normalize.
- 기존 `symbol_master`, `trading_calendar`, `corporate_actions`와 충돌 없는 upsert 계획 검증.
- 외부 네트워크 호출 없음.

## Phase 3F-4: Data Freshness/Quality Summary

상태: 대기

목표:

- read-only provider 상태와 기존 import 품질 정보를 한 화면에서 확인한다.

범위:

- latest date.
- stale source.
- missing row.
- duplicate summary.
- source별 freshness.
- `/data` UI read-only panel.

API contract:

| Method | Path | 설명 |
|---|---|---|
| `GET` | `/api/data/quality-summary` | 데이터 freshness/quality/safety 요약 |

응답 후보 필드:

- `latest_trade_date`
- `source_freshness`
- `missing_rows`
- `duplicate_summary`
- `quality_counts`
- `safety_counts`

테스트 계획:

- seeded DB summary 값 검증.
- duplicate quality code 집계 검증.
- summary 조회가 DB mutation을 만들지 않는지 검증.
- `/data` UI lint/typecheck/build 검증.
- `orders_count == 0`, `paper_* == 0` 유지.

## Phase 3F 공통 검증 명령

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
npm.cmd audit --audit-level=moderate
```

필요 시 fresh server `8010/3010`으로 `/data` browser smoke를 수행한다.

## 다음 Phase 연결

- Phase 3G: gap-aware stop execution, liquidity participation limit, partial fill model, delisted symbol handling, corporate action adjusted price, portfolio cash/position state, overlapping trades control, regime metrics, Sharpe/Sortino/Calmar/turnover, walk-forward validation.
- Phase 3H: momentum rank, relative strength leader, new high breakout, Darvas box, pullback 20EMA, weekly stage analysis.
- Phase 3I: weekly return, YTD return, benchmark return, setup별 win rate/expectancy, failed trades review, filter attribution, regime diagnostics, parameter drift.
- Phase 3J: max open positions, gross/sector/symbol/strategy exposure, daily loss limit, event risk hold, gap risk estimate.
- Phase 4A: broker paper adapter. 실제 live가 아니라 paper부터 다루며 별도 승인 전까지 paper mutation도 구현하지 않는다.
- Phase 4B: live gate design. 실주문/실계좌 연결은 별도 승인 전까지 구현하지 않는다.
