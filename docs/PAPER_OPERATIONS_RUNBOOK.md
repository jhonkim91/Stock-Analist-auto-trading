# KIS Paper Operations Runbook

## 핵심 요약

이 문서는 `goal.md` Phase 17 기준의 paper 운영 대응 절차다. 대상은 KIS 모의투자, local paper tables, report automation, Telegram/notification outbox이며, 실전(live) 주문 운영 절차가 아니다. 다만 실계좌 KIS live 주문은 더 이상 차단되지 않으며, fail-closed 게이트(`LIVE_TRADING_ENABLED` + `LIVE_ORDER_SUBMIT_ENABLED` + `ENABLE_REAL_ORDER` + live 자격증명 + live host + per-order confirm + kill switch + max-notional) 뒤에서 KRX 국내 현금 주문에 한해 활성화되어 있다(`/api/kis/orders/{status,preview,submit,cancel}`, `/api/live/status`). live 실행 경로는 실제 KIS API 대비 미검증이므로 첫 주문은 최소 수량으로 확인한다.

운영 환경은 단일 프로그램이다. 하나의 FastAPI 프로세스가 Next.js static export를 서빙하고, pywebview 네이티브 창으로 단일 Windows .exe로 패키징된다(`launcher.py` -> `app_main.py --host 127.0.0.1 --port 8000`, 별도 frontend 프로세스/포트 없음, same-origin). UI는 한국어이며 monospace + beige 라이트 테마에 light/dark 토글 슬라이더를 제공한다. 로그인은 로컬 JSON 기반(`backend/data/users.json`, PBKDF2-HMAC-SHA256, HMAC 30일 토큰, 사용자 생성 시에만 인증 강제)이고 `/api/auth/*` 라우트와 frontend AuthGate/logout으로 동작한다.

## 상태 확인 순서

| 순서 | 확인 항목 | 명령 또는 API |
|---|---|---|
| 1 | backend health | `GET /health` |
| 2 | KIS read-only status | `GET /api/kis/status` |
| 3 | broker safety | `GET /api/broker/status` |
| 4 | paper safety | `GET /api/paper/status` |
| 5 | bot safety | `GET /api/bot/status` |
| 6 | notification status | `GET /api/notifications/status` |
| 7 | report automation | `GET /api/reports/automation/status` |

## 주요 장애와 대응

| 장애 | 탐지 신호 | 즉시 대응 | 기록 기준 |
|---|---|---|---|
| KIS 장종료/거부 | `40580000`, submit 실패 | 추가 submit 중단, redacted record 저장 | status code, msg code, endpoint path, TR ID |
| credential 누락 | configured=false | 실행 중단, env scope 확인 | configured boolean만 기록 |
| kill switch 차단 | `KILL_SWITCH_ACTIVE` | 정상 차단으로 처리 | network_call_performed=false 확인 |
| notification 실패 | outbox `retry`/`failed` | trading/report rollback 금지, retry batch만 점검 | event id, status, last_error_code |
| report automation 실패 | `report_automation_failed` | report data availability 확인 | report_type, reason |
| live 주문 오작동 의심 | live route/status 이상 동작 | 즉시 submit 중단, live 게이트(`LIVE_ORDER_SUBMIT_ENABLED`/`ENABLE_REAL_ORDER`/kill switch) 확인 | route 목록, gate 상태, test 결과 |

## 중단 절차

1. `PAPER_BOT_AUTO_SUBMIT=false`를 유지한다.
2. `PAPER_TRADING_KILL_SWITCH=true` 또는 기본 kill switch 상태로 되돌린다.
3. report automation은 `REPORT_AUTOMATION_ENABLED=false` 또는 `REPORT_AUTOMATION_MODE=disabled`로 둔다.
4. notification은 `notifications.yaml` 기본값 `enabled=false`, `dry_run=true`를 유지한다.
5. live 주문도 함께 차단하려면 `LIVE_ORDER_SUBMIT_ENABLED=false`(또는 `ENABLE_REAL_ORDER=false`)와 kill switch를 유지한다.
6. `tools/secret_scan.py`와 관련 회귀 테스트를 실행한다.

## 검증 명령

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_no_live_trading_regression.py backend/tests/test_report_automation.py backend/tests/test_notifications.py -q
.\.venv\Scripts\python.exe tools\secret_scan.py
```
