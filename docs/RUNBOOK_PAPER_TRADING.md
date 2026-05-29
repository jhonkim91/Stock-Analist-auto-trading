# KIS 모의투자 자동매매 Runbook

## 핵심 요약

이 runbook은 KIS 모의투자 전용 자동매매 기능의 수동 운영 절차다. 현재 repo 기본값은 paper/broker/bot/report/notification을 수동 실행 가능 상태로 열어두되, live 주문, live cancel, live fallback, scheduler auto-start, unattended loop는 비활성 상태로 유지한다. 실제 KIS 호출은 CI에서 실행하지 않는다.

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
| `PAPER_TRADING_MARKET` | `KR` 또는 `US` | 미국장 해외주식 검증 시 `US` |
| `KIS_OVERSEAS_EXCHANGE_CODE` | `NASD` | 미국 WebSocket smoke는 현재 공식 샘플 확인 범위인 NASD만 사용 |
| `KIS_OVERSEAS_CURRENCY` | `USD` | 해외잔고 조회 통화 |
| `KIS_OVERSEAS_ORDER_SESSION` | `premarket` / `daytime` / `extended` | 현재 KIS paper host에서 미국주간주문 TR이 미지원으로 확인되어 submit은 네트워크 전 차단됨 |
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
- `paper_trading_enabled=true`
- credential/token/account/fresh quote가 없으면 `can_submit=false`, `can_create=false`
- `paper_order_created=false`
- `broker_order_created=false`
- `network_call_performed=false`
- `scheduler_enabled=false`
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

- 기본값은 paper realtime status가 enabled 상태로 노출될 수 있지만 장시간 WebSocket loop는 시작하지 않는다.
- realtime fresh quote gate를 켠 상태에서 quote가 없거나 stale이면 신규 주문은 `PAPER_REALTIME_QUOTE_MISSING` 또는 `PAPER_REALTIME_STALE_QUOTE`로 API 호출 전 차단된다.
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

$usSubBody = @{ symbol = "AAPL"; kind = "quote"; market = "US"; exchange = "NASD"; subscribe = $true } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/api/paper/realtime/websocket/subscription/preview -Method Post -ContentType "application/json" -Body $usSubBody
```

성공 기준:

- token 응답은 `token_issued=true`, `token_raw_value_persisted=false`, raw token 미노출이어야 한다.
- WebSocket approval 응답은 `approval_key_issued=true`, `approval_key_raw_value_persisted=false`, raw approval key 미노출이어야 한다.
- subscription preview는 `approval_key=***REDACTED***`만 반환하고 실제 socket loop를 시작하지 않는다.
- 미국장 subscription preview는 공식 샘플 확인 범위인 `market=US`, `exchange=NASD`, `HDFSCNT0`, `DNAS{symbol}`만 사용한다.

## Bounded WebSocket smoke

장시간 WebSocket loop는 금지한다. 연결 검증이 필요할 때만 현재 PowerShell 프로세스에서 아래 gate를 열고, `confirm=true`로 bounded smoke를 1회 실행한다.

```powershell
$env:PAPER_WEBSOCKET_ENABLED = "true"
$env:PAPER_WEBSOCKET_CONNECT_ENABLED = "true"
$env:KIS_ENV = "paper"
$env:ENABLE_REAL_ORDER = "false"
```

```powershell
$smokeBody = @{
  symbol = "AAPL"
  kind = "quote"
  market = "US"
  exchange = "NASD"
  confirm = $true
  receive_timeout_seconds = 3
} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/api/paper/realtime/websocket/smoke -Method Post -ContentType "application/json" -Body $smokeBody
```

성공 기준:

- `network_call_performed=true`
- `tr_id=HDFSCNT0`
- `message_received=true` 또는 `status=websocket_connected_no_message`
- raw approval key와 raw WebSocket message는 출력하지 않는다.
- smoke는 subscribe 후 unsubscribe를 전송하고 종료한다.

## Bot dry-run preview

기본 운영 확인은 반드시 dry-run부터 수행한다.

```powershell
$body = @{
  trade_date = "2026-05-27"
  strategies = @("trend_breakout")
  watchlist_symbols = @("005930", "000660")
  max_candidates = 5
  dry_run = $true
} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/api/paper/bot/preview -Method Post -ContentType "application/json" -Body $body
```

성공 기준:

- `dry_run=true`
- `watchlist_symbols`가 있으면 해당 종목의 저장된 passed screener 결과만 후보로 사용한다.
- `paper_order_submitted=false`
- `live_order_created=false`
- decision은 `skipped` 또는 `rejected`와 reason code를 반환한다.
- 조회는 `GET /api/paper/bot/runs/{run_id}`로 수행한다.

## Paper bot bounded runner

paper bot은 backend/launcher 시작만으로 자동 실행되지 않는다. loop 실행이 필요하면 현재 PowerShell 프로세스에서 gate를 명시적으로 열고, 반복 수와 stop marker를 함께 지정한다.

```powershell
$env:PAPER_BOT_ENABLED = "true"
$env:PAPER_BOT_SCHEDULER_ENABLED = "true"
$env:PAPER_BOT_KILL_SWITCH = "false"
$env:PAPER_BOT_MAX_ITERATIONS = "1"
$env:PAPER_BOT_MAX_ITERATIONS_CAP = "25"
$env:PAPER_BOT_STOP_FILE = "$env:TEMP\paper-bot.stop"
```

1회 실행:

```powershell
.\.venv\Scripts\python.exe -m backend.app.jobs.paper_bot_runner --once
```

bounded loop 실행:

```powershell
.\.venv\Scripts\python.exe -m backend.app.jobs.paper_bot_runner --loop --max-iterations 1 --stop-file $env:PAPER_BOT_STOP_FILE
```

중지 절차:

```powershell
New-Item -ItemType File $env:PAPER_BOT_STOP_FILE -Force
Invoke-RestMethod http://127.0.0.1:8000/api/bot/stop -Method Post
$env:PAPER_BOT_KILL_SWITCH = "true"
$env:PAPER_TRADING_KILL_SWITCH = "true"
```

Settings 화면에서는 `봇/주문 정지` preset을 누르면 현재 backend 프로세스의 bot/order gate가 즉시 차단 상태로 맞춰진다. 모든 runner 응답은 `auto_start=false`, `bounded_loop=true`, `live_order_created=false`, `network_call_performed=false`를 유지해야 한다.

## Paper sync worker bounded loop

체결/포지션/잔고 동기화는 backend 시작만으로 자동 실행되지 않는다. 반복 조회가 필요하면 현재 PowerShell 프로세스에서 worker gate와 반복 상한을 명시한 뒤 API 또는 CLI를 실행한다.

```powershell
$env:PAPER_SYNC_WORKER_ENABLED = "true"
$env:PAPER_SYNC_WORKER_INTERVAL_SECONDS = "60"
$env:PAPER_SYNC_WORKER_MAX_ITERATIONS = "1"
$env:PAPER_SYNC_WORKER_MAX_ITERATIONS_CAP = "10"
```

API bounded loop:

```powershell
$body = @{
  scope = "all"
  max_iterations = 1
  confirm = $true
} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/api/paper/sync-worker/run-loop -Method Post -ContentType "application/json" -Body $body
```

CLI bounded loop:

```powershell
.\.venv\Scripts\python.exe -m backend.app.jobs.paper_sync_runner --loop --scope all --max-iterations 1
```

성공 기준:

- `bounded_loop=true`
- `iteration_count <= max_iterations_cap`
- `auto_start=false`
- `live_order_created=false`
- paper network gate가 닫혀 있으면 `network_call_performed=false`와 reason code를 반환한다.

## Paper risk exit check

스탑로스, 트레일링 스탑, 이동평균 하향 교차 감시는 `/api/paper/risk/exit-check`로 수동 또는 bounded worker에서 호출한다. trigger가 발생해도 `confirm=true`, `idempotency_key`, paper fill simulator gate, kill-switch가 모두 통과해야 local sell order/fill과 position 감소가 수행된다.

```powershell
$exitBody = @{
  symbol = "005930"
  current_price = 71000
  ma_fast_previous = 72000
  ma_slow_previous = 71500
  ma_fast_current = 70800
  ma_slow_current = 71400
  confirm = $true
  idempotency_key = "risk-exit-005930-20260530-ma-cross"
} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/api/paper/risk/exit-check -Method Post -ContentType "application/json" -Body $exitBody
```

성공 기준:

- `trigger.ma_cross_triggered=true`
- `exit_order.order_type=ma_cross`
- `fill.fill_source=local_ma_cross_exit`
- `live_order_created=false`, `broker_order_created=false`, `network_call_performed=false`

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

미국장 해외주식 1회 검증은 process-only gate와 trading-window 확인 토큰을 함께 사용한다. helper는 `market=US`일 때 `America/New_York` 기준 정규장 `09:30-16:00`, 평일 조건만 submit 가능 세션으로 본다. 프리마켓은 `session=premarket`으로 기록하지만 adapter 호출 전 `US_REGULAR_SESSION_REQUIRED`로 중단하고 `next_regular_session_start`를 redacted record에 남긴다. 이 guard는 휴장일 calendar feed를 포함하지 않으므로 실제 실행 전 휴장/거래 가능 여부는 별도로 확인한다. 일반 프리마켓 주문 `VTTT1002U`는 `40570000`, 공식 미국주간주문 `/uapi/overseas-stock/v1/trading/daytime-order`, `TTTS6036U`는 `EGW02006 / 모의투자 TR 이 아닙니다.`로 각각 실제 KIS paper host에서 거부됐다. 따라서 premarket/daytime/extended submit은 현재 네트워크 전 차단하며, 장종료/거부/auth/rate-limit/stale 응답은 재시도하지 않고 record만 남긴다.

세션별 capability와 차단 trace 필드는 `docs/KIS_CAPABILITIES.md`를 기준으로 한다. paper 환경은 미국 정규장 `regular`만 허용하며, real 환경의 extended/daytime capability는 map상 분리되어 있지만 현재 프로젝트의 live adapter는 별도 승인 전까지 disabled scaffold 상태다.

```powershell
.\.venv\Scripts\python.exe tools\kis_paper_phase12c_dry_run.py `
  --execute `
  --temporary-paper-config `
  --market US `
  --exchange NASD `
  --currency USD `
  --symbol AAPL `
  --side buy `
  --qty 1 `
  --limit-price <LIMIT_PRICE> `
  --confirm-submit CONFIRM_KIS_PAPER_PHASE12C `
  --confirm-cancel CONFIRM_KIS_PAPER_PHASE12C `
  --confirm-trading-window CONFIRM_KIS_PAPER_TRADING_WINDOW `
  --record-path docs/research/kis-paper-phase21-us-redacted-record.json
```

`--allow-premarket-submit` 옵션은 이전 재확인 gate와의 CLI 호환을 위해 남아 있으나, 현재 helper는 이 옵션으로 프리마켓 submit을 열지 않는다.

token 발급, WebSocket approval, bounded WebSocket smoke, controlled submit/list/sync/cancel을 같은 redacted record로 묶어야 하면 Phase 21 helper를 사용한다. 아래 명령도 process env만 사용하며 `.env`/`.env.local`을 쓰지 않는다.

정규장 주문이 즉시 완전 체결되어 `sync` 단계에서 `filled` 또는 `remaining_qty=0`이 확인되면 helper는 불필요한 cancel을 호출하지 않고 `cancel_skipped_after_fill`, `lifecycle_evidence`를 redacted record에 남긴다. 미체결 또는 부분체결 잔량이 남은 경우에는 기존처럼 cancel 단계로 진행한다.

```powershell
.\.venv\Scripts\python.exe tools\kis_paper_phase21_us_activation.py `
  --issue-token `
  --issue-websocket-approval `
  --websocket-smoke `
  --execute-submit `
  --symbol AAPL `
  --qty 1 `
  --limit-price <LIMIT_PRICE> `
  --exchange NASD `
  --currency USD `
  --confirm-token CONFIRM_KIS_PAPER_PHASE21_TOKEN `
  --confirm-websocket CONFIRM_KIS_PAPER_PHASE21_WEBSOCKET `
  --confirm-submit CONFIRM_KIS_PAPER_PHASE12C `
  --confirm-cancel CONFIRM_KIS_PAPER_PHASE12C `
  --confirm-trading-window CONFIRM_KIS_PAPER_TRADING_WINDOW `
  --record-path docs/research/kis-paper-phase21-us-redacted-record.json
```

서비스 계층 persistence까지 한 번에 확인해야 하면 아래 helper를 사용한다. 이 경로는 정규장 gate 통과 후 `PaperOrderService.submit_order`로 `paper_orders`를 만들고, `PaperSyncService.sync`로 `paper_fills`/`paper_positions` 변경을 확인한다. fill/position이 확인되지 않으면 broker order id가 있는 경우 paper cancel을 1회 시도한다. 프리마켓/애프터/주간거래는 API 호출 전에 차단된다. 결과 record의 `completion_audit.complete`가 `true`여야 token, network, WebSocket, 주문 생성, 체결, 포지션 변경, no-live/no-secret 조건을 모두 만족한 것으로 본다. `status=completed`라도 `completion_audit.missing_requirements`가 비어 있지 않으면 전체 목표 완료로 보지 않는다.

```powershell
.\.venv\Scripts\python.exe tools\kis_paper_phase21_service_lifecycle.py `
  --symbol AAPL `
  --qty 1 `
  --limit-price <LIMIT_PRICE> `
  --exchange NASD `
  --currency USD `
  --confirm-submit CONFIRM_KIS_PAPER_PHASE12C `
  --confirm-sync CONFIRM_KIS_PAPER_PHASE12C `
  --confirm-cancel CONFIRM_KIS_PAPER_PHASE12C `
  --confirm-trading-window CONFIRM_KIS_PAPER_TRADING_WINDOW `
  --record-path docs/research/kis-paper-phase21-service-lifecycle-redacted-record.json
```

token/WebSocket proof와 service-level persistence proof를 같은 record에 묶으려면 Phase 21 helper에서 `--execute-submit` 대신 `--execute-service-lifecycle`을 사용한다. 두 submit 옵션은 중복 주문 방지를 위해 동시에 사용할 수 없다.

로컬 `.env.local`을 현재 helper 프로세스에만 읽어오려면 `--load-env-local`을 추가한다. 이 옵션은 파일을 수정하지 않고 allowlist key만 주입하며, record에는 raw 값과 secret-like key name을 남기지 않는다. 이미 현재 프로세스에 값이 있으면 기본적으로 덮어쓰지 않는다. 덮어써야 할 때만 `--env-file-override`를 명시한다.

정규장 직후 수동 제한가 계산을 줄이려면 `--derive-limit-from-price`를 추가한다. 이 옵션은 미국 정규장 gate가 통과된 뒤에만 read-only 해외 현재가 `/uapi/overseas-price/v1/quotations/price`, `HHDFS00000300`을 호출하고, `last_price * (1 + --limit-premium-bps / 10000)`로 제한가를 산정한다. 프리마켓/장외에서는 price call도 생략하고 `US_REGULAR_SESSION_REQUIRED` record만 남긴다.

```powershell
.\.venv\Scripts\python.exe tools\kis_paper_phase21_us_activation.py `
  --load-env-local `
  --issue-token `
  --issue-websocket-approval `
  --websocket-smoke `
  --execute-service-lifecycle `
  --derive-limit-from-price `
  --limit-premium-bps 300 `
  --symbol AAPL `
  --qty 1 `
  --exchange NASD `
  --currency USD `
  --confirm-token CONFIRM_KIS_PAPER_PHASE21_TOKEN `
  --confirm-websocket CONFIRM_KIS_PAPER_PHASE21_WEBSOCKET `
  --confirm-submit CONFIRM_KIS_PAPER_PHASE12C `
  --confirm-sync CONFIRM_KIS_PAPER_PHASE12C `
  --confirm-cancel CONFIRM_KIS_PAPER_PHASE12C `
  --confirm-trading-window CONFIRM_KIS_PAPER_TRADING_WINDOW `
  --record-path docs/research/kis-paper-phase21-us-service-lifecycle-redacted-record.json
```

즉시 sync에서 주문/포지션은 확인됐지만 체결 row가 늦게 반영될 수 있다. 이때는 새 주문이나 취소를 만들지 말고 follow-up sync helper만 실행한다. 이 helper는 `PaperSyncService.sync`만 호출하며 `submit_performed=false`, `cancel_performed=false`를 record에 남긴다.

```powershell
.\.venv\Scripts\python.exe tools\kis_paper_phase21_followup_sync.py `
  --load-env-local `
  --issue-token `
  --symbol AAPL `
  --exchange NASD `
  --currency USD `
  --scope all `
  --confirm-token CONFIRM_KIS_PAPER_PHASE21_TOKEN `
  --confirm-sync CONFIRM_KIS_PAPER_PHASE12C `
  --record-path docs/research/kis-paper-phase21-us-followup-sync-redacted-record.json
```

API/bot submit 경로에서 미국주간주문 세션을 명시해야 하는 경우에도 `.env.local`을 수정하지 말고 현재 PowerShell 프로세스에만 아래 값을 추가한다. 단, 현재 paper adapter는 이 값을 submit 허용이 아니라 unsupported 차단 신호로 사용한다.

```powershell
$env:KIS_OVERSEAS_ORDER_SESSION = "premarket"
```

공식 Open API 샘플에는 미국주간주문 `/uapi/overseas-stock/v1/trading/daytime-order`, `TTTS6036U`/`TTTS6037U`와 주간정정취소 `/daytime-order-rvsecncl`, `TTTS6038U`가 별도 존재하지만, 공식 legacy 지원표에서 모의투자 지원 표시가 없고 실제 paper host도 거부했다. live base URL, live fallback, 실전 주문은 계속 차단한다.

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
| `KIS_PAPER_US_DAYTIME_ORDER_UNSUPPORTED` | KIS paper host가 미국주간주문 `TTTS6036U`를 거부한 상태다. premarket/daytime 주문은 재시도하지 말고 정규장 paper 지원 경로만 사용한다. |
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
