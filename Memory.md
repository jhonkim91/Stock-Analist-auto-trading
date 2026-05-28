# Stock Analyst Auto Trading Memory

## 2026-05-28 PowerShell UTF-8 전역 정상화

- [x] 원인: Windows PowerShell 5.1 기본값이 코드페이지 949, `$OutputEncoding=us-ascii`, UTF-8 BOM 없는 파일 기본 ANSI 판독으로 섞여 한글 파이프/Here-string/`Get-Content`가 깨졌다.
- [x] 공식 Microsoft 문서/winget 기준 최신 안정 PowerShell은 `7.6.2.0`이며, 로컬에는 `pwsh`가 없어 `winget install --id Microsoft.PowerShell --source winget`로 설치했다.
- [x] 사용자 전역 프로필에 UTF-8 초기화를 추가했다: `C:\Users\demon\OneDrive\문서\WindowsPowerShell\profile.ps1`, `C:\Users\demon\OneDrive\문서\PowerShell\profile.ps1`, `C:\Users\demon\Documents\WindowsPowerShell\profile.ps1`, `C:\Users\demon\Documents\PowerShell\profile.ps1`.
- [x] 적용값: `chcp 65001`, `[Console]::InputEncoding`, `[Console]::OutputEncoding`, `$OutputEncoding`, `PYTHONIOENCODING=utf-8`, `PYTHONUTF8=1`, 주요 파일 cmdlet 기본 `-Encoding utf8`.
- [x] Windows Terminal 기본 프로필과 VS Code 통합 터미널 PowerShell 프로필을 `%LOCALAPPDATA%\Microsoft\WindowsApps\pwsh.exe`로 고정했다.
- [x] 검증: profile 로드 새 PowerShell은 `한글 테스트` Python stdin 파이프와 `Get-Content Memory.md` 한글 출력 정상. `-NoProfile`에서는 동일 테스트가 `?? ???` 또는 깨진 `Get-Content`로 재현됨.

## 2026-05-28 GUI 체크포인트

- [x] 영상 `녹음 2026-05-28 005845.mp4`와 `stock_analyst_gui_mockup.html` 기준 GUI tone match 작업 완료.
- [x] Frontend 전역 App Chrome을 추가해 `/dashboard`, `/screener`, `/backtest`, `/portfolio`, `/reports`, `/data`, `/paper`, `/bot`, `/settings`에 영상형 sidebar/navigation을 적용했다.
- [x] `gui_개선.txt` 후속 반영: 전역 Global Status Bar, dashboard 4-zone, Strategy Selector pill, Validation Framework loading/summary cards, 신규 `/sessions` Market Sessions route를 추가했다.
- [x] 색감 기준: body/panel `#FFFFFF`, sidebar `#F4F3EC`, active surface `#FAF9F4`, success accent `#1D8F6B`, danger `#9A2432`, thin border `#CFCAC0/#E6E2D8`.
- [x] `npm.cmd run lint`, `npm.cmd exec tsc -- --noEmit`, `npm.cmd run build` 통과. build script는 production chunk 404 회피를 위해 `next build --webpack`으로 고정했다.
- [x] Rendered smoke: Browser plugin `iab` 불가로 Playwright fallback 사용. `127.0.0.1:8000` backend + `127.0.0.1:3000` frontend에서 `/dashboard`, `/screener`, `/backtest`, `/sessions`, mobile `/dashboard` relevant console/http issue 0.
- [x] 대표 screenshot: `%TEMP%\stock_gui_validation\dashboard_desktop.png`, `%TEMP%\stock_gui_validation\screener_desktop.png`, `%TEMP%\stock_gui_validation\backtest_desktop.png`, `%TEMP%\stock_gui_validation\sessions_desktop.png`, `%TEMP%\stock_gui_validation\dashboard_mobile.png`.
- [x] 최신 `git diff --check`는 통과하며 CRLF warning만 남는다.

## 현재 체크포인트

- [x] 현재 작업: `goal.md` 기준 Phase 13-19 진행 완료. Phase 20은 runbook/preflight record까지 진행했으나 실제 live canary는 조건 미충족으로 blocked.
- [x] 현재 branch: `feature/kis-paper-goal-phases`.
- [x] PowerShell은 최신 안정판 `pwsh` 7.6.2로 설치했고 Windows Terminal/VS Code 기본 PowerShell을 `pwsh.exe`로 적용했다. 새 `pwsh` 세션에서는 `Get-Content`, `Select-String`, Python stdin 파이프가 UTF-8 기본값을 사용한다.
- [x] 최신 backend 전체 검증: `.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider --basetemp %TEMP%\stock_goal_phase19_20_backend_full_*` -> 405 passed in 302.67s.
- [x] 최신 targeted 검증: report automation/final safety/Phase 12C/no-live suite 27 passed, notification/bot suite 8 passed.
- [x] 최신 Phase 19/20 검증: live scaffold/preflight targeted suite 16 passed, app/frontend no-live static scan no matches.
- [x] 최신 secret scan: `.\.venv\Scripts\python.exe tools\secret_scan.py` -> `NO_SECRET_FINDINGS`.
- [x] 최신 `git diff --check` 통과. CRLF warning only.
- [x] 최신 로컬 실행 상태: 고아 Next/uvicorn 프로세스 종료 후 `py launcher.py run --no-browser`로 8000 backend와 3000 frontend를 launcher-owned 상태로 복구했다.
- [x] 최신 daily report direct Telegram delivery: `POST /api/reports/daily`로 `daily-2026-05-20` 생성 후 `.env.local`의 Telegram token을 사용해 private `getUpdates` 후보로 plain text 요약 전송 완료. token/chat id 원문 미출력.
- [x] 최신 realtime 보정 리포트: 샘플 `KRxxx` 종목은 제외하고 yfinance/Yahoo Finance 최신 가용 지연시세 기반 KRX 대형주 watchlist를 분석해 `backend/reports/realtime_market_report_ascii_20260528_080355.md`를 생성하고 Telegram 정정 메시지 전송 완료.
- [x] Goal continuation 상태: Phase 20 실제 canary는 live implementation 별도 승인, reviewer, 환경 분리, rollback proof 전까지 완료 불가.
- [ ] 현재 PowerShell의 `python -m pytest backend/tests`는 `Python`만 출력하고 exit 1로 종료된다. 검증은 로컬 `.venv` Python으로 수행했다.
- [ ] 내장 `ReportNotificationService` live delivery는 config/env opt-in 전까지 disabled/dry-run 상태다. 직접 전송이 필요하면 `.env.local`의 chat id 불일치 여부를 먼저 확인한다.

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, KIS read-only foundation, broker safety scaffold, paper trading local lifecycle, report notification, report automation, paper bot scheduler, validation/report/backtest 기능.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/sessions`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/bot`, `/settings`.
- Local launcher: 표준 실행 주소는 `http://127.0.0.1:3000/dashboard`이며 frontend build metadata의 API base는 `http://127.0.0.1:8000`이다.
- Notification: `backend/config/notifications.yaml` 기본값은 `enabled=false`, `default_dry_run=true`, `telegram_main.mode=disabled`, `telegram_main.dry_run=true`.
- Telegram secret은 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 환경 변수명만 참조하고 원문 값은 코드/문서/DB/API 응답에 저장하지 않는다.
- Paper/KIS execution은 fail-closed 기본값을 유지한다. live broker, live websocket, 실계좌 주문/취소/체결은 활성화하지 않는다.
- Phase 12C는 기존 redacted record의 KIS 장종료 거부 응답과 최신 no-network preflight로 종결 처리했다. 현재 기본 config/env는 fail-closed다.

## 최근 변경 요약

- `NotificationTemplateService`를 추가해 notification event payload를 plain text 템플릿으로 렌더링한다.
- `NotificationService.status()`가 `template_events`를 secret 없이 반환하고, outbox dispatch가 템플릿 메시지를 사용한다.
- `TelegramNotifier`는 plain text 기본값, unsafe MarkdownV2 기본 차단, 4096자 메시지 한도, 양수 timeout만 허용한다.
- `backend/config/notifications.yaml`에 기본 템플릿을 추가했다.
- `.env.example`에는 Telegram notifier가 config opt-in 전까지 disabled/dry-run임을 설명하고 placeholder만 유지했다.
- `docs/TELEGRAM_NOTIFIER.md`를 추가해 설정, 템플릿, 안전 계약, 검증 방법을 문서화했다.
- `ReportAutomationService`, `/api/reports/automation/status`, `/api/reports/automation/run-once`, `tools/report_automation_runner.py`를 추가했다. 기본값은 disabled이며 `confirm=true`와 env gate 없이는 report를 생성하지 않는다.
- report automation 완료/실패 notification event `daily_report_automation_completed`, `weekly_report_automation_completed`, `report_automation_failed`를 추가했다.
- `docs/REPORT_AUTOMATION.md`, `docs/PAPER_OPERATIONS_RUNBOOK.md`, `docs/LIVE_TRADING_READINESS.md`를 추가했다.
- `KisLiveBrokerAdapter`는 live operation 호출 시 예외 대신 `status=live_disabled` redacted payload를 반환한다.
- `tools/live_canary_preflight.py`, `docs/LIVE_CANARY_RUNBOOK.md`, `docs/research/live-canary-phase20-preflight-record.json`를 추가했다. 현재 Phase 20 실제 canary는 blocked다.

## 최신 검증 결과

- 2026-05-28 PowerShell 7 upgrade/application: `winget search --id Microsoft.PowerShell --exact` -> `7.6.2.0`; 기존 `pwsh` 없음; `winget install --id Microsoft.PowerShell --source winget` -> 설치 성공; `pwsh -NoProfile` -> `7.6.2`, `Core`, `$PSHOME=C:\Program Files\WindowsApps\Microsoft.PowerShell_7.6.2.0_x64__8wekyb3d8bbwe`; Windows Terminal defaultProfile `{574e775e-4f2a-5b96-ac1e-a2962a402336}`, VS Code PowerShell path `${env:LOCALAPPDATA}\Microsoft\WindowsApps\pwsh.exe`; `winget upgrade --id Microsoft.PowerShell` -> available upgrade 없음.
- 2026-05-28 GUI follow-up validation: `npm.cmd run lint`, `npm.cmd exec tsc -- --noEmit`, `npm.cmd run build`, `npm.cmd audit --audit-level=moderate`, `.\.venv\Scripts\python.exe tools\secret_scan.py`, `git diff --check`, `py launcher.py check` 통과. Playwright smoke: dashboard global status 1/KPI 4/validation cards 3, screener pills 9 and opt-in click selected 6, backtest validation cards 3, sessions bars 2, mobile dashboard body width 390. Browser `iab` unavailable로 Playwright fallback 사용.
- 2026-05-28 PowerShell UTF-8 normalization: profile 로드 새 PowerShell -> `chcp 65001`, `$OutputEncoding=utf-8`, Console input/output utf-8, `PYTHONIOENCODING=utf-8`, `PYTHONUTF8=1`; Python stdin `한글 테스트` 정상 출력; `Get-Content Memory.md` 한글 정상 출력. `-NoProfile` 비교 시 `$OutputEncoding=us-ascii`와 깨진 출력 재현.
- 2026-05-28 local launcher recovery: 기존 3000 Next PID 19988, 8001 uvicorn PID 17860 종료 후 `py launcher.py run --no-browser`; `py launcher.py check` -> all OK, backend 8000/frontend 3000 launcher-owned; `/health` 200, `/dashboard` 200, `/api/data/status` 200 with `orders_count=0`, `/api/broker/status` -> `can_submit=False`, `live=False`, `paper=False`.
- 2026-05-28 daily Telegram report: backend 8000/3000 alive; `/api/reports/daily` -> `daily-2026-05-20`, report path `backend/reports/daily_report_2026-05-20.md`; `/api/broker/status` -> `can_submit=False`, `live=False`, `paper=False`, `network=false`; direct Telegram send first failed with `chat not found`, then private `getUpdates` candidate send succeeded; secrets redacted.
- 2026-05-28 realtime Telegram report: `.venv`에 yfinance 설치 후 KRX/KOSPI 실제 대형주 18개와 `^KS11` 최신 가용 5분/일봉 데이터를 분석. 최종 추천 후보는 `000660.KS`, `012330.KS`, `005930.KS`, `028260.KS`, `005380.KS`; source는 delayed 가능 Yahoo Finance/yfinance로 표기. 첫 한글 리포트는 PowerShell 인코딩으로 일부 깨져 ASCII 정정 리포트/Telegram 메시지를 재전송. `tools/secret_scan.py` -> `NO_SECRET_FINDINGS`; `/api/broker/status` -> `can_submit=False`, `preview_only=True`, `network_call_performed=False`.
- 2026-05-28 targeted notification pytest: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_notifications.py backend/tests/test_notification_service.py backend/tests/test_notification_templates.py backend/tests/test_notification_outbox.py` -> 15 passed in 3.22s.
- 2026-05-28 Phase 13-18 targeted pytest: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_paper_runtime_flags.py backend/tests/test_no_live_trading_regression.py backend/tests/test_report_automation.py backend/tests/test_final_safety_hardening.py -q` -> 27 passed in 30.76s.
- 2026-05-28 notification/bot pytest: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_notification_service.py backend/tests/test_paper_bot_scheduler.py -q` -> 8 passed in 0.86s.
- 2026-05-28 report automation CLI: `.\.venv\Scripts\python.exe tools\report_automation_runner.py` -> disabled status, `execute_required=true`, `network_call_performed=false`.
- 2026-05-28 backend full pytest: `.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider --basetemp %TEMP%\stock_goal_phase19_20_backend_full_*` -> 405 passed in 302.67s.
- 2026-05-28 Phase 19/20 gate audit: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_final_safety_hardening.py -q` -> 13 passed in 0.76s; app/frontend static scan for live routes/default enablement -> no matches.
- 2026-05-28 Phase 19/20 plan/preflight: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_live_canary_preflight.py backend/tests/test_final_safety_hardening.py -q` -> 16 passed in 0.80s; `tools/live_canary_preflight.py --write-record` -> `status=blocked`, `canary_execution_allowed=false`, `network_call_performed=false`.
- 2026-05-28 publish frontend validation: `cd frontend; npm.cmd run lint`, `npm.cmd exec tsc -- --noEmit`, `npm.cmd run build` -> 통과.
- 2026-05-28 secret scan: `.\.venv\Scripts\python.exe tools\secret_scan.py` -> `NO_SECRET_FINDINGS`.
- 2026-05-28 `git diff --check` -> exit 0, CRLF warning only.
- `python -m pytest backend/tests` 직접 실행은 현재 셸의 `python` alias 문제로 실패했다. 출력: `Python`, exit 1.

## 안전 계약

- KIS 주문 API 구현 없음.
- live submit 활성화 없음.
- WebSocket 구현 없음.
- Phase 20 controlled live canary는 live implementation 별도 승인, reviewer, 환경 분리, rollback proof 전까지 실제 실행 금지.
- 계좌번호, KIS token, Telegram bot token/chat id 원문 출력 없음.
- notification failure는 trading/report 상태 commit을 막지 않고 delivery 상태만 기록한다.

## 남은 작업

- [ ] 내장 Telegram delivery가 필요하면 별도 승인 후 로컬/배포 secret과 `notifications.yaml` opt-in을 분리 검증한다. 직접 발송은 token/chat id 원문 없이 수행한다.
- [ ] Phase 20 실제 controlled live canary는 live implementation 별도 승인, reviewer, 환경 분리, rollback proof 전까지 진행하지 않는다.
- [ ] `python` launcher 문제가 계속 필요하면 Windows PATH/App execution alias를 별도 환경 작업으로 정리한다.
