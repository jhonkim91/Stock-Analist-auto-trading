# Phase 20 Controlled Live Canary Runbook

## 핵심 요약

실전 KIS live 주문이 ENABLED 되어 있다(고위험, 사용자 본인 계좌). 기본값은 fail-closed이며 다중 게이트(LIVE_TRADING_ENABLED + LIVE_ORDER_SUBMIT_ENABLED + ENABLE_REAL_ORDER + live credential + live host + per-order confirm + kill switch + max-notional) 뒤에서만 동작한다. KRX 국내 현금 주문만 지원하며 route는 `/api/kis/orders/{status,preview,submit,cancel}` + `/api/live/status`로 `KisLiveOrderExecutor`(paper mapper 재사용, V->T TR ID)를 사용한다. live 실행은 실제 KIS API 대비 아직 미검증이므로 첫 주문은 최소 수량으로 검증한다. 이 canary runbook은 redacted 검증 기록과 rollback 절차를 다룬다.

본 프로그램은 단일 .exe(pywebview 네이티브 창)로 배포되며, 하나의 FastAPI 프로세스가 Next.js static export를 same-origin으로 서빙한다(별도 frontend 프로세스 없음). UI는 한국어, monospace + beige 라이트 테마에 라이트/다크 토글 슬라이더를 제공한다. 로그인은 `backend/data/users.json`(PBKDF2-HMAC-SHA256) 기반 로컬 JSON 인증과 HMAC 30일 토큰을 사용하는 opt-in 방식이다.

## 공식 확인 기준

| 영역 | 확인 위치 | 적용 원칙 |
|---|---|---|
| KIS Developers | `https://apiportal.koreainvestment.com/intro` | REST, WebSocket, API 신청, 공지와 호출 제한을 실행 직전에 확인 |
| KIS official samples | `https://github.com/koreainvestment/open-trading-api` | 실전/모의 환경 분리, 인증 설정, 국내주식 예제 구조를 참고하되 repo production code에는 추정 endpoint를 넣지 않음 |
| Telegram Bot API | `https://core.telegram.org/bots/api` | canary 알림은 plain text, 4096자 이내 분할, token/chat id 원문 미노출 |

## Canary 전제조건

| Gate | 필요 조건 | 현재 판정 |
|---|---|---|
| 사용자 승인 | live 주문 활성화 승인 문구 | 요청 수신 |
| reviewer | 실행 직전 human reviewer 지정 | 미확인 |
| 환경 분리 | paper, prod-readonly, prod-live 분리 증거 | 미확인 |
| rollback | kill switch, scheduler stop, notifier-only rollback 절차 | 문서화 필요 |
| live executor | endpoint, 주문/취소/조회/체결 contract 확인 | `KisLiveOrderExecutor` 활성, 실제 KIS API 대비 미검증 |
| public route | `/api/kis/orders/{status,preview,submit,cancel}` + `/api/live/status` | 활성 (fail-closed 기본값) |
| secret | env-level secret, 원문 출력 금지 | 원문 미노출 유지 |

## Rollback 절차

아래 절차가 실행 직전 검토되지 않으면 `LIVE_CANARY_ROLLBACK_READY=true`를 설정하지 않는다.

1. `LIVE_CANARY_KILL_SWITCH_READY=true` 상태를 확인하고, 이상 징후 발생 시 kill switch를 먼저 켠다.
2. scheduler, bot loop, report automation, notification dispatch를 신규 실행하지 않는 notifier-only 상태로 전환한다.
3. live/public route가 열린 배포라면 해당 route를 즉시 disabled/fail-closed 설정으로 되돌린다.
4. canary 주문 또는 취소 후보의 redacted audit event, correlation id, reviewer, rollback 수행자를 기록한다.
5. secret 원문, 계좌번호 원문, raw token을 문서나 로그에 남기지 않는다.

## 실행 금지 조건

- `tools/live_canary_preflight.py`가 `status=ready`가 아닌 경우
- reviewer, 환경 분리, rollback 증거가 없는 경우
- KIS 공식 문서와 공식 샘플이 endpoint, TR ID, request field를 확인하지 못한 경우
- live fallback이 필요한 경우
- 자동 submit 또는 unattended 실행이 필요한 경우
- 계좌번호, token, app key, app secret, Telegram credential 원문을 출력해야 하는 경우

## 현재 실행 절차

```powershell
.\.venv\Scripts\python.exe tools\live_canary_preflight.py --write-record
.\.venv\Scripts\python.exe -m pytest backend/tests/test_live_canary_preflight.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py -q
.\.venv\Scripts\python.exe tools\secret_scan.py
git diff --check
```

## 완료 판정

완료 기준은 redacted preflight record와 canary 금지 조건이 문서화되고, live 주문이 fail-closed 다중 게이트 뒤에서만 동작함을 테스트로 증명하는 것이다(전체 pytest 534 통과). 실제 controlled live canary 실행은 환경 분리, reviewer, rollback proof가 모두 갖춰지고 첫 주문을 최소 수량으로 검증한 다음 진행한다.
