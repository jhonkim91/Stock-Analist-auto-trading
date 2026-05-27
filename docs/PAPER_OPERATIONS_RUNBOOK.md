# KIS Paper Operations Runbook

## 핵심 요약

이 문서는 `goal.md` Phase 17 기준의 paper 운영 대응 절차다. 대상은 KIS 모의투자, local paper tables, report automation, Telegram/notification outbox이며 실전매매 운영 절차가 아니다.

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
| live drift 의심 | live route/status 발견 | 즉시 중단, no-live regression 실행 | route 목록, test 결과 |

## 중단 절차

1. `PAPER_BOT_AUTO_SUBMIT=false`를 유지한다.
2. `PAPER_TRADING_KILL_SWITCH=true` 또는 기본 kill switch 상태로 되돌린다.
3. report automation은 `REPORT_AUTOMATION_ENABLED=false` 또는 `REPORT_AUTOMATION_MODE=disabled`로 둔다.
4. notification은 `notifications.yaml` 기본값 `enabled=false`, `dry_run=true`를 유지한다.
5. `tools/secret_scan.py`와 no-live regression을 실행한다.

## 검증 명령

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_no_live_trading_regression.py backend/tests/test_report_automation.py backend/tests/test_notifications.py -q
.\.venv\Scripts\python.exe tools\secret_scan.py
```
