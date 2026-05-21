# Validation

## 최신 검증 결과

검증 시각: 2026-05-21

| 항목 | 결과 | 명령/도구 |
|---|---|---|
| Phase 2 browser QA | 통과 | Playwright + Microsoft Edge, `http://127.0.0.1:3001` |
| Post-restore browser smoke | 통과 | `/dashboard`, `/reports`, `/backtest` |
| Backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests` |
| Frontend lint | 통과 | `npm.cmd run lint` |
| Frontend production build | 통과 | `npm.cmd run build` |
| Frontend npm audit | 통과 | `npm.cmd audit --audit-level=moderate` |
| Frontend type check | 통과 | `npm.cmd exec tsc -- --noEmit` |

Browser 플러그인은 세션에 있었지만 Node REPL 실행 도구가 노출되지 않아 Playwright fallback으로 실제 브라우저 QA를 수행했다.

## 수동 QA 결과

대상 주소:

| 구분 | URL |
|---|---|
| Backend | `http://127.0.0.1:8001` |
| Frontend | `http://127.0.0.1:3001` |

확인 결과:

| 영역 | 결과 |
|---|---|
| `/dashboard` 접속 | 통과 |
| Backend Health 카드 | 통과 |
| Data Status 카드 | 통과 |
| Seed Sample Data | `POST /api/data/seed` 200 |
| Recompute Indicators | `POST /api/indicators/recompute` 200 |
| Run Screener | `POST /api/screener/run` 200 |
| Generate Daily Report | `POST /api/reports/daily` 200 |
| Run Backtest | `POST /api/backtest/run` 200 |
| Preview Mock Order | `POST /api/broker/orders/preview` 200 |
| Preview 후 주문 생성 여부 | `orders_count == 0` |
| `/screener` 필터 | `strategy_name`, `passed`, `grade`, `symbol/name` 검색 통과 |
| `/screener` 정렬 | `total_score`, `reward_risk_ratio` desc 정렬 통과 |
| `/screener` 상세 | row 상세 패널, `pass_flags`, `failed_conditions` 접기/펼치기 통과 |
| `/reports` | 목록, preview, raw markdown, 다운로드 통과 |
| Markdown UTF-8 | 다운로드 파일 UTF-8 decode 및 한글 포함 확인 |
| `/backtest` | run 목록, metrics 카드, 전략 비교 table 통과 |
| `/portfolio` | mock risk 값 및 `broker_mode=mock` 표시 통과 |
| `/settings` | `app.yaml`, `strategies.yaml`, `risk.yaml`, `backtest.yaml` read-only 표시 통과 |
| Settings 민감 키워드 | `secret`, `token`, `password`, `api_key` 미노출 |

브라우저 QA 중 관련 request failure 0건, 관련 HTTP error 0건이다. CSV validation용 400 응답 3건과 Markdown 다운로드 시 브라우저가 기록하는 정상 `ERR_ABORTED`는 expected event로 분리했다.

## CSV Import QA

| 케이스 | 결과 |
|---|---|
| sample CSV 다운로드 | 통과 |
| sample CSV 업로드 | 통과 |
| import 결과 표시 | 통과 |
| count 필드 표시 | `inserted_count`, `updated_count`, `skipped_count`, `error_count` 표시 |
| 첫 sample 업로드 | `inserted_count=1`, `updated_count=0`, `skipped_count=0`, `error_count=0` |
| import 후 Recompute Indicators | API 200 |
| import 후 Run Screener | API 200 |
| 필수 컬럼 누락 CSV | 400 및 `CSV 필수 컬럼 누락` 표시 |
| `high < low` CSV | 400 및 `high가 low보다 작음` 표시 |
| 음수 가격/거래량 CSV | 400 및 `가격 또는 거래량 음수` 표시 |
| 중복 `symbol + trade_date` | `inserted_count=0`, `updated_count=1` |

## 수정한 QA 버그

| 파일 | 수정 내용 |
|---|---|
| `backend/app/main.py` | 3000/3001 로컬 프런트엔드 origin CORS 허용 |
| `backend/tests/test_api_smoke.py` | CORS preflight 테스트 추가 |
| `backend/tests/conftest.py` | pytest가 런타임 `app.db`를 drop하지 않도록 `backend/data/test_app.db` 사용 |
| `frontend/app/dashboard/DashboardClient.tsx` | CSV import 결과 라벨을 `*_count`로 표시 |
| `frontend/package.json`, `frontend/package-lock.json` | `postcss@8.5.15` override로 npm audit advisory 제거 |
| `.gitignore` | `.env*.local` 무시 |
| `frontend/.env.local.example` | 8000 기본값 및 8001 포트 충돌 예시 추가 |
| `frontend/.env.local` | 현재 QA용 `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001` |

## 검증 명령 결과

### Backend pytest

```text
collected 21 items
21 passed in 72.11s
```

### Frontend lint

```text
eslint . --max-warnings=0
통과
```

### Frontend build

```text
Next.js 16.2.6 (Turbopack)
Environments: .env.local
Compiled successfully

Route (app)
/
/_not-found
/backtest
/dashboard
/portfolio
/reports
/screener
/settings
```

### Frontend npm audit

```text
found 0 vulnerabilities
```

### Frontend type check

```text
npm.cmd exec tsc -- --noEmit
통과
```

## Port / Env 점검

기존 `8000/3000` 포트에는 이전 서버가 떠 있을 수 있어 이번 QA는 `8001/3001`로 수행했다.

| 항목 | 상태 |
|---|---|
| Backend `8001` | 실행 확인 |
| Frontend `3001` | 실행 확인 |
| `NEXT_PUBLIC_API_BASE_URL` | `frontend/.env.local`에서 `http://127.0.0.1:8001` |
| build env 반영 | `.next/static` client chunk에 `http://127.0.0.1:8001` 반영 확인 |
| post-build smoke | `POST_BUILD_BROWSER_SMOKE_OK` |
| post-restore smoke | `POST_RESTORE_BROWSER_SMOKE_OK` |

포트 충돌 시 실행법과 `NEXT_PUBLIC_API_BASE_URL` 설정법은 `README.md`에 기록했다.

## 최종 DB row count

검증 후 런타임 DB를 dashboard/reports/backtest가 바로 보이는 checkpoint 상태로 복구했다.

| table/status | count |
|---|---:|
| symbol_count | 15 |
| daily_ohlcv_count | 4,800 |
| index_ohlcv_count | 320 |
| sector_ohlcv_count | 2,880 |
| fundamentals_count | 30 |
| indicator_snapshot_count | 4,800 |
| screen_results_count | 45 |
| reports_count | 1 |
| backtest_runs_count | 1 |
| orders_count | 0 |

최신 기준일:

| field | value |
|---|---|
| latest_trade_date | 2026-05-20 |
| latest_indicator_date | 2026-05-20 |
| latest_screen_date | 2026-05-20 |

## 남은 검증 제외 범위

- 외부 API 연동
- 실제 주문, 주문 취소, 체결
- paper/live broker
- 실시간 websocket
- AI 예측 모델
- 모바일 viewport 상세 QA
