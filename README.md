# Stock Analyst Auto Trading

상위권 트레이더형 주식 분석 및 자동매매 보조 시스템 MVP입니다.

현재 checkpoint는 MVP v0.2 / Phase 2 Web Flow입니다. 실제 주문, 외부 API 연동, live broker, paper broker 체결은 구현하지 않습니다.

## Phase 2 현재 기능

- FastAPI 백엔드 상태 및 데이터 row count 조회
- deterministic 한국장 샘플 데이터 seed
- CSV import 기반 `daily_ohlcv` upsert
- 지표 재계산, 스크리너 실행, 일간 Markdown 리포트 생성
- `trend_breakout`, `vcp_breakout`, `canslim_lite` 조건검색 결과 조회
- Screener 필터: `strategy_name`, `passed`, `grade`, `symbol/name` 검색
- Screener 정렬: `total_score`, `reward_risk_ratio`
- Reports 목록, Markdown preview/raw/download
- Backtest run 목록, metrics 카드, 전략 비교 table
- Portfolio mock/synthetic risk summary
- `backend/config/*.yaml` read-only Settings 화면
- Mock Broker preview-only 주문 검토

## Backend 실행

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

포트 `8000`이 이미 사용 중이면 `8001`로 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001
```

## Frontend 실행

```powershell
cd frontend
npm.cmd install
npm.cmd run build
npm.cmd run start -- --hostname 127.0.0.1 --port 3000
```

포트 `3000`이 이미 사용 중이면 `3001`로 실행합니다.

```powershell
npm.cmd run build
npm.cmd run start -- --hostname 127.0.0.1 --port 3001
```

## NEXT_PUBLIC_API_BASE_URL

기본 API 주소는 `http://localhost:8000`입니다.

백엔드를 `8001`에서 실행할 때는 `frontend/.env.local`에 다음 값을 넣고 다시 build/start 합니다. Next.js의 `NEXT_PUBLIC_*` 값은 production build에 포함되므로 변경 후 `npm.cmd run build`가 필요합니다.

```powershell
cd frontend
Copy-Item .env.local.example .env.local
notepad .env.local
```

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001
```

현재 QA 기준 주소는 다음과 같습니다.

| 구분 | URL |
|---|---|
| Backend | `http://127.0.0.1:8001` |
| Frontend | `http://127.0.0.1:3001` |

## CSV Import

필수 컬럼:

| 컬럼 | 설명 |
|---|---|
| `symbol` | 종목 코드 |
| `trade_date` | 거래일, 날짜 파싱 가능 형식 |
| `open` | 시가 |
| `high` | 고가 |
| `low` | 저가 |
| `close` | 종가 |
| `volume` | 거래량 |

선택 컬럼:

| 컬럼 | 기본값 |
|---|---|
| `turnover_value` | `close * volume` |
| `market` | `KRX` |
| `provider` | `csv` |
| `adj_close` | `close` |

검증 규칙:

- 필수 컬럼 누락 시 import 실패
- `high < low`이면 import 실패
- 가격 또는 거래량이 음수이면 import 실패
- 동일 `symbol + trade_date`는 insert가 아니라 update 처리

## Mock Broker 주의사항

- `Preview Mock Order`는 검토용 preview만 생성합니다.
- `orders` row를 생성하지 않습니다.
- `orders_count == 0`은 Phase 2 QA 기준입니다.
- 실제 주문, 주문 취소, 체결, 계좌 자금 이동 기능은 없습니다.

## 검증

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests
cd frontend
npm.cmd run lint
npm.cmd run build
npm.cmd audit --audit-level=moderate
npm.cmd exec tsc -- --noEmit
```

상세 검증 결과는 `docs/VALIDATION.md`를 확인합니다.
