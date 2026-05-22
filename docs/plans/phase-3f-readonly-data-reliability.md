# Phase 3F: Read-only Data Reliability

Phase 3F는 주문 기능 확장보다 먼저 데이터 read-only adapter 기반과 데이터 신뢰성을 보강하는 단계다.

## 기준

- Phase 3E-1 paper trading safety shell은 완료 상태로 유지한다.
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
- 신규 fetch 실행 endpoint를 만들지 않는다.
- `orders_count == 0`, `paper_* == 0` 유지.

## Phase 3F-2: KIS Read-only Daily OHLCV Adapter

상태: 완료

목표:

- KIS 국내주식 일봉 OHLCV 조회 후보 adapter를 fixture 기반으로 구현한다.
- 주문/계좌/잔고/체결 API와 분리한다.
- `network_enabled=false` 기본값을 유지한다.
- 명시 config와 환경변수 조건이 없으면 실제 호출을 차단한다.

범위:

- `KisMarketDataProvider` daily OHLCV raw response normalize.
- fixture 기반 normalize 테스트.
- normalize 결과를 기존 external preview/confirm flow로만 연결.
- preview 단계에서는 import run과 quality check만 생성.
- confirm 전에 market table mutation 없음.
- confirm 후에만 `daily_ohlcv` upsert.

제외 범위:

- KIS 주문 API.
- 계좌, 잔고, 체결 API.
- token 발급, token refresh, token cache 저장.
- websocket, live broker, broker network call.

## Phase 3F-3: KRX Index/Sector/Symbol/Calendar/Corporate Action Source

상태: 완료

목표:

- KRX 계열 데이터를 주문과 무관한 read-only source로 분리한다.
- fixture schema와 raw-to-existing-model-column normalize 순수 함수만 구현한다.
- 실제 KRX network call, 신규 endpoint, DB write flow는 만들지 않는다.

범위:

- KRX index/sector fixture schema.
- KRX symbol master fixture schema.
- KRX trading calendar fixture schema.
- KRX corporate action fixture schema.
- 각 raw fixture를 기존 SQLAlchemy model 컬럼 payload `list[dict]`로 변환하는 순수 함수.
- 기존 `GET /api/data/read-only/providers` contract regression.
- 기존 KRX source 4종의 capability/asset_scope 보강.

DB 변경 원칙:

- 기존 `symbol_master`, `index_ohlcv`, `sector_ohlcv`, `trading_calendar`, `corporate_actions` 테이블을 우선 사용한다.
- Phase 3F-3에서는 DB schema 변경, Alembic/migration, runtime upsert flow를 구현하지 않는다.
- 부족한 컬럼/테이블이 필요하면 별도 migration 계획으로 분리한다.

완료 검증:

- fixture top-level schema 검증.
- index/sector, symbol master, trading calendar, corporate action normalize output 검증.
- fixture sensitive field 부재 검증.
- no network/no token/no mutation 검증.
- KIS execution routes 404 유지.
- `POST /api/paper/orders`, `POST /api/paper/fill-simulator/run` 404 유지.
- targeted pytest, 전체 backend pytest, frontend lint/typecheck/build/audit 통과.

## Phase 3F-4: Data Freshness/Quality Summary

상태: 완료

목표:

- 기존 DB와 provider status만 조회해 data freshness/quality/safety summary를 제공한다.
- `/data` 화면에서 read-only summary panel을 확인할 수 있게 한다.
- 실제 network call, token/cache, broker/order path는 계속 금지한다.

구현 범위:

- `backend/app/services/data_quality_summary_service.py` 신규 추가.
- `GET /api/data/quality-summary` 추가.
- `latest_trade_date`, source freshness, missing rows, duplicate summary, quality counts, safety counts 계산.
- frontend `/data`의 `Freshness & Quality Summary` panel 추가.
- `backend/tests/test_phase3f4_data_quality_summary.py` 추가.

API contract:

| Method | Path | 설명 |
|---|---|---|
| `GET` | `/api/data/quality-summary` | 데이터 freshness/quality/safety 요약 |

Query:

- `market`: 기본 `KR`
- `venue`: 기본 `KRX`
- `lookback_trading_dates`: 기본 `30`, 범위 `1..252`

Response 주요 필드:

- `market`
- `venue`
- `latest_trade_date`
- `row_counts`
- `source_freshness`
- `missing_rows`
- `duplicate_summary`
- `quality_counts`
- `safety_counts`

계산 규칙:

- `latest_trade_date`: `daily_ohlcv.trade_date` max, `venue` 필터 적용.
- disabled source는 `freshness_status=DISABLED`.
- enabled daily OHLCV source에 confirmed import run이 없으면 `NO_CONFIRMED_RUN`.
- enabled read-only reference source에 confirmed import run이 없으면 `NOT_APPLICABLE`.
- `trading_calendar` open date가 있으면 calendar 기준 missing rows 계산, 없으면 observed `daily_ohlcv` date 기준 fallback.
- latest trade date missing symbol sample은 최대 20개.
- duplicate summary는 physical duplicate와 `data_quality_checks` duplicate code를 분리.
- safety counts는 `orders_count`, `paper_*` count 0과 token/network/adapter flags false를 반환.

검증 결과:

- `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3f4_data_quality_summary.py -q`: 6 passed.
- `.\.venv\Scripts\python.exe -m pytest backend/tests`: 79 passed.
- `npm.cmd run lint`: 통과.
- `npm.cmd exec tsc -- --noEmit`: 통과.
- `npm.cmd run build`: 통과.
- `npm.cmd audit --audit-level=moderate`: found 0 vulnerabilities.
- fresh `8010/3010` `/data` Playwright screenshot smoke 통과.

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
- Phase 4A: broker paper adapter. 실제 live가 아니라 paper부터 다루며 별도 승인 전까지 paper mutation은 구현하지 않는다.
- Phase 4B: live gate design. 실주문 설계와 연결은 별도 승인 전까지 구현하지 않는다.
