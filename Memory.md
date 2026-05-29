# Stock Analyst Auto Trading Memory

## 현재 체크포인트

- [x] 방향 전환: `Project Reset: Telegram + KIS Paper Trading Bot`.
- [x] 기본 목표 모드: `paper_kis`.
- [x] 실계좌 live 자동매매는 범위 밖이며 `ENABLE_REAL_ORDER=true`는 계속 차단한다.
- [x] 기존 분석/스크리너/백테스트/리포트/포트폴리오 기능은 보존한다.
- [x] paper 주문은 legacy `orders`가 아니라 `paper_orders`를 사용한다.
- [x] secret/token/account/chat id 원문은 코드, 문서, API 응답, 테스트 출력에 남기지 않는다.

## 실행 모드

| 모드 | 상태 | 설명 |
|---|---|---|
| `analysis_only` | 지원 | 로컬 DB 분석, 스크리너, 백테스트, 리포트 |
| `telegram_report` | 진행 중 | Telegram 명령, webhook/polling dispatcher, report scheduler |
| `paper_kis` | 진행 중 | KIS 모의투자 token/quote/order/fill/position mirror, sync worker wrapper |
| `live_disabled` | 유지 | live endpoint/config가 있어도 실계좌 주문 차단 |

## 최근 변경 요약

- `goal.md`와 `docs/PROJECT_STATUS.md`를 Telegram + KIS paper trading bot 기준으로 리셋했다.
- `.env.example`에 실행 모드, KIS token cache, KIS quote, Telegram, paper blacklist/cooldown 변수를 추가했다.
- `.gitignore`에 `.cache/`를 추가해 local token cache가 공개 저장소에 포함되지 않도록 했다.
- `KisTokenManager`에 opt-in file token cache, refresh-token 우선 갱신, cache-hit skeleton을 추가했다.
- `KisMarketQuoteService`를 추가하고 종목 상세 조회가 KIS paper quote를 우선 시도한 뒤 DB 최신 OHLCV로 fallback하도록 했다.
- `/api/stocks/search`, `/api/stocks/{symbol}` route를 추가했다.
- `TelegramBotService`와 `/api/telegram/status`, `/api/telegram/command` route를 추가했다.
- `/api/telegram/webhook`, `/api/telegram/scheduler/status`, `/api/telegram/scheduler/run-once`를 추가했다. Scheduler는 기본 OFF, auto-start false, confirm gate 뒤에서 report summary를 Telegram channel로 dry-run/send한다.
- `/api/telegram/polling/status`, `/api/telegram/polling/run-once`, `backend.app.jobs.telegram_polling_runner`를 추가했다. Polling은 기본 OFF, confirm gate 뒤에서만 `getUpdates`를 1회 조회하며 응답/trace에 token/chat id 원문을 남기지 않는다.
- Telegram command dispatcher는 `/start`, `/help`, `/status`, `/search`, `/report`, `/portfolio`, `/rank`, `/bot`, `/stop`, `/buy`, `/sell`, `/orders`를 지원한다.
- `/bot status|enable|disable|auto|run|stop`은 paper bot process env를 명시 제어한다. enable/disable/auto/run은 `confirm`이 필요하다.
- `/buy`, `/sell`은 `confirm` 또는 `TELEGRAM_PAPER_TRADE_CONFIRM=true` 없이는 preview만 수행한다.
- `/api/paper/sync-worker/status`, `/api/paper/sync-worker/run-once`와 `backend.app.jobs.paper_sync_runner`를 추가했다. Worker는 기본 OFF이며 confirm과 paper network gate가 열릴 때만 `PaperSyncService.sync()`를 호출한다.
- paper risk gate에 `blacklist`, `cooldown_seconds`, `max_open_positions` 검사를 추가했다.
- paper bot 자동매매 기본값을 OFF로 정렬했다: `backend/config/bot.yaml`의 `enabled=false`, `auto_submit=false`, scheduler false.
- Settings runtime env 버튼은 클릭 시 process env에 반영되며 hover/focus에서 한국어 tooltip을 표시한다. `모의 주문 준비`, `자동매매 ON`, `텔레그램 리포트 ON`, `봇/주문 정지` preset은 여러 gate를 한 번에 맞추고 `ENABLE_REAL_ORDER`는 항상 `false`로 강제 적용한다.
- 공식 `koreainvestment/open-trading-api` sample commit `33e0e1e65cd1c8c8b639531483ec0b327087bab1` 기준으로 국내/해외 regular paper endpoint/TR ID와 현재 adapter 상수 일치를 재확인했다.
- paper bot loop는 자동 시작 없이 `PAPER_BOT_MAX_ITERATIONS`, `PAPER_BOT_MAX_ITERATIONS_CAP`, `PAPER_BOT_STOP_FILE` 기준의 bounded runner로만 실행되도록 보강했다.
- Windows sandbox 프로세스 생성 오류는 재부팅 후 재현되지 않았고 PowerShell 기반 backend 검증이 정상 실행됐다.
- 오래된 `disabled` 전제 테스트는 새 `paper_kis` 정책에 맞춰 `paper 기능은 켜짐, 실계좌/live와 무자격 네트워크 주문은 차단` 기준으로 갱신했다.

## 안전 계약

- [x] `paper_kis` 모드에서만 KIS 모의투자 주문/체결/잔고/포지션 갱신을 허용한다.
- [x] live 실계좌 주문, 주문취소, 체결 처리, live fallback은 비활성화한다.
- [x] `kill_switch`, `max_order_notional`, `max_order_qty`, `max_open_positions`, `blacklist`, `cooldown`은 paper 주문 allow/deny gate로 유지한다.
- [x] 모든 주문 생성에는 `idempotency_key`가 필요하다.
- [x] 주문/취소/체결/Telegram command 판단은 audit log에 남긴다.
- [x] KIS token cache는 `KIS_TOKEN_CACHE_ENABLED=true`일 때만 local file에 기록한다.
- [x] 테스트는 fake/mock client 기반이며 실제 KIS live 주문 호출을 수행하지 않는다.

## 최신 검증 결과

- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_project_reset_telegram_kis_bot.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_reset_bot_tests` -> `4 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_token_manager.py backend/tests/test_kis_token_lifecycle_phase1.py backend/tests/test_kis_paper_token_websocket_activation.py backend/tests/test_phase1_read_report_api.py backend/tests/test_paper_order_service.py backend/tests/test_paper_order_api.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_reset_related_tests` -> `18 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_frontend_api_contracts.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_reset_frontend_contract_only` -> `2 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase2_api.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_reset_phase2_only` -> `10 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_bot_scheduler.py backend/tests/test_no_live_trading_regression.py::test_paper_bot_endpoint_does_not_auto_submit_or_start_live_path -q -p no:cacheprovider --basetemp $env:TEMP\stock_reset_bot_default_off` -> `5 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase2_api.py::test_runtime_env_toggle_is_process_only_and_allowlisted backend/tests/test_phase2_api.py::test_runtime_env_toggle_keeps_live_order_locked_false backend/tests/test_phase2_api.py::test_runtime_env_preset_enables_paper_kis_gates_without_live_order backend/tests/test_frontend_api_contracts.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_settings_preset_focused` -> `5 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_telegram_scheduler_and_sync_worker.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_telegram_bot_control_tests` -> `10 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_api_matrix_docs.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_kis_matrix_docs` -> `1 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter_contract.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_kis_matrix_adapter_contract` -> `15 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_bot_scheduler.py backend/tests/test_no_live_trading_regression.py::test_paper_bot_endpoint_does_not_auto_submit_or_start_live_path -q -p no:cacheprovider --basetemp $env:TEMP\stock_paper_bot_bounded_loop_regression` -> `7 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_project_reset_telegram_kis_bot.py backend/tests/test_report_automation.py backend/tests/test_report_notify.py backend/tests/test_paper_sync.py backend/tests/test_paper_portfolio_api.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_telegram_sync_related` -> `18 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider --basetemp $env:TEMP\stock_settings_preset_full_backend` -> `521 passed in 823.78s`.
- [x] `.\.venv\Scripts\python.exe tools\secret_scan.py` -> `NO_SECRET_FINDINGS`.
- [x] `cd frontend; npm.cmd run lint`, `npm.cmd exec tsc -- --noEmit`, `npm.cmd run build` -> 모두 통과.
- [x] launcher 재기동 후 `/api/settings/runtime-env`, `/api/settings/runtime-env/preset`, `/settings` Playwright screenshot smoke 통과.
- [x] `git diff --check` -> exit 0, CRLF warning만 출력.
- [x] PowerShell 실행 채널 재검증 -> backend pytest와 shell command 정상 실행. `CreateProcessAsUserW failed: 1312` 재현 안 됨.

## 남은 작업

- [ ] KIS 국내 정정취소가능주문조회/매도가능수량조회 paper TR ID를 추가 확인한다.

## 주의 사항

- `.env.local`과 Windows User env 값은 출력하지 않는다.
- `.cache/kis/token.json`은 local runtime artifact이며 Git에 포함하지 않는다.
- `KIS_MARKET_QUOTE_ENABLED=false`이면 종목 상세 API는 DB 최신 OHLCV fallback을 정상 경로로 사용한다.
- `PAPER_TRADING_NETWORK_ENABLED=true`여도 token, broker mode, kill switch, idempotency, quote freshness, risk gate가 모두 통과해야 KIS paper adapter 호출이 가능하다.
- `live_disabled` 정책 때문에 live base URL이 설정되어 있어도 실계좌 주문 권한으로 해석하지 않는다.
