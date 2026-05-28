# KIS 모의투자 자동매매 Runbook

## 핵심 요약

이 runbook은 KIS 모의투자 전용 자동매매 기능의 수동 운영 절차다. 기본 상태는 disabled/fail-closed이며, 실제 KIS 호출은 CI에서 실행하지 않는다.

## 사전 조건

| 항목 | 필요값 | 비고 |
|---|---|---|
| `KIS_ENV` | `paper` | `live` 또는 빈 값이면 차단 |
| `ENABLE_REAL_ORDER` | `false` 또는 미설정 | true면 항상 차단 |
| `PAPER_TRADING_ENABLED` | `true` | paper trading runtime gate |
| `PAPER_TRADING_CAN_CREATE` | `true` | local paper order 생성 gate |
| `PAPER_TRADING_NETWORK_ENABLED` | `true` | KIS paper network gate |
| `PAPER_TRADING_KILL_SWITCH` | `false` | true/미설정이면 차단 |
| `PAPER_BOT_CONFIRM` | `true` | paper bot/order 최종 확인 gate |
| `BROKER_MODE` | `paper_kis` | KIS paper adapter만 허용 |
| `PAPER_ORDER_SUBMIT_ENABLED` | `true` | KIS paper submit 전용 gate |
| `KIS_TOKEN_ISSUE_ENABLED` | `true` | token 발급을 실제 KIS paper로 호출할 때만 |
| `KIS_WEBSOCKET_APPROVAL_ENABLED` | `true` | WebSocket approval key 발급을 실제 KIS paper로 호출할 때만 |
| `PAPER_WEBSOCKET_ENABLED` | `true` | paper WebSocket status/subscription gate |
| `PAPER_WEBSOCKET_CONNECT_ENABLED` | `false` 기본 | unattended loop 방지. bounded smoke 전 별도 승인 필요 |

실제 값은 절대 로그나 문서에 기록하지 않는다. 확인은 boolean configured 상태와 redacted fingerprint만 사용한다.

## 기본 상태 확인

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/kis/status
Invoke-RestMethod http://127.0.0.1:8000/api/broker/status
Invoke-RestMethod http://127.0.0.1:8000/api/paper/status
Invoke-RestMethod http://127.0.0.1:8000/api/paper/realtime/status
Invoke-RestMethod http://127.0.0.1:8000/api/paper/dashboard
```

기본 기대값:

- `live_trading_enabled=false`
- `paper_order_created=false`
- `broker_order_created=false`
- `network_call_performed=false`
- `kill_switch.blocking=true`
- secret/account/token 원문 미노출

## DB Migration

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

성공 기준:

- Alembic head가 `d1e2f3a4b5c6`까지 적용된다.
- `paper_bot_runs`에는 `trade_date`, `dry_run`, `preview_count`, `skipped_count`, `rejected_count`, `request_json`, `result_json`가 존재한다.
- raw account number, app key, app secret, access token, refresh token column이 없어야 한다.

## Worker 상태

기본 worker는 운영 WebSocket daemon이 아니라 backend process 내부의 polling/mock quote cache와 heartbeat 상태를 제공한다. KIS paper WebSocket은 approval key와 subscription preview route만 기본 제공하며, 장시간 연결 loop는 별도 bounded smoke 절차 전까지 실행하지 않는다.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/paper/realtime/status
Invoke-RestMethod http://127.0.0.1:8000/api/paper/realtime/websocket/status
```

성공 기준:

- 기본값은 `enabled=false`, `reason_codes`에 `PAPER_REALTIME_DISABLED`가 포함된다.
- realtime fresh quote gate를 켠 상태에서 quote가 없거나 stale이면 신규 주문은 `PAPER_REALTIME_STALE_QUOTE`로 차단된다.
- WebSocket reconnect 지표는 dashboard `metrics.websocket_reconnect_count` 또는 worker status `metrics.websocket_reconnect_count`에서 확인한다.
- `/api/kis/websocket/*` route는 live성 경계로 계속 미등록 상태를 유지한다.

## Token 및 WebSocket approval

token 발급과 WebSocket approval key 발급은 process-only gate와 `confirm=true`가 모두 있을 때만 실제 KIS paper network를 호출한다.

```powershell
$env:KIS_ENV = "paper"
$env:ENABLE_REAL_ORDER = "false"
$env:KIS_TOKEN_ISSUE_ENABLED = "true"
$env:KIS_WEBSOCKET_APPROVAL_ENABLED = "true"
$env:PAPER_WEBSOCKET_ENABLED = "true"
$env:PAPER_WEBSOCKET_CONNECT_ENABLED = "false"
```

```powershell
$tokenBody = @{ confirm = $true; install_to_process_env = $true } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/api/kis/token/issue -Method Post -ContentType "application/json" -Body $tokenBody

$wsBody = @{ confirm = $true; install_to_process_env = $true } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/api/paper/realtime/websocket/approval -Method Post -ContentType "application/json" -Body $wsBody

$subBody = @{ symbol = "005930"; kind = "quote"; subscribe = $true } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/api/paper/realtime/websocket/subscription/preview -Method Post -ContentType "application/json" -Body $subBody
```

성공 기준:

- token 응답은 `token_issued=true`, `token_raw_value_persisted=false`, raw token 미노출이어야 한다.
- WebSocket approval 응답은 `approval_key_issued=true`, `approval_key_raw_value_persisted=false`, raw approval key 미노출이어야 한다.
- subscription preview는 `approval_key=***REDACTED***`만 반환하고 실제 socket loop를 시작하지 않는다.

## Bot dry-run preview

기본 운영 확인은 반드시 dry-run부터 수행한다.

```powershell
$body = @{
  trade_date = "2026-05-27"
  strategies = @("trend_breakout")
  max_candidates = 5
  dry_run = $true
} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/api/paper/bot/preview -Method Post -ContentType "application/json" -Body $body
```

성공 기준:

- `dry_run=true`
- `paper_order_submitted=false`
- `live_order_created=false`
- decision은 `skipped` 또는 `rejected`와 reason code를 반환한다.
- 조회는 `GET /api/paper/bot/runs/{run_id}`로 수행한다.

## Paper live run

`dry_run=false`는 실전투자가 아니라 KIS 모의투자 전용 run이다. 아래 조건이 모두 충족되지 않으면 실행하지 않는다.

```powershell
$env:KIS_ENV = "paper"
$env:PAPER_TRADING_ENABLED = "true"
$env:PAPER_TRADING_CAN_CREATE = "true"
$env:PAPER_TRADING_KILL_SWITCH = "false"
$env:PAPER_BOT_CONFIRM = "true"
$env:ENABLE_REAL_ORDER = "false"
```

network submit을 실제 KIS paper로 열어야 하는 경우에만 별도 수동 승인 후 아래도 추가한다.

```powershell
$env:PAPER_TRADING_NETWORK_ENABLED = "true"
$env:BROKER_MODE = "paper_kis"
$env:PAPER_ORDER_SUBMIT_ENABLED = "true"
```

실행:

```powershell
$body = @{
  trade_date = "2026-05-27"
  strategies = @("trend_breakout")
  max_candidates = 1
  dry_run = $false
} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/api/paper/bot/run -Method Post -ContentType "application/json" -Body $body
```

성공 기준:

- 주문 전 risk gate reason code가 비어 있어야 한다.
- `submitted_count`는 `max_candidates`와 `max_auto_submit_orders`를 초과하지 않는다.
- `orders` legacy table은 증가하지 않는다.
- raw secret/account/token 값은 응답과 DB에 없어야 한다.

## Kill switch

kill switch 확인은 run 전에 수행한다.

```powershell
$env:PAPER_TRADING_KILL_SWITCH = "true"
Invoke-RestMethod http://127.0.0.1:8000/api/paper/status
```

`KILL_SWITCH_ACTIVE`가 반환되면 신규 주문이 차단되는 것이 정상이다. 장애나 의심 상황에서는 이 값을 true로 되돌리고 backend process를 재시작한다.

## Mock 주문 검증

CI와 로컬 자동 검증은 fake/mock adapter만 사용한다.

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_paper_submit_cancel_api.py backend/tests/test_paper_realtime_worker.py -q
```

성공 기준:

- mock submit/cancel/status/account payload가 paper-only로 반환된다.
- `orders` legacy table row가 생성되지 않는다.
- raw secret, token, account number가 응답과 DB에 포함되지 않는다.

## 실제 KIS Paper 수동 호출 절차

1. 별도 터미널에서 paper env만 주입한다. `.env`와 `.env.local`은 수정하지 않는다.
2. `/api/kis/config/validate`로 configured boolean과 `kis_env=paper`만 확인한다.
3. `/api/paper/realtime/status`가 stale이면 주문을 진행하지 않는다.
4. kill switch ON 상태에서 submit이 차단되는지 먼저 확인한다.
5. kill switch를 명시적으로 OFF로 바꾼 뒤 minimum-size paper 주문만 시도한다.
6. 주문 조회, sync, cancel 순서로 확인한다.
7. KIS가 장종료, rate limit, 인증 실패, payload 오류를 반환하면 즉시 중단하고 redacted 결과만 기록한다.

## 장애 대응

| 증상 | 조치 |
|---|---|
| `KIS_ENV_PAPER_REQUIRED` | `KIS_ENV=paper`인지 확인한다. live 값이면 즉시 중단한다. |
| `PAPER_BOT_CONFIRM_REQUIRED` | `PAPER_BOT_CONFIRM=true`가 필요한 수동 paper 실행인지 재확인한다. |
| `KILL_SWITCH_ACTIVE` | 주문 실행을 중단하거나 명시적으로 false 전환 전 차단 증거를 남긴다. |
| `PAPER_REALTIME_STALE_QUOTE` | quote worker heartbeat와 latest quote age를 확인하고 신규 주문을 중단한다. |
| `KIS_PAPER_RATE_LIMITED` | 재시도하지 말고 호출 간격과 runbook 승인 상태를 확인한다. |
| `KIS_LIVE_BASE_URL_BLOCKED` | live base URL이 섞인 상태이므로 즉시 중단한다. |
| `PAPER_BOT_DAILY_LOSS_LIMIT_EXCEEDED` | 당일 손실 한도 초과로 신규 주문을 중단하고 dashboard PnL과 audit event를 확인한다. |
| `PAPER_DUPLICATE_OPEN_ORDER` | 동일 symbol/side open order가 있으므로 중복 주문을 취소 또는 동기화한 뒤 재평가한다. |

## 검증 명령

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
alembic upgrade head
git diff --check
```

frontend 계약을 변경한 경우에만 다음을 추가한다.

```powershell
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
```
