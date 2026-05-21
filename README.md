# Stock Analyst Auto Trading

주식 분석과 자동매매 보조 흐름을 검증 가능한 MVP 형태로 구현한 FastAPI + Next.js 프로젝트입니다.

현재 checkpoint는 `MVP v0.7 Phase 3E-1 paper preview safety scaffold`입니다. 실제 주문, paper order create, paper fill/position 변경, live broker, cancel, fill, websocket 연결, KIS 실제 API 호출, 자동매매 스케줄러, AI 예측 모델은 구현하지 않습니다.

PR #3 `Phase 3C: Add KIS read-only foundation`과 PR #4 `Phase 3D: KIS broker safety scaffold`는 `main`에 merge 완료됐습니다. Phase 3D merge commit은 `2d5a146c8b89c355397eec458fd7343412e92c6e`입니다.

## Phase 3D 최종 기록

| 항목 | 값 |
|---|---|
| Status | Completed |
| PR | #4 |
| Merge commit | `2d5a146c8b89c355397eec458fd7343412e92c6e` |
| Post-merge docs commit | `127527ecec905227b15b5654dc3615f21fd244ec` |
| Current HEAD | `8e503332c23875bd82754ffd29314b65e1235089` |

최종 검증 결과는 backend pytest 56 passed, frontend lint/typecheck/build/audit 통과, API smoke 통과, browser route smoke 통과입니다. KIS execution routes는 404를 유지했고, `orders_count == 0`, `token_issued == false`, token cache 미생성, 외부 network call 미수행, adapter order/network call 미수행, audit DB persistence 비활성, sensitive value 미노출을 확인했습니다.

## Phase 3E-1 기록

Phase 3E-1은 paper preview safety scaffold까지만 구현했습니다.

- `backend/config/paper.yaml`: disabled/fail-closed 기본값
- `/api/paper/status`: paper control plane disabled 상태 요약
- `/api/paper/orders/preview`: DB write 없는 deny preview
- `PaperTradingService`, `LocalPaperSimulator` skeleton
- `paper_orders`, `paper_fills`, `paper_positions`, `paper_audit_events` 모델 정의
- frontend `/paper`: status와 preview deny 표시

이번 Phase에서 구현하지 않은 범위:

- `POST /api/paper/orders`
- `POST /api/paper/fill-simulator/run`
- paper order create DB write
- paper fill 생성 또는 paper position 변경
- cancel API
- KIS 주문, KIS paper API, KIS network call, token 발급/refresh/cache/DB 저장

최신 검증 결과는 backend pytest 60 passed, frontend lint/typecheck/build/audit 통과, `/paper` browser smoke 통과입니다. `orders_count == 0`, `paper_*` row 0, KIS execution routes 404, token/cache/network/adapter call 미수행을 확인했습니다.

## Phase 3D 기능

- Phase 3A CSV validate/confirm flow 유지
- Phase 3B provider-neutral external daily OHLCV preview/confirm flow 유지
- Phase 3C KIS read-only foundation 유지
- Phase 3D broker safety scaffold 추가
  - `backend/config/broker.yaml`: disabled/fail-closed 기본값
  - `/api/broker/status`: broker 안전 상태 요약
  - `/api/broker/orders/preview`: dry-run preview only
  - `TokenLifecycleService`: status-only, token 발급/refresh/cache/DB 저장 없음
  - `BrokerAuditService`: sanitize scaffold, DB persistence 비활성
  - `OrderRiskGate`: buy/sell preview deny reason code 반환
- KIS execution route 미등록 유지
  - `/api/kis/orders/*`: 404
  - `/api/kis/broker/*`: 404
  - `/api/kis/websocket/*`: 404

## Broker Safety Contract

`/api/broker/status`와 `/api/broker/orders/preview`는 항상 다음 안전 값을 보장합니다.

| field | value |
|---|---|
| `mode` | `disabled` 또는 `safety_scaffold` |
| `can_submit` | `false` |
| `preview_only` | `true` |
| `order_created` | `false` for preview |
| `token_issued` | `false` |
| `network_call_performed` | `false` |
| `adapter_selected` | boolean |
| `adapter_name` | `kis_openapi` |
| `adapter_order_call_performed` | `false` |
| `adapter_network_call_performed` | `false` |

Sell preview는 기존 long position 청산 검토 전용입니다. 기존 포지션이 없거나 보유 수량을 초과하면 deny하며, 신규 short sell은 지원하지 않습니다.

`backend/config/broker.yaml` 원문과 broker summary는 `/api/settings`에 노출하지 않습니다. broker 안전 상태 요약은 `/api/broker/status`에서만 반환합니다.

## Import Flow

CSV flow:

1. `POST /api/data/validate-csv`
2. `POST /api/data/import-csv-confirmed`

External flow:

1. `POST /api/data/external/preview-daily-ohlcv`
2. `POST /api/data/external/confirm-import`

Preview 단계는 market data table을 직접 변경하지 않습니다. 허용되는 write는 `import_runs +1`, `data_quality_checks +N`뿐입니다.

Confirm은 `run_id`만 받으며 파일 또는 provider를 다시 조회하지 않습니다. `import_runs.staged_rows_json`을 transaction으로 `daily_ohlcv`에 반영합니다.

## External Provider 정책

`yfinance`는 production-grade 데이터 provider가 아닙니다. 자동매매의 최종 의사결정 데이터 소스로 사용하지 않고, provider-neutral 구조 검증과 manual preview/prototype 용도로만 사용합니다.

- 기본값은 `network_enabled=false`입니다.
- 테스트와 smoke에서는 실제 외부 네트워크 호출을 하지 않습니다.
- API key, secret, token, account 정보는 저장하지 않습니다.
- provider별 symbol mapping은 `external_symbol_mapping`을 반드시 거칩니다.
- mapping이 없으면 `SYMBOL_MAPPING_FAILED` quality check를 생성하고 `daily_ohlcv`에는 쓰지 않습니다.

Symbol mapping 예:

| provider | internal_symbol | provider_symbol |
|---|---|---|
| yfinance | `005930` | `005930.KS` |
| kis | `005930` | `005930` |

## KIS 확장 정책

KIS는 data provider와 broker adapter를 분리합니다.

- `kis_market_data`: read-only market data 후보, 기본 disabled
- `kis_openapi`: broker placeholder, 기본 disabled
- `KisMarketDataProvider`: 실제 KIS 호출 금지 skeleton
- `MockKisMarketDataProvider`: KIS 기간별시세 형태 fixture provider

단계:

- Phase 3C: KIS read-only foundation
- Phase 3D: broker safety scaffold only
- Phase 3E-1: paper preview safety scaffold only, 현재 checkpoint
- Phase 3E-2 후보: paper order create/fill simulator 설계와 구현, 별도 승인 필요
- Phase 3F 후보: live trading gate 설계, 별도 승인 필요
- Phase 3G 후보: websocket/체결통보 설계, 별도 승인 필요

KIS read-only API 후보는 fixture/schema/normalization 설계에만 사용합니다.

| 후보 | 용도 |
|---|---|
| `/uapi/domestic-stock/v1/quotations/inquire-price`, TR `FHKST01010100` | 국내주식 현재가 후보 |
| `/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice`, TR `FHKST03010100` | Phase 3C primary daily_ohlcv fixture |
| `/uapi/domestic-stock/v1/quotations/inquire-daily-price`, TR `FHKST01010400` | 일자별 시세 후보 |
| `/uapi/domestic-stock/v1/quotations/search-stock-info` | 종목 기본정보 후보 |

## Secret 정책

- 실제 KIS app key/app secret/account/token은 저장하지 않습니다.
- `.env.example`에는 placeholder만 둡니다.
- `/api/kis/status`와 `/api/kis/config`는 configured boolean만 반환하며 secret 값을 반환하지 않습니다.
- `/api/kis/config/validate`는 환경변수 존재와 형식만 확인하고 KIS network call, token 발급, token cache 생성을 하지 않습니다.
- `/api/broker/status`와 `/api/broker/orders/preview`는 `token_issued=false`, `network_call_performed=false`를 반환합니다.
- Settings API와 logs에는 secret 값을 출력하지 않습니다.

## 주요 API

| Method | Path | 설명 |
|---|---|---|
| `GET` | `/api/data/status` | 데이터 row count와 최신 기준일 |
| `GET` | `/api/data/sources` | data source 목록 |
| `POST` | `/api/data/validate-csv` | CSV validation preview |
| `POST` | `/api/data/import-csv-confirmed` | validated CSV run confirm |
| `GET` | `/api/data/external/providers` | external-capable provider source 목록 |
| `POST` | `/api/data/external/preview-daily-ohlcv` | external daily OHLCV preview |
| `POST` | `/api/data/external/confirm-import` | external run confirm |
| `GET` | `/api/kis/status` | KIS read-only status |
| `GET` | `/api/kis/config` | KIS redacted config |
| `POST` | `/api/kis/config/validate` | KIS env configured boolean 검증 |
| `GET` | `/api/broker/status` | Phase 3D broker safety status |
| `POST` | `/api/broker/orders/preview` | Phase 3D dry-run preview only |
| `GET` | `/api/paper/status` | Phase 3E-1 paper disabled safety status |
| `POST` | `/api/paper/orders/preview` | Phase 3E-1 paper deny preview only |

## 실행

Backend:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm.cmd install
npm.cmd run build
npm.cmd run start -- --hostname 127.0.0.1 --port 3000
```

포트 충돌 시 backend `8001`, frontend `3001`을 사용합니다. backend 포트를 바꾸면 `frontend/.env.local`의 `NEXT_PUBLIC_API_BASE_URL`을 맞춘 뒤 다시 build해야 합니다.

## 검증

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
npm.cmd audit --audit-level=moderate
```

최신 검증 결과는 `docs/VALIDATION.md`를 확인합니다.

## 안전 제약

- KIS 실제 API 호출 없음
- KIS app key/app secret 저장 없음
- KIS 계좌번호 저장 없음
- KIS token 발급/refresh/cache/DB 저장 없음
- KIS 주문 API 구현 없음
- KIS broker/order/websocket route 등록 없음
- 실제 주문 없음
- paper order create, fill, position 변경, live broker 없음
- cancel/fill/websocket 연결 없음
- 주문 row 생성 없음
- audit DB persistence 없음
- API key/secret/token/password/account/header/raw credential 저장 또는 노출 없음
- Mock/safety broker는 preview-only
- Phase 3D 후에도 `orders_count == 0`
