# Live Phase 3 process-only environment template.
# Replace placeholder values in a fresh PowerShell session. Do not commit real values.
# This template does not run a network call or create an order.

$env:KIS_APP_KEY = "<kis_live_app_key>"
$env:KIS_APP_SECRET = "<kis_live_app_credential>"
$env:KIS_REFRESH_TOKEN = "<kis_refresh_token_from_authorization_code_flow>"
$env:KIS_LIVE_BASE_URL = "https://openapi.koreainvestment.com:9443"
$env:ENABLE_REAL_ORDER = "false"
$env:LIVE_TOKEN_REFRESH_ENABLED = "true"
$env:LIVE_TOKEN_REFRESH_PROCESS_ONLY = "true"
$env:LIVE_TOKEN_REFRESH_NETWORK_ENABLED = "true"
$env:LIVE_TOKEN_REFRESH_CONFIRMATION = "CONFIRM_KIS_LIVE_TOKEN_REFRESH"
$env:LIVE_CANARY_CONFIRMATION = "CONFIRM_LIVE_CANARY_PHASE20"
$env:LIVE_CANARY_REVIEWER = "<reviewer_id_no_secret>"
$env:LIVE_CANARY_ENVIRONMENT = "prod-live-isolated"
$env:LIVE_CANARY_ROLLBACK_READY = "true"
$env:LIVE_CANARY_KILL_SWITCH_READY = "true"
$env:LIVE_CANARY_MINIMUM_SIZE_CONFIRMED = "true"
$env:LIVE_EMERGENCY_STOP_ARMED = "true"
$env:LIVE_RATE_LIMIT_PER_SECOND = "2"
$env:LIVE_RATE_LIMIT_BURST = "5"
$env:LIVE_IDEMPOTENCY_REQUIRED = "true"
$env:LIVE_AUDIT_LOG_ENABLED = "true"
$env:LIVE_AUDIT_REDACTION_ENABLED = "true"
$env:LIVE_MAX_ORDER_NOTIONAL = "100000"
$env:LIVE_BLACKLIST_ENABLED = "true"
$env:LIVE_SYMBOL_BLACKLIST = "LEVERAGED,INVERSE"
$env:LIVE_ORDER_COOLDOWN_SECONDS = "30"

# No-network verification:
.\.venv\Scripts\python.exe tools\live_phase3_completion_audit.py
.\.venv\Scripts\python.exe tools\kis_live_token_refresh_preflight.py

# Token refresh proof requires separate operator approval:
# .\.venv\Scripts\python.exe tools\kis_live_token_refresh_preflight.py --execute --confirm CONFIRM_KIS_LIVE_TOKEN_REFRESH --write-record
# After a successful token refresh proof record:
# .\.venv\Scripts\python.exe tools\live_phase3_completion_audit.py --token-refresh-record-path docs\research\kis-live-token-refresh-preflight-record.json
# Optional redacted authority approval record, still no submit/cancel authority by itself:
# .\.venv\Scripts\python.exe tools\live_authority_approval_preflight.py --approve --confirm CONFIRM_LIVE_AUTHORITY_APPROVAL --operations submit,cancel --write-record
# .\.venv\Scripts\python.exe tools\live_phase3_completion_audit.py --authority-record-path docs\research\live-authority-approval-record.json
