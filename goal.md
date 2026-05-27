# Project Goal

Implement a paper-only KIS mock-trading bot on top of the current main branch.

Primary deliverables:
- KIS mock account order submit
- KIS mock order cancel
- KIS mock order/fill/balance/account/portfolio sync
- paper trading bot activation
- duplicate order prevention
- risk-guarded sizing
- Telegram-first notifications
- daily/weekly report notification
- goal.md driven Codex phase execution

# Non-Goals

- Live trading
- Real account order submit/cancel/balance mutation
- Live trading websocket order execution
- Live broker fallback from paper mode
- Secret persistence in code/docs/logs/DB/API responses
- Replacing existing report/backtest/screener contracts
- Breaking current preview-only safety behavior before paper-specific safeguards are complete

# Safety Rules

- Default trading mode must remain non-live.
- `KisLiveBrokerAdapter` must stay disabled placeholder only.
- Do not create live submit endpoints.
- Do not make paper mode fall back to live mode.
- `PAPER_BOT_ENABLED` default is false.
- `PAPER_BOT_AUTO_SUBMIT` default is false.
- If kill switch is on, no submit path may place an order.
- Never store KIS app key, app secret, access token, refresh token, account number, Telegram token, chat_id, or Discord webhook URL in code, docs, logs, DB, or API responses.
- `.env.example` may contain placeholders only.
- Do not create or modify `.env` or `.env.local`.
- Redact all secrets and account identifiers in logs, reports, notifications, and API errors.
- All submit/cancel routes must be explicitly paper-only.

# Current Baseline

- Backend has `/api/kis/status`, `/api/kis/config`, `/api/kis/config/validate`.
- Backend has `/api/broker/status`, `/api/broker/orders/preview`.
- Backend has `/api/paper/status`, `/api/paper/orders/preview`.
- Frontend has `/paper` preview UI and safety flags.
- Existing trading state is preview/read-only/fail-closed.
- Current DB has `orders`, `positions`, `reports`, `backtest_trade_ledger`, but not dedicated KIS paper persistence tables.
- Notification, outbox, bot scheduler, token manager, paper submit/cancel/sync are not implemented.

# Target Architecture

- Introduce `BrokerAdapter` contract.
- Implement `KisPaperBrokerAdapter`.
- Keep `KisLiveBrokerAdapter` disabled placeholder.
- Add `KisTokenManager` with metadata-only persistence.
- Add `CredentialRedactionService`.
- Add `NotificationService` abstraction.
- Implement `TelegramNotifier` first.
- Keep `DiscordWebhookNotifier` as optional follow-up implementation behind the same interface.
- Add notification outbox so notifier failures never break trading state transitions.
- Add dedicated tables for paper order/fill/position/portfolio/audit/notification/bot runs.
- Add paper bot modes: `manual`, `run_once`, `scheduled`.
- Use idempotency keys and duplicate-order checks for every submit path.
- Use polling for fills/positions/portfolio sync.
- Final behavior must remain fail-closed when config is incomplete or KIS mock capability is not confirmed.

# Phase Plan

- Phase 0: Latest Baseline Audit
- Phase 1: KIS Paper API Confirmation Matrix
- Phase 2: Paper Broker Adapter Hardening
- Phase 3: Token Hashkey Request Signing
- Phase 4: Paper Order Submit Cancel
- Phase 5: Order Fills Positions Portfolio Sync
- Phase 6: Notification Channel Decision
- Phase 7: Notification Implementation
- Phase 8: Report Portfolio Alerts
- Phase 9: Paper Bot Activation
- Phase 10: Frontend Integration
- Phase 11: End-to-End Mock Validation
- Phase 12A: KIS Paper Read-only Balance Dry-run
- Phase 12B: KIS Paper Submit/Cancel/Query/Sync Adapter Implementation
- Phase 12C: Controlled KIS Paper Submit/Cancel/Query/Sync Dry-run
- Phase 13: Final Safety Hardening

# Phase 0: Latest Baseline Audit

- 목적
  - Confirm actual main-branch baseline before touching execution paths.
- 수정 대상 파일
  - `Memory.md`
  - `docs/PROJECT_STATUS.md`
  - `docs/VALIDATION.md`
- 새로 생성할 파일
  - `goal.md`
  - `docs/research/kis-paper-baseline-audit.md`
- 금지 사항
  - No submit/cancel logic.
  - No DB schema changes.
- 구현 조건
  - Document exact current routes, tables, services, tests, and UI baseline.
  - Record no-live-trading invariant.
- 테스트 파일
  - None required beyond baseline verification notes.
- 검증 명령어
  - `python -m pytest backend/tests -q`
  - `cd frontend && npm run lint && npm exec tsc -- --noEmit && npm run build`
- 완료 기준
  - Baseline audit doc committed and consistent with main.
- rollback 기준
  - Revert doc-only changes if baseline text is inaccurate.
- 다음 Phase 진입 조건
  - No unresolved contradiction in current baseline docs.

# Phase 1: KIS Paper API Confirmation Matrix

- 목적
  - Freeze official KIS paper capability matrix before implementation.
- 수정 대상 파일
  - `docs/research/kis-paper-baseline-audit.md`
- 새로 생성할 파일
  - `docs/research/kis-paper-api-confirmation-matrix.md`
- 금지 사항
  - No production code changes yet.
- 구현 조건
  - Confirm mock base URL, token path, supported order/balance/account endpoints, mock-only limitations, TR IDs, hashkey requirement status, and known unconfirmed items.
  - Mark anything not verified as `확인 필요`.
- 테스트 파일
  - None
- 검증 명령어
  - N/A
- 완료 기준
  - Confirmation matrix exists and explicitly separates confirmed vs unconfirmed.
- rollback 기준
  - Remove matrix if it contains unsupported assumptions.
- 다음 Phase 진입 조건
  - Submit/cancel/sync API contract sufficiently confirmed to start adapter design.

# Phase 2: Paper Broker Adapter Hardening

- 목적
  - Introduce paper-only broker adapter structure without enabling submit yet.
- 수정 대상 파일
  - `backend/app/services/broker_service.py`
  - `backend/app/services/paper_trading_service.py`
  - `backend/app/models/schemas.py`
- 새로 생성할 파일
  - `backend/app/services/broker_adapter.py`
  - `backend/app/services/kis_paper_broker_adapter.py`
  - `backend/app/services/kis_live_broker_adapter.py`
- 금지 사항
  - No live implementation.
  - No real network order execution yet.
- 구현 조건
  - Add explicit broker interface.
  - Keep live adapter disabled.
  - Route paper work through paper adapter boundary only.
- 테스트 파일
  - `backend/tests/test_kis_paper_adapter_contract.py`
  - `backend/tests/test_no_live_adapter.py`
- 검증 명령어
  - `python -m pytest backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_no_live_adapter.py -q`
- 완료 기준
  - Adapter contract exists and live adapter is hard-disabled.
- rollback 기준
  - Revert any adapter path that can instantiate live execution.
- 다음 Phase 진입 조건
  - Adapter layer passes isolated mock tests.

# Phase 3: Token Hashkey Request Signing

- 목적
  - Add safe token lifecycle and request signing utilities for KIS mock calls.
- 수정 대상 파일
  - `backend/app/services/kis_service.py`
  - `backend/app/models/schemas.py`
- 새로 생성할 파일
  - `backend/app/services/kis_token_manager.py`
  - `backend/app/services/kis_request_signer.py`
  - `backend/app/services/credential_redaction.py`
- 금지 사항
  - No token raw value persistence.
  - No secret logging.
- 구현 조건
  - Store metadata only.
  - If hashkey contract remains unconfirmed, keep signer pluggable and fail-closed.
  - Reject submit if signing prerequisites are incomplete.
- 테스트 파일
  - `backend/tests/test_kis_token_manager.py`
  - `backend/tests/test_kis_request_signer.py`
  - `backend/tests/test_secret_redaction.py`
- 검증 명령어
  - `python -m pytest backend/tests/test_kis_token_manager.py backend/tests/test_kis_request_signer.py backend/tests/test_secret_redaction.py -q`
- 완료 기준
  - Token metadata lifecycle and redaction tests pass.
- rollback 기준
  - Revert if any raw secret reaches DB, logs, or API payload.
- 다음 Phase 진입 조건
  - Mock submit can be signed and gated safely.

# Phase 4: Paper Order Submit Cancel

- 목적
  - Add paper-only submit and cancel endpoints.
- 수정 대상 파일
  - `backend/app/api/paper.py`
  - `backend/app/models/schemas.py`
  - `backend/app/services/paper_trading_service.py`
- 새로 생성할 파일
  - `backend/app/api/paper_execution_helpers.py`
- 금지 사항
  - No live routes.
  - No submit when `PAPER_BOT_ENABLED=false`.
  - No submit when `PAPER_BOT_AUTO_SUBMIT=false` for bot-driven paths.
- 구현 조건
  - Add `POST /api/paper/orders/submit`
  - Add `POST /api/paper/orders/cancel`
  - Enforce kill switch, paper mode, idempotency, duplicate prevention.
  - Return redacted broker trace and paper-only markers.
- 테스트 파일
  - `backend/tests/test_paper_submit_cancel_api.py`
  - `backend/tests/test_no_live_trading_regression.py`
- 검증 명령어
  - `python -m pytest backend/tests/test_paper_submit_cancel_api.py backend/tests/test_no_live_trading_regression.py -q`
- 완료 기준
  - Paper submit/cancel works against mock adapter tests and is blocked by safety gates when disabled.
- rollback 기준
  - Revert immediately if any route can hit live domain.
- 다음 Phase 진입 조건
  - Submit/cancel state transitions stable under tests.

# Phase 5: Order Fills Positions Portfolio Sync

- 목적
  - Persist and synchronize paper trading state.
- 수정 대상 파일
  - `backend/app/models/tables.py`
  - `backend/app/models/schemas.py`
  - `backend/app/api/paper.py`
- 새로 생성할 파일
  - `backend/alembic/versions/<rev>_add_paper_trading_tables.py`
  - `backend/app/services/paper_sync_service.py`
  - `backend/app/repositories/paper_repository.py`
- 금지 사항
  - No raw credential persistence.
- 구현 조건
  - Add `paper_orders`, `paper_fills`, `paper_positions`, `paper_portfolio_snapshots`, `broker_audit_events`, `kis_token_status_metadata`.
  - Add `GET /api/paper/orders`
  - Add `GET /api/paper/fills`
  - Add `GET /api/paper/positions`
  - Add `GET /api/paper/portfolio`
  - Add `POST /api/paper/sync`
- 테스트 파일
  - `backend/tests/test_paper_sync_service.py`
  - `backend/tests/test_alembic_migrations.py`
- 검증 명령어
  - `python -m pytest backend/tests/test_paper_sync_service.py backend/tests/test_alembic_migrations.py -q`
- 완료 기준
  - Fill/position/portfolio snapshots are queryable and consistent.
- rollback 기준
  - Roll back migration if persistence contract is inconsistent or leaks secrets.
- 다음 Phase 진입 조건
  - Stable synced paper state is available for notifications and bot logic.

# Phase 6: Notification Channel Decision

- 목적
  - Freeze primary notifier channel and interface contract.
- 수정 대상 파일
  - `docs/research/kis-paper-api-confirmation-matrix.md`
- 새로 생성할 파일
  - `docs/research/notification-channel-decision.md`
- 금지 사항
  - No notifier implementation before decision record.
- 구현 조건
  - Record Telegram-first decision, Discord follow-up path, reason, constraints, and security handling.
- 테스트 파일
  - None
- 검증 명령어
  - N/A
- 완료 기준
  - Decision document committed.
- rollback 기준
  - Remove if unsupported by official docs.
- 다음 Phase 진입 조건
  - Primary channel finalized.

# Phase 7: Notification Implementation

- 목적
  - Add robust non-blocking notification pipeline.
- 수정 대상 파일
  - `backend/app/models/tables.py`
  - `backend/app/models/schemas.py`
  - `backend/app/api/settings.py`
- 새로 생성할 파일
  - `backend/app/services/notification_service.py`
  - `backend/app/services/telegram_notifier.py`
  - `backend/app/services/discord_webhook_notifier.py`
  - `backend/app/services/notification_outbox_service.py`
  - `backend/app/api/notifications.py`
  - `backend/alembic/versions/<rev>_add_notification_tables.py`
- 금지 사항
  - No notifier may block trading state commit.
- 구현 조건
  - Add `notification_events`, `notification_delivery_logs`.
  - Add `GET /api/notifications/status`
  - Add `POST /api/notifications/test`
  - Implement events:
    - `bot_started`
    - `bot_stopped`
    - `order_signal_created`
    - `paper_order_previewed`
    - `paper_order_submitted`
    - `paper_order_rejected`
    - `paper_order_filled`
    - `paper_order_cancelled`
    - `portfolio_snapshot`
    - `daily_report_generated`
    - `weekly_report_generated`
    - `risk_limit_warning`
    - `kis_token_error`
    - `broker_error`
    - `kill_switch_triggered`
- 테스트 파일
  - `backend/tests/test_notification_service.py`
  - `backend/tests/test_notification_outbox.py`
- 검증 명령어
  - `python -m pytest backend/tests/test_notification_service.py backend/tests/test_notification_outbox.py -q`
- 완료 기준
  - Notification failures are isolated and retriable.
- rollback 기준
  - Revert if any order path fails because notifier delivery failed.
- 다음 Phase 진입 조건
  - Notification pipeline proven non-blocking.

# Phase 8: Report Portfolio Alerts

- 목적
  - Send daily/weekly report summaries and portfolio snapshots to notifier channel.
- 수정 대상 파일
  - `backend/app/services/report_service.py`
  - `backend/app/api/reports.py`
- 새로 생성할 파일
  - `backend/app/services/report_notification_service.py`
- 금지 사항
  - No full secret dump in reports or notifications.
- 구현 조건
  - Add `POST /api/reports/{report_id}/notify`
  - Convert markdown reports to delivery-friendly summaries.
  - Split long messages.
  - Optionally attach report files when safe and size-limited.
- 테스트 파일
  - `backend/tests/test_report_notify.py`
- 검증 명령어
  - `python -m pytest backend/tests/test_report_notify.py -q`
- 완료 기준
  - Daily/weekly report summaries and portfolio snapshots can be delivered safely.
- rollback 기준
  - Revert if report notification breaks existing report routes.
- 다음 Phase 진입 조건
  - Notification channel ready for bot events and scheduled summaries.

# Phase 9: Paper Bot Activation

- 목적
  - Introduce bot decision loop with explicit enable flags.
- 수정 대상 파일
  - `backend/app/services/screener_service.py`
  - `backend/app/services/risk_service.py`
  - `backend/app/api/paper.py`
- 새로 생성할 파일
  - `backend/app/services/paper_bot_service.py`
  - `backend/app/services/paper_bot_scheduler.py`
  - `backend/app/api/bot.py`
  - `backend/alembic/versions/<rev>_add_paper_bot_tables.py`
- 금지 사항
  - No auto-submit unless explicitly enabled.
- 구현 조건
  - Add bot modes `manual`, `run_once`, `scheduled`.
  - Add `paper_bot_runs`, `paper_bot_decisions`.
  - Add `GET /api/bot/status`
  - Add `POST /api/bot/run-once`
  - Add `POST /api/bot/stop`
  - Enforce session checks, duplicate prevention, kill switch, risk caps.
- 테스트 파일
  - `backend/tests/test_paper_bot_decision.py`
  - `backend/tests/test_paper_bot_scheduler.py`
- 검증 명령어
  - `python -m pytest backend/tests/test_paper_bot_decision.py backend/tests/test_paper_bot_scheduler.py -q`
- 완료 기준
  - Bot can produce preview decisions and optional paper submits under explicit flags.
- rollback 기준
  - Revert if bot can auto-submit without explicit config.
- 다음 Phase 진입 조건
  - Bot path stable under mock tests.

# Phase 10: Frontend Integration

- 목적
  - Extend existing UI with minimal structural change.
- 수정 대상 파일
  - `frontend/app/paper/page.tsx`
  - `frontend/app/reports/page.tsx`
  - `frontend/app/settings/page.tsx`
  - `frontend/lib/*`
- 새로 생성할 파일
  - `frontend/app/bot/page.tsx`
  - `frontend/lib/paperApi.ts`
  - `frontend/lib/notificationApi.ts`
- 금지 사항
  - No UI language implying live trading.
- 구현 조건
  - Add paper dashboard sections for submit/cancel/orders/fills/positions/portfolio.
  - Add bot enabled/disabled indicator.
  - Add kill switch indicator.
  - Add notification test and report notify actions.
  - Add explicit `모의투자` labels.
- 테스트 파일
  - Frontend build/lint/typecheck only unless dedicated tests already exist.
- 검증 명령어
  - `cd frontend && npm run lint && npm exec tsc -- --noEmit && npm run build`
- 완료 기준
  - Frontend can operate new paper-only backend routes.
- rollback 기준
  - Revert UI changes if they imply live trading or break build.
- 다음 Phase 진입 조건
  - Frontend fully aligned with backend additive routes.

# Phase 11: End-to-End Mock Validation

- 목적
  - Validate full paper flow in mock-only environment.
- 수정 대상 파일
  - `docs/VALIDATION.md`
- 새로 생성할 파일
  - `backend/tests/test_e2e_paper_mock_flow.py`
- 금지 사항
  - No real KIS credentials in tests.
- 구현 조건
  - Cover preview -> submit -> poll -> fill sync -> portfolio snapshot -> notification outbox -> report notify.
- 테스트 파일
  - `backend/tests/test_e2e_paper_mock_flow.py`
- 검증 명령어
  - `python -m pytest backend/tests/test_e2e_paper_mock_flow.py -q`
  - `python -m pytest backend/tests -q`
- 완료 기준
  - Full mock-only flow passes.
- rollback 기준
  - Revert new orchestration if end-to-end state becomes inconsistent.
- 다음 Phase 진입 조건
  - End-to-end mock flow stable.

# Phase 12: KIS Paper Trading Dry-run Split

- 현재 상태
  - Phase 12A is complete for read-only balance dry-run planning/guarding.
  - Phase 12B adapter implementation is present behind paper-only network gates and mocked HTTP tests.
  - Phase 12C controlled real KIS paper dry-run remains incomplete and must not be marked complete from env flags alone.
  - Do not mark Phase 12 complete from env flags alone.
  - KIS paper submit/cancel/query/sync network execution is allowed only for paper mode after all explicit process/config/risk/idempotency gates pass.
  - Live trading paths must remain disabled.
- 분리 사유
  - Current code has read-only KIS paper balance support only when all safe gates are explicitly enabled.
  - `KisPaperBrokerAdapter` implements paper-only submit/cancel/list/query-balance/sync with official paper endpoint/TR ID mapping confirmed in the project matrix.
  - `POST /api/paper/sync` remains fail-closed by default and only calls the paper adapter when paper network/config/env gates are explicitly opened.

# Phase 12A: KIS Paper Read-only Balance Dry-run

- 목적
  - Validate KIS paper read-only balance/position inquiry without enabling submit, cancel, sync mutation, bot auto-submit, or live paths.
- 수정 대상 파일
  - `docs/VALIDATION.md`
  - `Memory.md`
  - `docs/research/kis-paper-dry-run-checklist.md`
- 새로 생성할 파일
  - None unless a redacted read-only evidence artifact is explicitly requested.
- 금지 사항
  - No submit/cancel/query/sync adapter implementation.
  - No live endpoint calls.
  - No `.env` or `.env.local` creation/modification.
  - No raw KIS AppKey, AppSecret, token, account number, Telegram token, chat ID, or webhook value in code/docs/logs/DB/API responses.
- 구현 조건
  - Use process env only for KIS paper credentials.
  - Keep `ENABLE_REAL_ORDER` absent or false.
  - Keep `PAPER_BOT_AUTO_SUBMIT=false`.
  - Keep live fallback disabled.
  - Enable only the read-only balance path after explicit human confirmation.
  - Record redacted metadata only: route, endpoint path, paper TR ID, status code, elapsed time, correlation ID, and result status.
- 테스트 파일
  - `backend/tests/test_kis_paper_balance.py`
  - `backend/tests/test_no_live_trading_regression.py`
- 검증 명령어
  - `python -m pytest backend/tests/test_kis_paper_balance.py backend/tests/test_no_live_trading_regression.py -q`
  - `python tools/secret_scan.py`
  - `git diff --check`
- 완료 기준
  - Redacted read-only balance dry-run result is documented.
  - API response/log/document output contains no raw secrets or account identifiers.
  - No submit/cancel/sync network path is enabled.
- rollback 기준
  - Disable KIS balance inquiry flags and fall back to local `paper_portfolio_snapshots` if response contract or safety gates mismatch.
- 다음 Phase 진입 조건
  - Phase 12A read-only dry-run completed without live path use or secret exposure.

# Phase 12B: KIS Paper Submit/Cancel/Query/Sync Adapter Implementation

- 목적
  - Implement paper-only KIS submit/cancel/query/sync adapter paths behind explicit safety gates.
- 수정 대상 파일
  - `backend/app/brokers/kis_paper.py`
  - `backend/app/services/kis_paper_broker_adapter.py`
  - `backend/app/services/paper_order_service.py`
  - `backend/app/services/paper_sync_service.py`
  - `backend/app/models/schemas.py`
  - `backend/tests/*paper*`
  - `docs/research/kis-paper-dry-run-checklist.md`
  - `docs/VALIDATION.md`
  - `Memory.md`
- 새로 생성할 파일
  - Adapter/query tests as needed for submit/cancel/query/sync contract coverage.
- 금지 사항
  - No controlled dry-run execution in the same implementation step.
  - No live trading route, live base URL, live fallback, websocket execution, or real-account mutation.
  - No bot auto-submit default enablement.
  - No raw secret/account/token persistence or response exposure.
- 구현 조건
  - Implement only KIS paper base URL and paper TR IDs confirmed in the project matrix.
  - Require `BROKER_MODE=paper_kis` for paper network adapter calls.
  - Require `PAPER_ORDER_SUBMIT_ENABLED=true` only for network submit.
  - Fail closed for any unconfirmed endpoint, TR ID, request field, response field, hashkey/signing prerequisite, or account mode.
  - Require explicit process env gates for paper network execution.
  - Keep kill switch blocking submit by default and require immediate human confirmation for submit/cancel operations.
  - Preserve idempotency keys, duplicate prevention, broker audit redaction, and local paper persistence separation.
  - Query/sync must upsert only dedicated paper tables and must not touch live account state or legacy synthetic `positions` as broker truth.
- 테스트 파일
  - Add/extend tests for paper submit/cancel/query/sync adapter success with mocked HTTP only.
  - Add/extend fail-closed tests for missing env flags, kill switch, live base URL, unsupported TR ID, redaction, idempotency, duplicate submit, and no-live regression.
- 검증 명령어
  - `python -m pytest backend/tests/test_paper_runtime_flags.py backend/tests/test_no_live_trading_regression.py -q`
  - `python -m pytest backend/tests -q`
  - `python tools/secret_scan.py`
  - `git diff --check`
- 완료 기준
  - Mocked HTTP adapter tests pass for submit/cancel/query/sync.
  - Real KIS network calls are still not required for CI.
  - Default runtime remains fail-closed without explicit process env flags.
- rollback 기준
  - Revert adapter network implementation if any path can reach live endpoints, bypass kill switch/idempotency, or expose secrets.
- 다음 Phase 진입 조건
  - Phase 12B adapter implementation passes mocked contract and safety regression tests.

# Phase 12C: Controlled KIS Paper Submit/Cancel/Query/Sync Dry-run

Implementation update:
- `tools/kis_paper_phase12c_dry_run.py` provides a preflight-only default helper for Phase 12C.
- `tools/kis_paper_phase12c_dry_run.py --temporary-paper-config` can use a process-only dry-run config without writing `backend/config/paper.yaml`.
- `tools/kis_paper_phase12c_dry_run.py --confirm-trading-window CONFIRM_KIS_PAPER_TRADING_WINDOW` is now required before any controlled submit attempt so a market-closed retry stops before adapter calls.
- `backend/tests/test_kis_paper_phase12c_tool.py` verifies no-op preflight, missing-gate stop, broker-mode/order-submit gates, process-only temporary config, trading-window confirmation, kill-switch proof, and broker identifier redaction.
- A controlled `--execute --temporary-paper-config` attempt reached the KIS paper submit endpoint after human confirmation, but KIS returned `40580000` / `모의투자 장종료 입니다.` before broker order creation; Phase 12C remains incomplete until submit/cancel/query/sync finishes with a redacted record.

- 목적
  - Execute a controlled KIS paper submit/cancel/query/sync dry-run after Phase 12B implementation is complete.
- 수정 대상 파일
  - `docs/VALIDATION.md`
  - `Memory.md`
  - `docs/research/kis-paper-dry-run-checklist.md`
  - `tools/kis_paper_phase12c_dry_run.py`
- 새로 생성할 파일
  - `backend/tests/test_kis_paper_phase12c_tool.py`
  - No redacted real-network evidence artifact unless a controlled dry-run actually executes.
- 금지 사항
  - No Phase 13 work.
  - No live endpoint calls.
  - No unattended auto-submit.
  - No `.env` or `.env.local` creation/modification.
  - No raw secrets, tokens, account numbers, order identifiers that reveal account identity, or notification credentials in outputs.
- 구현 조건
  - Require explicit human confirmation immediately before submit and cancel.
  - Require explicit trading-window confirmation before the helper can call the adapter.
  - Use a minimum-size paper order only.
  - Prove kill switch blocks submit before temporarily opening the submit gate.
  - Re-enable kill switch immediately after the controlled submit/cancel attempt.
  - Query cancelable orders and daily fills/orders through paper-only paths.
  - Run sync only after query response contract matches implementation assumptions.
  - Record redacted traces and outcome metadata only.
- 테스트 파일
  - No automated real-network tests required in CI.
  - Add helper tests that prove preflight is no-op, missing gates stop before adapter calls, trading-window confirmation is required, kill-switch proof is required, and broker identifiers are redacted.
- 검증 명령어
  - Manual dry-run checklist.
  - `python tools/kis_paper_phase12c_dry_run.py`
  - `python -m pytest backend/tests/test_kis_paper_phase12c_tool.py -q`
  - `python -m pytest backend/tests/test_paper_runtime_flags.py backend/tests/test_no_live_trading_regression.py -q`
  - `python tools/secret_scan.py`
  - `git diff --check`
- 완료 기준
  - Redacted controlled submit/cancel/query/sync dry-run result is documented.
  - No live path was enabled.
  - No raw secret/account/token value was exposed.
- rollback 기준
  - Disable submit/cancel/query/sync network path if KIS mock contract mismatches implementation.
- 다음 Phase 진입 조건
  - Phase 12C completed without violating safety rules.

# Phase 13: Final Safety Hardening

- 목적
  - Freeze paper-only hardening and prevent accidental live drift.
- 수정 대상 파일
  - `Memory.md`
  - `docs/PROJECT_STATUS.md`
  - `docs/VALIDATION.md`
  - `.env.example`
- 새로 생성할 파일
  - `backend/tests/test_final_safety_hardening.py`
- 금지 사항
  - No feature creep.
- 구현 조건
  - Add final no-live-trading regression checks.
  - Ensure `.env.example` placeholders only for new secrets.
  - Ensure redaction and kill switch coverage.
- 테스트 파일
  - `backend/tests/test_final_safety_hardening.py`
- 검증 명령어
  - `python -m pytest backend/tests -q`
  - `cd frontend && npm run lint && npm exec tsc -- --noEmit && npm run build`
  - `git diff --check`
- 완료 기준
  - Repository is paper-only, documented, validated, and CI-clean.
- rollback 기준
  - Revert if any final hardening weakens existing preview/read-only invariants.
- 다음 Phase 진입 조건
  - None

# Final Acceptance Criteria

- Paper-only submit/cancel/query/sync paths exist and are additive.
- Live adapter remains disabled.
- No live endpoints are callable.
- No secret raw value is persisted or exposed.
- KIS mock account paper orders can be submitted and cancelled under explicit flags only.
- Fills, positions, cash, and portfolio snapshots can be synchronized.
- Duplicate submit prevention and idempotency are enforced.
- Telegram notifications work with non-blocking outbox behavior.
- Reports can be notified safely.
- Bot can run once or on schedule in paper-only mode.
- Frontend clearly labels the feature as `모의투자`.
- No-live-trading regression tests pass.
