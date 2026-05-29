# Project Instructions

이 문서는 `Stock-Analist-auto trading` 저장소에서 Codex와 다음 작업자가 반드시 따라야 하는 프로젝트별 지침이다.

## Repo Layout

| 경로 | 역할 |
|---|---|
| `backend/app` | FastAPI 앱, API router, service, repository, model, strategy 코드 |
| `backend/config` | 전략 파라미터, 리스크 한도, 백테스트, 앱 설정 YAML |
| `backend/data` | 로컬 SQLite 런타임 DB와 테스트 DB |
| `backend/reports` | 생성된 Markdown 리포트 |
| `backend/tests` | backend pytest 테스트와 fixture |
| `frontend/app` | Next.js App Router 화면, route, 전역 스타일 |
| `frontend/lib` | frontend 공통 typed API client와 formatting helper |
| `docs` | 검증 결과, 운영 문서, 상세 기록 |
| `Memory.md` | 현재 프로젝트 상태, 최신 검증 결과, 주의 사항의 압축 요약 |
| `README.md` | 사용자가 실행할 수 있는 주요 기능과 실행 가이드 |

## Backend 실행 방법

PowerShell 기준으로 프로젝트 루트에서 실행한다.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

`8000` 포트가 이미 사용 중이면 `8001`을 사용한다.

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001
```

## Frontend 실행 방법

PowerShell 기준으로 `frontend` 디렉터리에서 실행한다. Windows에서는 `npm` 정책 오류를 피하기 위해 `npm.cmd`를 우선 사용한다.

```powershell
cd frontend
npm.cmd install
npm.cmd run build
npm.cmd run start -- --hostname 127.0.0.1 --port 3000
```

`3000` 포트가 이미 사용 중이면 `3001`을 사용한다.

```powershell
npm.cmd run build
npm.cmd run start -- --hostname 127.0.0.1 --port 3001
```

backend를 `8001`에서 실행할 때는 `frontend/.env.local`에 다음 값을 설정한 뒤 다시 build/start 한다.

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001
```

`NEXT_PUBLIC_*` 값은 Next.js production build에 포함되므로 `.env.local` 변경 후 `npm.cmd run build`를 반드시 다시 실행한다.

## Test / Lint / Build 명령어

Backend:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests
```

Frontend:

```powershell
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
npm.cmd audit --audit-level=moderate
```

문서 전용 변경은 관련 heading과 명령어가 반영됐는지 확인하는 것으로 충분하다. 코드, API contract, DB schema, UI 동작을 변경한 경우에는 위 backend/frontend 검증을 함께 실행한다.

## Coding Conventions

- 모든 응답과 작업 로그는 한국어로 작성한다.
- 코드 주석은 한국어로 작성한다.
- 변수명과 함수명은 영어를 사용한다.
- Python은 `snake_case`, TypeScript/JavaScript는 `camelCase`를 사용한다.
- 기존 FastAPI 구조인 `api`, `services`, `repositories`, `models`, `strategies` 경계를 유지한다.
- frontend API 호출은 `frontend/lib/api.ts`의 typed client와 기존 helper를 우선 사용한다.
- 새로 추가하거나 동작을 변경한 공개 함수에는 docstring 또는 JSDoc을 추가한다.
- 복잡한 로직에는 짧은 인라인 주석으로 의도를 남기되, 단순 설명성 주석은 추가하지 않는다.
- 검증 결과는 `docs/VALIDATION.md`와 `Memory.md`에 최신 상태만 압축 기록한다.
- `Memory.md`는 장문 작업 로그가 아니라 현재 상태, 최신 검증 결과, 남은 작업 중심으로 유지한다.

## 절대 하지 말아야 할 것
- Mock Broker preview 과정에서 `orders` row를 생성하지 않는다.
- legacy `orders` row를 paper 주문 저장소로 사용하지 않는다. KIS 모의투자 주문은 `paper_orders`에만 저장한다.
- 실계좌 live 주문, live 주문 취소, live 체결 처리, live fallback은 명시 요청 없이 구현하거나 실행하지 않는다.
- `.env`, API key, token, password, service role key 등 시크릿을 출력하거나 문서에 기록하지 않는다.
- 운영 DB 삭제, 파괴적 migration, 대량 파일 삭제, 이력 변경 작업을 명시 요청 없이 수행하지 않는다.
- `npm audit fix --force`처럼 주요 패키지 downgrade나 파괴적 변경을 유발할 수 있는 명령을 명시 요청 없이 실행하지 않는다.
- 요청 범위를 벗어난 대규모 리팩토링, 파일 구조 개편, 공개 API 변경을 하지 않는다.

## 프로젝트 도메인 규칙

- 전략 파라미터와 리스크 한도는 `backend/config/*.yaml`에서 관리한다.
- 조건검색 결과는 `passed`, `pass_flags`, `failed_conditions`, `reason_summary`를 반드시 저장한다.
- 재무 데이터는 항상 `effective_date <= trade_date` 조건으로만 조회한다.
- 백테스트는 종가 신호 후 다음 거래일 시가 체결을 기본으로 한다.
- 같은 봉에서 stop과 target이 모두 닿으면 stop을 우선한다.
- `/api/settings`는 `backend/config/*.yaml`을 read-only로 보여주며 `.env`나 시크릿 값을 반환하지 않는다.

## 완료 기준

- 요청된 범위가 실제 파일에 반영되어야 한다.
- 공개 API, DB schema, 런타임 로직을 바꿨다면 관련 테스트와 빌드를 통과해야 한다.
- broker/paper 관련 작업은 실행 모드가 `analysis_only`, `telegram_report`, `paper_kis`, `live_disabled` 중 어디에 해당하는지 확인해야 한다.
- `paper_kis` 작업은 `paper_orders`/`paper_fills`/`paper_positions`와 audit log 기준으로 검증하고, live 경로는 계속 차단해야 한다.
- UI 변경은 필요 시 실제 브라우저 smoke로 렌더링과 주요 route를 확인해야 한다.
- `docs/VALIDATION.md`와 `Memory.md`는 최신 상태만 남기도록 압축 갱신해야 한다.
- 실패하거나 검증하지 못한 항목은 완료처럼 쓰지 않고 사유와 다음 조치를 남긴다.

## 검증 방법

문서 구조 검증:

```powershell
rg -n "Repo Layout|Backend 실행 방법|Frontend 실행 방법|Test / Lint / Build|Coding Conventions|절대 하지 말아야 할 것|완료 기준|검증 방법" AGENTS.md
```

Backend API smoke 기준:

- `/health` 응답 확인
- seed, indicator recompute, market regime, instruments, screener, reports, backtest, portfolio risk, broker status, broker preview flow 확인
- broker preview 후 `orders_count == 0` 유지 확인

Frontend route smoke 기준:

- backend URL과 `NEXT_PUBLIC_API_BASE_URL`이 일치하는지 확인
- `/`, `/dashboard`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/settings` route 확인
- 브라우저 request failure와 관련 HTTP error가 없는지 확인

상세 검증 결과는 `docs/VALIDATION.md`에 기록하고, `Memory.md`에는 최신 대표 결과만 남긴다.
