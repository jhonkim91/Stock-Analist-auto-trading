# Paper Trading Operation

## 핵심 요약

이 프로젝트의 paper trading은 `모의투자` 기능이다. 실계좌 KIS 주문도 다중 게이트(`LIVE_TRADING_ENABLED` + `LIVE_ORDER_SUBMIT_ENABLED` + `ENABLE_REAL_ORDER` + live 자격증명 + live host + 주문별 confirm + kill switch + max-notional) 뒤에서 기본 fail-closed로 활성화되어 있으며, KRX 국내 현금 주문만 허용한다(`/api/kis/orders/{status,preview,submit,cancel}` + `/api/live/status`, `KisLiveOrderExecutor`가 paper mapper 재사용, V->T TR ID). 실계좌 실행 경로는 실제 KIS API 대비 미검증이므로 첫 주문은 최소 수량으로 검증한다.

전체 시스템은 단일 프로그램이다. 하나의 FastAPI 프로세스가 Next.js 정적 export를 서빙하고, pywebview 네이티브 창으로 단일 Windows .exe로 패키징된다(`launcher.py`가 `app_main.py --host 127.0.0.1 --port 8000` 단일 프로세스 구동, 별도 frontend 프로세스 없음, same-origin). UI는 한국어이며 monospace + beige 라이트 테마에 라이트/다크 토글 슬라이더를 제공한다. 로그인은 로컬 JSON 기반(`backend/data/users.json`, PBKDF2-HMAC-SHA256, HMAC 30일 토큰, 사용자가 생성된 뒤에만 인증 강제되는 opt-in, 라우트 `/api/auth/*`, 프론트엔드 AuthGate + logout)이다.

## 허용 범위

| 항목 | 현재 상태 |
|---|---|
| Paper preview | `/api/paper/orders/preview`, DB write 없음 |
| Local paper submit | `/api/paper/orders/submit`, `confirm=true`, `idempotency_key`, kill-switch/config gate 통과 시 `paper_orders`만 저장 |
| Paper cancel | `/api/paper/orders/cancel`, 공식 cancel payload 확인 전 disabled |
| Paper views | `/api/paper/orders`, `/api/paper/fills`, `/api/paper/positions`, `/api/paper/portfolio` |
| KIS paper balance | `/api/paper/portfolio`에서 조건부 read-only 호출. 기본 disabled/mock 상태는 local snapshot fallback 유지 |
| Paper sync | `/api/paper/sync`, 공식 sync/network gate 통과 시만 KIS paper 조회 동기화 |
| Paper sync worker | `/api/paper/sync-worker/status`, `/api/paper/sync-worker/run-once`, `backend.app.jobs.paper_sync_runner`, 기본 OFF/confirm required |
| Paper risk exit | `/api/paper/risk/exit-check`, stop-loss/trailing/이동평균 하향 교차 trigger 시 confirm/idempotency/gate 뒤 local sell fill |
| Report notify | `/api/reports/{report_id}/notify`, secret redaction 및 delivery failure isolation |
| Paper bot | runner/API 존재, scheduler와 auto-submit은 기본 disabled, loop는 bounded iteration/stop-file 방식만 허용 |

## 금지 범위

- 실계좌 주문은 위 다중 게이트가 모두 통과된 경우에만 허용되며 기본값은 fail-closed이다. KRX 국내 현금 주문 외 경로(해외/파생 등)는 금지.
- paper mode에서 의도하지 않은 live mode fallback.
- KIS credential, access token, refresh token, 계좌번호, webhook, chat_id 원문 저장 또는 출력.
- 공식 문서로 확인되지 않은 KIS endpoint, TR ID, request field 추정 구현.

## 운영 전 점검

```powershell
.\.venv\Scripts\python.exe tools/secret_scan.py
.\.venv\Scripts\python.exe -m pytest backend/tests/test_no_live_trading_regression.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_secret_redaction.py -q
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
cd ..
```

## Safe Defaults

`.env.example`는 placeholder와 disabled 기본값만 제공한다.

| 변수 | 기본값 | 의미 |
|---|---|---|
| `BROKER_MODE` | `disabled` | KIS paper network adapter는 `paper_kis`일 때만 허용 |
| `PAPER_TRADING_ENABLED` | `false` | paper trading runtime enable gate |
| `PAPER_TRADING_CAN_CREATE` | `false` | paper order 생성 runtime gate |
| `PAPER_TRADING_NETWORK_ENABLED` | `false` | KIS paper network 호출 runtime gate |
| `PAPER_TRADING_KILL_SWITCH` | `true` | local paper submit 차단 우선 |
| `PAPER_ORDER_SUBMIT_ENABLED` | `false` | KIS paper network submit 전용 gate |
| `PAPER_BOT_AUTO_SUBMIT` | `false` | bot 자동 submit 비활성 |
| `PAPER_BOT_SCHEDULER_ENABLED` | `false` | scheduler 비활성 |
| `PAPER_BOT_KILL_SWITCH` | `true` | bot 실행 안전 차단 |
| `PAPER_BOT_MAX_ITERATIONS` | `1` | CLI loop 기본 반복 수 |
| `PAPER_BOT_MAX_ITERATIONS_CAP` | `25` | CLI loop 반복 수 상한 |
| `PAPER_BOT_STOP_FILE` | 빈 값 | 존재하면 loop가 다음 iteration 전에 중지되는 marker path |
| `PAPER_BOT_MAX_SUBMITS_PER_RUN` | `1` | bot 1회 실행 최대 submit 수 |
| `PAPER_BOT_MAX_ORDER_QTY` | `1` | bot 자동 submit 종목별 최대 수량 |
| `PAPER_BOT_MAX_ORDER_NOTIONAL` | `100000` | bot 자동 submit 1건 최대 주문금액 |
| `PAPER_SYNC_WORKER_ENABLED` | `false` | KIS paper sync worker 실행 허용 |
| `PAPER_SYNC_WORKER_INTERVAL_SECONDS` | `60` | bounded loop 간격 |
| `PAPER_SYNC_WORKER_MAX_ITERATIONS` | `1` | runner 기본 반복 수 |
| `ENABLE_REAL_ORDER` | `false` | 실계좌 주문 경로 fail-closed 게이트 중 하나(기본 false). live 주문은 `LIVE_TRADING_ENABLED` + `LIVE_ORDER_SUBMIT_ENABLED` + `ENABLE_REAL_ORDER` + live 자격증명/host + 주문별 confirm + kill switch + max-notional이 모두 충족돼야 활성화 |
| `KIS_ACCESS_TOKEN` | `<placeholder>` | KIS paper balance 조회에 필요한 token placeholder. 자격증명은 UI에서 입력해 `backend/data/runtime_env.json`(allowlist, 마스킹)에 영속화하거나 env로 제공 |
| `KIS_ACCOUNT_NO` | `<placeholder>` | KIS paper balance 조회 CANO env placeholder |
| `KIS_PRODUCT_CODE` | `<placeholder>` | KIS paper balance 조회 ACNT_PRDT_CD env placeholder |

## 장애 대응

| 증상 | 확인 |
|---|---|
| submit이 차단됨 | `reason_codes`에서 `KILL_SWITCH_ACTIVE`, `PAPER_PREVIEW_ONLY`, `PAPER_CREATE_DISABLED` 확인 |
| cancel이 차단됨 | `KIS_PAPER_CANCEL_CONFIRMATION_REQUIRED`면 정상 안전 동작 |
| sync가 차단됨 | `KIS_PAPER_SYNC_CONFIRMATION_REQUIRED`면 정상 안전 동작 |
| notifier 실패 | report 생성은 유지되고 `notification_delivery_logs`에 sanitized status만 저장되는지 확인 |
| secret scan 실패 | 출력된 `file:line:label`을 기준으로 원문 secret을 제거하고 placeholder/env 변수명으로 대체 |
