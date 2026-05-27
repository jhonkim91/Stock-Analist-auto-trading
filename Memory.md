# Stock Analyst Auto Trading Memory

## Checkpoint

- [ ] 현재 goal.md Phase 12: Phase 12B adapter implementation은 커밋 완료. Phase 12C는 credential/runtime/config gate 미충족으로 preflight 중단. Phase 13 진입 불가.
- [x] 현재 상태명: `KIS Paper Phase 12C Preflight Stopped`
- [x] 현재 version: `MVP v0.26.0`
- [x] 현재 branch: `feature/kis-paper-goal-phases` (baseline: `main`)
- [x] 현재 goal.md Phase 12B adapter implementation: KIS paper submit/cancel/query/sync adapter와 mocked HTTP tests 추가, commit `bcd40fac2a67e8c06aad32bd1f1f386b3abcab8e`
- [ ] 현재 goal.md Phase 12C controlled dry-run: KIS paper credential/runtime/config gate 미충족으로 실제 network call 없이 중단
- [x] 최신 secret scan: `NO_SECRET_FINDINGS`
- [x] 최신 diff check: `git diff --check` exit 0, CRLF warning만 있음

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, external daily OHLCV preview/confirm, KIS read-only foundation, broker safety scaffold, paper trading local lifecycle, report notification, paper bot scheduler, validation/report/backtest 기능.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/bot`, `/settings`.
- Paper trading은 사전 안전장치가 기본이며 live broker, live websocket, real-account mutation은 구현/활성화하지 않는다.
- `/api/paper/orders/submit`은 기본 fail-closed/local-only이며, paper mode/config/env/network/kill-switch/confirm/idempotency gate가 모두 열릴 때만 KIS paper adapter submit으로 이동한다.
- `/api/paper/sync`는 기본 fail-closed no-op이며, paper network/config/env/adapter gate가 모두 열릴 때만 KIS paper query 결과를 paper 전용 table에 반영한다.
- `/api/paper/portfolio`는 기본 disabled/mock 상태에서 기존 `paper_portfolio_snapshots` fallback을 유지한다.
- KIS paper balance 조건이 모두 만족될 때만 `/uapi/domestic-stock/v1/trading/inquire-balance`를 `tr_id=VTTC8434R`로 read-only 호출한다.
- KIS credential과 access token은 env에서만 주입한다. 코드, fixture, 문서, 로그, DB, API 응답에 raw 값을 남기지 않는다.
- `ENABLE_REAL_ORDER=true`이면 KIS balance/query/order 경로를 차단한다.
- 실전투자 TR ID와 live base URL 경로는 사용하지 않는다.

## 최근 변경 요약

- Phase 11: `backend/tests/test_e2e_paper_mock_flow.py`로 preview, local submit, order poll, mock fill/position/portfolio, notification outbox, report notify를 KIS credential 없이 검증했다.
- Phase 12 split review: `goal.md`와 `docs/research/kis-paper-dry-run-checklist.md`를 12A/12B/12C 구조로 재정리했다.
- Phase 12B: `KisPaperBrokerAdapter`에 `order-cash`, `order-rvsecncl`, `inquire-daily-ccld`, `inquire-balance` mapper와 redacted trace를 추가하고, `PaperOrderService`/`PaperSyncService`에 explicit network gate 분기를 연결했다.
- Phase 12B commit: `bcd40fac2a67e8c06aad32bd1f1f386b3abcab8e Implement KIS paper phase 12B adapter`.
- Phase 12C preflight: 12B commit 후 현재 프로세스에 KIS credential/runtime flag가 없고 `backend/config/paper.yaml`도 fail-closed라 실제 KIS paper submit/cancel/query/sync dry-run 없이 중단했다.

## 최신 검증 결과

- 2026-05-27 Phase 12B 지정 pytest: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_paper_submit_cancel_api.py backend/tests/test_paper_sync_service.py backend/tests/test_no_live_trading_regression.py -q`: 18 passed in 2.53s.
- 2026-05-27 Phase 12B 추가 paper regression: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter.py backend/tests/test_paper_order_service.py backend/tests/test_paper_order_api.py backend/tests/test_paper_runtime_flags.py backend/tests/test_paper_sync.py backend/tests/test_frontend_api_contracts.py -q`: 16 passed in 1.62s.
- 2026-05-27 Phase 12C preflight: 실제 KIS network call 없음. `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCESS_TOKEN`, `KIS_ACCOUNT_NO`, `KIS_PRODUCT_CODE`, `PAPER_TRADING_ENABLED`, `PAPER_TRADING_CAN_CREATE`, `PAPER_TRADING_NETWORK_ENABLED` 모두 current process에서 미설정.
- 2026-05-27 Phase 12C safety pytest: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_runtime_flags.py backend/tests/test_no_live_trading_regression.py -q`: 10 passed in 1.89s.
- 2026-05-27 `git diff --check`: 통과, CRLF warning만 있음.
- 2026-05-27 `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS`.

## 주의 사항

- `paper.yaml`의 KIS 관련 flag는 기본 disabled다. 실제 KIS paper dry-run을 켜려면 paper mode, network, adapter enable, official endpoint confirmation을 모두 명시해야 한다.
- KIS credential과 access token은 env에서만 주입한다. 코드, fixture, 문서, 로그, DB, API 응답에 raw 값을 남기지 않는다.
- KIS paper submit/cancel/query/sync network path는 Phase 12B에서 구현됐지만 기본 disabled/fail-closed다. Phase 12C 실제 dry-run은 credential/runtime/config gate가 준비될 때까지 실행하지 않는다.
- `ENABLE_REAL_ORDER=false`를 유지한다. true이면 KIS paper 경로를 차단한다.
- `.cache/kis/token.json` 같은 token cache 파일은 생성하지 않는다.

## 남은 작업

- [ ] Phase 12C controlled submit/cancel/query/sync dry-run은 KIS paper credential, process runtime flags, repo config gate, 즉시 human confirm 준비 후 재시도한다.
- [ ] Phase 13 final safety hardening은 Phase 12C redacted 성공 기록 전까지 시작하지 않는다.
- [ ] 실제 KIS paper balance/order 운영 전 env credential 주입 방식과 token 발급/갱신 운영 절차를 별도 확인한다.
