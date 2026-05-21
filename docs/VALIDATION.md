# Validation

## 최신 검증 결과

검증 시각: 2026-05-21

Checkpoint: `MVP v0.5 Phase 3C KIS read-only foundation`

작업 브랜치: `phase-3c-kis-readonly-foundation`

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests` |
| Frontend lint | 통과 | `npm.cmd run lint` |
| Frontend typecheck | 통과 | `npm.cmd exec tsc -- --noEmit` |
| Frontend production build | 통과 | `npm.cmd run build` |
| Frontend npm audit | 통과 | `npm.cmd audit --audit-level=moderate` |
| Browser/API smoke | 통과 | backend `8002`, frontend `3010`, Playwright headless + API assertions |

## Phase 3C API

| Method | Path | 검증 |
|---|---|---|
| `GET` | `/api/kis/status` | pytest + browser |
| `GET` | `/api/kis/config` | pytest |
| `POST` | `/api/kis/config/validate` | pytest |
| `POST` | `/api/data/external/preview-daily-ohlcv` with `source_id=kis_market_data` | disabled 차단 pytest, mock fixture preview pytest |
| `POST` | `/api/data/external/confirm-import` | KIS mock fixture confirm pytest |

기존 Phase 3A/3B API 회귀도 pytest와 browser smoke에서 함께 확인했다.

## KIS Read-only Foundation

- `kis_market_data`는 `provider_type=external_market_data`, `provider_name=kis`인 read-only market data source다.
- 기본값은 `enabled=false`, `network_enabled=false`, `read_only_enabled=false`, `manual_preview_only=true`다.
- `kis_openapi`는 `broker_placeholder`로 유지되며 Phase 3D 이후 broker adapter용 placeholder다.
- `KisMarketDataProvider`는 Phase 3C에서 실제 KIS network call을 수행하지 않는 skeleton이다.
- `MockKisMarketDataProvider`는 KIS `inquire-daily-itemchartprice` 형태 fixture를 생성하고 표준 `daily_ohlcv` row로 normalize한다.
- `KisBrokerAdapter`는 DI와 route에 연결하지 않았다.

## Secret / Redaction 검증

- `kis_market_data` source에 `app_key`, `app_secret`, `token`, `access_token`, `refresh_token`, `approval_key`, `account`, `account_no`, `cano`, `hts_id`, `password`, `authorization` 필드가 없다.
- `/api/kis/status`, `/api/kis/config`, `/api/kis/config/validate`, `/api/settings` 응답에 sentinel secret 값이 노출되지 않음을 pytest와 browser/API smoke로 확인했다.
- `app_key_configured`, `app_secret_configured`는 boolean만 반환한다.
- token cache 파일은 생성하지 않았다.
- Git 추적 파일에 sentinel secret 값이 없음을 pytest로 확인했다.

## Data Quality / Preview-Confirm 검증

- `kis_market_data` disabled 상태에서 external preview 요청은 `400`으로 차단된다.
- KIS mock fixture preview는 `import_runs`와 `data_quality_checks`만 기록한다.
- preview 후 `symbol_master`, `daily_ohlcv`, `indicator_snapshot`, `screen_results`, `reports`, `backtest_runs`, `orders` count가 바뀌지 않음을 pytest로 확인했다.
- confirm 후에만 `daily_ohlcv` upsert가 발생한다.
- KIS mock preview/confirm 후에도 `orders_count == 0`을 유지한다.
- 기존 `external_yfinance` mock preview와 CSV validate/confirm 회귀 테스트가 통과했다.

## Browser Smoke

| Route | H1 |
|---|---|
| `/` | Dashboard |
| `/dashboard` | Dashboard |
| `/data` | Data Quality |
| `/screener` | Screener |
| `/reports` | Reports |
| `/backtest` | Backtest |
| `/portfolio` | Portfolio / Risk |
| `/settings` | Settings |

추가 확인:

- `/data`에 `KIS Read-only Status` panel 표시
- `kis_market_data`, `app_key_configured`, `app_secret_configured`, `token_cache_enabled`, `Phase 3C read-only foundation only` 표시
- `/api/kis/status`, `/api/kis/config`, `/api/kis/config/validate`, `/api/settings` sentinel secret 미노출
- `source_id=kis_market_data` external preview는 disabled 상태에서 HTTP 400으로 차단
- token cache 파일 없음
- UI smoke 전후 `orders_count == 0`
- console error 0
- request failure 0
- API HTTP error 0

## 명령 결과

### Backend pytest

```text
collected 50 items
50 passed in 286.25s
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
Route (app): /, /dashboard, /data, /screener, /reports, /backtest, /portfolio, /settings
```

### Frontend audit

```text
found 0 vulnerabilities
```

## 최종 DB 상태

Browser smoke 기준 backend `http://127.0.0.1:8002`:

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

| field | value |
|---|---|
| latest_trade_date | 2026-05-20 |
| latest_indicator_date | 2026-05-20 |
| latest_screen_date | 2026-05-20 |

## 제외 범위

- KIS 실제 API 호출
- KIS app key/app secret/account/token 저장
- token cache 생성
- KIS 주문 API
- KIS broker route
- paper/live broker
- 실제 주문 또는 모의 주문
- 주문 row 생성
- 계좌/잔고/체결 조회
- 실시간 websocket
- 자동매매 스케줄러
