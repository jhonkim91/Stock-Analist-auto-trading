# Validation

## 최신 검증 결과

검증 시각: 2026-05-21

Checkpoint: `MVP v0.3 Phase 3A data quality`

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests` |
| Frontend lint | 통과 | `npm.cmd run lint` |
| Frontend typecheck | 통과 | `npm.cmd exec tsc -- --noEmit` |
| Frontend production build | 통과 | `npm.cmd run build` |
| Frontend npm audit | 통과 | `npm.cmd audit --audit-level=moderate` |
| Browser smoke | 통과 | Microsoft Edge + Playwright fallback, backend `8010`, frontend `3010` |

## Phase 3A API

| Method | Path | 검증 |
|---|---|---|
| `GET` | `/api/data/sources` | pytest + browser |
| `GET` | `/api/data/import-runs` | pytest + browser |
| `GET` | `/api/data/import-runs/{run_id}` | pytest + browser |
| `POST` | `/api/data/validate-csv` | pytest + browser |
| `POST` | `/api/data/import-csv-confirmed` | pytest + browser |
| `GET` | `/api/data/quality` | pytest + browser |
| `GET` | `/api/data/quality/{run_id}` | pytest + browser |
| `POST` | `/api/data/import/daily-ohlcv` | legacy 호환 pytest |

## 새 DB 테이블

- `data_sources`
- `import_runs`
- `data_quality_checks`
- `external_symbol_mapping`
- `corporate_actions`
- `trading_calendar`

`corporate_actions`와 `trading_calendar`는 Phase 3A placeholder입니다. 수정주가 적용과 실제 휴장일 완전성 처리는 Phase 3B 이후 검토합니다.

## Validate 불변식

`POST /api/data/validate-csv` 전후 아래 market data table count 불변을 pytest로 검증했습니다.

- `symbol_master`
- `daily_ohlcv`
- `index_ohlcv`
- `sector_ohlcv`
- `fundamentals_pti`
- `indicator_snapshot`
- `screen_results`
- `reports`
- `backtest_runs`
- `orders`

허용된 변화는 아래뿐입니다.

| 테이블 | 결과 |
|---|---|
| `import_runs` | validate마다 `+1` |
| `data_quality_checks` | 검증 결과에 따라 `+N` |

Confirm 전에는 `daily_ohlcv`와 `symbol_master`가 변경되지 않으며, confirm 후에만 insert/update가 발생함을 검증했습니다.

## Confirm 결과

검증 항목:

- 정상 run confirm 성공
- confirm 성공 후 `inserted_count`, `updated_count`, `skipped_count` 확정
- `can_confirm=false` run confirm 실패
- 이미 `confirmed`인 run 재confirm `409`
- 존재하지 않는 `run_id` confirm `404`
- confirm은 파일 재업로드 없이 `import_runs.staged_rows_json` 사용
- legacy direct import endpoint 호환 유지

## Data Quality 테스트

pytest로 검증한 check:

- 정상 CSV validation
- 필수 컬럼 누락
- `high < low`
- `high < open` 또는 `high < close`
- `low > open` 또는 `low > close`
- 음수 가격
- 음수 volume
- zero volume warning
- 결측치
- 날짜 parse 실패
- batch duplicate
- unknown symbol warning
- provider mismatch error
- adjusted close missing warning
- turnover value missing warning
- weekend date error

고정 check_code taxonomy와 severity `error/warning/info`를 사용합니다.

## Browser Smoke

Browser 플러그인의 Node 실행 도구가 노출되지 않아 Python Playwright fallback으로 Microsoft Edge headless smoke를 수행했습니다.

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

- `/data` source 선택: `csv_krx`
- 정상 CSV validate 성공
- 실패 CSV validate 실패 상태 표시
- validation summary 표시
- preview rows 표시
- quality checks table 표시
- `can_confirm=false`일 때 Confirm 비활성화
- `can_confirm=true`일 때 Confirm 활성화
- Confirm 후 Import History 반영
- Import Run 상세 표시
- Dashboard에서 legacy direct CSV import 대신 `/data` flow 안내 표시
- Dashboard flow: seed -> indicators -> screener -> report -> backtest -> mock preview
- browser smoke 후 `orders_count == 0`

## 명령 결과

### Backend pytest

```text
collected 37 items
37 passed in 115.85s
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

Browser smoke 기준 backend `http://127.0.0.1:8010`:

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
| backtest_runs | 2 |
| orders | 0 |
| data_sources | 0 |
| import_runs | 11 |
| data_quality_checks | 56 |

| field | value |
|---|---|
| latest_trade_date | 2026-05-20 |
| latest_indicator_date | 2026-05-20 |
| latest_screen_date | 2026-05-20 |

## 제외 범위

- 외부 API 호출
- 실제 주문, 주문 취소, 체결
- 주문 row 생성
- paper/live broker
- 실시간 websocket
- AI 예측 모델
- 수정주가 실제 적용
- 실제 거래소 휴장일 완전성 처리

대용량 CSV는 Phase 3B 이후 staging table 분리를 검토합니다.
