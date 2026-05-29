# Paper Trading Operation

## 핵심 요약

이 프로젝트의 paper trading은 `모의투자` 보조 기능이며 `실거래 아님` 상태를 유지한다. KIS paper endpoint, TR ID, request field가 공식 문서로 완전 확인되기 전에는 broker submit/cancel/sync network 구현을 사용하지 않는다.

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

- 실거래 주문, 주문 취소, 체결, 계좌 자금 이동.
- live broker adapter 활성화.
- paper mode에서 live mode fallback.
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
| `ENABLE_REAL_ORDER` | `false` | KIS balance 조회 포함 실전/주문 경로 차단 |
| `KIS_ACCESS_TOKEN` | `<placeholder>` | KIS paper balance 조회에 필요한 env-only token placeholder |
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
