# KIS Paper Dry-run Checklist

## Scope

This checklist belongs to `goal.md` Phase 12, but Phase 12 is no longer treated
as a single dry-run step. It is split into:

| Phase | Name | Status |
|---|---|---|
| Phase 12A | KIS paper read-only balance dry-run | Not executed in this run |
| Phase 12B | KIS paper submit/cancel/query/sync adapter implementation | Implemented and committed in `bcd40fac2a67e8c06aad32bd1f1f386b3abcab8e`; mock tests passed |
| Phase 12C | Controlled KIS paper submit/cancel/query/sync dry-run | Actual paper submit attempted after human confirmation; KIS rejected during market-closed window before broker order creation |

Phase 13 must not start until Phase 12C has a redacted successful dry-run
record. Phase 12 must not be marked complete from env flags alone.

## Current Code Finding

Status: Phase 12 remains incomplete. Phase 12B adapter implementation is present, and Phase 12C reached the KIS paper submit endpoint after human confirmation. KIS returned `40580000` / `모의투자 장종료 입니다.`, so no broker order id was created and cancel/query/sync did not run.

The current code has dedicated paper KIS submit/cancel/list/sync adapter paths behind
explicit gates. A separate real KIS live-order path now also exists (KRX domestic
cash only) behind its own fail-closed gates and reuses the paper mappers; it is not
exercised by this paper checklist. Default runtime remains fail-closed. A controlled
Phase 12C KIS paper submit call was executed only after human confirmation and
produced a redacted failure record; no live endpoint was called during this paper run.

| Area | Current code behavior | Evidence |
|---|---|---|
| KIS paper balance | Can call read-only `/uapi/domestic-stock/v1/trading/inquire-balance` only when all config/env/credential gates pass | `PaperSyncService.portfolio()` and `KisPaperBalanceClient` |
| Paper submit | Local submit remains default. KIS paper network submit exists only when paper mode, process env flags, config gate, adapter gate, credential gate, kill switch off, `confirm=true`, and idempotency key all pass | `PaperOrderService` and `KisPaperBrokerAdapter.submit_order()` |
| Paper cancel | KIS paper network cancel exists only for a stored paper order with broker order id and all cancel gates passing | `PaperOrderService.cancel_order()` and `KisPaperBrokerAdapter.cancel_order()` |
| Paper query/sync | KIS paper query/sync exists only when paper network/config/adapter/credential gates pass, and persists only dedicated paper tables | `KisPaperBrokerAdapter.list_orders()` and `PaperSyncService.sync()` |
| KIS paper adapter | Uses paper endpoint/TR ID mappers, redacted trace, timeout/retry/rate-limit/error handling; unconfirmed cancelable-order query remains unimplemented/fail-closed | `KisPaperBrokerAdapter` |
| Live adapter | Real KIS live orders are now enabled (KRX domestic cash only) but fail-closed by default behind multiple gates: `LIVE_TRADING_ENABLED` + `LIVE_ORDER_SUBMIT_ENABLED` + `ENABLE_REAL_ORDER` + live credentials + live host + per-order confirm + kill switch + max-notional. Routes `/api/kis/orders/{status,preview,submit,cancel}` + `/api/live/status` reuse the paper mappers (V->T TR ID). Live execution is UNTESTED vs the real KIS API; verify the first order with minimal qty | `KisLiveOrderExecutor` |

## Required Env/Config Items

Settings are toggleable from the UI and persist to `backend/data/runtime_env.json`
(allowlisted keys, masked values); credentials can be entered in-app. Runtime
values may still be injected through the process environment for this checklist,
and raw values must not be printed.

| Item | Phase 12A | Phase 12B | Phase 12C |
|---|---|---|---|
| `KIS_APP_KEY` | Required for read-only balance dry-run | Mocked in tests only; real value not required | Required via in-app persisted settings or process env |
| `KIS_APP_SECRET` | Required for read-only balance dry-run | Mocked in tests only; real value not required | Required via in-app persisted settings or process env |
| `KIS_ACCESS_TOKEN` | Required for read-only balance dry-run | Mocked in tests only; real value not required | Required via in-app persisted settings or process env |
| `KIS_ACCOUNT_NO` | Required for read-only balance dry-run | Mocked/redacted only | Required via in-app persisted settings or process env |
| `KIS_PRODUCT_CODE` | Required for read-only balance dry-run | Mocked/redacted only | Required via in-app persisted settings or process env |
| `KIS_PAPER_BASE_URL` | Optional; must not be live host | Mocked; live host must be rejected | Optional; must not be live host |
| `ENABLE_REAL_ORDER` | Keep absent or false for this paper dry-run (it is now a live-order gate, not forced false) | Keep absent or false for this paper dry-run (it is now a live-order gate, not forced false) | Keep absent or false for this paper dry-run (it is now a live-order gate, not forced false) |
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
- [ ] Provide KIS paper credentials in-app (persisted to `backend/data/runtime_env.json`, allowlisted and masked) or through the process environment; do not print raw values.
- [ ] Confirm `ENABLE_REAL_ORDER` is absent or false.
- [ ] Confirm `PAPER_BOT_AUTO_SUBMIT=false`.
- [ ] Confirm the live-order gates stay off for this paper dry-run so no live path activates.
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
- [ ] Provide credentials in-app (persisted to `backend/data/runtime_env.json`, allowlisted and masked) or through the process environment; do not print raw values.
- [ ] Confirm `ENABLE_REAL_ORDER` is absent or false.
- [ ] Confirm the live-order gates stay off for this paper dry-run so no live path activates.
- [ ] Confirm `PAPER_BOT_AUTO_SUBMIT=false`.
- [ ] Keep bot loop stopped during first controlled dry-run.

### Controlled execution

- [ ] Run `.\.venv\Scripts\python.exe tools\kis_paper_phase12c_dry_run.py` first and confirm it reports only redacted preflight status with no network call.
- [ ] Verify kill switch blocks submit while enabled.
- [ ] Obtain explicit human confirmation immediately before submit.
- [ ] Confirm KIS paper trading window immediately before submit, then pass `--confirm-trading-window CONFIRM_KIS_PAPER_TRADING_WINDOW`.
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

- [ ] If using the helper, execute with `--execute --confirm-submit CONFIRM_KIS_PAPER_PHASE12C --confirm-cancel CONFIRM_KIS_PAPER_PHASE12C --confirm-trading-window CONFIRM_KIS_PAPER_TRADING_WINDOW` only after all process env/runtime gates are prepared and the KIS paper trading window is currently open.
- [ ] Record submit attempt ID, symbol, side, quantity, sanitized order identifier, status, and error code if any.
- [ ] Record query/sync scope, status, redacted broker trace, and row counts.
- [ ] Record cancel status and sanitized order identifier only.
- [ ] Do not store raw KIS AppKey, AppSecret, token, account number, Telegram token, chat ID, webhook URL, or raw broker payload.

### 12C validation

```powershell
.\.venv\Scripts\python.exe tools\kis_paper_phase12c_dry_run.py
.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase12c_tool.py -q
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
| Execution status | Phase 12C submit stopped after KIS paper market-closed response |
| Phase 12B commit | `bcd40fac2a67e8c06aad32bd1f1f386b3abcab8e` |
| Reason | KIS paper submit returned `40580000` / `모의투자 장종료 입니다.` before broker order creation |
| Credential gate | `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCESS_TOKEN`, `KIS_ACCOUNT_NO`, `KIS_PRODUCT_CODE` all configured by redacted boolean check; raw values were not printed or recorded |
| Runtime gate | `PAPER_TRADING_ENABLED`, `PAPER_TRADING_CAN_CREATE`, `PAPER_TRADING_NETWORK_ENABLED` enabled and `PAPER_TRADING_KILL_SWITCH` explicitly false by redacted boolean check |
| Config gate | `backend/config/paper.yaml` remains `mode=safety_scaffold`, `enabled=false`, `can_create=false`, `network_enabled=false`, `kill_switch_enabled=true`, adapter disabled |
| 12C helper | `tools/kis_paper_phase12c_dry_run.py` added; default mode is preflight-only and performs no network call |
| 12C temporary config | `--temporary-paper-config` uses a process-only config override and does not write `backend/config/paper.yaml` |
| 12C helper preflight | `--temporary-paper-config` reported `preflight_only`, `preflight.ok=true`, and `network_call_performed=false` |
| Execute confirmation gate | `--temporary-paper-config --execute` without submit/cancel tokens stopped with `confirmation_required` and `network_call_performed=false` |
| Trading-window confirmation gate | `--temporary-paper-config --execute --confirm-submit CONFIRM_KIS_PAPER_PHASE12C --confirm-cancel CONFIRM_KIS_PAPER_PHASE12C` stopped with `trading_window_confirmation_required` and `network_call_performed=false` |
| Controlled submit | `--temporary-paper-config --execute --confirm-submit CONFIRM_KIS_PAPER_PHASE12C --confirm-cancel CONFIRM_KIS_PAPER_PHASE12C --qty 1 --limit-price 230000` reached `/uapi/domestic-stock/v1/trading/order-cash`, `tr_id=VTTC0012U`, `status_code=200`, then failed with `KIS_PAPER_RESPONSE_ERROR` |
| Network calls | One KIS paper submit call; no cancel/query/sync network call because no broker order id was created |
| Live endpoint calls | None |
| Secret exposure | None observed; no raw credential/account/token value was printed or written |
| Next executable phase | Phase 12C controlled dry-run must be retried during a KIS paper trading window; Phase 13 remains blocked |
| Phase 13 eligibility | Not eligible |

## Rollback Rule

If the KIS mock contract mismatches the implementation at any step, keep the
submit/cancel/query/sync network path disabled, preserve local-only fallback
behavior, re-enable the kill switch, and stop before entering Phase 13.
