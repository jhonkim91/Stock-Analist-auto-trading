# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `KIS Paper Balance Inquiry Read-only`
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
- [x] 최신 backend pytest: `342 passed in 327.46s`
- [x] 최신 frontend 검증: lint, typecheck, build 통과
- [x] 최신 secret scan: `NO_SECRET_FINDINGS`
- [x] 최신 diff check: `git diff --check` exit 0, CRLF warning만 있음

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, external daily OHLCV preview/confirm, KIS read-only foundation, broker safety scaffold, paper trading local lifecycle, report notification, paper bot scheduler, validation/report/backtest 기능.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/settings`.
- Paper trading은 여전히 실거래가 아니다. 실제 주문, 주문 취소, 체결, 계좌 자금 이동, live broker, websocket은 구현하지 않는다.
- `/api/paper/orders/submit`은 local `paper_orders` 전용이며 `confirm=true`, `idempotency_key`, kill-switch/config gate가 필요하다.
- `/api/paper/sync`는 KIS sync가 아니라 fail-closed no-op이다.
- `/api/paper/portfolio`는 기본 disabled/mock 상태에서 기존 `paper_portfolio_snapshots` fallback을 유지한다.
- KIS paper balance 조건이 모두 만족될 때만 `/uapi/domestic-stock/v1/trading/inquire-balance`를 `tr_id=VTTC8434R`로 read-only 호출한다.
- KIS paper balance 성공 응답은 `holdings`, `account_summary`, 기존 UI 호환 `snapshot`, `positions_summary`를 반환한다.
- KIS balance 경로는 `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCESS_TOKEN`, `KIS_ACCOUNT_NO`, `KIS_PRODUCT_CODE`를 env에서만 읽고 응답/로그/문서에는 raw 값을 남기지 않는다.
- `ENABLE_REAL_ORDER=true`이면 KIS balance client를 호출하지 않고 local snapshot fallback으로 차단한다.
- 실전투자 TR ID와 live base URL 경로는 사용하지 않는다.
- `goal.md` Phase 0는 main ref `bfcb1691e56dbdbbfc18b043bc65ec447acafa3e`와 현재 작업 브랜치 HEAD `ffd7f52a4745df2b99c8dae694796eab5e8f024d`를 분리해 감사했다.

## 최근 변경 요약

- `docs/research/kis-paper-baseline-audit.md`: `goal.md` Phase 0 산출물로 main 기준 route/table/service/test/UI와 no-live-trading 불변식 문서화.
- `docs/research/kis-paper-api-confirmation-matrix.md`: `goal.md` Phase 1 산출물로 공식 KIS 포털/공식 GitHub 샘플 기반 확인 항목과 `확인 필요` 항목 분리.
- `backend/app/services/broker_adapter.py`, `backend/app/services/kis_paper_broker_adapter.py`, `backend/app/services/kis_live_broker_adapter.py`: Phase 2 service adapter boundary 추가.
- `backend/app/services/broker_service.py`, `backend/app/services/paper_trading_service.py`: 기존 broker implementation 대신 service adapter boundary import로 전환.
- `backend/tests/test_kis_paper_adapter_contract.py`, `backend/tests/test_no_live_adapter.py`: paper adapter fail-closed와 live adapter hard-disabled 회귀 추가.
- `backend/app/services/kis_token_manager.py`, `backend/app/services/kis_request_signer.py`, `backend/app/services/credential_redaction.py`: Phase 3 metadata-only token lifecycle, pluggable fail-closed hashkey signer, 민감값 redaction 추가.
- `backend/app/services/kis_service.py`, `backend/app/models/schemas.py`, `backend/app/services/token_manager.py`: 기존 status/schema 호환을 유지하면서 Phase 3 token/signing metadata를 additive로 노출.
- `backend/tests/test_kis_token_manager.py`, `backend/tests/test_kis_request_signer.py`, `backend/tests/test_secret_redaction.py`: raw token 미저장, signing prerequisite reject, nested credential redaction 검증 추가.
- `backend/app/api/paper_execution_helpers.py`, `backend/app/api/paper.py`: submit/cancel API 응답에 `paper_only`, `execution_mode`, `live_fallback_enabled=false`, redacted `broker_trace` 추가.
- `backend/tests/test_paper_submit_cancel_api.py`: default kill-switch blocked submit, cancel disabled, no-live/no-network/no-secret 응답 검증 추가.
- `backend/app/repositories/paper_repository.py`, `backend/app/services/paper_sync_service.py`: Phase 5 paper persistence 조회/count 경계를 repository로 분리하고 sync no-op 응답의 count를 보강.
- `backend/tests/test_paper_sync_service.py`: paper repository, sync service payload, idempotent fail-closed sync, metadata marker 비노출 검증 추가.
- `docs/research/notification-channel-decision.md`, `docs/research/kis-paper-api-confirmation-matrix.md`: Phase 6 Telegram-first notification decision, Discord follow-up path, security/non-blocking constraints 문서화.
- `backend/app/services/notification_outbox_service.py`, `backend/app/services/discord_webhook_notifier.py`, `backend/app/services/notification_service.py`: Phase 7 supported events, Telegram-first ordering, non-blocking retry outbox, Discord webhook wrapper 보강.
- `backend/tests/test_notification_service.py`, `backend/tests/test_notification_outbox.py`: Phase 7 notifier status/event list, mock dispatch, outbox redaction, retry isolation 검증 추가.
- `backend/app/services/report_notification_service.py`, `backend/tests/test_report_notify.py`: Phase 8 report notification summary에 local paper portfolio snapshot 요약을 추가하고 metadata raw marker 비노출을 검증.
- `backend/app/services/paper_bot_service.py`, `backend/app/api/bot.py`, `backend/alembic/versions/b9c0d1e2f3a4_add_paper_bot_tables.py`: Phase 9 bot run/decision preview path, `/api/bot/*`, explicit auto-submit gates 추가.
- `backend/tests/test_paper_bot_decision.py`, `backend/tests/test_paper_bot_scheduler.py`: Phase 9 preview decision persistence, default disabled/kill-switch, bot API no-submit 회귀 검증 추가.
- `docs/PROJECT_STATUS.md`: Goal Phase 0 감사 문서 위치와 main/current branch 분리 기준 추가.
- `docs/VALIDATION.md`: Goal Phase 0/1/2/3/4/5/6/7/8/9 검증 결과 추가.
- KIS paper balance read-only 런타임 변경은 유지하되 이번 Phase 0/1/2/3/4/5/6/7/8/9에서는 `.env` 계열 파일을 변경하지 않았다.

## 최신 검증 결과

- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 342 passed in 327.46s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_no_live_adapter.py -q`: 5 passed in 0.08s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_token_manager.py backend/tests/test_kis_request_signer.py backend/tests/test_secret_redaction.py -q`: 10 passed in 0.94s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_submit_cancel_api.py backend/tests/test_no_live_trading_regression.py -q`: 9 passed in 0.68s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_sync_service.py backend/tests/test_alembic_migrations.py -q`: 5 passed in 3.16s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_sync.py backend/tests/test_paper_portfolio_api.py backend/tests/test_no_live_trading_regression.py -q`: 13 passed in 0.81s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_persistence_migration.py backend/tests/test_paper_order_api.py -q`: 4 passed in 2.65s.
- 2026-05-27 Phase 6 문서 구조 확인: `docs/research/notification-channel-decision.md`, `docs/research/kis-paper-api-confirmation-matrix.md`에 Telegram-first, Discord follow-up, security/non-blocking constraints 반영.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_notification_service.py backend/tests/test_notification_outbox.py -q`: 6 passed in 0.63s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_notifications.py backend/tests/test_notification_api.py backend/tests/test_report_notify.py backend/tests/test_no_live_trading_regression.py -q`: 18 passed in 0.93s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_alembic_migrations.py backend/tests/test_paper_persistence_migration.py -q`: 4 passed in 4.52s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_report_notify.py -q`: 3 passed in 0.68s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_notifications.py backend/tests/test_notification_api.py backend/tests/test_report_quality.py backend/tests/test_no_live_trading_regression.py -q`: 19 passed in 29.51s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_bot_decision.py backend/tests/test_paper_bot_scheduler.py -q`: 7 passed in 1.19s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_alembic_migrations.py backend/tests/test_paper_persistence_migration.py -q`: 4 passed in 4.57s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_no_live_trading_regression.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_paper_order_api.py -q`: 13 passed in 0.94s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_order_api.py backend/tests/test_paper_order_service.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_no_live_adapter.py -q`: 14 passed in 0.87s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_token_manager.py backend/tests/test_phase3c_kis_readonly.py backend/tests/test_no_live_trading_regression.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_no_live_adapter.py -q`: 22 passed in 3.29s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py -q`: 20 passed in 0.97s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3c_kis_readonly.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py -q`: 17 passed in 3.36s.
- 2026-05-27 frontend `npm.cmd run lint`, `npm.cmd exec tsc -- --noEmit`, `npm.cmd run build`: 통과.
- 2026-05-27 `git diff --check`: 통과, CRLF warning만 있음.
- 2026-05-27 `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS`.

## 주의 사항

- `paper.yaml`의 KIS balance 관련 flag는 기본 disabled다. 실제 KIS paper balance 조회를 켜려면 paper mode, network, balance inquiry, adapter enable, official balance endpoint confirmation을 모두 명시해야 한다.
- KIS credential과 access token은 env에서만 주입한다. 코드, fixture, 문서, 로그에 raw 값을 남기지 않는다.
- KIS balance 조회는 read-only다. 주문 API, 취소 API, 체결 조회 sync, paper fill/position mutation으로 확장하지 않는다.
- `ENABLE_REAL_ORDER=false`를 유지한다. true이면 KIS balance 조회도 차단된다.
- `.cache/kis/token.json` 같은 token cache 파일을 생성하지 않는다.
- frontend build 중 `.next\launcher-backend.err.log` EBUSY가 나면 오래 켜진 로컬 uvicorn/next 서버가 `.next` 로그를 잡고 있는지 먼저 확인한다.
- 테스트 실행으로 `backend/reports/strategy_validation_252d.json`이 갱신될 수 있으나, 이번 작업 범위 산출물이 아니면 남기지 않는다.

## 남은 작업

- [ ] KIS paper submit/cancel/sync network 구현은 계속 보류한다.
- [ ] 실제 KIS paper balance 운영 전 env credential 주입 방식과 token 발급/갱신 운영 절차를 별도 승인 후 정리한다.
- [ ] UI에서 KIS balance holdings 상세 목록을 보여줄지 별도 범위로 검토한다.
