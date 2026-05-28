# Stock Analyst Auto Trading Memory

## 현재 체크포인트

- [x] 현재 branch: `feature/kis-paper-goal-phases`.
- [x] 현재 작업: KIS paper token 발급, WebSocket approval 발급, US bounded WebSocket 구독 ACK, 국내/미국 paper submit endpoint 도달까지 진행했다. 국내 submit은 장종료, 미국 submit은 HTTP 500 거부로 중단됐다. 최신 미국장 재요청은 뉴욕 정규장 전이라 `US_REGULAR_SESSION_REQUIRED`로 adapter 호출 전 차단했고, API/bot submit 경로의 US metadata 전달, broker fill persistence 귀속, controlled/Phase21 helper를 보강했다.
- [x] 기본 실행 주소: backend `http://127.0.0.1:8000`, frontend `http://127.0.0.1:3000/dashboard`.
- [x] 로컬 launcher는 검증 전 중지 상태로 유지했다. 필요 시 `py launcher.py run --no-browser` 후 `py launcher.py check`로 확인한다.
- [x] 현재 셸의 `python --version`은 `Python`만 출력하고 exit 1이다. 검증은 `.\.venv\Scripts\python.exe`로 수행한다.
- [x] `alembic` 실행 파일은 PATH에 없으므로 `.\.venv\Scripts\python.exe -m alembic ...`를 사용한다.

## KIS Paper Auto Bot Phase 1-6 상태

- [x] 루트 `goal.md`: `Phase 16A: Controlled KIS Paper Bot Run Validation`은 `.env.local` KIS paper readiness까지 재확인했지만 repo config/bot gate에서 `차단` 상태다.
- [x] 루트 `goal.md`: `KIS Paper Auto Bot Phase 1-6 진행 상태` 섹션을 추가해 설정/secret/token, KIS paper adapter, paper DB/API, realtime worker, bot executor/risk guard, monitoring/report/runbook을 완료 상태로 연결했다.
- [x] `docs/goal.md`: 목표, 범위, 안전조건, Phase 1-6, 완료기준 문서화.
- [x] `docs/RUNBOOK_PAPER_TRADING.md`: env 설정, DB migration, backend 실행, worker 상태, dry-run, paper run, kill switch, 장애 복구 절차 문서화.
- [x] Phase 1-4: KIS paper 설정/token/http client, adapter facade, account snapshot/API, realtime stale quote gate 구현.
- [x] Phase 5: `backend/app/services/paper_bot_executor.py`, `/api/paper/bot/preview`, `/api/paper/bot/run`, `/api/paper/bot/runs/{run_id}` 추가.
- [x] Phase 5 후보 필터: `passed=true`, 유효한 `risk_metadata`, 통과한 `data_quality_flags`만 사용.
- [x] Phase 5 sizing/gate: risk per trade, max order notional, max positions, cash, exposure, stop/risk per share, kill switch, session, stale quote, duplicate order, daily loss, concentration, cash/notional limit 반영.
- [x] Phase 6: `/api/paper/dashboard`, `PaperOperationalMetricsService`, daily/weekly report `## Paper Trading` section 추가.
- [x] Alembic head: `d1e2f3a4b5c6_extend_paper_bot_run_contract`.
- [x] 신규/확장 table 계약: `paper_account_snapshots`, `paper_bot_runs.trade_date/dry_run/preview_count/skipped_count/rejected_count/request_json/result_json`.

## 안전 계약

- [x] 실전투자, live trading, 실계좌 주문/취소/체결, 신용/공매도/파생상품 구현 없음.
- [x] 기본값은 disabled/fail-closed/dry-run.
- [x] KIS paper submit은 `KIS_ENV=paper`, `PAPER_TRADING_ENABLED=true`, `PAPER_BOT_CONFIRM=true`, kill switch off, `confirm=true`, idempotency, risk gate, no-live 조건이 필요하다.
- [x] `dry_run=true` bot run은 주문 row를 생성하지 않고 run/decision preview만 저장한다.
- [x] token/approval key는 process env에만 설치할 수 있고, API/문서/record에는 raw value를 남기지 않는다.
- [x] `ENABLE_REAL_ORDER=true`, live base URL, live fallback은 차단.
- [x] `orders_count == 0` 정책 유지. paper order는 `paper_orders`에만 저장.
- [x] secret, token, account number 원문은 API 응답/DB/log/docs에 저장하지 않는다.
- [x] CI/pytest는 mock/fake client 기반. 실제 KIS 호출은 runbook 수동 절차만 사용.

## 최신 검증 결과

- [x] KIS paper activation: `.env.local`을 현재 Python 검증 프로세스에만 로드하고 process-only gate를 열어 `POST /oauth2/tokenP` 1회 성공, `POST /oauth2/Approval` 1회 성공. raw token/approval key 미출력, `docs/research/kis-paper-phase21-activation-redacted-record.json`와 `docs/research/kis-paper-phase21-us-redacted-record.json` 생성.
- [x] Minimum domestic paper submit: temporary paper config와 process-only network gate로 `POST /uapi/domestic-stock/v1/trading/order-cash`, `tr_id=VTTC0012U` 1회 도달 -> `40580000`, `모의투자 장종료 입니다.`, `status=submit_failed`, 재시도 없음.
- [x] US paper WebSocket/submit: process-only gate로 `HDFSCNT0`/`DNASAAPL` bounded WebSocket subscribe ACK 성공(`SUBSCRIBE SUCCESS`), AAPL price/balance 조회 성공, `POST /uapi/overseas-stock/v1/trading/order`, `tr_id=VTTT1002U` 1회 도달 -> HTTP 500 / `KIS_PAPER_RESPONSE_ERROR`, 재시도 없음.
- [x] US post-reject read-only query: submit 재시도 없이 `GET /uapi/overseas-stock/v1/trading/inquire-ccnl`, `tr_id=VTTS3035R` -> `query_ok`, open order/fill 0개. 이후 sync balance leg는 `EGW00201`, `초당 거래건수를 초과하였습니다.`로 중단, 재시도 없음.
- [x] 주문/체결/포지션: submit 실패로 broker order id가 없어 query/sync/cancel 및 `paper_orders`/`paper_fills`/`paper_positions` persistence는 미완료.
- [x] US service submit metadata: `PAPER_TRADING_MARKET=US`, `KIS_OVERSEAS_EXCHANGE_CODE=NASD`, `KIS_OVERSEAS_CURRENCY=USD`가 `PaperOrderService` network submit metadata로 전달되도록 보강. service+adapter regression -> `13 passed in 0.76s`.
- [x] Broker lifecycle persistence: broker sync fill이 기존 `paper_orders.broker_order_id`를 찾아 내부 `paper_order_id`에 귀속되도록 보강. submit -> sync mock lifecycle regression -> `9 passed in 1.02s`.
- [x] Controlled helper US options: `tools/kis_paper_phase12c_dry_run.py`가 `--market US --exchange NASD --currency USD`를 받아 kill-switch proof -> submit -> list -> sync -> cancel을 US metadata/config로 수행. helper+adapter/order/sync regression -> `28 passed in 1.06s`.
- [x] Phase 21 activation helper: `tools/kis_paper_phase21_us_activation.py`가 token issue, WebSocket approval/subscription/smoke, controlled US submit lifecycle을 하나의 redacted record로 묶음. `market=US` submit은 `America/New_York` 정규장 `09:30-16:00` 밖에서 adapter 호출 전 차단.
- [x] US regular-session guard: 2026-05-28 05:13 New York 기준 `.env.local`을 현재 PowerShell 프로세스에만 로드한 Phase21 `--execute-submit`은 preflight 통과 후 `US_REGULAR_SESSION_REQUIRED`, `network_call_performed=false`, adapter/list/sync/cancel 미호출로 종료. record: `docs/research/kis-paper-phase21-us-window-guard-redacted-record.json`.
- [x] US window guard regression: `test_kis_paper_phase21_us_activation_tool.py`, `test_kis_paper_phase12c_tool.py` -> `15 passed in 0.14s`.
- [x] US adapter/WebSocket targeted regression: token issue, paper WebSocket approval/status/subscription/smoke route, 국내+미국 KIS paper adapter contract -> `12 passed in 0.67s`.
- [x] Domestic route regression after US 분기: Phase 12C KRX metadata가 국내 endpoint를 유지하는지 포함 -> `22 passed in 0.76s`.
- [x] Phase 21 US paper/no-live regression after window guard: phase21 helper/order/sync/realtime/dashboard/API smoke/no-live suite -> `71 passed in 35.67s`.
- [x] Token/WebSocket targeted regression: token issue, paper WebSocket approval/status/subscription preview, no-live regression -> `17 passed in 0.78s`.
- [x] Paper/no-live regression: paper realtime/dashboard/API smoke와 `/api/kis/websocket` 미등록 회귀 포함 -> `60 passed in 42.05s`.
- [x] `.env.local` KIS paper readiness recheck: 현재 Python 검증 프로세스에만 로드. `POST /api/kis/config/validate` -> `configured=true`, `kis_env_paper=true`, `network_call_performed=false`; raw secret/account/token 미노출.
- [x] `.env.local` dry-run preview: `POST /api/paper/bot/preview`, `max_candidates=1`, `dry_run=true` -> `run_id=paper-bot-fb740345fe7f4608`, `status=disabled`, `PAPER_BOT_DISABLED`, `KILL_SWITCH_ACTIVE`, `submitted_count=0`, `network_call_performed=false`.
- [x] `.env.local` status/dashboard: KIS/broker/paper/realtime/dashboard/bot status API 200. `orders_count=0`, `paper_orders_count=0`, 외부 TCP connect 시도 0.
- [x] Goal Phase 16A dry-run preview: `POST /api/paper/bot/preview`, `max_candidates=1`, `dry_run=true` -> `run_id=paper-bot-0439a452f5b84f40`, `status=disabled`, `submitted_count=0`, `network_call_performed=false`.
- [x] Goal Phase 16A dashboard/status: KIS/status/broker/paper/realtime/dashboard/bot status API 200. raw secret/account/token 미노출, `orders_count=0`, `paper_orders_count=0`.
- [x] Goal Phase 16A process-only paper run: 현재 PowerShell 프로세스에 paper gate만 주입하고 network gate는 미개방. `POST /api/paper/bot/run`, `max_candidates=1`, `dry_run=false` -> `run_id=paper-bot-7a43c3c83f3244f7`, `status=disabled`, `PAPER_BOT_DISABLED`, `PAPER_BOT_KILL_SWITCH_ACTIVE`, `KILL_SWITCH_ACTIVE`, `network_call_performed=false`.
- [x] Goal KIS Paper Auto Bot Phase 1-6 alignment: 루트 `goal.md`에 6단계 진행 상태 반영, heading/status docs 확인 완료.
- [x] Phase 1-6 targeted regression: `test_kis_paper_adapter_contract.py`, `test_paper_runtime_flags.py`, `test_paper_order_service.py`, `test_paper_order_api.py`, `test_paper_sync_service.py`, `test_paper_realtime_worker.py`, `test_paper_bot_executor_phase5.py`, `test_paper_dashboard_report_phase6.py`, migration/no-live suite -> `39 passed in 20.60s`.
- [x] Phase 16A secret scan: `.\.venv\Scripts\python.exe tools\secret_scan.py` -> `NO_SECRET_FINDINGS`.
- [x] Phase 16A diff check: `git diff --check` -> exit 0.
- [x] Backend full: `.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider --basetemp $env:TEMP\stock_kis_paper_phase56_pytest_final2` -> `416 passed in 310.50s`.
- [x] Phase 5/6 targeted: `test_paper_bot_executor_phase5.py`, `test_paper_dashboard_report_phase6.py`, migration tests -> `12 passed`.
- [x] Paper regression: bot/order/report/no-live subset -> `27 passed`.
- [x] Alembic: `.\.venv\Scripts\python.exe -m alembic upgrade head` -> `c0d1e2f3a4b5 -> d1e2f3a4b5c6` 적용.
- [x] Secret scan: `.\.venv\Scripts\python.exe tools\secret_scan.py` -> `NO_SECRET_FINDINGS`.
- [x] Diff check: `git diff --check` -> exit 0, CRLF warning only.
- [x] Frontend 영향 없음. frontend lint/typecheck/build는 이번 변경에서 생략.

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite + Alembic, sample seed, CSV import, KIS read-only foundation, broker safety scaffold, paper trading lifecycle, KIS paper adapter, token issue route, paper WebSocket approval route, report notification/automation, paper bot scheduler, Phase 5 bot executor, realtime quote worker skeleton.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/sessions`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/bot`, `/settings`.
- Notification: `backend/config/notifications.yaml` 기본값은 disabled/dry-run.
- Paper/KIS execution: 기본 config는 fail-closed. KIS paper token/WebSocket approval은 process-only gate로 호출 가능. live broker, live websocket, 실계좌 주문/취소/체결은 활성화하지 않는다.

## 최근 변경 요약

- `PaperBotExecutor`, bot preview/run/get-run API, request/result persistence 추가.
- `PaperDashboardService`, `PaperOperationalMetricsService`, realtime reconnect metric 상태 추가.
- report daily/weekly에 `## Paper Trading` section 추가.
- `paper_bot_runs` additive migration과 migration 테스트 갱신.
- KIS paper token issue API와 paper WebSocket approval/status/subscription preview/smoke API 추가.
- KIS paper adapter에 공식 샘플 기반 미국 해외주식 order/cancel/ccnl/balance 분기 추가.
- `PaperConfigService`와 `PaperOrderService` network submit 경로가 US market/exchange/currency metadata를 adapter로 넘기도록 보강.
- `PaperSyncService`가 broker fill을 기존 paper order에 귀속하도록 broker order id lookup을 추가.
- `tools/kis_paper_phase12c_dry_run.py`에 US market/exchange/currency 옵션과 미국 정규장 static guard 추가.
- `tools/kis_paper_phase21_us_activation.py`에 token/WebSocket/US submit lifecycle record helper 추가.
- Phase 21 activation redacted records `docs/research/kis-paper-phase21-activation-redacted-record.json`, `docs/research/kis-paper-phase21-us-redacted-record.json`, `docs/research/kis-paper-phase21-us-window-guard-redacted-record.json` 추가.

## 남은 작업

- [ ] KIS paper 주문 생성이 가능한 미국 정규장 시간/상품 조건에서 minimum submit -> query -> sync -> cancel을 1회 재시도한다. 장종료/거부/auth/rate-limit/stale 응답이면 재시도하지 않고 redacted record만 갱신한다.
- [ ] 주문 생성/체결/포지션 변경 persistence는 아직 미완료다. 국내는 장종료, 미국은 HTTP 500으로 broker order id가 없었다.
- [ ] 로컬 서버가 필요하면 `py launcher.py run --no-browser` 후 `py launcher.py check`로 확인한다.
- [ ] `python` launcher 문제가 계속 필요하면 Windows PATH/App execution alias를 별도 환경 작업으로 정리한다.
