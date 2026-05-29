# Report Automation

## 핵심 요약

Report automation은 `goal.md` Phase 15 범위의 disabled-by-default run-once 기능이다. 기존 daily/weekly report 생성 계약을 재사용하고, 완료/실패 상태는 notification outbox event로 남긴다. 스케줄러 자동 시작, live trading, KIS 주문 호출은 포함하지 않는다.

## Public Surface

| 항목 | 경로 |
|---|---|
| status API | `GET /api/reports/automation/status` |
| run-once API | `POST /api/reports/automation/run-once` |
| CLI | `tools/report_automation_runner.py` |
| Telegram scheduler status | `GET /api/telegram/scheduler/status` |
| Telegram scheduler run-once | `POST /api/telegram/scheduler/run-once` |
| Telegram scheduler CLI | `python -m backend.app.jobs.telegram_report_runner` |
| Telegram polling status | `GET /api/telegram/polling/status` |
| Telegram polling run-once | `POST /api/telegram/polling/run-once` |
| Telegram polling CLI | `python -m backend.app.jobs.telegram_polling_runner` |
| 완료 event | `daily_report_automation_completed`, `weekly_report_automation_completed` |
| 실패 event | `report_automation_failed` |

## Runtime Gates

| 변수 | 기본값 | 의미 |
|---|---|---|
| `REPORT_AUTOMATION_ENABLED` | false | run-once 실행 허용 여부 |
| `REPORT_AUTOMATION_MODE` | disabled | `manual`일 때만 실행 가능 |
| `REPORT_AUTOMATION_DRY_RUN` | true | notification dispatch dry-run 기본값 |
| `REPORT_AUTOMATION_NOTIFY` | false | run-once 후 pending outbox dispatch 여부 |
| `TELEGRAM_REPORT_SCHEDULER_ENABLED` | false | 장 시작 전/장 종료 후/주간 Telegram report slot 허용 |
| `TELEGRAM_REPORT_DRY_RUN` | true | Telegram report scheduler delivery dry-run 기본값 |
| `TELEGRAM_POLLING_ENABLED` | false | Telegram getUpdates polling 허용 |
| `TELEGRAM_POLLING_DRY_RUN` | true | polling command reply 전송 dry-run 기본값 |
| `TELEGRAM_POLLING_SEND_REPLIES` | false | polling dispatch 결과를 Telegram sendMessage로 회신할지 여부 |

기본 상태에서는 API와 CLI가 report를 생성하지 않는다. 실행하려면 runtime gate와 request `confirm=true`가 모두 필요하다.

## Safety Contract

- 기존 `POST /api/reports/daily`, `POST /api/reports/weekly`, `POST /api/reports/{report_id}/notify` 계약을 제거하지 않는다.
- notification event enqueue/dispatch 실패는 생성된 report를 rollback하지 않는다.
- status와 result payload는 token, account, Telegram credential 원문을 반환하지 않는다.
- scheduler auto-start는 구현하지 않는다. Telegram scheduler도 status/run-once/CLI 구조만 제공하며 request `confirm=true`가 필요하다.
- Telegram polling은 token을 URL path에 사용하지만 응답/trace에는 `/bot[REDACTED]/...` 형태로만 남긴다.
- KIS paper/live 주문, live route, WebSocket 실행과 연결하지 않는다.

## 재현 명령

```powershell
.\.venv\Scripts\python.exe tools\report_automation_runner.py
.\.venv\Scripts\python.exe -m pytest backend/tests/test_report_automation.py -q
```
