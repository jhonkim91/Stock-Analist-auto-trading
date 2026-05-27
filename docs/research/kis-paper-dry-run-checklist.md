# KIS Paper Dry-run Checklist

## Scope

This checklist belongs to `goal.md` Phase 12, but Phase 12 is no longer treated
as a single dry-run step. It is split into:

| Phase | Name | Status |
|---|---|---|
| Phase 12A | KIS paper read-only balance dry-run | Not executed in this run |
| Phase 12B | KIS paper submit/cancel/query/sync adapter implementation | Implemented and committed in `bcd40fac2a67e8c06aad32bd1f1f386b3abcab8e`; mock tests passed |
| Phase 12C | Controlled KIS paper submit/cancel/query/sync dry-run | Preflight stopped: required process credential/runtime/config gates are not open |

Phase 13 must not start until Phase 12C has a redacted successful dry-run
record. Phase 12 must not be marked complete from env flags alone.

## Current Code Finding

Status: Phase 12 remains incomplete. Phase 12B adapter implementation is present, but Phase 12C real-network dry-run stopped at preflight.

The current code has paper-only KIS submit/cancel/list/sync adapter paths behind
explicit gates. Default runtime remains fail-closed, and no real KIS paper
network call has been executed in this review.

| Area | Current code behavior | Evidence |
|---|---|---|
| KIS paper balance | Can call read-only `/uapi/domestic-stock/v1/trading/inquire-balance` only when all config/env/credential gates pass | `PaperSyncService.portfolio()` and `KisPaperBalanceClient` |
| Paper submit | Local submit remains default. KIS paper network submit exists only when paper mode, process env flags, config gate, adapter gate, credential gate, kill switch off, `confirm=true`, and idempotency key all pass | `PaperOrderService` and `KisPaperBrokerAdapter.submit_order()` |
| Paper cancel | KIS paper network cancel exists only for a stored paper order with broker order id and all cancel gates passing | `PaperOrderService.cancel_order()` and `KisPaperBrokerAdapter.cancel_order()` |
| Paper query/sync | KIS paper query/sync exists only when paper network/config/adapter/credential gates pass, and persists only dedicated paper tables | `KisPaperBrokerAdapter.list_orders()` and `PaperSyncService.sync()` |
| KIS paper adapter | Uses paper endpoint/TR ID mappers, redacted trace, timeout/retry/rate-limit/error handling; unconfirmed cancelable-order query remains unimplemented/fail-closed | `KisPaperBrokerAdapter` |
| Live adapter | Placeholder only and always disabled | `KisLiveBrokerAdapter` |

## Required Env/Config Items

Do not create or modify `.env` or `.env.local`. Inject runtime values through
the current process environment only, and do not print raw values.

| Item | Phase 12A | Phase 12B | Phase 12C |
|---|---|---|---|
| `KIS_APP_KEY` | Required for read-only balance dry-run | Mocked in tests only; real value not required | Required through process env only |
| `KIS_APP_SECRET` | Required for read-only balance dry-run | Mocked in tests only; real value not required | Required through process env only |
| `KIS_ACCESS_TOKEN` | Required for read-only balance dry-run | Mocked in tests only; real value not required | Required through process env only |
| `KIS_ACCOUNT_NO` | Required for read-only balance dry-run | Mocked/redacted only | Required through process env only |
| `KIS_PRODUCT_CODE` | Required for read-only balance dry-run | Mocked/redacted only | Required through process env only |
| `KIS_PAPER_BASE_URL` | Optional; must not be live host | Mocked; live host must be rejected | Optional; must not be live host |
| `ENABLE_REAL_ORDER` | Must be absent or false | Must be absent or false | Must be absent or false |
| `PAPER_TRADING_ENABLED` | Explicit true only for manual read-only test | Required gate in implementation tests | Explicit true only for controlled dry-run |
| `PAPER_TRADING_CAN_CREATE` | Keep false/not needed for read-only | Required for local submit path tests | Explicit true only around controlled submit |
| `PAPER_TRADING_NETWORK_ENABLED` | Explicit true only for read-only balance network call | Required gate, but mocked HTTP only | Explicit true only for controlled paper network call |
| `PAPER_TRADING_KILL_SWITCH` | Keep true/absent for read-only | Must default to blocking | Must prove block first, then explicit false only for one controlled attempt |
| `PAPER_BOT_AUTO_SUBMIT` | Must stay false | Must default false | Must stay false |
| `live_fallback_enabled` | Must remain false | Must remain false | Must remain false |

## Phase 12A Checklist: Read-only Balance Dry-run

### Preflight

- [ ] Confirm current branch is not `main`.
- [ ] Confirm worktree is clean before injecting any runtime credential.
- [ ] Confirm `.env` and `.env.local` are not created or modified.
- [ ] Inject KIS paper credentials only through the process environment.
- [ ] Confirm `ENABLE_REAL_ORDER` is absent or false.
- [ ] Confirm `PAPER_BOT_AUTO_SUBMIT=false`.
- [ ] Confirm live adapter and live fallback remain disabled.
- [ ] Confirm submit/cancel/sync paths remain blocked.

### Read-only execution

- [ ] Enable only the read-only KIS paper balance path.
- [ ] Call `/api/paper/portfolio` and verify the request uses paper base URL and paper balance TR ID only.
- [ ] Record only redacted metadata: route, endpoint path, TR ID, status code, elapsed time, correlation ID, and result status.
- [ ] Confirm API response does not include raw account number, token, app key, app secret, webhook URL, Telegram token, or chat ID.
- [ ] Confirm fallback stays local `paper_portfolio_snapshots` when read-only query is disabled or fails.

### 12A validation

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_balance.py backend/tests/test_no_live_trading_regression.py -q
.\.venv\Scripts\python.exe tools\secret_scan.py
git diff --check
```

### 12A completion

- [ ] `docs/VALIDATION.md` contains the redacted read-only dry-run result.
- [ ] `Memory.md` says Phase 12A is complete but Phase 12 as a whole remains incomplete.
- [ ] No submit/cancel/sync network implementation or execution happened.

## Phase 12B Checklist: Adapter Implementation

Phase 12B is an implementation phase, not a real-network dry-run phase.
Real KIS paper submit/cancel/query/sync calls must not be executed during 12B.

### Implementation conditions

- [ ] Confirm official KIS paper submit, cancel, cancelable-order query, daily order/fill query, balance/position query, hashkey/signing, request fields, response fields, and paper TR IDs.
- [ ] Keep unconfirmed endpoint/TR/request/response items fail-closed.
- [ ] Implement only paper base URL support; reject live base URL.
- [ ] Require explicit process env gates for paper network execution.
- [ ] Keep kill switch blocking submit by default.
- [ ] Preserve `confirm=true`, idempotency key, duplicate prevention, risk gate, and broker audit redaction.
- [ ] Store/update only dedicated paper tables for broker-synced state.
- [ ] Do not touch live account state or treat synthetic `positions` as broker truth.
- [ ] Keep bot auto-submit disabled by default.

### Required test conditions

- [ ] Mocked HTTP success tests for submit/cancel/query/sync.
- [ ] Missing credential/env flag tests fail closed.
- [ ] Kill-switch tests block submit.
- [ ] Live base URL tests fail closed.
- [ ] Unsupported TR ID or unconfirmed field tests fail closed.
- [ ] Secret/account/token redaction tests pass.
- [ ] Idempotency and duplicate submit tests pass.
- [ ] No-live regression tests pass.
- [ ] CI does not require real KIS network calls.

### 12B validation

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_runtime_flags.py backend/tests/test_no_live_trading_regression.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe tools\secret_scan.py
git diff --check
```

### 12B completion

- [ ] Mocked contract and safety tests pass.
- [ ] Default runtime remains fail-closed.
- [ ] No real KIS paper submit/cancel/query/sync dry-run has been executed yet.

## Phase 12C Checklist: Controlled Submit/Cancel/Query/Sync Dry-run

Phase 12C is blocked until Phase 12B is implemented and tested.

### Preflight

- [ ] Confirm Phase 12B commit is present and tests passed.
- [ ] Confirm current branch is not `main`.
- [ ] Confirm `.env` and `.env.local` are not created or modified.
- [ ] Inject credentials only through process env.
- [ ] Confirm `ENABLE_REAL_ORDER` is absent or false.
- [ ] Confirm live adapter/fallback remain disabled.
- [ ] Confirm `PAPER_BOT_AUTO_SUBMIT=false`.
- [ ] Keep bot loop stopped during first controlled dry-run.

### Controlled execution

- [ ] Verify kill switch blocks submit while enabled.
- [ ] Obtain explicit human confirmation immediately before submit.
- [ ] Use a minimum-size paper order only.
- [ ] Temporarily disable kill switch only for the single controlled paper submit attempt.
- [ ] Confirm paper mode, paper base URL, and paper TR ID are used.
- [ ] Query cancelable/open paper orders.
- [ ] Query daily paper order/fill status.
- [ ] Run paper sync only if query response contract matches implementation assumptions.
- [ ] Obtain explicit human confirmation immediately before cancel.
- [ ] Cancel only the paper order created during this dry-run.
- [ ] Re-enable kill switch immediately after the controlled attempt.

### Redacted record

- [ ] Record submit attempt ID, symbol, side, quantity, sanitized order identifier, status, and error code if any.
- [ ] Record query/sync scope, status, redacted broker trace, and row counts.
- [ ] Record cancel status and sanitized order identifier only.
- [ ] Do not store raw KIS AppKey, AppSecret, token, account number, Telegram token, chat ID, webhook URL, or raw broker payload.

### 12C validation

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_runtime_flags.py backend/tests/test_no_live_trading_regression.py -q
.\.venv\Scripts\python.exe tools\secret_scan.py
git diff --check
```

### 12C completion

- [ ] `docs/VALIDATION.md` contains the redacted controlled submit/cancel/query/sync dry-run result.
- [ ] `Memory.md` says Phase 12C completed and Phase 13 is eligible.
- [ ] No live endpoint was called and no secret/account/token value was exposed.

## Current Dry-run Result Record

| Item | Result |
|---|---|
| Execution status | Phase 12C preflight stopped |
| Phase 12B commit | `bcd40fac2a67e8c06aad32bd1f1f386b3abcab8e` |
| Reason | Required KIS paper credential/process env gates are not present, and repo config remains fail-closed |
| Credential gate | `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCESS_TOKEN`, `KIS_ACCOUNT_NO`, `KIS_PRODUCT_CODE` all not configured in the current process |
| Runtime gate | `PAPER_TRADING_ENABLED`, `PAPER_TRADING_CAN_CREATE`, `PAPER_TRADING_NETWORK_ENABLED`, `PAPER_TRADING_KILL_SWITCH` not configured in the current process |
| Config gate | `backend/config/paper.yaml` remains `mode=safety_scaffold`, `enabled=false`, `can_create=false`, `network_enabled=false`, `kill_switch_enabled=true`, adapter disabled |
| Network calls | None in this Phase 12C preflight |
| Live endpoint calls | None |
| Secret exposure | None observed; no raw credential/account/token value was printed or written |
| Next executable phase | Phase 12C retry after process credential/runtime/config gates are prepared, or Phase 12A if read-only balance dry-run is required first |
| Phase 13 eligibility | Not eligible |

## Rollback Rule

If the KIS mock contract mismatches the implementation at any step, keep the
submit/cancel/query/sync network path disabled, preserve local-only fallback
behavior, re-enable the kill switch, and stop before entering Phase 13.
