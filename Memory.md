# Stock Analyst Auto Trading Memory

## Latest Phase 12C Status

- [ ] 현재 goal.md Phase 12C는 미완료다. 사용자 승인 후 실제 KIS paper submit endpoint까지 도달했지만, KIS가 `40580000` / `모의투자 장종료 입니다.`를 반환해 broker order id가 생성되지 않았다.
- [x] kill switch 차단 증명은 통과했다. `KILL_SWITCH_ACTIVE` 상태에서 submit은 network call 없이 차단됐다.
- [x] redacted attempt record: `docs/research/kis-paper-phase12c-redacted-record.json`
- [x] Phase 12C helper는 이제 `--confirm-trading-window CONFIRM_KIS_PAPER_TRADING_WINDOW` 없이는 preflight 통과 후에도 adapter 호출 전 중단한다.
- [x] `.env` / `.env.local`은 생성 또는 수정하지 않았다. raw KIS credential/account/token 값은 코드, 문서, 로그, DB, API 응답에 기록하지 않는다.
- [ ] Phase 13은 Phase 12C submit/cancel/query/sync 성공 기록 전까지 진입 금지다.

## Checkpoint

- [ ] 현재 goal.md Phase 12: Phase 12B paper-only network adapter와 gate hardening은 mock 검증 완료. Phase 12C 실제 KIS paper submit은 장 종료 응답으로 broker order 생성 전 실패.
- [x] 현재 상태명: `KIS Paper Phase 12C Market-closed Submit Stopped`
- [x] 현재 version: `MVP v0.26.0`
- [x] 현재 branch: `feature/kis-paper-goal-phases` (baseline: `main`)
- [x] 현재 goal.md Phase 12B adapter implementation: KIS paper submit/cancel/query_balance/list_orders/sync adapter와 paper-only gate hardening을 mocked HTTP/fake adapter tests로 검증. 기존 commit `bcd40fac2a67e8c06aad32bd1f1f386b3abcab8e`, 현재 변경은 아직 미커밋.
- [ ] 현재 goal.md Phase 12C controlled dry-run: KIS paper credential/runtime gate와 process-only temporary config preflight는 redacted 기준 통과했고, 승인 후 submit network call은 수행됐지만 `40580000` / `모의투자 장종료 입니다.`로 cancel/query/sync 전 중단
- [x] 최신 secret scan: `NO_SECRET_FINDINGS`
- [x] 최신 diff check: `git diff --check` exit 0, CRLF warning만 있음

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, external daily OHLCV preview/confirm, KIS read-only foundation, broker safety scaffold, paper trading local lifecycle, report notification, paper bot scheduler, validation/report/backtest 기능.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/bot`, `/settings`.
- Paper trading은 사전 안전장치가 기본이며 live broker, live websocket, real-account mutation은 구현/활성화하지 않는다.
- `/api/paper/orders/submit`은 기본 fail-closed/local-only이며, `BROKER_MODE=paper_kis`, paper config/env/network/kill-switch/confirm/idempotency/risk/duplicate/`PAPER_ORDER_SUBMIT_ENABLED`/`ENABLE_REAL_ORDER=false` gate가 모두 열릴 때만 KIS paper adapter submit으로 이동한다.
- `/api/paper/sync`는 기본 fail-closed no-op이며, paper network/config/env/adapter gate가 모두 열릴 때만 KIS paper query 결과를 paper 전용 table에 반영한다.
- `/api/paper/portfolio`는 기본 disabled/mock 상태에서 기존 `paper_portfolio_snapshots` fallback을 유지한다.
- KIS paper balance 조건이 모두 만족될 때만 paper base host의 `/uapi/domestic-stock/v1/trading/inquire-balance`를 `tr_id=VTTC8434R`로 read-only 호출한다.
- KIS credential과 access token은 env에서만 주입한다. 코드, fixture, 문서, 로그, DB, API 응답에 raw 값을 남기지 않는다.
- `ENABLE_REAL_ORDER=true`이면 KIS balance/query/order 경로를 차단한다.
- 실전투자 TR ID와 live base URL 경로는 사용하지 않는다.

## 최근 변경 요약

- Phase 11: `backend/tests/test_e2e_paper_mock_flow.py`로 preview, local submit, order poll, mock fill/position/portfolio, notification outbox, report notify를 KIS credential 없이 검증했다.
- Phase 12 split review: `goal.md`와 `docs/research/kis-paper-dry-run-checklist.md`를 12A/12B/12C 구조로 재정리했다.
- Phase 12B: `KisPaperBrokerAdapter`에 `order-cash`, `order-rvsecncl`, `inquire-daily-ccld`, `inquire-balance` mapper와 redacted trace를 추가하고, `PaperOrderService`/`PaperSyncService`에 explicit network gate 분기를 연결했다.
- Phase 12B hardening: `BROKER_MODE=paper_kis`, `PAPER_ORDER_SUBMIT_ENABLED`, paper base host 강제, duplicate open order guard, bot max submit/qty/notional cap, trace correlation id를 추가했다.
- Phase 12B commit: `bcd40fac2a67e8c06aad32bd1f1f386b3abcab8e Implement KIS paper phase 12B adapter`.
- Phase 12C attempt: 최신 재시도에서 현재 프로세스의 KIS credential/runtime flag 존재 여부는 redacted boolean 기준 통과했고, `--temporary-paper-config` process-only override도 blockers 없이 통과했다. 승인 후 paper submit endpoint까지 도달했으나 KIS 장 종료 응답으로 broker order id가 생성되지 않았다. `backend/config/paper.yaml`은 fail-closed 그대로 둔다.
- Phase 12C helper: `tools/kis_paper_phase12c_dry_run.py`와 `backend/tests/test_kis_paper_phase12c_tool.py`를 추가/보강해 preflight-only no-op, missing gate stop, broker-mode/order-submit gate, process-only temporary config, kill-switch proof, broker identifier redaction을 검증한다.
- Phase 12C trading-window gate: submit/cancel 확인 토큰이 있어도 `CONFIRM_KIS_PAPER_TRADING_WINDOW`가 없으면 adapter 호출 전 `trading_window_confirmation_required`로 중단한다.

## 최신 검증 결과

- 2026-05-27 Phase 12B 지정 pytest: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_paper_submit_cancel_api.py backend/tests/test_paper_sync_service.py backend/tests/test_paper_runtime_flags.py backend/tests/test_no_live_trading_regression.py -q`: 22 passed in 3.10s.
- 2026-05-27 Phase 12B 추가 bot/order/balance pytest: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_bot_decision.py backend/tests/test_paper_order_service.py backend/tests/test_kis_paper_balance.py -q`: 11 passed in 3.10s.
- 2026-05-27 Phase 12C controlled submit attempt: KIS paper `/uapi/domestic-stock/v1/trading/order-cash`, `tr_id=VTTC0012U`, `status_code=200`, `msg_cd=40580000`, `msg1=모의투자 장종료 입니다.`. broker order id 미생성, cancel/query/sync 미실행.
- 2026-05-27 Phase 12C temporary config preflight: `.\.venv\Scripts\python.exe tools\kis_paper_phase12c_dry_run.py --temporary-paper-config`: `status=preflight_only`, `preflight.ok=true`, `temporary_config_used=true`, `network_call_performed=false`.
- 2026-05-27 Phase 12C execute confirmation gate: `.\.venv\Scripts\python.exe tools\kis_paper_phase12c_dry_run.py --temporary-paper-config --execute`: `status=confirmation_required`, `network_call_performed=false`, exit code 2.
- 2026-05-27 Phase 12C helper pytest: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase12c_tool.py -q -p no:cacheprovider`: 9 passed in 0.06s.
- 2026-05-27 Phase 12C trading-window gate smoke: `.env.local` 값을 현재 프로세스에만 주입한 뒤 `.\.venv\Scripts\python.exe tools\kis_paper_phase12c_dry_run.py --execute --temporary-paper-config --confirm-submit CONFIRM_KIS_PAPER_PHASE12C --confirm-cancel CONFIRM_KIS_PAPER_PHASE12C`: `status=trading_window_confirmation_required`, `network_call_performed=false`, exit code 2.
- 2026-05-27 Phase 12C targeted pytest: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_paper_runtime_flags.py backend/tests/test_no_live_trading_regression.py -q -p no:cacheprovider`: 19 passed in 0.86s.
- 2026-05-27 backend full pytest: `.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider --basetemp %TEMP%\stock_phase12c_backend_full_*`: 389 passed in 325.65s. repo 내부 basetemp는 secret scan fixture와 충돌할 수 있으므로 workspace 밖 temp 사용.
- 2026-05-27 Phase 12C safety pytest: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_runtime_flags.py backend/tests/test_no_live_trading_regression.py -q -p no:cacheprovider --basetemp .pytest_tmp\phase12c`: 10 passed in 0.80s. 임시 디렉터리는 제거함.
- 2026-05-27 `git diff --check`: 통과, CRLF warning만 있음.
- 2026-05-27 `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS`.

## 주의 사항

- `paper.yaml`의 KIS 관련 flag는 기본 disabled다. 실제 KIS paper dry-run을 켜려면 paper mode, network, adapter enable, official endpoint confirmation을 모두 명시해야 한다.
- KIS credential과 access token은 env에서만 주입한다. 코드, fixture, 문서, 로그, DB, API 응답에 raw 값을 남기지 않는다.
- KIS paper submit/cancel/query/sync network path는 Phase 12B에서 구현됐지만 기본 disabled/fail-closed다. Phase 12C 실제 dry-run 재시도는 KIS paper trading window에서만 수행한다.
- `ENABLE_REAL_ORDER=false`를 유지한다. true이면 KIS paper 경로를 차단한다.
- `.cache/kis/token.json` 같은 token cache 파일은 생성하지 않는다.

## 남은 작업

- [ ] Phase 12C controlled submit/cancel/query/sync dry-run은 KIS paper trading window에 KIS paper credential, process runtime flags, repo config gate, 즉시 human confirm, `CONFIRM_KIS_PAPER_TRADING_WINDOW` 준비 후 재시도한다.
- [ ] Phase 13 final safety hardening은 Phase 12C redacted 성공 기록 전까지 시작하지 않는다.
- [ ] 실제 KIS paper balance/order 운영 전 env credential 주입 방식과 token 발급/갱신 운영 절차를 별도 확인한다.
