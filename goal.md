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
- Phase 12: Controlled KIS Paper Trading Dry Run
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

# Phase 12: Controlled KIS Paper Trading Dry Run

- 목적
  - Run controlled KIS mock-account validation without enabling live paths.
- 수정 대상 파일
  - `docs/VALIDATION.md`
  - `Memory.md`
- 새로 생성할 파일
  - `docs/research/kis-paper-dry-run-checklist.md`
- 금지 사항
  - No live endpoint calls.
  - No unattended auto-submit during first dry run.
- 구현 조건
  - Require explicit human-enabled flags.
  - Validate submit/cancel/query/sync on KIS mock account.
  - Record only redacted traces and outcome metadata.
- 테스트 파일
  - No automated live-network tests required in CI.
- 검증 명령어
  - Manual dry-run checklist only.
- 완료 기준
  - Redacted dry-run result documented.
- rollback 기준
  - Disable submit path if KIS mock contract mismatches implementation.
- 다음 Phase 진입 조건
  - Dry run completed without violating safety rules.

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
