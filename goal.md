# Project Goal

Implement KIS paper-trading support on top of the current fail-closed preview-only baseline.
Deliver a safe paper-only broker abstraction, KIS paper order/sync flow, Telegram/Discord notifications, daily/weekly report delivery, an optional paper-bot scheduler, and minimal frontend integration.
Keep live trading disabled by default and out of scope.

## Non-Goals

- No real trading order submission
- No live-account balance mutation
- No live WebSocket trading
- No automatic live-mode fallback
- No secret persistence in code, docs, logs, DB, or reports
- No destructive refactor of existing screener/backtest/report/portfolio baseline
- No breaking change to existing APIs unless strictly additive and backward-compatible
- No toolchain major-version refactor unrelated to this feature

## Safety Rules

- Keep `live trading` disabled by default everywhere
- Keep `KisLiveBrokerAdapter` as a disabled placeholder only
- Paper and live code paths must be physically separated
- If official KIS endpoint details are not confirmed, do not guess; keep the capability disabled and document it as `확인 필요`
- Keep existing `preview-only` behavior intact until the paper submit phase explicitly enables paper submission
- Never store raw `KIS AppKey`, `KIS AppSecret`, `access token`, `refresh token`, `account number`, `Discord webhook URL`, `Telegram bot token`, or `chat_id` in code, docs, logs, DB, or reports
- `.env.example` may contain placeholders only
- Real values may only come from `.env.local` or local environment variables
- Do not log full Telegram request URLs because the token is embedded in the URL path
- Do not log raw Discord webhook URLs
- Do not expose raw account numbers in API responses, logs, reports, or notifications; use aliases only
- Notification failures must not roll back or block paper-trading state transitions
- Use additive DB migrations only; do not drop existing tables for this project
- Keep `positions` / `portfolio risk` synthetic baseline separate from `paper_positions` / paper account snapshots
- Default `PAPER_BOT_AUTO_SUBMIT=false`
- Default scheduler disabled
- Preserve existing lint, typecheck, pytest, build, and CI behavior

## Current Baseline

- Backend: FastAPI app with routers for `broker`, `paper`, `kis`, `reports`, `portfolio`, `settings`, and related core features
- Frontend: Next.js App Router with `/paper`, `/portfolio`, `/reports`, `/settings`
- Existing KIS code is read-only only
- Existing broker and paper services are preview-only / fail-closed
- Existing report service generates daily/weekly markdown reports
- Existing portfolio service provides synthetic risk summary
- Existing paper DB tables already exist:
  - `paper_orders`
  - `paper_fills`
  - `paper_positions`
  - `paper_audit_events`
- Existing docs are inconsistent; Phase 0 must reconcile them
- Current launcher manages backend/frontend only

## Target Architecture

- `backend/app/brokers/base.py`
  - Defines `BrokerAdapter` contract
- `backend/app/brokers/kis_paper.py`
  - Implements KIS paper-only REST adapter
- `backend/app/brokers/kis_live.py`
  - Disabled placeholder only
- `backend/app/services/token_manager.py`
  - In-memory token lifecycle handling with no raw-token persistence
- `backend/app/services/paper_order_service.py`
  - Preview/submit/cancel lifecycle
- `backend/app/services/paper_sync_service.py`
  - Orders/fills/positions/portfolio sync
- `backend/app/services/notification_service.py`
  - Channel selection, outbox dispatch, retry, and redaction
- `backend/app/services/report_notification_service.py`
  - Report summary rendering, split, and file attachment policy
- `backend/app/services/paper_bot_service.py`
  - Screening to order orchestration
- `backend/app/jobs/paper_bot_runner.py`
  - `--once` and `--loop` bot runner
- Existing `PaperTradingService` remains the API facade and delegates internally
- New DB objects:
  - extend existing `paper_*` tables
  - `paper_portfolio_snapshots`
  - `broker_audit_events`
  - `notification_events`
  - `notification_delivery_logs`
  - `kis_token_status_metadata`
- Frontend changes remain minimal and focused on:
  - `/paper`
  - `/portfolio`
  - `/reports`
  - `/settings`

## Phase Plan

- Always execute phases in order
- Do not skip a phase gate
- If a phase fails its acceptance or rollback condition, stop and fix before continuing
- At the end of each phase, keep diffs minimal and document only the delta relevant to that phase

### Phase 0: Baseline Audit

- 목적
  - Reconcile the current main-branch baseline before new implementation starts
  - Identify stale docs and establish the source of truth
  - Create a KIS paper API confirmation matrix for later phases

- 수정 대상 파일
  - `goal.md`
  - `README.md`
  - `docs/PROJECT_STATUS.md`
  - `docs/VALIDATION.md`
  - `docs/DB_MIGRATION.md`
  - `docs/plans/README.md`
  - `Memory.md`

- 새로 생성할 파일
  - `docs/plans/phase-paper-broker-baseline-audit.md`
  - `docs/KIS_PAPER_API_MATRIX.md`

- 금지 사항
  - No runtime behavior changes
  - No new API endpoints
  - No DB schema changes
  - No live trading implementation
  - No secret handling changes beyond documentation

- 구현 조건
  - Treat `docs/PROJECT_STATUS.md` and `docs/VALIDATION.md` as primary truth if README conflicts
  - Explicitly mark stale information instead of silently deleting it
  - `docs/KIS_PAPER_API_MATRIX.md` must list each planned capability with:
    - capability name
    - official doc confirmation status
    - endpoint/path/TR-ID status
    - implementation status
    - note `확인 필요` where needed

- 테스트 파일
  - No new dedicated test file required in this phase
  - Existing safety suites must still pass

- 실행할 검증 명령어
  - `.\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_phase3c_kis_readonly.py -q`
  - `.\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_phase3d_broker_safety.py -q`
  - `.\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_phase3e_paper_safety.py -q`
  - `git diff --check`

- 완료 기준
  - Baseline source-of-truth is clearly documented
  - Stale doc conflicts are reconciled or explicitly marked
  - KIS paper API matrix exists and distinguishes confirmed vs unconfirmed details
  - Safety regression tests pass with no behavior drift

- 실패 시 rollback 기준
  - Revert documentation-only changes if they introduce inconsistency
  - Do not proceed if baseline truth remains ambiguous

- 다음 Phase 진입 조건
  - Baseline audit doc completed
  - KIS paper API matrix created
  - Existing safety tests pass unchanged

### Phase 1: Notification Foundation

- 목적
  - Add notifier abstraction and redacted channel configuration
  - Provide disabled/mock notifier by default
  - Add safe status/test endpoints without coupling them to trading flow

- 수정 대상 파일
  - `backend/app/main.py`
  - `backend/app/api/settings.py`
  - `backend/app/services/settings_service.py`
  - `frontend/app/settings/page.tsx`
  - `frontend/lib/api.ts`
  - `.env.example`

- 새로 생성할 파일
  - `backend/config/notifications.yaml`
  - `backend/app/api/notifications.py`
  - `backend/app/services/notification_service.py`
  - `backend/app/services/discord_notifier.py`
  - `backend/app/services/telegram_notifier.py`
  - `backend/tests/test_notifications.py`
  - `backend/tests/test_notification_api.py`

- 금지 사항
  - No trade path coupling
  - No real secret values in config files
  - No blocking of trading state on notifier failure
  - No raw webhook/token/chat_id logging

- 구현 조건
  - Support notifier aliases such as `discord_ops`, `telegram_main`
  - Read actual webhook/token/chat_id values from env only
  - `/api/notifications/status` must be fully redacted
  - `/api/notifications/test` must support disabled/mock mode and safe dry-run behavior
  - Discord notifier must set `allowed_mentions.parse=[]`
  - Telegram formatter must avoid unsafe MarkdownV2 defaults unless explicitly handled

- 테스트 파일
  - `backend/tests/test_notifications.py`
  - `backend/tests/test_notification_api.py`

- 실행할 검증 명령어
  - `.\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_notifications.py backend/tests/test_notification_api.py -q`
  - `.\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py -q`
  - `cd frontend && npm.cmd run lint && npm.cmd exec tsc -- --noEmit && cd ..`
  - `git diff --check`

- 완료 기준
  - Disabled notifier is the safe default
  - Notification status/test endpoints work with redacted output
  - Discord and Telegram adapters exist behind the abstraction
  - No secret leakage in API or logs

- 실패 시 rollback 기준
  - Remove new notification routes/services if notifier behavior leaks secrets or affects trading logic
  - Revert `.env.example` if any real-looking value appears

- 다음 Phase 진입 조건
  - Notification foundation exists
  - Tests pass
  - Default runtime remains safe and disabled

### Phase 2: KIS Paper Broker Contract

- 목적
  - Define the broker abstraction contract
  - Create `KisPaperBrokerAdapter`
  - Create `KisLiveBrokerAdapter` disabled placeholder
  - Introduce token manager contract without raw-token persistence

- 수정 대상 파일
  - `backend/app/services/kis_service.py`
  - `backend/app/services/broker_service.py`
  - `backend/app/services/paper_trading_service.py`
  - `backend/app/models/schemas.py`
  - `backend/config/broker.yaml`
  - `backend/config/paper.yaml`
  - `.env.example`

- 새로 생성할 파일
  - `backend/app/brokers/base.py`
  - `backend/app/brokers/kis_paper.py`
  - `backend/app/brokers/kis_live.py`
  - `backend/app/services/token_manager.py`
  - `backend/tests/test_kis_paper_adapter.py`
  - `backend/tests/test_token_manager.py`
  - `backend/tests/test_no_live_trading_regression.py`

- 금지 사항
  - No live implementation
  - No guessed KIS endpoint details
  - No token persistence in DB/files/logs
  - No hidden fallback from paper to live

- 구현 조건
  - `BrokerAdapter` must define preview/submit/cancel/list/sync contract methods
  - `KisPaperBrokerAdapter` may implement only document-confirmed capabilities
  - Any unconfirmed capability must raise explicit disabled/confirmation-required errors
  - `KisLiveBrokerAdapter` must remain disabled and fail-closed
  - `KisTokenManager` must keep tokens in memory only and expose redacted metadata only

- 테스트 파일
  - `backend/tests/test_kis_paper_adapter.py`
  - `backend/tests/test_token_manager.py`
  - `backend/tests/test_no_live_trading_regression.py`

- 실행할 검증 명령어
  - `.\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_kis_paper_adapter.py backend/tests/test_token_manager.py backend/tests/test_no_live_trading_regression.py -q`
  - `.\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_phase3c_kis_readonly.py backend/tests/test_phase3d_broker_safety.py -q`
  - `git diff --check`

- 완료 기준
  - Adapter contract exists
  - Paper adapter skeleton exists
  - Live adapter exists only as disabled placeholder
  - Token manager does not persist raw secrets

- 실패 시 rollback 기준
  - Revert adapter introduction if it changes current runtime behavior or weakens fail-closed defaults
  - Revert any path that accidentally makes live mode reachable

- 다음 Phase 진입 조건
  - Contract and token manager tests pass
  - Live-mode regression tests pass

### Phase 3: Paper Trading Persistence

- 목적
  - Extend existing paper tables for broker-synced use
  - Add portfolio snapshot, outbox, delivery log, and generic broker audit tables
  - Keep current synthetic tables untouched

- 수정 대상 파일
  - `backend/app/models/tables.py`
  - `backend/tests/test_alembic_migrations.py`

- 새로 생성할 파일
  - `backend/alembic/versions/<new_revision>_paper_trading_persistence.py`
  - `backend/tests/test_paper_persistence_migration.py`

- 금지 사항
  - No destructive migration
  - No dropping existing tables
  - No raw token columns
  - No reuse of `positions` as paper mirror state

- 구현 조건
  - Extend existing:
    - `paper_orders`
    - `paper_fills`
    - `paper_positions`
  - Add new:
    - `paper_portfolio_snapshots`
    - `broker_audit_events`
    - `notification_events`
    - `notification_delivery_logs`
    - `kis_token_status_metadata`
  - Use nullable-first additive migration strategy
  - Preserve zero-write assumptions until Phase 4 enables paper submit

- 테스트 파일
  - `backend/tests/test_paper_persistence_migration.py`
  - `backend/tests/test_alembic_migrations.py`

- 실행할 검증 명령어
  - `.\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_paper_persistence_migration.py backend/tests/test_alembic_migrations.py -q`
  - `.\\.venv\\Scripts\\python.exe -m alembic upgrade head`
  - `git diff --check`

- 완료 기준
  - Migration upgrades cleanly
  - Existing tables remain intact
  - New tables exist with safe defaults
  - No raw secret field exists

- 실패 시 rollback 기준
  - `alembic downgrade -1` if schema is not yet depended on
  - Revert migration file if tests fail or data model violates safety rules

- 다음 Phase 진입 조건
  - Migration tests pass
  - Schema is additive only

### Phase 4: Paper Order Preview/Submit/Cancel

- 목적
  - Implement paper order lifecycle for preview, submit, and cancel
  - Preserve preview separation
  - Add audit + idempotency guarantees

- 수정 대상 파일
  - `backend/app/api/paper.py`
  - `backend/app/services/paper_trading_service.py`
  - `backend/app/models/schemas.py`
  - `backend/app/brokers/kis_paper.py`

- 새로 생성할 파일
  - `backend/app/services/paper_order_service.py`
  - `backend/tests/test_paper_order_api.py`
  - `backend/tests/test_paper_order_service.py`

- 금지 사항
  - No live submit path
  - No silent submit without `confirm=true`
  - No order creation if kill switch is on
  - No guessed cancel payload if official fields are not confirmed

- 구현 조건
  - Keep `POST /api/paper/orders/preview`
  - Add:
    - `POST /api/paper/orders/submit`
    - `POST /api/paper/orders/cancel`
    - `GET /api/paper/orders`
  - Require explicit `confirm=true` for submit/cancel
  - Use `idempotency_key` and canonical request hash
  - If cancel capability is not fully confirmed from official docs, keep the cancel path disabled with explicit reason instead of guessing

- 테스트 파일
  - `backend/tests/test_paper_order_api.py`
  - `backend/tests/test_paper_order_service.py`
  - `backend/tests/test_no_live_trading_regression.py`

- 실행할 검증 명령어
  - `.\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_paper_order_api.py backend/tests/test_paper_order_service.py backend/tests/test_no_live_trading_regression.py -q`
  - `.\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_phase3e_paper_safety.py -q`
  - `git diff --check`

- 완료 기준
  - Submit path exists for paper only
  - Preview path remains separate
  - Orders are idempotent
  - Cancel behavior is either implemented from confirmed docs or safely disabled with explicit reason

- 실패 시 rollback 기준
  - Revert submit/cancel endpoints if any path can place live orders
  - Revert if confirm/idempotency/kill-switch protections are bypassed

- 다음 Phase 진입 조건
  - Paper order lifecycle tests pass
  - No-live regression passes

### Phase 5: Fill/Position/Portfolio Sync

- 목적
  - Mirror KIS paper account state into local paper tables
  - Add positions, fills, and account snapshot APIs
  - Keep synthetic portfolio logic separate

- 수정 대상 파일
  - `backend/app/api/paper.py`
  - `backend/app/services/paper_trading_service.py`
  - `backend/app/services/portfolio_service.py`
  - `backend/app/brokers/kis_paper.py`

- 새로 생성할 파일
  - `backend/app/services/paper_sync_service.py`
  - `backend/tests/test_paper_sync.py`
  - `backend/tests/test_paper_portfolio_api.py`

- 금지 사항
  - No writes into synthetic `positions` as a mirror of KIS paper state
  - No live sync paths
  - No direct exposure of account numbers

- 구현 조건
  - Add:
    - `GET /api/paper/fills`
    - `GET /api/paper/positions`
    - `GET /api/paper/portfolio`
    - `POST /api/paper/sync`
  - Support sync scopes:
    - `orders`
    - `fills`
    - `positions`
    - `portfolio`
    - `all`
  - Sync must be idempotent and deduplicate repeated fetches
  - Snapshot and position views must rely on `paper_*` tables only

- 테스트 파일
  - `backend/tests/test_paper_sync.py`
  - `backend/tests/test_paper_portfolio_api.py`

- 실행할 검증 명령어
  - `.\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_paper_sync.py backend/tests/test_paper_portfolio_api.py -q`
  - `.\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_no_live_trading_regression.py -q`
  - `git diff --check`

- 완료 기준
  - Paper sync works idempotently
  - Positions and portfolio snapshot endpoints return paper-only mirrored state
  - Synthetic portfolio baseline remains unchanged

- 실패 시 rollback 기준
  - Revert sync if duplicate fills/orders/positions occur
  - Revert if synthetic tables become coupled to paper mirrors

- 다음 Phase 진입 조건
  - Sync tests pass
  - No data mixing between synthetic and paper states

### Phase 6: Report Notification

- 목적
  - Deliver daily/weekly reports through Telegram/Discord
  - Convert markdown reports into channel-safe summaries
  - Support optional file attachment

- 수정 대상 파일
  - `backend/app/api/reports.py`
  - `backend/app/services/report_service.py`
  - `backend/app/services/notification_service.py`

- 새로 생성할 파일
  - `backend/app/services/report_notification_service.py`
  - `backend/tests/test_report_notify.py`

- 금지 사항
  - No raw secret exposure in report-delivery logs
  - No overly long unsplit messages
  - No blocking of report generation because delivery fails

- 구현 조건
  - Add `POST /api/reports/{report_id}/notify`
  - Support:
    - `summary`
    - `summary_and_file`
  - Telegram:
    - split safely below 4096 chars
    - file attachment via document when needed
  - Discord:
    - split safely below 2000 chars or use embed/file
    - set `allowed_mentions.parse=[]`
  - Delivery failures must be logged to delivery tables and not roll back report creation

- 테스트 파일
  - `backend/tests/test_report_notify.py`

- 실행할 검증 명령어
  - `.\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_report_notify.py backend/tests/test_notifications.py -q`
  - `git diff --check`

- 완료 기준
  - Existing reports can be delivered to supported channels
  - Long reports are summarized/split safely
  - Delivery failure does not corrupt report generation

- 실패 시 rollback 기준
  - Revert report notify path if channel length or secret redaction rules are violated

- 다음 Phase 진입 조건
  - Report notify tests pass
  - Delivery logs are correctly recorded

### Phase 7: Bot Scheduler

- 목적
  - Add paper-bot orchestration and scheduler runner
  - Keep auto-submit opt-in only
  - Support once/loop operation with kill switch

- 수정 대상 파일
  - `launcher.py`
  - `backend/app/services/paper_trading_service.py`
  - `backend/app/api/paper.py`
  - `backend/app/services/settings_service.py`
  - `frontend/app/settings/page.tsx`
  - `.env.example`

- 새로 생성할 파일
  - `backend/config/bot.yaml`
  - `backend/app/services/paper_bot_service.py`
  - `backend/app/jobs/paper_bot_runner.py`
  - `backend/tests/test_paper_bot_scheduler.py`

- 금지 사항
  - No default auto-submit
  - No always-on scheduler by default
  - No live trading path
  - No implicit scheduling from API worker without explicit enable flag

- 구현 조건
  - Runner supports:
    - `--once`
    - `--loop`
  - Bot flow:
    - candidate screening
    - signal selection
    - risk guard
    - order preview
    - optional paper submit
    - polling/sync
    - notification
    - report generation
  - `PAPER_BOT_AUTO_SUBMIT=false` by default
  - Scheduler remains disabled unless explicitly enabled
  - Optional launcher integration must also remain disabled by default

- 테스트 파일
  - `backend/tests/test_paper_bot_scheduler.py`

- 실행할 검증 명령어
  - `.\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_paper_bot_scheduler.py backend/tests/test_no_live_trading_regression.py -q`
  - `git diff --check`

- 완료 기준
  - Bot runner exists and can run once safely
  - Loop mode is gated and disabled by default
  - Auto-submit remains explicit opt-in only

- 실패 시 rollback 기준
  - Revert runner integration if scheduler starts automatically or can bypass safety flags

- 다음 Phase 진입 조건
  - Bot scheduler tests pass
  - Default runtime remains manual and safe

### Phase 8: Frontend Integration

- 목적
  - Add minimal UI for paper submit/history/snapshot/notify control
  - Keep the UI clearly labeled as mock trading
  - Avoid any appearance of live-trading readiness

- 수정 대상 파일
  - `frontend/app/paper/page.tsx`
  - `frontend/app/portfolio/page.tsx`
  - `frontend/app/reports/page.tsx`
  - `frontend/app/settings/page.tsx`
  - `frontend/lib/api.ts`

- 새로 생성할 파일
  - `frontend/components/paper-mode-banner.tsx`
  - `backend/tests/test_frontend_api_contracts.py`

- 금지 사항
  - No UI copy that implies live trading
  - No secret values rendered to the browser
  - No frontend-only assumption that bypasses backend safety checks

- 구현 조건
  - `/paper`
    - show paper-mode banner
    - preview/submit/cancel controls
    - recent orders/fills
    - sync action
    - current paper portfolio snapshot
  - `/portfolio`
    - separate synthetic vs paper sections
  - `/reports`
    - add notify button/status
  - `/settings`
    - show redacted `paper`, `notifications`, `bot` summary
  - UI must use explicit labels such as:
    - `모의투자`
    - `실거래 아님`
    - `paper only`

- 테스트 파일
  - `backend/tests/test_frontend_api_contracts.py`

- 실행할 검증 명령어
  - `.\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_frontend_api_contracts.py -q`
  - `cd frontend && npm.cmd run lint && npm.cmd exec tsc -- --noEmit && npm.cmd run build && cd ..`
  - `git diff --check`

- 완료 기준
  - Frontend builds cleanly
  - UI exposes paper-only controls with clear labeling
  - No secret values appear in rendered pages

- 실패 시 rollback 기준
  - Revert UI features if they obscure the mock-trading boundary or fail build/typecheck

- 다음 Phase 진입 조건
  - Frontend lint/typecheck/build pass
  - API contract tests pass

### Phase 9: Validation & Hardening

- 목적
  - Finalize docs, security checks, and regression coverage
  - Ensure live trading remains disabled
  - Prepare the project for controlled paper-mode use

- 수정 대상 파일
  - `README.md`
  - `docs/PROJECT_STATUS.md`
  - `docs/VALIDATION.md`
  - `Memory.md`
  - `.github/workflows/ci.yml`
  - `.env.example`

- 새로 생성할 파일
  - `backend/tests/test_secret_redaction.py`
  - `tools/secret_scan.py`
  - `docs/PAPER_TRADING_OPERATION.md`

- 금지 사항
  - No weakening of safety defaults for convenience
  - No real secret values in docs or examples
  - No silent live-mode support

- 구현 조건
  - Update docs to reflect the new paper-only baseline
  - Add explicit final acceptance notes
  - Add/expand:
    - security/redaction tests
    - no-live-trading regression tests
    - migration tests
    - notifier mock tests
    - KIS adapter mock tests
  - Add secret scan step to local validation and CI if practical

- 테스트 파일
  - `backend/tests/test_secret_redaction.py`
  - `backend/tests/test_no_live_trading_regression.py`
  - `backend/tests/test_alembic_migrations.py`

- 실행할 검증 명령어
  - `.\\.venv\\Scripts\\python.exe -m pytest backend/tests -q`
  - `.\\.venv\\Scripts\\python.exe tools/secret_scan.py`
  - `cd frontend && npm.cmd run lint && npm.cmd exec tsc -- --noEmit && npm.cmd run build && cd ..`
  - `git diff --check`

- 완료 기준
  - Full backend pytest passes
  - Frontend lint/typecheck/build passes
  - Secret scan passes
  - Docs match actual code state
  - Live trading remains disabled by default and fail-closed

- 실패 시 rollback 기준
  - Revert final hardening changes that break CI/build or weaken the safety boundary
  - Do not declare the project complete unless full validation passes

- 다음 Phase 진입 조건
  - None; this is the final phase

## Final Acceptance Criteria

- KIS paper broker path exists and is clearly separated from live
- Live trading remains disabled by default and unreachable in normal flow
- Existing preview-only baseline is preserved where expected
- Paper submit/sync/report/notify flow works without mixing paper and synthetic portfolio state
- Notifications support disabled/mock plus real Discord/Telegram implementations
- No raw secrets or raw account numbers appear in code, docs, logs, DB, reports, or browser output
- Scheduler exists but remains disabled by default
- Frontend clearly labels all paper features as mock trading only
- Backend tests pass
- Frontend lint, typecheck, and build pass
- Final docs accurately reflect the implemented state
