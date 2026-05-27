# KIS Paper Dry-run Checklist

## Scope

This checklist belongs to `goal.md` Phase 12: Controlled KIS Paper Trading Dry Run.
It is a manual validation checklist only. It must not enable live trading paths and
must not store raw KIS credentials, access tokens, account numbers, Telegram tokens,
chat IDs, or Discord webhook URLs in code, documents, logs, DB rows, or API responses.

## Current preflight result

Status: blocked before network execution.

As of 2026-05-27, the local checkout did not have the required KIS paper credentials
or explicit paper-network/submit enable flags in the process environment. `backend/config/paper.yaml`
also remained on the safe default:

| Gate | Current state | Required for dry-run |
|---|---:|---:|
| `KIS_APP_KEY` | absent | present via process env only |
| `KIS_APP_SECRET` | absent | present via process env only |
| `KIS_ACCESS_TOKEN` | absent | present via process env only |
| `KIS_ACCOUNT_NO` | absent | present via process env only |
| `KIS_PRODUCT_CODE` | absent | present via process env only |
| `PAPER_TRADING_ENABLED` | absent | explicit human-enabled value |
| `PAPER_TRADING_CAN_CREATE` | absent | explicit human-enabled value |
| `PAPER_TRADING_NETWORK_ENABLED` | absent | explicit human-enabled value |
| `PAPER_TRADING_KILL_SWITCH` | absent | must be explicitly off for submit test |
| `PAPER_BOT_AUTO_SUBMIT` | absent | must stay off during first dry-run |
| config `enabled` | false | explicit true only for manual test |
| config `can_create` | false | explicit true only for manual test |
| config `network_enabled` | false | explicit true only for manual test |
| config `kill_switch_enabled` | true | must block all submit while true |
| config `live_fallback_enabled` | false | must remain false |

No KIS network call was executed in this preflight.

## Official sample references checked

The following capability references were checked against the official
`koreainvestment/open-trading-api` sample repository before attempting the dry-run:

| Capability | Official sample path | Paper-mode note |
|---|---|---|
| Cash order submit | `examples_llm/domestic_stock/order_cash/order_cash.py` | `env_dv="demo"` selects paper TR IDs for buy/sell |
| Order modify/cancel | `examples_llm/domestic_stock/order_rvsecncl/order_rvsecncl.py` | `env_dv="demo"` selects paper cancel/modify TR ID |
| Cancelable order query | `examples_llm/domestic_stock/inquire_psbl_rvsecncl/inquire_psbl_rvsecncl.py` | sample currently uses a single TR ID and needs local policy review before enabling |
| Daily order/fill query | `examples_llm/domestic_stock/inquire_daily_ccld/inquire_daily_ccld.py` | `env_dv="demo"` selects paper TR IDs |
| Balance/position query | `examples_llm/domestic_stock/inquire_balance/inquire_balance.py` | `env_dv="demo"` selects paper balance TR ID |

The local application still treats submit/cancel/sync network execution as disabled
unless all project safety gates are explicitly opened for a manual paper-only test.

## Runtime flag enforcement

The backend enforces the manual flags through `PaperConfigService`.

| Config gate | Required env gate | Effective behavior |
|---|---|---|
| `paper.enabled=true` | `PAPER_TRADING_ENABLED=true` | without env, paper trading remains disabled |
| `paper.can_create=true` | `PAPER_TRADING_CAN_CREATE=true` | without env, local paper submit remains blocked |
| `paper.network_enabled=true` | `PAPER_TRADING_NETWORK_ENABLED=true` | without env, network stays disabled; with env, paper submit still rejects network order execution |
| `paper.kill_switch_enabled=false` | `PAPER_TRADING_KILL_SWITCH=false` | without explicit false, kill switch remains blocking |

This keeps configuration-file edits from accidentally opening paper submit/network
paths. It also preserves the current no-live-trading boundary: live fallback remains
disabled, and submit network execution remains unsupported until the KIS paper
contract is separately confirmed.

## Manual dry-run checklist

### 1. Preflight

- [ ] Confirm current branch is not `main`.
- [ ] Confirm worktree is clean before enabling any runtime flag.
- [ ] Confirm `.env` and `.env.local` are not created or modified.
- [ ] Inject KIS paper credentials only through the process environment.
- [ ] Confirm no raw credential/account/token value is printed to terminal or stored in docs.
- [ ] Confirm `ENABLE_REAL_ORDER` is absent or false.
- [ ] Confirm live adapter remains disabled.
- [ ] Confirm `live_fallback_enabled=false`.
- [ ] Confirm `PAPER_BOT_AUTO_SUBMIT=false`.
- [ ] Keep bot loop stopped during first dry-run.
- [ ] Keep submit blocked while `kill_switch_enabled=true`; verify blocked submit first.

### 2. Read-only query validation

- [ ] Validate `/api/paper/portfolio` read-only balance/position query with paper credentials.
- [ ] Record only redacted request metadata: route name, paper/live mode, endpoint path, TR ID, status code, elapsed time, and correlation ID.
- [ ] Confirm API response does not include raw account number, token, app key, app secret, webhook URL, Telegram token, or chat ID.
- [ ] Confirm fallback stays local snapshot when the read-only query is disabled or fails.

### 3. Controlled submit validation

- [ ] Obtain explicit human confirmation immediately before submit.
- [ ] Use a minimum-size paper order only.
- [ ] Verify kill switch blocks submit when enabled.
- [ ] Disable kill switch only for the single controlled submit attempt.
- [ ] Confirm paper mode is selected and no live endpoint/base URL is used.
- [ ] Record redacted outcome metadata only: submit attempt ID, symbol, side, quantity, sanitized order identifier, status, and error code if any.
- [ ] Re-enable kill switch immediately after the submit attempt.

### 4. Query/sync validation

- [ ] Query cancelable/open orders before attempting cancel.
- [ ] Query daily order/fill status after submit.
- [ ] Run local sync only if the KIS paper query contract matches implementation assumptions.
- [ ] Do not mutate live account, live balance, or live order state.
- [ ] Record only redacted outcome metadata.

### 5. Controlled cancel validation

- [ ] Cancel only a paper order created during this dry-run.
- [ ] Obtain explicit human confirmation immediately before cancel.
- [ ] Confirm cancel request uses paper endpoint/TR only.
- [ ] Confirm cancel result through paper query path.
- [ ] Record only sanitized order identifiers and status/error code.

### 6. Notification and report validation

- [ ] Verify notification failures stay non-blocking and outbox-backed.
- [ ] Confirm notification payloads contain no raw credential/account/token/webhook/chat ID values.
- [ ] Confirm report notification includes redacted outcome metadata only.

### 7. Post-run validation

- [ ] Run targeted backend tests.
- [ ] Run `.\.venv\Scripts\python.exe tools\secret_scan.py`.
- [ ] Run `git diff --check`.
- [ ] Confirm no raw secrets in modified files.
- [ ] Confirm no live trading path was enabled.
- [ ] Document the redacted dry-run result in `docs/VALIDATION.md`.
- [ ] Update `Memory.md` with the latest state and remaining risk.

## Dry-run result record

| Item | Result |
|---|---|
| Execution status | Not executed |
| Reason | Required KIS paper credentials and explicit human-enabled paper-network/submit flags were not present |
| Network calls | None |
| Live endpoint calls | None |
| Secret exposure | None observed in preflight |
| Next Phase eligibility | Not eligible until a controlled paper dry-run completes |

## Rollback rule

If the KIS mock contract mismatches the current implementation at any step, keep
the submit/cancel/sync network path disabled, preserve local-only fallback behavior,
and stop before entering Phase 13.
