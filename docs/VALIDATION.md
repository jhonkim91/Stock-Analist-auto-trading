# Validation

## 최신 검증 결과

검증 시각: 2026-05-21

Checkpoint: `MVP v0.4 Phase 3B provider-neutral external data`

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests` |
| Frontend lint | 통과 | `npm.cmd run lint` |
| Frontend typecheck | 통과 | `npm.cmd exec tsc -- --noEmit` |
| Frontend production build | 통과 | `npm.cmd run build` |
| Frontend npm audit | 통과 | `npm.cmd audit --audit-level=moderate` |
| Browser smoke | 통과 | Browser Node 실행 도구 미노출로 Node Playwright fallback, backend `8002`, frontend `3010` |

## Phase 3B API

| Method | Path | 검증 |
|---|---|---|
| `GET` | `/api/data/external/providers` | pytest + browser |
| `POST` | `/api/data/external/preview-daily-ohlcv` | pytest + browser |
| `POST` | `/api/data/external/confirm-import` | pytest + browser |
| `GET` | `/api/data/external/fetch-runs` | pytest + browser |
| `GET` | `/api/data/external/fetch-runs/{run_id}` | pytest |

기존 Phase 3A API도 회귀 검증했습니다.

| Method | Path | 검증 |
|---|---|---|
| `GET` | `/api/data/sources` | pytest + browser |
| `GET` | `/api/data/import-runs` | pytest + browser |
| `GET` | `/api/data/import-runs/{run_id}` | pytest + browser |
| `POST` | `/api/data/validate-csv` | pytest |
| `POST` | `/api/data/import-csv-confirmed` | pytest |
| `GET` | `/api/data/quality` | pytest + browser |
| `GET` | `/api/data/quality/{run_id}` | pytest + browser |
| `POST` | `/api/data/import/daily-ohlcv` | legacy 호환 pytest |

## Provider-Neutral 검증

- `external_yfinance`는 `provider_type=external_market_data`, `provider_name=yfinance`로 동작합니다.
- `external_yfinance`는 `unknown_symbol_policy=warn_and_create_on_confirm`입니다.
- `external_yfinance`는 `network_enabled=false`에서 `provider_metadata.provider_mode=mock`, `provider_metadata.data_origin=deterministic_mock`을 기록합니다.
- `network_enabled=false`에서 실제 yfinance network fetch가 호출되지 않음을 monkeypatch 테스트로 검증했습니다.
- `kis_openapi`는 disabled placeholder이며 fetch 요청이 400으로 차단됩니다.
- `kis_openapi`는 `unknown_symbol_policy=reject`를 유지합니다.
- KIS placeholder에는 `app_key`, `app_secret`, `token`, `password`, `account_no`, `hts_id`, `access_token`, `refresh_token` 필드가 없습니다.
- Settings 응답에도 KIS secret 값이 노출되지 않습니다.
- `external_symbol_mapping` 매핑이 없으면 `SYMBOL_MAPPING_FAILED`를 기록하고 `daily_ohlcv`에는 쓰지 않습니다.

## Preview/Confirm 불변식

External preview 전후 아래 market data table count 불변을 pytest로 검증했습니다.

- `symbol_master`
- `daily_ohlcv`
- `indicator_snapshot`
- `screen_results`
- `reports`
- `backtest_runs`
- `orders`

Preview 단계 허용 변화:

| 테이블 | 결과 |
|---|---|
| `import_runs` | external preview마다 `+1` |
| `data_quality_checks` | 검증 결과에 따라 `+N` |

Confirm 후에만 `daily_ohlcv` insert/update가 발생합니다. Browser smoke에서 `external_yfinance` preview 후 confirm 결과 `daily_ohlcv +3`, `symbol_master +1`, `orders_count == 0`을 확인했습니다.

## Data Quality 테스트

Phase 3A taxonomy 회귀:

- 정상 CSV validation
- 필수 컬럼 누락
- 가격/거래량 숫자 검증
- batch duplicate
- provider mismatch error
- adjusted close missing warning
- weekend date error
- confirm 재시도 `409`

Phase 3B 추가 검증:

- provider-neutral API가 `source_id`로 동작
- `external_yfinance` preview
- `kis_openapi` disabled 차단
- `SYMBOL_MAPPING_FAILED`
- `PROVIDER_ROW_COUNT_MISMATCH`
- `DATE_RANGE_TOO_LARGE`
- `network_enabled=false` network 차단
- mock provider fixture 기반 preview
- external confirm 후 insert/update
- external confirm 재시도 `409`
- CSV run을 external confirm으로 confirm하려 하면 `400`

## Browser Smoke

Browser 플러그인의 Node 실행 도구가 노출되지 않아 Node Playwright fallback으로 Chromium headless smoke를 수행했습니다.

| Route | H1 |
|---|---|
| `/data` | Data Quality |

추가 확인:

- External Daily OHLCV Preview panel 표시
- `network_enabled=false` mock/fixture 안내 문구 표시
- `external_yfinance` provider-neutral source 표시
- `kis_openapi` disabled placeholder 표시
- Fetch Preview 후 `can_confirm=true`
- provider metadata에 `provider_mode=mock`, `data_origin=deterministic_mock` 표시
- Confirm External Import 후 Import History에 `provider=yfinance`, `status=confirmed` 표시
- API request failure 없음
- Browser smoke 후 `orders_count == 0`

## 명령 결과

### Backend pytest

```text
collected 43 items
43 passed in 101.54s
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
| symbol_master | 16 |
| daily_ohlcv | 4,803 |
| index_ohlcv | 320 |
| sector_ohlcv | 2,880 |
| fundamentals_pti | 30 |
| indicator_snapshot | 4,800 |
| screen_results | 45 |
| reports | 1 |
| backtest_runs | 3 |
| orders | 0 |
| import_runs | 23 |
| data_quality_checks | 122 |
| external_symbol_mapping | 32 |

| field | value |
|---|---|
| latest_trade_date | 2026-05-21 |
| latest_indicator_date | 2026-05-20 |
| latest_screen_date | 2026-05-20 |

## 제외 범위

- KIS 실제 API 호출
- KIS app key/app secret 저장
- KIS 계좌번호 저장
- KIS 주문 API 구현
- paper/live broker
- 실제 주문
- 주문 row 생성
- 실시간 websocket
- 자동매매 스케줄러
- AI 예측 모델
- yfinance production-grade 데이터 보장
- 수정주가 완전 처리
- 거래정지/상장폐지 완전 처리
