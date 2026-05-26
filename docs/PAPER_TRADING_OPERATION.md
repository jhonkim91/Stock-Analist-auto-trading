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
| Paper sync | `/api/paper/sync`, 공식 sync contract 확인 전 fail-closed no-op |
| Report notify | `/api/reports/{report_id}/notify`, secret redaction 및 delivery failure isolation |
| Paper bot | runner/API 존재, scheduler와 auto-submit은 기본 disabled |

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
| `PAPER_TRADING_KILL_SWITCH` | `true` | local paper submit 차단 우선 |
| `PAPER_BOT_AUTO_SUBMIT` | `false` | bot 자동 submit 비활성 |
| `PAPER_BOT_SCHEDULER_ENABLED` | `false` | scheduler 비활성 |
| `PAPER_BOT_KILL_SWITCH` | `true` | bot 실행 안전 차단 |

## 장애 대응

| 증상 | 확인 |
|---|---|
| submit이 차단됨 | `reason_codes`에서 `KILL_SWITCH_ACTIVE`, `PAPER_PREVIEW_ONLY`, `PAPER_CREATE_DISABLED` 확인 |
| cancel이 차단됨 | `KIS_PAPER_CANCEL_CONFIRMATION_REQUIRED`면 정상 안전 동작 |
| sync가 차단됨 | `KIS_PAPER_SYNC_CONFIRMATION_REQUIRED`면 정상 안전 동작 |
| notifier 실패 | report 생성은 유지되고 `notification_delivery_logs`에 sanitized status만 저장되는지 확인 |
| secret scan 실패 | 출력된 `file:line:label`을 기준으로 원문 secret을 제거하고 placeholder/env 변수명으로 대체 |
