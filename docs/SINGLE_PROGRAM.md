# 단일 프로그램 (Single Program)

기존에는 백엔드(FastAPI, 8000)와 프론트엔드(Next.js, 3000) **두 프로세스**를
`launcher.py`가 조율해 실행했다. 이제는 다음과 같이 **단일 프로세스 / 단일 실행 파일**로 동작한다.

- Next.js를 **정적 사이트로 export**(`output: "export"` → `frontend/out`)
- FastAPI가 동일 오리진(127.0.0.1:8000)에서 **UI와 `/api/*`를 함께 서빙**
- 프론트엔드는 절대 URL 없이 상대 경로(`/api/...`)로 백엔드를 호출
- **pywebview 네이티브 창**(Windows: WebView2)에 띄워 일반 Windows 프로그램처럼 동작
  (콘솔창/브라우저 탭 없음). pywebview가 없으면 기본 브라우저로 폴백.
- PyInstaller로 **단일 `.exe`** 패키징 → 최종 사용자는 Python/Node 설치 불필요

## UI / 테마

- **모노스페이스 + 밝은 베이지 톤**을 라이트 테마로 유지하고, 동일 미감의 **다크 테마**를 추가.
- 사이드바 하단의 **슬라이더 토글**로 라이트↔다크 전환. 선택은 `localStorage('sa-theme')`에 저장되며,
  최초 방문 시 OS 선호(`prefers-color-scheme`)를 따른다. 페인트 이전 사전 스크립트로 깜빡임(FOUC) 없음.
- 모든 색은 `frontend/app/globals.css`의 CSS 변수(`:root` / `[data-theme="dark"]`)로 일원화.
- **로컬 JSON 로그인**: 자격증명은 `backend/data/users.json`(PBKDF2-HMAC-SHA256)에 저장하고,
  HMAC 서명 30일 토큰을 발급한다. 사용자가 한 명이라도 생성된 뒤에만 인증을 강제하는 **opt-in** 방식이며,
  프론트엔드의 AuthGate(설정/로그인)와 로그아웃을 제공한다. 라우트는 `/api/auth/*`.

## 구조

| 구성 | 경로 | 비고 |
|------|------|------|
| 단일 진입점 | `app_main.py` | uvicorn 1개 실행 + 브라우저 오픈 |
| 정적 UI 서빙 | `backend/app/main.py` (`_frontend_export_dir`) | `/`에 `frontend/out` 마운트 |
| 경로 해석 | `backend/app/core/paths.py` | frozen(.exe)일 때 config는 번들, DB/reports는 exe 옆 |
| 오케스트레이션 | `launcher.py` | setup / run / stop / check / build-exe |
| 패키징 정의 | `stock_analyst.spec` | PyInstaller onefile |

## 개발/실행 명령

```powershell
py launcher.py check       # 준비 상태 점검
py launcher.py setup       # 의존성 설치 + 정적 export 빌드
py launcher.py run         # 단일 프로세스 실행 (http://127.0.0.1:8000/)
py launcher.py stop        # 실행 중인 프로세스 종료
py launcher.py build-exe   # dist/StockAnalyst.exe 생성
```

또는 더블클릭: `start_stock_analyst.cmd` (= `py launcher.py run`)

직접 실행도 가능:
```powershell
.\.venv\Scripts\python app_main.py            # 브라우저 자동 오픈
.\.venv\Scripts\python app_main.py --no-browser --port 8080
```

## 단일 실행 파일(.exe)

```powershell
py launcher.py build-exe
```

- 산출물: `dist/StockAnalyst.exe` (단일 파일)
- 실행 시 **exe와 같은 폴더**에 `backend/data/app.db`, `backend/reports/`가 생성된다(영속).
- 설정(`backend/config/*.yaml`)과 UI(`frontend/out`)는 exe 내부에 번들된다(읽기 전용).

## 환경 변수

| 변수 | 용도 | 기본값 |
|------|------|--------|
| `STOCK_ANALYST_HOST` | 바인딩 호스트 | `127.0.0.1` |
| `STOCK_ANALYST_PORT` | 바인딩 포트 | `8000` |
| `DATABASE_URL` | DB 위치 override | exe 옆 `backend/data/app.db` |
| `NEXT_PUBLIC_API_BASE_URL` | (개발) 프론트 API base | 빌드 시 빈 값(동일 오리진) |

> KIS/Telegram/Discord 등 외부 연동 자격증명과 설정은 `.env`/환경 변수뿐 아니라 **UI에서 직접 입력·토글**할 수 있고,
> `backend/data/runtime_env.json`에 **영속**된다(허용 키만, 민감 값은 마스킹). 시작 시 로드된다.

## 개발 모드(선택)

프론트엔드를 핫리로드로 개발하려면 기존처럼 두 프로세스를 띄울 수 있다.

```powershell
.\.venv\Scripts\python -m uvicorn backend.app.main:app --port 8000   # 백엔드
cd frontend; npm run dev                                              # 프론트(3000)
```

이때 `frontend/.env.local`의 `NEXT_PUBLIC_API_BASE_URL`로 백엔드 주소를 지정한다.
정적 export(`setup`/`build-exe`)는 이 값을 무시하고 항상 동일 오리진으로 빌드한다.
