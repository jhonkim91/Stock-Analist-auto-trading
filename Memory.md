# Stock Analyst Auto Trading Memory

## Checkpoint

- [ ] 현재 goal.md Phase 12: Phase 12B adapter implementation 완료. 실제 KIS paper network dry-run은 실행하지 않았고 Phase 12C로 남긴다. Phase 13 진입 불가.
- [x] 현재 상태명: `KIS Paper Phase 12B Adapter Implementation`
- [x] 현재 version: `MVP v0.26.0`
- [x] 현재 branch: `feature/kis-paper-goal-phases` (baseline: `main`)
- [x] 현재 goal.md Phase 0 감사: `docs/research/kis-paper-baseline-audit.md`
- [x] 현재 goal.md Phase 1 matrix: `docs/research/kis-paper-api-confirmation-matrix.md`
- [x] 현재 goal.md Phase 2 adapter hardening: service adapter boundary 추가, live disabled 유지
- [x] 현재 goal.md Phase 3 token/signing: metadata-only token, fail-closed signer, credential redaction 추가
- [x] 현재 goal.md Phase 4 submit/cancel: paper-only API marker와 redacted broker trace 추가
- [x] 현재 goal.md Phase 5 sync: `PaperRepository` 기반 paper 전용 fills/positions/portfolio 조회 경계 보강
- [x] 현재 goal.md Phase 6 notification decision: Telegram-first primary, Discord follow-up path 문서화
- [x] 현재 goal.md Phase 7 notification implementation: non-blocking/retriable outbox 보강
- [x] 현재 goal.md Phase 8 report portfolio alerts: report notify에 local paper portfolio snapshot 요약 추가
- [x] 현재 goal.md Phase 9 paper bot activation: preview decision loop, bot audit tables, `/api/bot/*` safety route 추가
- [x] 현재 goal.md Phase 10 frontend integration: `/bot` UI와 paper/notification wrapper, paper-only controls 추가
- [x] 현재 goal.md Phase 11 e2e mock validation: mock-only paper flow E2E 테스트 추가
- [x] 현재 goal.md Phase 12B adapter implementation: KIS paper submit/cancel/query/sync adapter와 mocked HTTP tests 추가
- [x] 최신 backend 검증: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_paper_submit_cancel_api.py backend/tests/test_paper_sync_service.py backend/tests/test_no_live_trading_regression.py -q`: 18 passed in 2.53s
- [x] 최신 frontend 검증: lint, typecheck, build, rendered smoke 통과
- [x] 최신 secret scan: `NO_SECRET_FINDINGS`
- [x] 최신 diff check: `git diff --check` exit 0, CRLF warning만 있음

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, external daily OHLCV preview/confirm, KIS read-only foundation, broker safety scaffold, paper trading local lifecycle, report notification, paper bot scheduler, validation/report/backtest 기능.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/bot`, `/settings`.
- Paper trading은 여전히 실거래가 아니다. 실제 주문, 주문 취소, 체결, 계좌 자금 이동, live broker, websocket은 구현하지 않는다.
- `/api/paper/orders/submit`은 기본 fail-closed/local-only이며, paper mode/config/env/network/kill-switch/confirm/idempotency gate가 모두 열릴 때만 KIS paper adapter submit으로 이동한다.
- `/api/paper/sync`는 기본 fail-closed no-op이며, paper network/config/env/adapter gate가 모두 열릴 때만 KIS paper query 결과를 paper 전용 table에 반영한다.
- `/api/paper/portfolio`는 기본 disabled/mock 상태에서 기존 `paper_portfolio_snapshots` fallback을 유지한다.
- KIS paper balance 조건이 모두 만족될 때만 `/uapi/domestic-stock/v1/trading/inquire-balance`를 `tr_id=VTTC8434R`로 read-only 호출한다.
- KIS paper balance 성공 응답은 `holdings`, `account_summary`, 기존 UI 호환 `snapshot`, `positions_summary`를 반환한다.
- KIS balance 경로는 `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCESS_TOKEN`, `KIS_ACCOUNT_NO`, `KIS_PRODUCT_CODE`를 env에서만 읽고 응답/로그/문서에는 raw 값을 남기지 않는다.
- `ENABLE_REAL_ORDER=true`이면 KIS balance client를 호출하지 않고 local snapshot fallback으로 차단한다.
- 실전투자 TR ID와 live base URL 경로는 사용하지 않는다.
- `goal.md` Phase 0는 main ref `bfcb1691e56dbdbbfc18b043bc65ec447acafa3e`와 현재 작업 브랜치 HEAD `ffd7f52a4745df2b99c8dae694796eab5e8f024d`를 분리해 감사했다.

## 최근 변경 요약

- Phase 9: `paper_bot_runs`, `paper_bot_decisions`, `/api/bot/status`, `/api/bot/run-once`, `/api/bot/stop`, preview decision loop, explicit auto-submit gates를 추가했다.
- Phase 10: `frontend/app/bot/page.tsx`, `frontend/lib/paperApi.ts`, `frontend/lib/notificationApi.ts`를 추가하고 `/paper`, `/reports`, `/settings`에 bot/kill switch/notification/report notify controls를 paper-only로 연결했다.
- Phase 11: `backend/tests/test_e2e_paper_mock_flow.py`를 추가해 preview, local submit, order poll, mock fill/position/portfolio, notification outbox, report notify를 KIS credential 없이 검증했다.
- Phase 12 preflight: `docs/research/kis-paper-dry-run-checklist.md`에 manual dry-run 절차와 redacted preflight 중단 결과를 기록했다. 실제 KIS network call은 실행하지 않았다. 문서상 explicit env gate와 코드상 config-only gate의 불일치를 패치했다.
- Phase 12 split review: `goal.md`와 `docs/research/kis-paper-dry-run-checklist.md`를 12A/12B/12C 구조로 재정리했다. submit/cancel/query/sync network 구현은 하지 않았고 fail-closed 상태를 유지한다.
- Phase 12B: `KisPaperBrokerAdapter`에 `order-cash`, `order-rvsecncl`, `inquire-daily-ccld`, `inquire-balance` mapper와 redacted trace를 추가하고, `PaperOrderService`/`PaperSyncService`에 explicit network gate 분기를 연결했다.

## 최신 검증 결과

- 2026-05-27 Phase 12B 지정 pytest: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_paper_submit_cancel_api.py backend/tests/test_paper_sync_service.py backend/tests/test_no_live_trading_regression.py -q`: 18 passed in 2.53s.
- 2026-05-27 Phase 12B 추가 paper regression: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter.py backend/tests/test_paper_order_service.py backend/tests/test_paper_order_api.py backend/tests/test_paper_runtime_flags.py backend/tests/test_paper_sync.py backend/tests/test_frontend_api_contracts.py -q`: 16 passed in 1.62s.
- 2026-05-27 `git diff --check`: 통과, CRLF warning만 있음.
- 2026-05-27 `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS`.
- 2026-05-27 Phase 12B: 실제 KIS network call 없음. mock HTTP client/fake adapter 테스트만 수행.

## 주의 사항

- `paper.yaml`의 KIS balance 관련 flag는 기본 disabled다. 실제 KIS paper balance 조회를 켜려면 paper mode, network, balance inquiry, adapter enable, official balance endpoint confirmation을 모두 명시해야 한다.
- KIS credential과 access token은 env에서만 주입한다. 코드, fixture, 문서, 로그에 raw 값을 남기지 않는다.
- KIS paper submit/cancel/query/sync network path는 Phase 12B에서 구현됐지만 기본 disabled/fail-closed다. 실제 dry-run은 Phase 12C 전까지 실행하지 않는다.
- `ENABLE_REAL_ORDER=false`를 유지한다. true이면 KIS balance 조회도 차단된다.
- `.cache/kis/token.json` 같은 token cache 파일을 생성하지 않는다.
- frontend build 중 `.next\launcher-backend.err.log` EBUSY가 나면 오래 켜진 로컬 uvicorn/next 서버가 `.next` 로그를 잡고 있는지 먼저 확인한다.
- 테스트 실행으로 `backend/reports/strategy_validation_252d.json`이 갱신될 수 있으나, 이번 작업 범위 산출물이 아니면 남기지 않는다.

## 남은 작업

- [ ] Phase 12A read-only balance dry-run은 아직 실제 KIS credential로 실행하지 않았다.
- [ ] Phase 12C controlled submit/cancel/query/sync dry-run은 Phase 12B 구현 및 테스트 완료 전까지 금지한다.
- [ ] 실제 KIS paper balance 운영 전 env credential 주입 방식과 token 발급/갱신 운영 절차를 별도 승인 후 정리한다.
- [ ] UI에서 KIS balance holdings 상세 목록을 보여줄지 별도 범위로 검토한다.
