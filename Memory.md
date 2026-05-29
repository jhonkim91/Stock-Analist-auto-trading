# Stock Analyst Auto Trading Memory

## 현재 체크포인트

- [x] 현재 branch: `feature/kis-paper-goal-phases`.
- [x] 기본 실행 주소: backend `http://127.0.0.1:8000`, frontend `http://127.0.0.1:3000/dashboard`.
- [x] 현재 로컬 앱은 `py launcher.py run --no-browser` 후 backend 8000/frontend 3000이 launcher-owned 상태다.
- [x] `python --version`은 이 환경에서 불안정할 수 있으므로 검증은 `.\.venv\Scripts\python.exe`를 우선 사용한다.
- [x] `alembic` 실행 파일은 PATH에 없으므로 `.\.venv\Scripts\python.exe -m alembic ...`를 사용한다.

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite + Alembic, sample seed, CSV import, KIS read-only foundation, broker safety scaffold, paper trading lifecycle, KIS paper adapter, token issue route, paper WebSocket approval route, report notification/automation, paper bot scheduler/executor, realtime quote worker skeleton.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/market`, `/data`, `/sessions`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/bot`, `/settings`.
- Paper/KIS: KIS paper token/WebSocket approval, US WebSocket subscribe ACK, 미국 정규장 AAPL 1주 paper submit/follow-up sync completion을 redacted record와 DB로 확인했다. premarket/daytime/extended는 paper host 거부 확인 후 adapter/network 전 차단한다.
- Runtime controls: Settings 화면에 process-only runtime env ON/OFF 버튼이 있다. `.env.local`/config 파일을 수정하지 않고 현재 backend 프로세스 env만 바꾸며 `ENABLE_REAL_ORDER`는 UI/API에서 true로 켤 수 없다.
- Notification/Report: 기본은 manual/dry-run 중심이다. Telegram/notification payload와 logs에는 secret/account/token 원문을 남기지 않는다.

## 안전 계약

- [x] 실전투자, live trading, 실계좌 주문/취소/체결, 신용/공매도/파생상품 구현 없음.
- [x] 기본값은 fail-closed이며 live fallback은 차단.
- [x] KIS paper submit은 `KIS_ENV=paper`, `PAPER_TRADING_ENABLED=true`, `PAPER_BOT_CONFIRM=true`, kill switch off, `confirm=true`, idempotency, risk gate, no-live 조건이 필요하다.
- [x] `dry_run=true` bot run은 주문 row를 생성하지 않고 run/decision preview만 저장한다.
- [x] token/approval key는 process env에만 설치 가능하고 API/문서/record에는 raw value를 남기지 않는다.
- [x] `ENABLE_REAL_ORDER=true`, live base URL, live fallback은 차단.
- [x] `orders_count == 0` 정책 유지. paper order는 `paper_orders`에만 저장한다.
- [x] secret, token, account number 원문은 API 응답/DB/log/docs에 저장하지 않는다.
- [x] CI/pytest는 mock/fake client 기반이다. 실제 KIS 호출은 runbook 수동 절차만 사용한다.

## 최근 변경 요약

- Goal Read/Report Phase 1 완료: local DB 기반 `backend/app/api/market_realtime.py`, `account.py`, `trade_journal.py`와 service 3개를 추가했다.
- `/api/market-realtime/search`, `/symbols/{symbol}`, `/symbols/{symbol}/chart`, `/rankings`가 종목 검색, 상세 quote/indicator/screener/fundamentals, 차트 series, 랭킹을 반환한다.
- `/api/account/summary`, `/holdings`, `/report`가 `paper_account_snapshots`/`paper_positions` 기반 계좌/보유/포트폴리오 리포트를 반환한다.
- `/api/trade-journal/entries`, `/csv`가 `backtest_trade_ledger`, `paper_fills`, `paper_orders`를 CSV 매매일지 형태로 정규화한다.
- frontend `/market` route와 sidebar `Market` nav를 추가했다. 화면은 검색, KPI, 종목 상세, SVG line/volume chart, 랭킹, strategy signals를 표시한다.
- `backend/tests/test_phase1_read_report_api.py`를 추가했다.
- 현재 repo 설정은 paper/manual 기능이 활성화된 상태이므로 `test_api_smoke.py`의 broker/paper smoke 기대값을 disabled-only에서 paper-enabled fail-closed 기준으로 갱신했다.
- `README.md`, `docs/VALIDATION.md`, `goal.md`, `Memory.md`를 1단계 조회/보고 상태로 갱신했다.

## 최신 검증 결과

- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase1_read_report_api.py -q` -> `3 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_api_smoke.py backend/tests/test_frontend_api_contracts.py -q` -> `4 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_no_live_trading_regression.py -q` -> `7 passed`.
- [x] `cd frontend; npm.cmd run lint` -> 통과.
- [x] `cd frontend; npm.cmd exec tsc -- --noEmit` -> 통과.
- [x] `cd frontend; npm.cmd run build` -> 통과. 첫 시도는 기존 launcher 프로세스가 `.next\launcher-backend.err.log`를 잠가 `EBUSY`였고, repo 소유 프로세스 정리 후 성공.
- [x] `py launcher.py run --no-browser`, `py launcher.py check` -> backend 8000/frontend 3000 launcher-owned.
- [x] `Invoke-WebRequest http://127.0.0.1:3000/market -UseBasicParsing` -> 200.
- [x] `Invoke-RestMethod 'http://127.0.0.1:8000/api/market-realtime/rankings?metric=total_score&limit=3'` -> `network_call_performed=false`.
- [x] `npx.cmd playwright screenshot http://127.0.0.1:3000/market %TEMP%\stock-market-phase1.png --wait-for-timeout=3000` -> screenshot 생성.
- [x] `.\.venv\Scripts\python.exe tools\secret_scan.py` -> `NO_SECRET_FINDINGS`.
- [x] `git diff --check` -> exit 0, CRLF warning only.

## 남은 작업

- [ ] 2단계 paper order/fill/position/cancel/stop 기능 확장은 별도 승인과 paper gate 확인 후 진행한다.
- [ ] 실계좌 주문 연동은 kill switch, rate limiter, idempotency, audit log, max notional, blacklist, cooldown 설계/검증 전까지 구현하지 않는다.
- [ ] 추가 실제 KIS paper 주문은 정규장, fresh quote, process-only credential/token/account/product code, 별도 network 승인 조건에서만 수행한다.
