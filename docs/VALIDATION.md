# Validation

## 2026-05-28 `.env.local` KIS Paper Readiness Recheck

사용자가 로컬 `.env.local`에 `KIS_ENV=paper`를 추가한 뒤, 값을 출력하지 않고 키 존재와 runtime status만 재확인했다. Codex는 `.env.local`을 수정하지 않았고, 현재 Python 검증 프로세스에만 로드했다. 실제 KIS paper 주문/조회/sync/cancel 네트워크 호출은 실행하지 않았다.

| 항목 | 결과 | 근거 |
|---|---|---|
| `.env.local` key/value check | 통과 | `KIS_ENV`, KIS credential/account/product code, `ENABLE_REAL_ORDER`, paper gate key 존재 확인. `KIS_ENV_paper=true`, `ENABLE_REAL_ORDER_false=true`, `PAPER_TRADING_NETWORK_ENABLED_true=true`, `BROKER_MODE_paper_kis=true`, raw value 미출력 |
| KIS config validate | 통과 | `POST /api/kis/config/validate` -> HTTP 200, `configured=true`, `kis_env=paper`, `kis_env_paper=true`, credential/account/product format valid, `network_call_performed=false`, raw secret/account/token 미노출 |
| Status/dashboard | 확인 | `/api/kis/status`, `/api/broker/status`, `/api/paper/status`, `/api/paper/realtime/status`, `/api/paper/dashboard`, `/api/paper/bot/status` -> HTTP 200. `orders_count=0`, `paper_orders_count=0`, `network_call_performed=false` |
| Dry-run preview | 안전 차단 | `POST /api/paper/bot/preview`, `max_candidates=1`, `dry_run=true` -> `run_id=paper-bot-fb740345fe7f4608`, `status=disabled`, `reason_codes=[PAPER_BOT_DISABLED, KILL_SWITCH_ACTIVE]`, `submitted_count=0`, `paper_order_submitted=false`, `live_order_created=false`, `network_call_performed=false` |
| External network guard | 통과 | 외부 TCP connect 차단 가드 적용 상태에서 `network_attempts_blocked=0`; FastAPI `TestClient` 내부 loopback만 허용 |
| Secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py` -> `NO_SECRET_FINDINGS` |
| Diff whitespace check | 통과 | `git diff --check` -> exit 0 |

결론: `.env.local` 기준 KIS paper credential/env readiness는 redacted boolean으로 통과했다. 다만 repo 기본 `backend/config/paper.yaml`과 `backend/config/bot.yaml`은 여전히 fail-closed이므로 paper bot submit/run은 주문 없이 차단된다. 실제 KIS paper 최소 주문/조회/sync/cancel은 별도 network 승인과 process-only temporary config/bot gate 해제 절차가 있을 때만 진행한다.

## 2026-05-28 Goal.md KIS Paper Auto Bot Phase 1-6 Alignment

사용자 요청에 따라 루트 `goal.md`에 KIS 모의투자 전용 자동매매 봇 6단계 진행 상태를 명시했다. 이번 변경은 이미 구현/검증된 `docs/goal.md` Phase 1-6 범위를 루트 `goal.md`에 동기화하는 문서 정합화이며, live 주문, KIS paper network 호출, scheduler auto-start, `.env`/`.env.local` 수정은 수행하지 않았다.

| 항목 | 결과 | 근거 |
|---|---|---|
| Phase 1 설정/secret/token | 완료로 반영 | `backend/config/paper.yaml`, `.env.example`, `KisHttpClient`, `KisTokenManager`, KIS status/config/validate API |
| Phase 2 KIS paper broker adapter | 완료로 반영 | `KisPaperBrokerAdapter`, service alias, paper endpoint/TR-ID mapper, mock HTTP adapter tests |
| Phase 3 paper DB/API | 완료로 반영 | `paper_orders`, `paper_fills`, `paper_positions`, `paper_account_snapshots`, `paper_audit_events`, paper order/account/sync API |
| Phase 4 realtime worker | 완료로 반영 | `RealtimeMarketWorker`, polling quote cache, heartbeat/stale status, `/api/paper/realtime/status`, stale quote order gate |
| Phase 5 bot executor/risk guard | 완료로 반영 | `PaperBotExecutor`, bot preview/run/runs API, candidate filter, sizing, risk gate |
| Phase 6 monitoring/report/runbook | 완료로 반영 | `/api/paper/dashboard`, `PaperOperationalMetricsService`, report `## Paper Trading`, `docs/RUNBOOK_PAPER_TRADING.md` |
| Goal heading check | 통과 | `rg -n "KIS Paper Auto Bot Phase 1-6 진행 상태|Phase 1: 설정/secret/token 기반 구축|Phase 6: 모니터링/리포트/운영 runbook" goal.md` |
| Status docs check | 통과 | `rg -n "Goal.md KIS Paper Auto Bot Phase 1-6|KIS Paper Auto Bot Phase 1-6 Alignment" docs\PROJECT_STATUS.md docs\VALIDATION.md Memory.md` |
| Targeted backend regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_paper_runtime_flags.py backend/tests/test_paper_order_service.py backend/tests/test_paper_order_api.py backend/tests/test_paper_sync_service.py backend/tests/test_paper_realtime_worker.py backend/tests/test_paper_bot_executor_phase5.py backend/tests/test_paper_dashboard_report_phase6.py backend/tests/test_alembic_migrations.py backend/tests/test_paper_persistence_migration.py backend/tests/test_no_live_trading_regression.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_goal_phase1_6_alignment` -> `39 passed in 20.60s` |
| Secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py` -> `NO_SECRET_FINDINGS` |
| Diff whitespace check | 통과 | `git diff --check` -> exit 0, CRLF warning only |

## 2026-05-28 Goal.md Phase 16A Controlled KIS Paper Bot Run Validation

루트 `goal.md`의 `Phase 16A: Controlled KIS Paper Bot Run Validation`만 수행했다. FastAPI `TestClient`로 동일 API route를 호출했으며, scheduler auto-start, unattended loop, `.env`/`.env.local` 수정, live 주문/cancel/fallback, raw secret 출력은 수행하지 않았다. 별도 승인 없는 KIS paper network gate는 열지 않았다.

| 항목 | 결과 | 근거 |
|---|---|---|
| Dry-run preview | 안전 차단 | `POST /api/paper/bot/preview`, `max_candidates=1`, `dry_run=true` -> `run_id=paper-bot-0439a452f5b84f40`, `status=disabled`, `submitted_count=0`, `paper_order_submitted=false`, `live_order_created=false`, `network_call_performed=false` |
| Dashboard/status | 확인 | `/api/kis/config/validate`, `/api/kis/status`, `/api/broker/status`, `/api/paper/status`, `/api/paper/realtime/status`, `/api/paper/dashboard`, `/api/paper/bot/status` 모두 HTTP 200. status payload는 configured boolean만 기록하고 raw secret/account/token 미노출 |
| Process-only paper gate | 적용 | 현재 PowerShell 프로세스에서만 `KIS_ENV=paper`, `ENABLE_REAL_ORDER=false`, `PAPER_TRADING_ENABLED=true`, `PAPER_TRADING_CAN_CREATE=true`, `PAPER_BOT_CONFIRM=true`, `PAPER_TRADING_KILL_SWITCH=false` 주입 |
| KIS paper network gate | 미개방 | 별도 승인 없음. `PAPER_TRADING_NETWORK_ENABLED`, `BROKER_MODE`, `PAPER_ORDER_SUBMIT_ENABLED`는 해당 프로세스에서 미설정으로 유지 |
| `max_candidates=1` paper run | 차단 | `POST /api/paper/bot/run`, `dry_run=false` -> `run_id=paper-bot-7a43c3c83f3244f7`, `status=disabled`, `reason_codes=[PAPER_BOT_DISABLED, PAPER_BOT_KILL_SWITCH_ACTIVE, KILL_SWITCH_ACTIVE]`, `submitted_count=0`, `network_call_performed=false` |
| Counts | 유지 | 최종 `orders_count=0`, `paper_orders_count=0`, `paper_fills_count=0`, `paper_positions_count=0`, `paper_bot_decisions_count=0`; bot run metadata만 `paper_bot_runs_count=5` |
| Redacted record | 생성 | `docs/research/kis-paper-phase16a-bot-run-redacted-record.json` |
| Goal heading check | 통과 | `rg -n "Phase 16A|Controlled KIS Paper Bot Run Validation|dry_run=true|max_candidates=1|PAPER_TRADING_KILL_SWITCH" goal.md` |
| Secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py` -> `NO_SECRET_FINDINGS` |
| Diff whitespace check | 통과 | `git diff --check` -> exit 0, CRLF warning only |

결론: Phase 16A는 로컬 safety gate에서 차단 상태로 기록한다. 실제 KIS paper 최소 주문/조회/sync/cancel은 별도 network 승인, 계좌/product code 환경 준비, config/bot kill switch 해제 절차가 필요하다.

## 2026-05-28 KIS Paper Auto Bot Phase 1-6

`docs/goal.md` 기준 Phase 5-6 범위에서 bot executor/risk gate, paper dashboard, report paper trading section, 운영 metrics를 추가하고 Phase 1-4 fail-closed 계약과 함께 재검증했다.

| 항목 | 결과 | 근거 |
|---|---|---|
| Bot executor/dashboard targeted | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_bot_executor_phase5.py backend/tests/test_paper_dashboard_report_phase6.py backend/tests/test_alembic_migrations.py backend/tests/test_paper_persistence_migration.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase56_targeted2` -> `12 passed` |
| Paper regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_bot_scheduler.py backend/tests/test_paper_bot_decision.py backend/tests/test_no_live_trading_regression.py backend/tests/test_paper_order_service.py backend/tests/test_paper_order_api.py backend/tests/test_paper_submit_cancel_api.py backend/tests/test_report_quality.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase56_paper_regression2` -> `27 passed` |
| Backend full pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider --basetemp $env:TEMP\stock_kis_paper_phase56_pytest_final2` -> `416 passed in 310.50s` |
| Alembic upgrade | 통과 | `.\.venv\Scripts\python.exe -m alembic upgrade head` -> `c0d1e2f3a4b5 -> d1e2f3a4b5c6` 적용 |
| Secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py` -> `NO_SECRET_FINDINGS` |
| Diff whitespace check | 통과 | `git diff --check` -> exit 0, CRLF warning only |
| Exact command note | 대체 | 현재 셸의 `python --version`은 `Python`만 출력하고 exit 1, `alembic` 실행 파일은 PATH 미등록. 검증은 프로젝트 `.venv`의 동일 모듈로 수행 |
| Frontend | 해당 없음 | frontend 파일/API client 변경 없음 |

안전 확인:

- `/api/paper/bot/preview`는 dry-run preview만 저장하고 paper order를 생성하지 않는다.
- `/api/paper/bot/run`은 `dry_run=false`여도 kill switch, market session, stale quote, duplicate order, daily loss, concentration, cash/notional gate를 통과해야 submit을 시도한다.
- run/decision 결과는 `paper_bot_runs`, `paper_bot_decisions`에 submitted/skipped/rejected와 reason code로 저장된다.
- `/api/paper/dashboard`는 account, positions, open orders, fills, PnL, risk, worker status, token/reconnect/latency/reject/sync lag metrics를 secret 없이 반환한다.
- daily/weekly Markdown report는 `## Paper Trading` section에 주문 수, 체결 수, reject reason, PnL, stale data event, risk gate 차단 내역을 포함한다.

## 2026-05-28 KIS Paper Auto Bot Phase 1-4

`docs/goal.md` 기준 Phase 1-4 범위에서 KIS 모의투자 전용 설정/token/http client, paper adapter facade, 주문/체결/포지션/계좌 snapshot 저장 계약, realtime stale quote gate를 추가하고 fail-closed 상태를 재검증했다.

| 항목 | 결과 | 근거 |
|---|---|---|
| Goal 문서 | 통과 | `docs/goal.md`, `docs/RUNBOOK_PAPER_TRADING.md` 생성 |
| Backend full pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider --basetemp $env:TEMP\stock_kis_paper_phase1_4_pytest_final` -> `408 passed in 336.39s` |
| Alembic upgrade | 통과 | `.\.venv\Scripts\python.exe -m alembic upgrade head` -> `a8b9c0d1e2f3 -> b9c0d1e2f3a4 -> c0d1e2f3a4b5` 적용 |
| Secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py` -> `NO_SECRET_FINDINGS` |
| Diff whitespace check | 통과 | `git diff --check` -> exit 0, CRLF warning only |
| Exact command note | 대체 | 현재 셸의 `python --version`은 `Python`만 출력하고 exit 1, `alembic` 실행 파일은 PATH 미등록. 검증은 프로젝트 `.venv`의 동일 모듈로 수행 |
| Frontend | 해당 없음 | frontend 파일/API client 변경 없음 |

안전 확인:

- 기본 config/env에서는 주문, 네트워크, token issue, realtime worker가 disabled/fail-closed다.
- KIS paper submit은 `KIS_ENV=paper`, `PAPER_TRADING_ENABLED=true`, `PAPER_BOT_CONFIRM=true`, kill switch off, idempotency, risk gate, no-live 조건이 모두 필요하다.
- `/api/paper/orders`, `/api/paper/orders/{order_id}/cancel`, `/api/paper/account`, `/api/paper/realtime/status`는 additive route이며 기존 route key를 제거하지 않았다.
- `paper_account_snapshots`는 raw account number column 없이 snapshot/account alias/amount metadata만 저장한다.
- stale quote 상태에서는 신규 paper submit이 `PAPER_REALTIME_STALE_QUOTE`로 차단된다.

## 2026-05-28 GUI Mockup Follow-up

`stock_analyst_gui_mockup.html`와 `gui_개선.txt` 기준으로 누락된 Global Status Bar, dashboard 4-zone, Strategy Selector pill, Validation Framework 카드, Market Sessions route를 반영한 뒤 frontend production smoke를 재검증했다.

| 항목 | 결과 | 근거 |
|---|---|---|
| Frontend lint | 통과 | `cd frontend; npm.cmd run lint` |
| Frontend typecheck | 통과 | `cd frontend; npm.cmd exec tsc -- --noEmit` |
| Frontend build | 통과 | `cd frontend; npm.cmd run build`; route list에 `/sessions` 포함 |
| Launcher state | 통과 | `py launcher.py run --no-browser`; `py launcher.py check` -> backend 8000/frontend 3000 launcher-owned |
| Browser path | 대체 | Browser plugin `iab` unavailable로 Playwright fallback 사용 |
| Rendered desktop smoke | 통과 | `/dashboard`: global status 1, KPI 4, validation cards 3, overlay 0; `/screener`: strategy pills 9, available pill click 후 selected 6, overlay 0; `/backtest`: validation cards 3, Walk-forward heading 1; `/sessions`: session bars 2, KRX/NXT 표시 |
| Mobile smoke | 통과 | `390x844` `/dashboard`: global status 1, KPI 4, body width 390 = viewport 390, overlay 0 |
| Console/request health | 통과 | relevant error 0. Route 전환 중 pending `strategy-summary` request abort 2건은 Playwright navigation side effect로 별도 제외 |
| Audit | 통과 | `cd frontend; npm.cmd audit --audit-level=moderate` -> `found 0 vulnerabilities` |
| Secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py` -> `NO_SECRET_FINDINGS` |
| Diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning only |

대표 screenshot은 `%TEMP%\stock_gui_validation\dashboard_desktop.png`, `%TEMP%\stock_gui_validation\screener_desktop.png`, `%TEMP%\stock_gui_validation\backtest_desktop.png`, `%TEMP%\stock_gui_validation\sessions_desktop.png`, `%TEMP%\stock_gui_validation\dashboard_mobile.png`에 남겼다.

주의: 현재 로컬 DB 기준 `/api/backtest/strategy-summary?lookback_days=252`는 60초 내 응답하지 않을 수 있다. UI는 해당 API가 늦어도 Validation Framework loading 카드를 먼저 렌더링하고, 응답 도착 시 실제 값으로 교체한다.

## 2026-05-28 PowerShell 7 Latest Install And Default Shell

PowerShell 5.1이 계속 기본으로 열리는 문제를 보정하기 위해 로컬 설치 상태를 확인하고, 공식 Microsoft 문서와 winget 기준 최신 안정판 PowerShell 7을 설치한 뒤 Windows Terminal/VS Code 기본 PowerShell 프로필을 `pwsh`로 고정했다.

| 항목 | 결과 | 근거 |
|---|---|---|
| 최신 안정판 확인 | 확인 | Microsoft Learn의 Windows 설치 문서는 `winget search --id Microsoft.PowerShell --exact` 예시와 MSI 링크 기준 `7.6.2`를 최신 안정판으로 안내한다. 로컬 `winget search --id Microsoft.PowerShell --exact`도 `Microsoft.PowerShell 7.6.2.0`을 반환 |
| 기존 설치 상태 | 미설치 | `Get-Command pwsh` 결과 없음, `C:\Program Files\PowerShell\7\pwsh.exe` 없음, `%LOCALAPPDATA%\Microsoft\WindowsApps\pwsh.exe` 없음 |
| 설치 | 완료 | `winget install --id Microsoft.PowerShell --source winget --accept-package-agreements --accept-source-agreements` -> 설치 성공 |
| 설치 버전 | 통과 | `pwsh -NoProfile` -> `7.6.2`, `Core`, `$PSHOME=C:\Program Files\WindowsApps\Microsoft.PowerShell_7.6.2.0_x64__8wekyb3d8bbwe` |
| 최신 여부 | 통과 | `winget list --id Microsoft.PowerShell --exact` -> `7.6.2.0`; `winget upgrade --id Microsoft.PowerShell` -> 사용 가능한 업그레이드 없음 |
| Windows Terminal 적용 | 통과 | `%LOCALAPPDATA%\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json`의 `defaultProfile`을 `{574e775e-4f2a-5b96-ac1e-a2962a402336}`로 설정하고 해당 profile commandline을 `%LOCALAPPDATA%\Microsoft\WindowsApps\pwsh.exe`로 추가 |
| VS Code 적용 | 통과 | `%APPDATA%\Code\User\settings.json`의 `terminal.integrated.defaultProfile.windows=PowerShell`, `terminal.integrated.profiles.windows.PowerShell.path=${env:LOCALAPPDATA}\Microsoft\WindowsApps\pwsh.exe` 확인 |
| UTF-8 연동 | 통과 | profile 로드 `pwsh`에서 `chcp 65001`, `$OutputEncoding=utf-8`, Console input/output utf-8, `PYTHONIOENCODING=utf-8`, `PYTHONUTF8=1`, `GetContentDefault=utf8`; Python stdin `한글 테스트`와 `Get-Content Memory.md` 한글 정상 출력 |

## 2026-05-28 PowerShell UTF-8 Global Normalization

`/goal` 진행 중 PowerShell 한글 출력과 Python/Playwright here-string 파이프가 깨지는 원인을 점검하고, 프로젝트 한정이 아닌 사용자 전역 PowerShell 초기화로 보정했다.

| 항목 | 결과 | 근거 |
|---|---|---|
| 원인 | 확인 | Windows PowerShell 5.1 세션에서 `chcp=949`, `$OutputEncoding=us-ascii`, `ConsoleInput=ks_c_5601-1987`로 확인됨. PowerShell 5.1은 UTF-8 BOM 없는 파일을 기본 ANSI로 읽어 `Get-Content Memory.md`도 깨짐 |
| 전역 프로필 | 적용 | `C:\Users\demon\OneDrive\문서\WindowsPowerShell\profile.ps1`, `C:\Users\demon\OneDrive\문서\PowerShell\profile.ps1`, `C:\Users\demon\Documents\WindowsPowerShell\profile.ps1`, `C:\Users\demon\Documents\PowerShell\profile.ps1`에 UTF-8 초기화 추가 |
| 콘솔/파이프 인코딩 | 통과 | profile 로드 새 PowerShell에서 `chcp 65001`, `$OutputEncoding=utf-8`, `[Console]::InputEncoding=utf-8`, `[Console]::OutputEncoding=utf-8` 확인 |
| Python UTF-8 | 통과 | 사용자 환경 변수 `PYTHONIOENCODING=utf-8`, `PYTHONUTF8=1` 설정. profile 로드 새 PowerShell의 Python stdin 파이프에서 `한글 테스트` 정상 출력 |
| 파일 읽기 기본값 | 통과 | `Get-Content:Encoding`, `Select-String:Encoding`, `Import-Csv:Encoding`, `Set-Content:Encoding`, `Out-File:Encoding`, `Add-Content:Encoding`, `Export-Csv:Encoding` 기본값을 `utf8`로 지정. 새 PowerShell에서 `Get-Content Memory.md` 한글 정상 출력 |
| 비교 재현 | 확인 | `powershell.exe -NoProfile`에서는 `$OutputEncoding=us-ascii`가 유지되고 같은 Python stdin 테스트가 `?? ???`, `Get-Content Memory.md`가 깨진 출력으로 재현됨 |

## 2026-05-28 Local Launcher Recovery

`start_stock_analyst.cmd`/`py launcher.py run` 재실행 시 응답이 없어 보이는 상태를 점검했다. 원인은 3000 포트의 기존 Next 서버와 8001 백엔드가 런처 상태 파일 없이 남아 있어 표준 런처가 fail-closed로 중단된 것이다.

| 항목 | 결과 | 근거 |
|---|---|---|
| 기존 포트 상태 | 원인 확인 | 3000: Next `node.exe` PID 19988, 8001: uvicorn PID 17860. `frontend/.next/launcher-state.json`과 `launcher-build.json`은 없음 |
| 기존 API 상태 | 부분 정상 | 기존 frontend build는 `http://127.0.0.1:8001`을 호출했고, 8001 `/health`, `/api/data/status`, `/api/screener/strategies`는 200 응답 |
| 복구 조치 | 완료 | PID 19988, 17860 종료 후 `py launcher.py run --no-browser` 실행. 의존성 확인, `npm.cmd run build`, backend/frontend start 완료 |
| Launcher check | 통과 | `py launcher.py check`: python, venv, npm, frontend build, launcher build metadata, backend 8000, frontend 3000 all OK |
| HTTP smoke | 통과 | `http://127.0.0.1:8000/health` 200, `http://127.0.0.1:3000/dashboard` 200 |
| Safety smoke | 통과 | `/api/data/status`: `orders_count=0`; `/api/broker/status`: `can_submit=False`, `live=False`, `paper=False` |
| Build API base | 통과 | `frontend/.next/launcher-build.json`: `next_public_api_base_url=http://127.0.0.1:8000` |

## 2026-05-28 Phase 19-20 Publish Validation

커밋/푸시 전 현재 작업트리 기준으로 backend, frontend, secret, whitespace 검증을 재확인했다.

| 항목 | 결과 | 근거 |
|---|---|---|
| Backend full pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider --basetemp %TEMP%\stock_goal_phase19_20_backend_full_*`: 405 passed in 302.67s |
| Phase 19/20 targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_live_canary_preflight.py backend/tests/test_final_safety_hardening.py -q`: 16 passed in 0.80s |
| Frontend lint | 통과 | `cd frontend; npm.cmd run lint` |
| Frontend typecheck | 통과 | `cd frontend; npm.cmd exec tsc -- --noEmit` |
| Frontend build | 통과 | `cd frontend; npm.cmd run build` |
| Secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning only |

## 2026-05-28 Phase 19-20 Plan And Preflight

사용자 요청으로 Phase 19와 Phase 20을 계획 후 진행했다. Phase 19는 disabled live adapter scaffold 강화까지 완료했고, Phase 20은 runbook과 no-network preflight record까지 진행했다. 실제 live 주문, live endpoint 호출, WebSocket 체결은 수행하지 않았다.

| 항목 | 결과 | 근거 |
|---|---|---|
| Phase 19 disabled scaffold | 완료 | `KisLiveBrokerAdapter` live operation method가 예외 대신 `status=live_disabled`, `network_call_performed=false`, `live_order_created=false`, `endpoint_called=false` payload 반환 |
| Phase 20 runbook | 완료 | `docs/LIVE_CANARY_RUNBOOK.md` 추가. KIS 공식 포털/GitHub 샘플/Telegram Bot API 재확인 기준과 금지 조건 기록 |
| Phase 20 preflight | 차단 | `.\.venv\Scripts\python.exe tools\live_canary_preflight.py --write-record`: `status=blocked`, `canary_execution_allowed=false`, `network_call_performed=false`, `live_order_created=false` |
| Redacted record | 완료 | `docs/research/live-canary-phase20-preflight-record.json` 생성. credential은 configured boolean만 기록 |
| Targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_live_canary_preflight.py backend/tests/test_final_safety_hardening.py -q`: 16 passed in 0.80s |
| Backend full pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider --basetemp %TEMP%\stock_goal_phase19_20_backend_full_*`: 405 passed in 302.67s |
| No-live static scan | 통과 | `rg -n '/api/live|/api/kis/orders|/api/kis/broker|/api/kis/websocket|ENABLE_LIVE_SUBMIT\s*=\s*true|live_fallback_enabled\s*[:=]\s*true' backend/app frontend -g '!frontend/.next/**'`: `NO_MATCHES` |

결론: Phase 19는 완료됐다. Phase 20은 canary 계획과 preflight record까지 완료됐지만, 현재 저장소에는 live adapter 실행, live route, reviewer, 환경 분리, rollback proof가 없어 실제 controlled live canary는 차단 상태다.

## 2026-05-28 Phase 19-20 Approval Gate Audit

이 섹션은 Phase 19/20 진행 승인 전 상태의 감사 기록이다. 이후 사용자 요청으로 Phase 19 scaffold와 Phase 20 preflight는 위 섹션까지 진행됐다.

| 항목 | 결과 | 근거 |
|---|---|---|
| Phase 19 상태 | 대기 | `goal.md`에 `승인 조건: 사용자의 별도 명시 승인 필요`가 남아 있어 disabled live scaffold 확장 작업은 시작하지 않음 |
| Phase 20 상태 | 대기 | controlled live canary는 별도 명시 승인, 환경 분리, required reviewer, rollback 절차 전까지 시작 금지 |
| No-live targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_final_safety_hardening.py -q`: 13 passed |
| No-live static scan | 통과 | `rg -n '/api/live|/api/kis/orders|/api/kis/broker|/api/kis/websocket|ENABLE_LIVE_SUBMIT\s*=\s*true|live_fallback_enabled\s*[:=]\s*true' backend/app frontend -g '!frontend/.next/**'`: no matches |
| Secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning only |

결론: 이 시점에는 Phase 19~20을 진행하지 않았다. 이후 최신 상태는 `2026-05-28 Phase 19-20 Plan And Preflight` 섹션을 우선한다.

## 2026-05-28 Goal.md Phase 13-18 Progress

이번 변경은 `goal.md` 기준 Phase 13~18 범위를 안전 계약 안에서 진행했다. Phase 12C는 기존 redacted KIS 장종료 거부 응답과 최신 no-network preflight로 종결 상태를 문서화했고, Phase 19~20은 별도 명시 승인 전까지 진행하지 않는다.

| 항목 | 결과 | 근거 |
|---|---|---|
| Phase 12C default preflight | 통과 | `.\.venv\Scripts\python.exe tools\kis_paper_phase12c_dry_run.py`: `status=preflight_only`, `network_call_performed=false`, 기본 config/env blocker 유지 |
| Phase 13 final safety | 통과 | `backend/tests/test_final_safety_hardening.py` 포함 targeted suite 통과 |
| Phase 14 Telegram opt-in | 통과 | Telegram live mode config에서도 `dry_run=true`, `attempted=false`, token/chat id 원문 미노출 검증 |
| Phase 15 report automation | 구현/통과 | `GET /api/reports/automation/status`, `POST /api/reports/automation/run-once`, `tools/report_automation_runner.py`, automation 완료/실패 outbox event 추가 |
| Phase 16 paper bot soak | 통과 | `.\.venv\Scripts\python.exe -m backend.app.jobs.paper_bot_runner --once`: `paper_order_submitted=false`, `network_call_performed=false`; `--loop --max-iterations 1`: `status=loop_disabled` |
| Phase 17 runbook | 완료 | `docs/PAPER_OPERATIONS_RUNBOOK.md` 추가 |
| Phase 18 readiness design | 완료 | `docs/LIVE_TRADING_READINESS.md` 추가. live 구현/route/network call 없음 |
| Targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_report_automation.py backend/tests/test_final_safety_hardening.py backend/tests/test_notification_service.py backend/tests/test_notification_templates.py -q`: 13 passed |
| Safety pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_paper_runtime_flags.py backend/tests/test_no_live_trading_regression.py backend/tests/test_report_automation.py backend/tests/test_final_safety_hardening.py -q`: 27 passed |
| Bot/notification pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_notification_service.py backend/tests/test_paper_bot_scheduler.py -q`: 8 passed |
| Backend full pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider --basetemp %TEMP%\stock_goal_phase13_18_backend_full_final_*`: 402 passed in 352.11s |
| Report automation CLI | 통과 | `.\.venv\Scripts\python.exe tools\report_automation_runner.py`: disabled status, `execute_required=true`, `network_call_performed=false` |
| Secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning only |

## 2026-05-28 GUI Mockup Tone Match

이번 변경은 사용자가 제공한 `녹음 2026-05-28 005845.mp4`와 `stock_analyst_gui_mockup.html`을 기준으로 frontend GUI 색감과 밀도를 맞춘 작업이다. 영상 프레임 기준으로 흰 본문, 따뜻한 회백색 sidebar `#F4F3EC`, 얇은 border, compact mono typography, green active/accent tone을 전역 token으로 반영했다.

| 항목 | 결과 | 근거 |
|---|---|---|
| Reference 확인 | 통과 | 영상 13.59초에서 6개 프레임 추출, HTML 목업 구조 확인. 대표 reference: `%TEMP%\stock_analyst_gui_ref\frame_01_0.2s.png` |
| Frontend lint | 통과 | `cd frontend; npm.cmd run lint` |
| Frontend typecheck | 통과 | `cd frontend; npm.cmd exec tsc -- --noEmit` |
| Frontend build | 통과 | `cd frontend; npm.cmd run build` -> `next build --webpack`, 12 static pages 생성 |
| Production rendered smoke | 통과 | Browser plugin `iab` 연결 불가로 Playwright fallback 사용. `127.0.0.1:8001` backend + `127.0.0.1:3000` frontend에서 `/screener`, `/backtest`, mobile `/data` 확인, console/http issue 0 |
| Screenshot evidence | 생성 | `%TEMP%\stock_analyst_gui_ref\final_screener_prod_desktop.png`, `%TEMP%\stock_analyst_gui_ref\final_backtest_prod_desktop.png`, `%TEMP%\stock_analyst_gui_ref\final_data_prod_mobile.png` |
| Production build note | 조치 | 기본 Turbopack build 산출물은 `next start`에서 route chunk 404가 재현되어 hydrate가 막혔다. `frontend/package.json`의 build script를 `next build --webpack`으로 고정해 production rendered smoke를 통과시켰다. |
| Diff whitespace check | 기존 이슈 | `git diff --check`: `goal.md:7 trailing whitespace`. 이번 GUI 변경 파일에는 whitespace error 없음 |

## 2026-05-28 Goal.md Phase 2 Telegram Notifier

이번 변경은 `goal.md`의 `Phase 2: Telegram 거래 알림 및 포트폴리오 리포트 구현` 중 Telegram notifier 범위만 수행했다. 기존 notification skeleton을 교체하지 않고 `TelegramNotifier`, `NotificationService`, `NotificationOutboxService`에 메시지 템플릿 렌더링을 additive로 연결했으며, `backend/config/notifications.yaml` 기본값은 계속 `enabled: false`, `mode: disabled`, `dry_run: true`이다.

| 항목 | 결과 | 근거 |
|---|---|---|
| 지정 명령 확인 | 환경 이슈 | `python -m pytest backend/tests`: 현재 PowerShell에서 `Python`만 출력하고 exit 1. 로컬 `python` launcher가 테스트 실행 가능한 interpreter로 연결되지 않음 |
| Targeted notification pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_notifications.py backend/tests/test_notification_service.py backend/tests/test_notification_templates.py backend/tests/test_notification_outbox.py`: 15 passed in 3.22s |
| Backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests`: 393 passed in 647.04s |
| Secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Diff whitespace check | 기존 이슈 | `git diff --check`: `goal.md:7 trailing whitespace`. 해당 공백은 작업 전 존재한 `goal.md` Markdown hard-break 변경분이며 이번 notifier 구현 파일에는 whitespace error 없음 |
| Telegram template contract | 통과 | template missing field는 `not_available`로 대체, sensitive key payload는 제거, status API는 `template_events`만 노출 |
| Safety contract | 유지 | KIS 주문 API, live submit, WebSocket 경로 변경 없음. `.env.example`은 Telegram placeholder 설명만 추가했고 token/chat id 원문은 문서/API/테스트 출력에 기록하지 않음 |

## 2026-05-27 Goal.md Phase 12C Controlled KIS Paper Dry-run Attempt

이번 실행은 사용자 승인 후 `goal.md`의 `Phase 12C: Controlled KIS Paper Submit/Cancel/Query/Sync Dry-run` 범위에서 실제 KIS 모의투자 paper host까지 도달했다. `.env.local`은 생성/수정하지 않았고, 현재 PowerShell 프로세스 환경으로만 값을 주입했다. raw KIS AppKey/AppSecret/access token/account number는 출력하거나 기록하지 않았다.

결론: Phase 12C는 미완료다. kill switch 차단 증명은 통과했고 submit network call은 수행됐지만, KIS가 `40580000` / `모의투자 장종료 입니다.`를 반환해 주문번호가 생성되지 않았다. 따라서 cancel/query/sync dry-run까지 진행하지 못했고 Phase 13 진입 조건도 충족하지 않는다.

| 항목 | 결과 | 근거 |
|---|---|---|
| Preflight | 통과 | `--temporary-paper-config` 사용 시 credential/runtime/config blockers 없음. repo 기본 `backend/config/paper.yaml`은 fail-closed 유지 |
| Kill switch proof | 통과 | `submit_blocked`, `KILL_SWITCH_ACTIVE`, `network_call_performed=false` |
| Submit network call | 수행 후 실패 | paper endpoint `/uapi/domestic-stock/v1/trading/order-cash`, `tr_id=VTTC0012U`, `status_code=200`, `msg_cd=40580000`, `msg1=모의투자 장종료 입니다.` |
| Broker order | 미생성 | `broker_order_created=false`, raw broker order id 없음 |
| Cancel/query/sync | 미실행 | broker order id가 생성되지 않아 helper가 후속 단계를 수행하지 않음 |
| Live safety | 통과 | `ENABLE_REAL_ORDER=false`, paper base URL, `live_order_created=false`, `live_fallback_enabled=false` |
| Redacted record | 생성 | `docs/research/kis-paper-phase12c-redacted-record.json` |
| Phase 12C completion | 미완료 | redacted submit/cancel/query/sync 성공 기록 없음 |
| Phase 12C no-network helper | 통과 | `.\.venv\Scripts\python.exe tools\kis_paper_phase12c_dry_run.py`: `status=preflight_only`, `network_call_performed=false` |
| Trading-window gate | 통과 | `.env.local` 값을 현재 프로세스에만 주입한 뒤 `.\.venv\Scripts\python.exe tools\kis_paper_phase12c_dry_run.py --execute --temporary-paper-config --confirm-submit CONFIRM_KIS_PAPER_PHASE12C --confirm-cancel CONFIRM_KIS_PAPER_PHASE12C`: `status=trading_window_confirmation_required`, `network_call_performed=false`, exit code 2 |
| Targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_paper_runtime_flags.py backend/tests/test_no_live_trading_regression.py -q -p no:cacheprovider`: 19 passed in 0.86s |
| Backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider --basetemp %TEMP%\stock_phase12c_backend_full_*`: 389 passed in 325.65s. repo 내부 basetemp 사용 시 secret scan fixture를 스캔할 수 있으므로 workspace 밖 temp 경로를 사용 |
| Secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning only |

## 2026-05-27 Goal.md Phase 12B Paper-only Network Gate Hardening

이번 작업은 `feature/kis-paper-goal-phases` 기준 KIS 실전투자가 아닌 KIS 모의투자 계좌 전용 paper network submit/cancel/query/sync 제한 완화와 추가 hardening을 수행했다. 실제 KIS 네트워크 호출은 실행하지 않았고, mock HTTP client/fake adapter 검증만 수행했다. `.env`, `.env.local`은 생성하거나 수정하지 않았다.

| 항목 | 결과 | 근거 |
|---|---|---|
| Paper-only adapter | 구현/보강 | `KisPaperBrokerAdapter` submit/cancel/list_orders/query_balance/sync는 paper base host만 허용하고 live host 및 custom host를 차단 |
| Network submit gate | 보강 | `BROKER_MODE=paper_kis`, `PAPER_TRADING_ENABLED=true`, `PAPER_TRADING_CAN_CREATE=true`, `PAPER_TRADING_NETWORK_ENABLED=true`, `PAPER_TRADING_KILL_SWITCH=false`, `PAPER_ORDER_SUBMIT_ENABLED=true`, `confirm=true`, `idempotency_key`, risk gate, duplicate guard, `ENABLE_REAL_ORDER=false` 조건 필요 |
| Cancel/query/sync gate | 보강 | paper mode, paper adapter, network flag, `BROKER_MODE=paper_kis`, no live fallback, `ENABLE_REAL_ORDER=false` 조건 필요. cancel은 `paper_orders`에 저장된 paper order만 대상 |
| Bot auto submit | 보강 | 기본 disabled 유지. `PAPER_BOT_AUTO_SUBMIT=true` 외에 run cap, max qty, max notional, symbol duplicate guard, kill switch를 적용 |
| Redacted trace | 보강 | endpoint path, paper TR ID, mode, status code, elapsed ms, correlation id 중심 metadata만 저장하고 token/account/app key/app secret 원문은 저장하지 않음 |
| 지정 backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_paper_submit_cancel_api.py backend/tests/test_paper_sync_service.py backend/tests/test_paper_runtime_flags.py backend/tests/test_no_live_trading_regression.py -q`: 22 passed in 3.10s |
| 추가 bot/order/balance pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_bot_decision.py backend/tests/test_paper_order_service.py backend/tests/test_kis_paper_balance.py -q`: 11 passed in 3.10s |
| Secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning만 있음 |
| KIS real network call | 미실행 | Phase 12C controlled dry-run으로 남김 |

## 2026-05-27 Goal.md Phase 12C Controlled KIS Paper Dry-run Preflight (superseded)

이 섹션은 실제 `--execute --temporary-paper-config` 승인 실행 전의 preflight 기록이다. 최신 상태는 위의 `Controlled KIS Paper Dry-run Attempt` 섹션을 기준으로 본다.

이번 작업은 `goal.md`의 `Phase 12C: Controlled KIS Paper Submit/Cancel/Query/Sync Dry-run` 진입 조건을 점검했다. 먼저 Phase 12B 구현분을 `bcd40fac2a67e8c06aad32bd1f1f386b3abcab8e` 커밋으로 고정했다.

Phase 12C 실제 KIS paper network submit/cancel/query/sync dry-run은 실행하지 않았다. 최신 재시도에서 사용자가 준비한 로컬 환경값을 현재 프로세스에만 주입해 preflight를 재실행했고, KIS credential 존재 여부와 runtime network gate는 redacted boolean 기준으로 통과했다. repo 기본 config는 fail-closed 상태를 유지한다. `--temporary-paper-config`를 추가해 `backend/config/paper.yaml`을 쓰지 않는 process-only dry-run config를 검증했고, 해당 preflight는 blockers 없이 통과했다. Codex는 `.env`, `.env.local`을 생성/수정하지 않았고, raw credential/account/token 값은 출력하거나 기록하지 않았다.

| 항목 | 결과 | 근거 |
|---|---|---|
| Phase 12B commit | 완료 | `bcd40fac2a67e8c06aad32bd1f1f386b3abcab8e Implement KIS paper phase 12B adapter` |
| Branch preflight | 통과 | `feature/kis-paper-goal-phases`, `main` 아님 |
| Worktree preflight | 통과 | 12B 커밋 직후 clean 상태에서 12C preflight 시작 |
| Credential preflight | 통과 | 최신 preflight에서 `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCESS_TOKEN`, `KIS_ACCOUNT_NO`, `KIS_PRODUCT_CODE` 모두 configured=true로만 확인. 원문 값은 출력/기록하지 않음 |
| Runtime gate preflight | 통과 | 최신 preflight에서 `PAPER_TRADING_ENABLED`, `PAPER_TRADING_CAN_CREATE`, `PAPER_TRADING_NETWORK_ENABLED` enabled=true, `PAPER_TRADING_KILL_SWITCH` explicit_false=true |
| Config gate preflight | 중단 | `backend/config/paper.yaml`: `mode=safety_scaffold`, `enabled=false`, `can_create=false`, `network_enabled=false`, `kill_switch_enabled=true`, `broker_adapter.enabled=false`, `official_endpoint_confirmed=false` |
| Temporary config preflight | 통과 | `.\.venv\Scripts\python.exe tools\kis_paper_phase12c_dry_run.py --temporary-paper-config`: `status=preflight_only`, `preflight.ok=true`, `temporary_config_used=true`, `network_call_performed=false` |
| Execute confirmation gate | 통과 | `.\.venv\Scripts\python.exe tools\kis_paper_phase12c_dry_run.py --temporary-paper-config --execute`: `status=confirmation_required`, `reason_codes=[PHASE12C_SUBMIT_CANCEL_CONFIRMATION_REQUIRED]`, `network_call_performed=false`, process exit code 2 |
| Live safety | 통과 | `ENABLE_REAL_ORDER=false`, `PAPER_BOT_AUTO_SUBMIT=false`, `live_order_enabled=false`, `live_fallback_enabled=false`, paper base URL live host 아님 |
| 12C helper | 추가 | `tools/kis_paper_phase12c_dry_run.py`: default preflight-only, `--execute`와 submit/cancel 확인 토큰 없이는 네트워크 호출 없음 |
| 12C helper preflight | 중단 | `.\.venv\Scripts\python.exe tools\kis_paper_phase12c_dry_run.py`: `status=preflight_only`, `network_call_performed=false`, config blockers만 redacted 출력 |
| 12C helper pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase12c_tool.py -q -p no:cacheprovider`: 7 passed in 0.06s |
| KIS network call | 미실행 | submit/cancel/query/sync 모두 `--execute`와 즉시 human confirmation 전까지 호출하지 않음 |
| Phase 12C completion | 미완료 | redacted controlled submit/cancel/query/sync dry-run result가 없으므로 Phase 13 진입 불가 |
| Phase 12C safety pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_runtime_flags.py backend/tests/test_no_live_trading_regression.py -q -p no:cacheprovider --basetemp .pytest_tmp\phase12c`: 10 passed in 0.80s. 기본 temp/cache 경로 권한 문제를 피하기 위해 workspace temp를 지정했고, 임시 디렉터리는 제거함 |
| Secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning만 있음 |

## 2026-05-27 Goal.md Phase 12B KIS Paper Adapter Implementation

이번 작업은 `goal.md`의 `Phase 12B: KIS Paper Submit/Cancel/Query/Sync Adapter Implementation` 범위만 수행했다. 실제 KIS credential, `.env`, `.env.local`, live adapter, live endpoint, paper→live fallback은 사용하지 않았다. KIS paper network dry-run은 실행하지 않았고, adapter 동작은 mock HTTP client와 service-level fake adapter로만 검증했다.

`KisPaperBrokerAdapter`는 공식 샘플에서 확인된 KIS paper endpoint/TR ID/request field만 사용해 `order-cash`, `order-rvsecncl`, `inquire-daily-ccld`, `inquire-balance` request mapper와 response mapper를 추가했다. `inquire-psbl-rvsecncl`의 paper TR ID는 현재 프로젝트 matrix에서 직접 확인되지 않은 상태이므로 adapter 구현에 사용하지 않았다. submit/cancel/query/sync는 paper mode, process env flag, config gate, live-block, credential, kill-switch/confirm/idempotency 조건을 통과해야만 network path로 이동하며, 모든 trace는 endpoint/TR ID/status/retry 중심의 redacted metadata만 반환한다.

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Adapter submit/cancel/query/sync | 구현 | `backend/app/brokers/kis_paper.py`에 paper-only request/response mapper, redacted trace, timeout/retry/rate-limit/error handling 추가 |
| Service 연결 | 구현 | `PaperOrderService`는 network gate가 열릴 때만 adapter submit/cancel을 호출하고, `PaperSyncService`는 network gate가 열릴 때만 paper 전용 table에 sync 결과 반영 |
| Live trading path | disabled 유지 | `KisLiveBrokerAdapter` 변경 없음, `/api/kis/orders/*`, `/api/kis/broker/*`, `/api/kis/websocket/*` route 없음 |
| Real KIS network dry-run | 미실행 | mock HTTP client/fake adapter 테스트만 수행. Phase 12C로 보류 |
| 지정 backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_paper_submit_cancel_api.py backend/tests/test_paper_sync_service.py backend/tests/test_no_live_trading_regression.py -q`: 18 passed in 2.53s |
| 추가 paper regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter.py backend/tests/test_paper_order_service.py backend/tests/test_paper_order_api.py backend/tests/test_paper_runtime_flags.py backend/tests/test_paper_sync.py backend/tests/test_frontend_api_contracts.py -q`: 16 passed in 1.62s |
| Secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning만 있음 |

## 2026-05-27 Goal.md Phase 12 Split Review

이번 작업은 preflight에서 중단된 Phase 12를 완료 처리하지 않고 재검토했다. 코드 기준으로 현재 KIS paper submit/cancel/query/sync network execution은 아직 unsupported/confirmation required 상태이며, Phase 13으로 진행하지 않는다. `.env`, `.env.local`, runtime code, API route, DB schema는 수정하지 않았다.

`goal.md`의 Phase 12를 `Phase 12A: KIS paper read-only balance dry-run`, `Phase 12B: KIS paper submit/cancel/query/sync adapter implementation`, `Phase 12C: controlled KIS paper submit/cancel/query/sync dry-run`으로 분리했고, `docs/research/kis-paper-dry-run-checklist.md`도 같은 구조로 재정리했다. 다음 실행 대상은 Phase 12A이며, Phase 12B 전에는 submit/cancel/query/sync network 구현을 하지 않는다.

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase 12 상태 | 미완료 유지 | env flag만으로 완료 불가. 실제 KIS paper submit/cancel/query/sync dry-run 결과 없음 |
| 코드 기준 미완료 사유 | 확인 | `KisPaperBrokerAdapter.submit_order/cancel_order/list_orders/sync`는 confirmation-required error를 발생시킴 |
| Read-only balance 경로 | 제한적 가능 | 모든 config/env/credential gate 충족 시 `/uapi/domestic-stock/v1/trading/inquire-balance`, `tr_id=VTTC8434R`만 read-only 호출 |
| Paper submit | fail-closed 유지 | network flag가 열려도 `PAPER_NETWORK_UNSUPPORTED`, local paper submit은 confirm/idempotency/config/kill-switch gate 필요 |
| Paper cancel | fail-closed 유지 | `KIS_PAPER_CANCEL_CONFIRMATION_REQUIRED` |
| Paper sync | fail-closed 유지 | `POST /api/paper/sync`는 `KIS_PAPER_SYNC_CONFIRMATION_REQUIRED` no-op |
| Live trading path | disabled 유지 | `KisLiveBrokerAdapter`는 disabled placeholder, live route/fallback 사용 없음 |
| 문서 변경 | 적용 | `goal.md`, `docs/research/kis-paper-dry-run-checklist.md`, `docs/VALIDATION.md`, `Memory.md` |
| 지정 backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_runtime_flags.py backend/tests/test_no_live_trading_regression.py -q`: 10 passed in 0.90s |
| Secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning만 있음 |
| KIS network call | 미실행 | submit/cancel/query/sync 구현 및 dry-run 실행 없음 |
| Live endpoint call | 미실행 | 실전투자/live trading 경로 disabled 유지 |

## 2026-05-27 Goal.md Phase 12 Controlled KIS Paper Dry Run Preflight

이번 작업은 `goal.md`의 `Phase 12: Controlled KIS Paper Trading Dry Run` 범위만 확인했다. 실제 KIS 모의계좌 dry-run은 실행하지 않았다. 로컬 프로세스 환경에 KIS paper credential과 명시적 paper network/submit enable flag가 없고, `backend/config/paper.yaml`도 `enabled=false`, `can_create=false`, `network_enabled=false`, `kill_switch_enabled=true`, `live_fallback_enabled=false`의 fail-closed 상태였기 때문이다.

신규 체크리스트 `docs/research/kis-paper-dry-run-checklist.md`를 추가해 preflight 중단 사유, 수동 dry-run 절차, redaction 기준, rollback 기준을 기록했다. 공식 `koreainvestment/open-trading-api` 샘플에서 paper cash order, order modify/cancel, cancelable order query, daily order/fill query, balance query capability를 다시 확인했지만, 현재 저장소 설정에서는 네트워크 호출 조건을 충족하지 못한다. Phase 12 완료 기준인 redacted dry-run result documented는 실제 dry-run 미실행으로 아직 미충족이다.

추가로 발견된 문제는 문서상 `PAPER_TRADING_ENABLED`, `PAPER_TRADING_CAN_CREATE`, `PAPER_TRADING_NETWORK_ENABLED`, `PAPER_TRADING_KILL_SWITCH=false` 같은 human-enabled runtime flag를 요구하면서도 backend gate가 기존에는 `paper.yaml` 값만 읽었다는 점이다. 이 불일치를 막기 위해 `PaperConfigService`를 보강했다. 이제 config가 paper submit/network를 열어도 대응하는 process env flag가 명시되지 않으면 fail-closed로 유지되며, kill switch는 env에서 명시적으로 false일 때만 꺼진다. `PAPER_TRADING_NETWORK_ENABLED=true`가 있더라도 현재 paper submit network execution은 계속 `PAPER_NETWORK_UNSUPPORTED`로 차단된다.

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase 12 환경 preflight | 중단 | `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCESS_TOKEN`, `KIS_ACCOUNT_NO`, `KIS_PRODUCT_CODE`, `PAPER_TRADING_ENABLED`, `PAPER_TRADING_CAN_CREATE`, `PAPER_TRADING_NETWORK_ENABLED` 모두 absent |
| Phase 12 config gate | 중단 | `backend/config/paper.yaml`: `enabled=false`, `can_create=false`, `network_enabled=false`, `kill_switch_enabled=true`, `live_fallback_enabled=false` |
| Runtime flag hardening | 적용 | `backend/tests/test_paper_runtime_flags.py`: config true만으로 paper submit/network가 열리지 않음 |
| Runtime flag pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_runtime_flags.py -q`: 3 passed in 0.63s |
| Paper order/e2e regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_order_service.py backend/tests/test_e2e_paper_mock_flow.py -q`: 4 passed in 1.11s |
| Paper/no-live regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_submit_cancel_api.py backend/tests/test_paper_order_api.py backend/tests/test_paper_sync_service.py backend/tests/test_paper_sync.py backend/tests/test_no_live_trading_regression.py -q`: 17 passed in 1.19s |
| Full backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 373 passed in 344.18s |
| Secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| KIS network call | 미실행 | credential/explicit flag 미충족으로 호출하지 않음 |
| Live endpoint call | 미실행 | live adapter/fallback 미사용 |
| Phase 12 checklist | 작성 | `docs/research/kis-paper-dry-run-checklist.md` |

## 2026-05-27 Goal.md Phase 11 End-to-End Mock Validation

이번 변경은 `goal.md`의 `Phase 11: End-to-End Mock Validation` 범위만 수행했다. `backend/tests/test_e2e_paper_mock_flow.py`를 추가해 preview -> local paper submit -> order poll -> mock fill/position/portfolio snapshot -> fail-closed sync -> notification outbox -> report notify 흐름을 KIS credential 없이 검증한다. Phase 10 wrapper 이동으로 기존 frontend static contract 테스트가 실패해 스캔 대상에 `frontend/lib/paperApi.ts`, `frontend/lib/notificationApi.ts`, `/bot` page를 additive로 포함시켰다.

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase 11 지정 pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_e2e_paper_mock_flow.py -q`: 1 passed in 0.75s |
| Phase 11 E2E + frontend contract regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_e2e_paper_mock_flow.py backend/tests/test_frontend_api_contracts.py -q`: 3 passed in 0.84s |
| Phase 11 full backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 370 passed in 316.27s |
| Phase 11 secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Phase 11 diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning만 있음 |

## 2026-05-27 Goal.md Phase 10 Frontend Integration

이번 변경은 `goal.md`의 `Phase 10: Frontend Integration` 범위만 수행했다. 기존 `/paper`, `/reports`, `/settings` 화면 구조를 유지하면서 `frontend/lib/paperApi.ts`, `frontend/lib/notificationApi.ts` wrapper를 추가하고, `/bot` 화면에서 paper-only bot status/run-once/stop route를 조작할 수 있게 했다. 모든 UI 문구는 `모의투자`, `paper only`, `실거래 아님` 경계를 유지하며 `.env`/`.env.local`은 수정하지 않았다.

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase 10 frontend lint | 통과 | `cd frontend; npm.cmd run lint` |
| Phase 10 frontend typecheck | 통과 | `cd frontend; npm.cmd exec tsc -- --noEmit` |
| Phase 10 frontend build | 통과 | `cd frontend; npm.cmd run build`: `/bot` 포함 12 static pages 생성 |
| Phase 10 backend route smoke | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_bot_scheduler.py backend/tests/test_paper_order_api.py backend/tests/test_notification_api.py backend/tests/test_report_notify.py -q`: 12 passed in 1.20s |
| Phase 10 rendered smoke | 통과 | Browser plugin은 연결 가능한 browser가 없어 fallback Playwright로 확인. `127.0.0.1:8001` backend + `127.0.0.1:3000` frontend에서 `/bot` run-once, `/paper` preview, `/settings` notification dry-run, `/reports`, `/bot` mobile viewport 확인. framework overlay 없음, console issue 0. |
| Phase 10 screenshot evidence | 생성 | `%TEMP%\stock-analyst-phase10-bot-desktop.png`, `%TEMP%\stock-analyst-phase10-paper-desktop.png`, `%TEMP%\stock-analyst-phase10-settings-desktop.png`, `%TEMP%\stock-analyst-phase10-reports-desktop.png`, `%TEMP%\stock-analyst-phase10-bot-mobile.png` |
| Phase 10 secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Phase 10 diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning만 있음 |

## 2026-05-27 Goal.md Phase 9 Paper Bot Activation

이번 변경은 `goal.md`의 `Phase 9: Paper Bot Activation` 범위만 수행했다. `paper_bot_runs`, `paper_bot_decisions`를 추가하고 `/api/bot/status`, `/api/bot/run-once`, `/api/bot/stop`을 추가했다. bot은 기본 disabled/kill-switch active 상태이며, preview decision은 저장하되 paper submit은 config와 요청이 모두 명시 opt-in이고 session/risk gate가 통과해야만 시도한다.

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase 9 지정 pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_bot_decision.py backend/tests/test_paper_bot_scheduler.py -q`: 7 passed in 1.19s |
| Phase 9 migration pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_alembic_migrations.py backend/tests/test_paper_persistence_migration.py -q`: 4 passed in 4.57s |
| Phase 9 no-live/paper regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_no_live_trading_regression.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_paper_order_api.py -q`: 13 passed in 0.94s |
| Phase 9 secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Phase 9 live enable scan | 통과 | static scan: live/paper auto-submit true pattern 없음. 문서의 `ENABLE_REAL_ORDER=true` 언급은 차단 동작 설명이다. |
| Phase 9 diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning만 있음 |

## 2026-05-27 Goal.md Phase 8 Report Portfolio Alerts

이번 변경은 `goal.md`의 `Phase 8: Report Portfolio Alerts` 범위만 수행했다. 기존 `/api/reports/{report_id}/notify` 경로를 유지하면서 report summary에 local paper portfolio snapshot 요약을 추가했다. 이 요약은 KIS 네트워크를 호출하지 않고 `paper_portfolio_snapshots`/`paper_positions`만 읽으며, snapshot metadata raw payload는 notification payload에 포함하지 않는다.

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase 8 지정 pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_report_notify.py -q`: 3 passed in 0.68s |
| Phase 8 report/notification/no-live regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_notifications.py backend/tests/test_notification_api.py backend/tests/test_report_quality.py backend/tests/test_no_live_trading_regression.py -q`: 19 passed in 29.51s |
| Phase 8 secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Phase 8 live enable scan | 통과 | static scan: live/paper auto-submit true pattern 없음. 문서의 `ENABLE_REAL_ORDER=true` 언급은 차단 동작 설명이다. |
| Phase 8 diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning만 있음 |

## 2026-05-27 Goal.md Phase 7 Notification Implementation

이번 변경은 `goal.md`의 `Phase 7: Notification Implementation` 범위만 수행했다. 기존 notification skeleton을 교체하지 않고 Telegram-first channel ordering, supported event list, `NotificationOutboxService`, Discord webhook wrapper, schema/API request model 정리를 additive로 보강했다. outbox dispatch 실패는 caller로 예외를 전파하지 않고 event를 `retry` 상태로 남긴다.

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase 7 지정 pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_notification_service.py backend/tests/test_notification_outbox.py -q`: 6 passed in 0.63s |
| Phase 7 notification/report/no-live regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_notifications.py backend/tests/test_notification_api.py backend/tests/test_report_notify.py backend/tests/test_no_live_trading_regression.py -q`: 18 passed in 0.93s |
| Phase 7 migration regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_alembic_migrations.py backend/tests/test_paper_persistence_migration.py -q`: 4 passed in 4.52s |
| Phase 7 secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Phase 7 live enable scan | 통과 | static scan: live/paper auto-submit true pattern 없음. 문서의 `ENABLE_REAL_ORDER=true` 언급은 차단 동작 설명이다. |
| Phase 7 diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning만 있음 |

## 2026-05-27 Goal.md Phase 6 Notification Channel Decision

이번 변경은 `goal.md`의 `Phase 6: Notification Channel Decision` 범위만 수행했다. notifier 구현, route, migration, config 변경은 하지 않았고, Telegram-first primary channel 결정과 Discord follow-up path를 문서화했다.

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase 6 테스트 | N/A | `goal.md` 기준 테스트 파일과 검증 명령어 없음. 문서 결정만 수행 |
| Phase 6 문서 구조 확인 | 통과 | `rg -n "Telegram-first|Discord|Security Handling|Interface Contract|Phase 6 Notification Channel Decision" docs/research/notification-channel-decision.md docs/research/kis-paper-api-confirmation-matrix.md` |
| Phase 6 secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Phase 6 live enable scan | 통과 | static scan: live/paper auto-submit true pattern 없음. 문서의 `ENABLE_REAL_ORDER=true` 언급은 차단 동작 설명이다. |
| Phase 6 diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning만 있음 |

## 2026-05-27 Goal.md Phase 5 Order Fills Positions Portfolio Sync

이번 변경은 `goal.md`의 `Phase 5: Order Fills Positions Portfolio Sync` 범위만 수행했다. 기존 paper persistence schema와 `/api/paper/*` read/sync route는 유지하고, `PaperRepository`를 추가해 `paper_orders`, `paper_fills`, `paper_positions`, `paper_portfolio_snapshots`, `broker_audit_events`, `kis_token_status_metadata` 조회/count 경계를 고정했다. `POST /api/paper/sync`는 공식 KIS sync 계약 확인 전까지 fail-closed/idempotent no-op을 유지한다.

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase 5 지정 pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_sync_service.py backend/tests/test_alembic_migrations.py -q`: 5 passed in 3.16s |
| Phase 5 paper/no-live regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_sync.py backend/tests/test_paper_portfolio_api.py backend/tests/test_no_live_trading_regression.py -q`: 13 passed in 0.81s |
| Phase 5 migration/order regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_persistence_migration.py backend/tests/test_paper_order_api.py -q`: 4 passed in 2.65s |
| Phase 5 secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Phase 5 live enable scan | 통과 | static scan: live/paper auto-submit true pattern 없음. 문서의 `ENABLE_REAL_ORDER=true` 언급은 차단 동작 설명이다. |
| Phase 5 diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning만 있음 |

## 2026-05-27 Goal.md Phase 4 Paper Order Submit Cancel

이번 변경은 `goal.md`의 `Phase 4: Paper Order Submit Cancel` 범위만 수행했다. 기존 paper submit/cancel API를 유지하면서 API 응답에 `paper_only`, `execution_mode="paper"`, `live_fallback_enabled=false`, redacted `broker_trace`를 추가했다. 기본 config에서는 kill-switch/config gate로 submit이 blocked되고 cancel은 공식 KIS cancel payload 확인 전 disabled 상태를 유지한다.

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase 4 지정 pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_submit_cancel_api.py backend/tests/test_no_live_trading_regression.py -q`: 9 passed in 0.68s |
| Phase 4 related regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_order_api.py backend/tests/test_paper_order_service.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_no_live_adapter.py -q`: 14 passed in 0.87s |
| Phase 4 secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Phase 4 live enable scan | 통과 | static scan: live/paper auto-submit true pattern 없음. 문서의 `ENABLE_REAL_ORDER=true` 언급은 차단 동작 설명이다. |
| Phase 4 diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning만 있음 |

## 2026-05-27 Goal.md Phase 3 Token Hashkey Request Signing

이번 변경은 `goal.md`의 `Phase 3: Token Hashkey Request Signing` 범위만 수행했다. token raw value를 저장하지 않는 metadata-only manager, hashkey 미확인 시 fail-closed signer, credential/account/header redaction utility를 추가했다. 실제 token 발급, hashkey 네트워크 호출, 주문 submit은 구현하지 않았다.

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase 3 지정 pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_token_manager.py backend/tests/test_kis_request_signer.py backend/tests/test_secret_redaction.py -q`: 10 passed in 0.94s |
| Phase 3 related regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_token_manager.py backend/tests/test_phase3c_kis_readonly.py backend/tests/test_no_live_trading_regression.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_no_live_adapter.py -q`: 22 passed in 3.29s |
| Phase 3 secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Phase 3 live enable scan | 통과 | static scan: live/paper auto-submit true pattern 없음. 문서의 `ENABLE_REAL_ORDER=true` 언급은 차단 동작 설명이다. |
| Phase 3 diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning만 있음 |

## 2026-05-27 Goal.md Phase 2 Paper Broker Adapter Hardening

이번 변경은 `goal.md`의 `Phase 2: Paper Broker Adapter Hardening` 범위만 수행했다. 서비스 계층 adapter import path를 추가하고 `BrokerService`/`PaperTradingService`가 새 paper-only/live-disabled adapter boundary를 사용하도록 전환했다. 네트워크 주문, live adapter 활성화, DB schema 변경은 없다.

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase 2 지정 pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_no_live_adapter.py -q`: 5 passed in 0.08s |
| Phase 2 related regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py -q`: 20 passed in 0.97s |
| Phase 2 secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Phase 2 live enable scan | 통과 | static scan: live/paper auto-submit true pattern 없음. 문서의 `ENABLE_REAL_ORDER=true` 언급은 차단 동작 설명이다. |
| Phase 2 diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning만 있음 |

## 2026-05-27 Goal.md Phase 1 KIS Paper API Confirmation Matrix

이번 변경은 `goal.md`의 `Phase 1: KIS Paper API Confirmation Matrix` 범위만 수행했다. `docs/research/kis-paper-api-confirmation-matrix.md`를 추가해 공식 KIS 포털/공식 GitHub 샘플에서 확인 가능한 endpoint/TR ID와 `확인 필요` 항목을 분리했고, production code, API route, DB schema, `.env` 계열 파일은 변경하지 않았다.

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase 1 safety regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3c_kis_readonly.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py -q`: 17 passed in 3.36s |
| Phase 1 secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Phase 1 live enable scan | 통과 | static scan: live/paper auto-submit true pattern 없음. `Memory.md`의 `ENABLE_REAL_ORDER=true` 언급은 차단 동작 설명이다. |
| Phase 1 diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning만 있음 |

## 2026-05-27 Goal.md Phase 0 Baseline Audit Refresh

이번 변경은 루트 `goal.md`의 `Phase 0: Latest Baseline Audit` 범위만 수행했다. `docs/research/kis-paper-baseline-audit.md`를 추가해 main ref와 현재 작업 브랜치를 분리 감사했고, runtime code, API route, DB schema, `.env` 계열 파일은 변경하지 않았다.

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Goal Phase 0 full backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 342 passed in 327.46s |
| Goal Phase 0 secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Goal Phase 0 frontend lint/typecheck/build | 통과 | `npm.cmd run lint`, `npm.cmd exec tsc -- --noEmit`, `npm.cmd run build` |
| Goal Phase 0 diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning만 있음 |

## 2026-05-27 KIS Paper Balance Inquiry

이번 변경은 `/api/paper/portfolio`에 KIS 모의투자 주식잔고조회 read-only 경로를 조건부로 추가했다. 기본 disabled/mock 상태에서는 기존 `paper_portfolio_snapshots` fallback을 유지하며, KIS paper mode와 env credential이 모두 안전 조건을 만족할 때만 `/uapi/domestic-stock/v1/trading/inquire-balance`를 `tr_id=VTTC8434R`로 호출한다. 주문 API, 실전 TR ID, token/cache persistence는 연결하지 않았다.

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| KIS balance client 및 paper portfolio fallback pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_balance.py backend/tests/test_paper_portfolio_api.py -q`: 7 passed in 0.96s |
| no-live/secret/adapter 회귀 | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_no_live_trading_regression.py backend/tests/test_secret_redaction.py backend/tests/test_kis_paper_adapter.py -q`: 13 passed in 1.20s |
| 전체 backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 342 passed in 631.22s |
| repo secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| frontend lint/typecheck/build | 통과 | `npm.cmd run lint`, `npm.cmd exec tsc -- --noEmit`, `npm.cmd run build` |
| diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning만 있음 |

주의: frontend build 최초 1회는 기존 localhost backend/frontend 서버가 `frontend\.next\launcher-backend.err.log`를 잠그고 있어 `EBUSY`로 실패했다. 해당 저장소의 로컬 uvicorn/next 서버 프로세스를 종료한 뒤 같은 `npm.cmd run build`가 통과했다.

## 최신 검증 결과

검증 기준일: 2026-05-27

Version: `MVP v0.26.0`

Checkpoint: `KIS Paper Balance Inquiry Read-only`

기준 브랜치: `feature/kis-paper-goal-phases` (baseline: `main`)

Next recommended phase: KIS paper submit/cancel/sync network 구현은 보류. balance 조회는 read-only 조건부 경로만 허용

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Goal Phase 0 full backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 342 passed in 327.46s |
| Goal Phase 0 secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Goal Phase 0 frontend lint/typecheck/build | 통과 | `npm.cmd run lint`, `npm.cmd exec tsc -- --noEmit`, `npm.cmd run build` |
| Goal Phase 0 diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning만 있음 |
| Phase 0 KIS read-only safety pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3c_kis_readonly.py -q`: 7 passed in 2.70s |
| Phase 0 broker safety pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3d_broker_safety.py -q`: 6 passed in 0.54s |
| Phase 0 paper safety pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3e_paper_safety.py -q`: 4 passed in 0.55s |
| Phase 0 secret exposure scan | 통과 | changed Phase 0 docs/goal scope scan: `NO_SECRET_FINDINGS` |
| Phase 0 live trading enable scan | 통과 | backend/frontend/config static scan: `NO_LIVE_TRADING_ENABLE_FINDINGS` |
| Phase 1 notification pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_notifications.py backend/tests/test_notification_api.py -q`: 8 passed in 0.49s |
| Phase 1 broker/paper safety regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py -q`: 10 passed in 0.68s |
| Phase 1 frontend lint/typecheck/build | 통과 | `npm.cmd run lint`, `npm.cmd exec tsc -- --noEmit`, `npm.cmd run build` |
| Phase 1 secret exposure scan | 통과 | changed/untracked Phase 1 scope scan: `NO_PHASE1_SECRET_FINDINGS` |
| Phase 1 live trading enable scan | 통과 | backend/frontend/config static scan: `NO_PHASE1_LIVE_TRADING_ENABLE_FINDINGS` |
| Phase 2 adapter/token/no-live pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter.py backend/tests/test_token_manager.py backend/tests/test_no_live_trading_regression.py -q`: 9 passed in 0.54s |
| Phase 2 KIS/broker safety regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3c_kis_readonly.py backend/tests/test_phase3d_broker_safety.py -q`: 13 passed in 3.05s |
| Phase 2 secret exposure scan | 통과 | changed/untracked Phase 2 scope scan: `NO_PHASE2_SECRET_FINDINGS` |
| Phase 2 live trading enable scan | 통과 | backend/frontend/config static scan: `NO_PHASE2_LIVE_TRADING_ENABLE_FINDINGS` |
| Phase 3 migration pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_persistence_migration.py backend/tests/test_alembic_migrations.py -q`: 4 passed in 4.17s |
| Phase 3 local Alembic upgrade | 통과 | local SQLite drift를 additive column 보강 후 `.\.venv\Scripts\python.exe -m alembic stamp f7a8b9c0d1e2`, `.\.venv\Scripts\python.exe -m alembic upgrade head`: current `a8b9c0d1e2f3 (head)` |
| Phase 3 secret exposure scan | 통과 | changed/untracked Phase 3 scope scan: `NO_PHASE3_SECRET_FINDINGS` |
| Phase 3 live trading enable scan | 통과 | backend/frontend/config static scan: `NO_PHASE3_LIVE_TRADING_ENABLE_FINDINGS` |
| Phase 4 paper order lifecycle pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_order_api.py backend/tests/test_paper_order_service.py backend/tests/test_no_live_trading_regression.py -q`: 9 passed in 0.79s |
| Phase 4 paper safety regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3e_paper_safety.py -q`: 4 passed in 0.59s |
| Phase 4 related regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3f_readonly_provider_contract.py backend/tests/test_phase3f2_kis_daily_ohlcv_adapter.py backend/tests/test_phase3f3_krx_fixture_contract.py backend/tests/test_phase3f4_data_quality_summary.py backend/tests/test_phase3g_backtest_execution_model.py -q`: 21 passed in 39.73s |
| Phase 4 secret exposure scan | 통과 | changed/untracked Phase 4 scope scan: `NO_PHASE4_SECRET_FINDINGS` |
| Phase 4 live trading enable scan | 통과 | backend/frontend/config static scan: `NO_PHASE4_LIVE_TRADING_ENABLE_FINDINGS` |
| Phase 5 paper sync/portfolio pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_sync.py backend/tests/test_paper_portfolio_api.py -q`: 6 passed in 0.76s |
| Phase 5 no-live regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_no_live_trading_regression.py -q`: 5 passed in 0.63s |
| Phase 5 KIS adapter regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter.py -q`: 3 passed in 0.03s |
| Phase 5 secret exposure scan | 통과 | changed/untracked Phase 5 scope scan: `NO_PHASE5_SECRET_FINDINGS` |
| Phase 5 live trading enable scan | 통과 | backend/frontend/config static scan: `NO_PHASE5_LIVE_TRADING_ENABLE_FINDINGS` |
| Phase 6 report notify pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_report_notify.py backend/tests/test_notifications.py -q`: 8 passed in 0.73s |
| Phase 6 notification API regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_notification_api.py -q`: 3 passed in 0.54s |
| Phase 6 report quality regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_report_quality.py -q`: 4 passed in 28.61s |
| Phase 6 secret exposure scan | 통과 | changed/untracked Phase 6 scope scan: `NO_PHASE6_SECRET_FINDINGS` |
| Phase 6 live trading enable scan | 통과 | backend/frontend/config static scan: `NO_PHASE6_LIVE_TRADING_ENABLE_FINDINGS` |
| Phase 7 bot scheduler pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_bot_scheduler.py backend/tests/test_no_live_trading_regression.py -q`: 9 passed in 1.76s |
| Phase 7 launcher regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_local_launcher.py -q`: 7 passed in 0.08s |
| Phase 7 frontend lint/typecheck/build | 통과 | `npm.cmd run lint`, `npm.cmd exec tsc -- --noEmit`, `npm.cmd run build` |
| Phase 7 secret exposure scan | 통과 | changed/untracked Phase 7 scope scan: `NO_PHASE7_SECRET_FINDINGS` |
| Phase 7 live trading enable scan | 통과 | backend/frontend/config static scan: `NO_PHASE7_LIVE_TRADING_ENABLE_FINDINGS` |
| Phase 8 frontend API contract pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_frontend_api_contracts.py -q`: 2 passed in 0.61s |
| Phase 8 related regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_frontend_api_contracts.py backend/tests/test_no_live_trading_regression.py backend/tests/test_report_notify.py -q`: 11 passed in 1.62s |
| Phase 8 frontend lint/typecheck/build | 통과 | `npm.cmd run lint`, `npm.cmd exec tsc -- --noEmit`, `npm.cmd run build` |
| Phase 8 local UI smoke | 통과 | backend `127.0.0.1:8123` + frontend `127.0.0.1:3123` fallback HTTP smoke: `/paper`, `/portfolio`, `/reports`, `/settings` 모두 `모의투자`, `실거래 아님`, `paper only` 포함, secret/live-ready copy 없음 |
| Phase 8 secret exposure scan | 통과 | changed/untracked Phase 8 scope scan: `NO_PHASE8_SECRET_FINDINGS` |
| Phase 8 live trading enable scan | 통과 | backend/frontend/config static scan: `NO_PHASE8_LIVE_TRADING_ENABLE_FINDINGS` |
| Phase 9 secret/no-live/migration pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_secret_redaction.py backend/tests/test_no_live_trading_regression.py backend/tests/test_alembic_migrations.py -q`: 12 passed in 7.23s |
| Phase 9 notifier/KIS regression | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_notifications.py backend/tests/test_notification_api.py backend/tests/test_kis_paper_adapter.py backend/tests/test_token_manager.py -q`: 14 passed in 0.82s |
| Phase 9 full backend pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 338 passed in 514.20s |
| Phase 9 secret scan | 통과 | `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS` |
| Phase 9 frontend lint/typecheck/build | 통과 | `npm.cmd run lint`, `npm.cmd exec tsc -- --noEmit`, `npm.cmd run build` |
| Diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF warning 외 whitespace error 없음 |
| Documentation cross-reference check | 통과 | `README.md`, `docs/PROJECT_STATUS.md`, `docs/DB_MIGRATION.md`, `docs/plans/README.md`, `docs/VALIDATION.md`, `Memory.md` Phase 0 기준선 반영 |
| 직전 backend full pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 293 passed in 282.75s |
| 직전 frontend install/lint/typecheck/build | 통과 | `node -v`: v24.15.0, `npm.cmd ci`, `npm.cmd run lint`, `npm.cmd exec tsc -- --noEmit`, `npm.cmd run build` |

## 검증 범위

- KIS paper broker Phase 0는 문서 전용 변경이며 runtime code, API endpoint, DB schema를 변경하지 않았다.
- KIS paper broker Phase 1은 notification foundation만 추가했다. 기본 config는 disabled/dry-run이며 trading flow와 연결하지 않았다.
- `/api/notifications/status`와 `/api/notifications/test`는 secret 값을 반환하지 않고 credential configured boolean만 반환한다.
- Discord adapter는 `allowed_mentions.parse=[]` payload를 강제하고, Telegram adapter는 unsafe MarkdownV2를 기본값으로 사용하지 않는다.
- KIS paper broker Phase 2는 adapter/token contract skeleton만 추가했다. `KisPaperBrokerAdapter`는 공식 endpoint/TR-ID/request field 확인 전 capability를 `KIS_PAPER_OFFICIAL_ENDPOINT_CONFIRMATION_REQUIRED`로 막고, `KisLiveBrokerAdapter`는 disabled placeholder로만 존재한다.
- `KisTokenManager`는 raw token을 process memory에만 저장하고 metadata/status에서는 `***REDACTED***`만 반환한다. token cache file/DB persistence는 활성화하지 않는다.
- KIS paper broker Phase 3는 `paper_orders`, `paper_fills`, `paper_positions`에 nullable broker-sync metadata만 추가하고, `positions` synthetic table은 변경하지 않았다.
- 신규 table은 `paper_portfolio_snapshots`, `broker_audit_events`, `notification_events`, `notification_delivery_logs`, `kis_token_status_metadata`이며 raw token/account/webhook/chat_id column을 만들지 않는다.
- `docs/plans/phase-paper-broker-baseline-audit.md`는 현재 `main` baseline, stale 문서 충돌, source-of-truth 우선순위를 기록한다.
- `docs/KIS_PAPER_API_MATRIX.md`는 공식 문서에서 완전 확인되지 않은 KIS paper endpoint/path/TR-ID/request field를 `확인 필요`로 남긴다.
- `README.md`, `docs/plans/README.md`, `docs/DB_MIGRATION.md`의 stale 기준선을 `docs/PROJECT_STATUS.md`와 `docs/VALIDATION.md` 기준으로 조정했다.
- `strategy_parameter_snapshots` SQLAlchemy model과 Alembic head `a8b9c0d1e2f3_paper_trading_persistence`가 테스트 DB에 적용된다.
- strategy parameter snapshot은 `strategy_name`, `config_hash`, `snapshot_date`, `effective_date`, `parameter_json`, `created_at`을 저장한다.
- `StrategyParameterSnapshotService.save_current_snapshots()`는 현재 config의 `common + strategy` payload를 strategy별 snapshot으로 저장하고, `latest_snapshots()`로 기준일 이전 최신 snapshot을 조회한다.
- `StrategyParameterSnapshotService.parameter_drift_check()`는 snapshot이 없으면 `not_available_in_current_mvp`, `strategy_parameter_snapshot_not_found`, `comparison_available=false`, `drifted_parameter_count=0`을 반환해 거짓 diff를 만들지 않는다.
- snapshot이 있으면 현재 config와 snapshot의 parameter path별 diff, changed key 목록, unchanged key count, snapshot/effective date 목록, config hash 변경 요약을 계산한다.
- Weekly Strategy Review의 `Parameter Drift Check`는 placeholder bullet 대신 `changed_keys`, `unchanged_keys_count`, `snapshot_dates`, `effective_dates`, `config_hash_diff`와 strategy별 diff table을 출력한다.
- drift가 없으면 Markdown과 detail metadata에 `no_drift_detected`를 명시한다.
- snapshot이 없는 weekly report는 `parameter_snapshot_status: not_available_in_current_mvp`, `comparison_available: false`, `unavailable_reason: strategy_parameter_snapshot_not_found`를 Markdown에 명시한다.
- `GET /api/reports/{report_id}`와 `POST /api/reports/weekly` 응답의 `metadata.parameter_drift`는 저장된 Markdown에서 추출한 값이므로 Markdown과 모순되지 않는다.
- 기존 daily/weekly report API 응답 key, `reports` table, Markdown 다운로드 contract는 변경하지 않았다.
- `indicator_snapshot` breadth fields SQLAlchemy model과 이전 Alembic head `e5f6a7b8c9d0_add_indicator_breadth_fields`는 새 head의 선행 migration으로 유지된다.
- `IndicatorService.recompute()`는 full recompute와 `symbol/start_date/end_date` 증분 recompute를 모두 지원하고, 증분 결과가 full recompute changed range와 일치한다.
- weekly derived field availability flags는 short-history 입력에서 false/not_available 계열로 fail-closed 처리된다.
- `RegimeService`는 breadth proxy를 제공하고, universe breadth 데이터가 없으면 `breadth_regime="not_available"`로 처리한다.
- `momentum_rank`, `stage_analysis_weekly` breadth hardening은 optional enabled 상태에서만 pass/fail에 적용된다.
- CANSLIM Lite earnings blackout은 `earnings_date`, `release_ts`, `session`을 함께 사용하며 release timestamp/session 누락 또는 미인식 session은 fail-closed로 처리된다.
- `MarketRepository.corporate_actions_asof()`는 `corporate_actions.action_date <= trade_date`만 반환하고 future corporate action을 제외한다.
- Backtest `execution.use_adjusted_price=true`는 유효한 corporate action as-of row가 있는 bar에서만 `adj_close / close` factor를 적용하고, 그 외에는 raw OHLC로 실행한다.
- CSV/external daily OHLCV preview는 `adj_close != close`인데 effective corporate action이 없으면 `ADJUSTED_CLOSE_WITHOUT_EFFECTIVE_CORPORATE_ACTION` warning을 남긴다.
- 별도 `weekly_ohlcv` table/migration은 추가하지 않았다. 주봉 파생값은 daily OHLCV 기반 as-of 계산과 `indicator_snapshot` nullable fields를 유지한다.
- `backtest_trade_ledger` SQLAlchemy model과 saved backtest trade ledger migration이 테스트 DB에 적용된다.
- 저장형 `POST /api/backtest/run`은 `backtest_runs`와 함께 closed trade ledger rows를 저장한다.
- `GET /api/backtest/runs/{run_id}`는 기존 metric contract를 유지하면서 `trade_ledger_count`, `trade_ledger`, `trades`를 additive로 반환한다.
- `GET /api/backtest/runs/{run_id}/trades`는 저장된 ledger rows를 조회한다.
- `POST /api/reports/daily` 기존 daily report 생성 계약을 유지한다.
- `POST /api/reports/weekly`는 `report_type="weekly"`로 Report 테이블을 재사용한다.
- `GET /api/reports?report_type=daily|weekly`는 기존 `limit` query에 additive filter로 동작한다.
- `GET /api/reports/{report_id}/markdown`는 daily/weekly 모두 Markdown 다운로드로 동작한다.
- Weekly Strategy Review는 ledger가 있으면 realized trade count, realized PnL, realized return, win rate, average holding days, setup별 trade hit rate, failed trades review를 계산한다.
- `FactorFilterAttributionService`는 `backtest_trade_ledger.signal_date = screen_results.trade_date`, `symbol`, `strategy_name/strategy_tag`로 ledger와 screen_results를 join한다.
- realized PnL attribution과 screen filter failure counts는 별도 section으로 계산한다.
- join 가능한 row만 `strategy_name`, `pass_flags`, `failed_conditions`, `risk_flags`, `sector`, `market_regime` 기준 attribution에 사용하며, join 불가능하거나 저장되지 않은 dimension은 `not_available_in_current_mvp`로 남긴다.
- sector는 `symbol_master.sector`에서 조회하고, market_regime은 `screen_results.metadata_json.market_regime`처럼 저장된 값이 있을 때만 사용한다. 현재 screen 결과에 저장되지 않은 market regime은 재추정하지 않는다.
- Weekly Strategy Review의 `Factor/Filter Attribution`은 placeholder bullet 대신 realized PnL attribution table과 screen filter failure counts table을 출력한다.
- ledger가 없거나 현재 MVP에 저장 계약이 없는 realized drawdown/exposure/open position risk, regime segment return, MAE/MFE 항목은 `not_available_in_current_mvp`로 표기한다.
- `GET /api/portfolio/risk`는 기존 주요 응답 필드를 유지하면서 `max_open_positions`, gross/sector/symbol/strategy exposure, `daily_loss_budget`, `gap_risk_estimate`, `concentration_warnings`를 additive로 반환한다.
- portfolio risk summary는 `positions`와 최신 통과 `screen_results`를 함께 활용하되 synthetic/preview 한계를 `warnings`와 `gap_risk_estimate.status`에 남긴다.
- `MarketSessionService`는 KRX `regular`/`after_hours`, NXT `pre_market`/`main`/`after_market`, 휴장일 또는 세션 외 시간을 판정한다.
- `GET /api/market/session`, `GET /api/market/sessions`, `GET /api/market/calendar`는 network 없이 venue/session/calendar metadata를 반환한다.
- `/api/broker/orders/preview`와 `/api/paper/orders/preview`는 기존 deny/fail-closed 계약을 유지하면서 `venue`, `session`, `session_metadata`를 additive로 반환한다.
- 실제 주문, paper order, broker/KIS route, credential/token 저장 경로는 추가하지 않았다.
- `StrategyValidationService`는 strategy summary 계산을 담당하고, `ValidationReportService`는 JSON artifact 저장을 담당한다. 기존 `BacktestService.strategy_summary()`와 `ReportService.write_strategy_validation_summary()`는 호환 wrapper로 유지한다.
- baseline 비교는 `ValidationBaselineComparator`가 담당하며 `baseline_run_id`, `baseline_snapshot`, strategy list snapshot, 단일 strategy snapshot shape를 재사용 가능한 metric map으로 정규화한다.
- `GET /api/backtest/strategy-summary`는 기존 strategy-level `screener`, `backtest`, `delta` payload를 유지하면서 `validation_framework`와 strategy별 `validation` payload를 additive로 반환한다.
- `WalkForwardRunner`는 입력받은 train/test/step trading-day window와 rebalance frequency로 rolling window를 만들고, 각 window의 test 구간만 `BacktestService.run(save=False)`로 실행한다.
- 기본 summary path는 train 126 trading days, test 21 trading days, step 63 trading days, backtest config의 rebalance frequency를 사용한다.
- strategy별 `validation.walk_forward`는 실제 OOS window metric에서 `oos_trade_count`, `oos_weighted_win_rate`, `oos_total_return`, `oos_average_window_return`, `oos_median_window_return`, `oos_positive_window_rate`, `oos_max_drawdown`, `oos_average_sharpe_ratio`, `oos_average_turnover`를 계산한다.
- indicator trading day가 train+test보다 부족하면 `calculated=false`, `reason="insufficient_indicator_trading_days"`, `summary=null`, `windows=[]`를 반환해 거짓 OOS 수치를 만들지 않는다.
- `validation_framework.overfitting.pbo`는 walk-forward window `total_return` 행렬이 strategy 2개 이상, 비교 가능 window 2개 이상일 때 leave-one-window-out CSCV-lite 방식으로 계산한다.
- `validation_framework.overfitting.deflated_sharpe_ratio`는 strategy 2개 이상, strategy별 OOS return sample 4개 이상, return variance가 있을 때 multiple-testing expected-max Sharpe와 skewness/kurtosis input shape를 포함해 계산한다.
- strategy별 `validation.overfitting`에도 PBO rank-decay lite와 Deflated Sharpe Ratio payload를 additive로 반환한다.
- `backend/reports/strategy_validation_252d.json` artifact는 top-level `validation_framework.walk_forward`/`validation_framework.attribution`과 strategy별 `validation.walk_forward`/`validation.attribution` 결과를 함께 저장한다.
- `POST /api/backtest/run`은 기존 응답 key를 제거하지 않고 `validation_framework`를 additive로 반환한다.
- backtest metrics에는 `walk_forward`, `pbo`, `probability_of_backtest_overfitting`, `deflated_sharpe_ratio`, `factor_filter_attribution` placeholder가 추가됐다.
- 저장형 backtest run metrics의 `walk_forward` placeholder는 호환을 위해 유지한다. strategy-summary의 validation payload에서만 최소 OOS summary를 계산한다.
- PBO/Deflated Sharpe Ratio는 표본이 부족하면 `not_available_in_current_mvp`, `calculated=false`, 명확한 `reason`을 유지한다. factor/filter attribution은 저장된 ledger/screen join으로 확인 가능한 값만 계산한다.
- minimal trade ledger schema는 `validation_framework.trade_ledger_schema`에 문서화한다. 범위는 `backtest_and_report_analysis_only`이며 `orders`, `paper_orders`, broker adapter, KIS order route, live trading과 연결하지 않는다.

## 재현 명령

Phase 1 notification:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_notifications.py backend/tests/test_notification_api.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py -q
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
cd ..
```

Phase 2 broker contract:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter.py backend/tests/test_token_manager.py backend/tests/test_no_live_trading_regression.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3c_kis_readonly.py backend/tests/test_phase3d_broker_safety.py -q
```

Phase 3 paper persistence:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_persistence_migration.py backend/tests/test_alembic_migrations.py -q
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Phase 4 paper order lifecycle:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_order_api.py backend/tests/test_paper_order_service.py backend/tests/test_no_live_trading_regression.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3e_paper_safety.py -q
```

Phase 5 paper sync/portfolio:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_sync.py backend/tests/test_paper_portfolio_api.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_no_live_trading_regression.py -q
```

Phase 6 report notification:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_report_notify.py backend/tests/test_notifications.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_notification_api.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_report_quality.py -q
```

Phase 7 bot scheduler:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_bot_scheduler.py backend/tests/test_no_live_trading_regression.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_local_launcher.py -q
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
cd ..
```

Phase 8 frontend integration:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_frontend_api_contracts.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_frontend_api_contracts.py backend/tests/test_no_live_trading_regression.py backend/tests/test_report_notify.py -q
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
cd ..
```

Phase 9 validation hardening:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_secret_redaction.py backend/tests/test_no_live_trading_regression.py backend/tests/test_alembic_migrations.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_notifications.py backend/tests/test_notification_api.py backend/tests/test_kis_paper_adapter.py backend/tests/test_token_manager.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe tools\secret_scan.py
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
cd ..
```

Phase 0 safety:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3c_kis_readonly.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3d_broker_safety.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3e_paper_safety.py -q
```

Targeted backend:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_phase2_api.py -q
```

Frontend:

```powershell
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
cd ..
```

Diff:

```powershell
git diff --check
```

## Safety Contract

| 항목 | 상태 |
|---|---|
| 실제 주문/주문 취소/체결/계좌 이동 | 없음 |
| broker/paper adapter 호출 | 없음 |
| paper order/fill/position mutation | local `paper_orders` submit만 config opt-in + `confirm=true` + idempotency + kill-switch gate 통과 시 허용. paper fill/position mutation 없음 |
| KIS/KRX/yfinance network call | 없음 |
| credential/token 저장 | 없음 |
| earnings/corporate action 실데이터 fetch | 없음 |
| venue/session metadata가 submit 가능 상태로 전환 | 없음 |
| 기존 backtest run/list/detail 응답 필드 제거 | 없음 |
| 기존 portfolio risk 응답 주요 필드 제거 | 없음 |
| 실주문 관련 route 추가 | 없음 |
| walk-forward 추정 수치 생성 | 없음. OOS test window의 실제 local backtest metric만 집계 |
| PBO/Deflated Sharpe 허위 precision 생성 | 없음. 충분 표본에서만 계산하고 부족하면 `not_available_in_current_mvp`, `calculated=false`, `reason` 유지 |
| factor/filter attribution 추정 수치 생성 | 없음. 저장된 ledger/screen join으로 확인되는 값만 계산하고 불완전 join은 `not_available_in_current_mvp`로 표시 |
| report schema 변경 | 없음. 기존 `reports` 테이블 재사용 |
| report notification log secret exposure | 없음. event/log에는 message 본문 대신 hash, 길이, 첨부 metadata만 저장 |
| indicator schema 변경 | 이번 변경 없음. 기존 breadth proxy nullable fields와 availability flags 유지 |
| parameter snapshot schema 변경 | `strategy_parameter_snapshots` 추가. report/backtest/order 실행 테이블과 분리 |
| backtest/report schema 변경 | `backtest_trade_ledger` 유지, 기존 report persistence contract 유지 |
| trade ledger와 주문 테이블 연결 | 없음. validation scaffold에도 `not_connected_to`로 명시 |
| weekly_ohlcv migration 추가 | 없음 |
| `orders_count == 0` 정책 변경 | 없음 |
| paper sync network/fetch | 없음. `POST /api/paper/sync`는 공식 KIS sync contract 확인 전 `KIS_PAPER_SYNC_CONFIRMATION_REQUIRED` no-op |
| paper bot scheduler auto-start | 없음. launcher는 check-only 상태만 표시하며 scheduler/auto-submit은 기본 disabled |
| frontend paper-mode boundary | `/paper`, `/bot`, `/portfolio`, `/reports`, `/settings`는 `모의투자`, `실거래 아님`, `paper only`를 명시하고 backend safety API만 호출 |
| settings secret key-name exposure | 없음. `/api/settings`는 민감 key 이름도 `redacted_field_*`로 익명화 |
| repo secret scan | `tools/secret_scan.py`와 CI backend job에서 실행 |

## 남은 검증

- Phase 0는 DB schema 변경이 없으므로 Alembic pytest를 재실행하지 않았다.
- `goal.md` 기준 Phase 11까지 완료됐다.
- KIS endpoint/path/TR-ID/request field는 공식 문서에서 완전 확인되기 전까지 `확인 필요` 상태로 유지한다.
