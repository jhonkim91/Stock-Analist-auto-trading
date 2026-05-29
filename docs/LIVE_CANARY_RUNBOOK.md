# Phase 20 Controlled Live Canary Runbook

## 핵심 요약

Phase 20은 실전 주문 기능 구현이 아니라 별도 승인형 canary 절차와 redacted 검증 기록을 준비하는 단계다. 현재 저장소는 live adapter가 disabled scaffold로 고정되어 있고 live 주문 route가 없으므로 실계좌 주문은 실행할 수 없다.

## 공식 확인 기준

| 영역 | 확인 위치 | 적용 원칙 |
|---|---|---|
| KIS Developers | `https://apiportal.koreainvestment.com/intro` | REST, WebSocket, API 신청, 공지와 호출 제한을 실행 직전에 확인 |
| KIS official samples | `https://github.com/koreainvestment/open-trading-api` | 실전/모의 환경 분리, 인증 설정, 국내주식 예제 구조를 참고하되 repo production code에는 추정 endpoint를 넣지 않음 |
| Telegram Bot API | `https://core.telegram.org/bots/api` | canary 알림은 plain text, 4096자 이내 분할, token/chat id 원문 미노출 |

## Canary 전제조건

| Gate | 필요 조건 | 현재 판정 |
|---|---|---|
| 사용자 승인 | Phase 20 별도 승인 문구 | 요청 수신 |
| reviewer | 실행 직전 human reviewer 지정 | 미확인 |
| 환경 분리 | paper, prod-readonly, prod-live 분리 증거 | 미확인 |
| rollback | kill switch, scheduler stop, notifier-only rollback 절차 | 문서화 필요 |
| live adapter | endpoint, 주문/취소/조회/체결 contract 확인 | 현재 disabled scaffold |
| public route | live route는 Phase 20 실제 승인 전까지 없음 | 없음 |
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

현재 Phase 20 산출물의 완료 기준은 redacted preflight record와 canary 금지 조건이 문서화되고, 저장소가 실전 주문을 실행할 수 없음을 테스트로 증명하는 것이다. 실제 controlled live canary 실행은 별도 구현 승인, 환경 분리, reviewer, rollback proof가 모두 갖춰진 다음 별도 작업으로 다룬다.
