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
- `KisTokenManager`에 opt-in file token cache, issue, refresh-token 우선 갱신, cache-hit ensure 경로를 추가했고 `/api/kis/token/ensure`를 노출했다.
- `KisMarketQuoteService`를 추가하고 종목 상세 조회가 KIS paper quote를 우선 시도한 뒤 DB 최신 OHLCV로 fallback하도록 했다.
- `/api/stocks/search`, `/api/stocks/{symbol}` route를 추가했고, 상세 응답 `summary`에 현재가, 등락률, 시가/고가/저가, 거래량, 거래대금, 주요 지표, 전략 통과 요약을 담는다.
- 종목 상세는 KIS paper quote 성공 경로와 DB fallback 경로 모두 테스트로 고정했다.
- `TelegramBotService`와 `/api/telegram/status`, `/api/telegram/command` route를 추가했다.
- `/api/telegram/webhook`, `/api/telegram/scheduler/status`, `/api/telegram/scheduler/run-once`를 추가했다. Scheduler는 기본 OFF, auto-start false, confirm gate 뒤에서 report summary를 Telegram channel로 dry-run/send한다.
- `/api/telegram/polling/status`, `/api/telegram/polling/run-once`, `backend.app.jobs.telegram_polling_runner`를 추가했다. Polling은 기본 OFF, confirm gate 뒤에서만 `getUpdates`를 1회 조회하며 응답/trace에 token/chat id 원문을 남기지 않는다.
- Telegram command dispatcher는 `/start`, `/help`, `/status`, `/search`, `/report`, `/portfolio`, `/rank`, `/bot`, `/stop`, `/buy`, `/sell`, `/orders`, `/cancel`을 지원한다.
- `/search 종목코드`는 종목 상세 `summary`를 사용해 가격/거래/지표/통과전략을 한국어 메시지로 요약한다.
- `/report daily`, `/report weekly`, `/report type=daily|weekly`는 해당 Markdown 리포트를 생성한 뒤 Telegram reply-safe 요약 메시지로 반환한다.
- `/bot status|enable|disable|auto|run|stop`은 paper bot process env를 명시 제어한다. enable/disable/auto/run은 `confirm`이 필요하다.
- `/buy`, `/sell`은 `confirm` 또는 `TELEGRAM_PAPER_TRADE_CONFIRM=true` 없이는 preview만 수행한다.
- 가격을 생략한 `/buy`/`/sell`은 시장가 paper order로 저장되며, 시장가 주문도 DB 최신 종가 기준 추정 주문금액으로 `max_order_notional` gate를 통과해야 한다.
- `/sell 종목 all` 또는 `qty=all`은 현재 `paper_positions` 보유 수량을 전량 매도 수량으로 사용한다.
- `/cancel paper_order_id confirm`은 paper-only local cancel gate를 사용하며 live/network 호출 없이 `paper_orders` 상태와 audit log만 갱신한다.
- `/orders open` 또는 `/orders 미체결`은 `GET /api/paper/orders/open`과 같은 미체결 전용 상태 집합을 사용한다.
- `/api/paper/sync-worker/status`, `/api/paper/sync-worker/run-once`, `/api/paper/sync-worker/run-loop`와 `backend.app.jobs.paper_sync_runner`를 추가했다. Worker는 기본 OFF이며 confirm과 paper network gate가 열릴 때만 `PaperSyncService.sync()`를 호출한다. loop는 `PAPER_SYNC_WORKER_MAX_ITERATIONS_CAP` 안에서만 bounded 실행된다.
- paper risk gate에 `blacklist`, `cooldown_seconds`, `max_open_positions` 검사를 추가했다.
- `/api/paper/bot/preview`, `/api/paper/bot/run`은 요청의 `watchlist_symbols`로 저장된 passed screener 후보 universe를 제한할 수 있다.
- paper bot 자동매매 기본값을 OFF로 정렬했다: `backend/config/bot.yaml`의 `enabled=false`, `auto_submit=false`, scheduler false.
- Settings runtime env 버튼은 클릭 시 process env에 반영되며 hover/focus에서 한국어 tooltip을 표시한다. `모의 주문 준비`, `자동매매 ON`, `텔레그램 리포트 ON`, `봇/주문 정지` preset과 주요 toggle은 runtime env 조회가 늦어져도 fallback 버튼으로 렌더링되고 같은 API를 호출한다. `ENABLE_REAL_ORDER`는 항상 `false`로 강제 적용한다. `모의 주문 준비`와 `자동매매 ON`은 KIS token issue/cache, KIS quote, paper sync worker bounded loop gate도 함께 맞춘다.
- 공식 `koreainvestment/open-trading-api` sample commit `33e0e1e65cd1c8c8b639531483ec0b327087bab1` 기준으로 국내/해외 regular paper endpoint/TR ID와 현재 adapter 상수 일치를 재확인했다.
- 국내 정정취소가능주문조회/매도가능수량조회는 공식 샘플에서 real `TTTC0084R`/`TTTC8408R` only로 확인되어 paper TR 확인 전 구현 보류로 유지한다.
- paper bot loop는 자동 시작 없이 `PAPER_BOT_MAX_ITERATIONS`, `PAPER_BOT_MAX_ITERATIONS_CAP`, `PAPER_BOT_STOP_FILE` 기준의 bounded runner로만 실행되도록 보강했다.
- `/api/paper/risk/exit-check`는 stop-loss/trailing stop 외에 이동평균 하향 교차를 `ma_cross` local sell order/fill로 처리한다.
- Windows sandbox 프로세스 생성 오류는 재부팅 후 재현되지 않았고 PowerShell 기반 backend 검증이 정상 실행됐다.
- 오래된 `disabled` 전제 테스트는 새 `paper_kis` 정책에 맞춰 `paper 기능은 켜짐, 실계좌/live와 무자격 네트워크 주문은 차단` 기준으로 갱신했다.
- 오래된 문서/서비스 주석의 `paper mutation 금지`, `paper sync no-op` 표현은 새 `paper_kis` 정책에 맞춰 정리했다. paper writes는 confirm/idempotency/kill-switch/risk/sync gate 뒤에서만 허용되고 live mutation은 계속 차단된다.

## 안전 계약

- [x] `paper_kis` 모드에서만 KIS 모의투자 주문/체결/잔고/포지션 갱신을 허용한다.
- [x] live 실계좌 주문, 주문취소, 체결 처리, live fallback은 비활성화한다.
- [x] `kill_switch`, `max_order_notional`, `max_order_qty`, `max_open_positions`, `blacklist`, `cooldown`은 paper 주문 allow/deny gate로 유지한다.
- [x] 모든 주문 생성에는 `idempotency_key`가 필요하다.
- [x] 주문/취소/체결/Telegram command 판단은 audit log에 남긴다.
- [x] KIS token cache는 `KIS_TOKEN_CACHE_ENABLED=true`일 때만 local file에 기록한다.
- [x] 테스트는 fake/mock client 기반이며 실제 KIS live 주문 호출을 수행하지 않는다.

## 최신 검증 결과

- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_token_manager.py backend/tests/test_kis_token_manager.py backend/tests/test_kis_token_lifecycle_phase1.py backend/tests/test_kis_paper_token_websocket_activation.py backend/tests/test_frontend_api_contracts.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_token_settings_focused` -> `14 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_project_reset_telegram_kis_bot.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_project_reset_after_quote_priority` -> `9 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_project_reset_telegram_kis_bot.py::test_stock_detail_api_prefers_kis_quote_when_available backend/tests/test_project_reset_telegram_kis_bot.py::test_stock_detail_api_uses_db_fallback_without_kis_network -q -p no:cacheprovider --basetemp $env:TEMP\stock_detail_kis_quote_priority` -> `2 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_paper_sync.py backend/tests/test_paper_sync_service.py backend/tests/test_project_reset_telegram_kis_bot.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_paper_sync_docs_alignment` -> `32 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider --basetemp $env:TEMP\stock_reset_full_after_token_settings` -> `536 passed`.
- [x] `cd frontend; npm.cmd run lint`, `npm.cmd exec tsc -- --noEmit`, `npm.cmd run build` -> 모두 통과.
- [x] `.\.venv\Scripts\python.exe tools\secret_scan.py` -> `NO_SECRET_FINDINGS`.
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
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_phase2_engine.py backend/tests/test_no_live_trading_regression.py::test_paper_bot_endpoint_does_not_auto_submit_or_start_live_path -q -p no:cacheprovider --basetemp $env:TEMP\stock_paper_ma_cross_exit_regression` -> `6 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_project_reset_telegram_kis_bot.py backend/tests/test_telegram_scheduler_and_sync_worker.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_telegram_sell_all_related` -> `15 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_bot_executor_phase5.py backend/tests/test_paper_bot_scheduler.py backend/tests/test_project_reset_telegram_kis_bot.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_paper_bot_watchlist_related` -> `18 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_project_reset_telegram_kis_bot.py backend/tests/test_telegram_scheduler_and_sync_worker.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_telegram_report_command` -> `16 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_project_reset_telegram_kis_bot.py backend/tests/test_telegram_scheduler_and_sync_worker.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_telegram_cancel_related` -> `17 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_telegram_scheduler_and_sync_worker.py backend/tests/test_paper_sync.py backend/tests/test_paper_sync_service.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_sync_worker_loop_api` -> `19 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase2_api.py::test_runtime_env_preset_enables_paper_kis_gates_without_live_order backend/tests/test_telegram_scheduler_and_sync_worker.py::test_paper_sync_worker_loop_api_is_confirm_gated_and_bounded -q -p no:cacheprovider --basetemp $env:TEMP\stock_settings_sync_worker_preset` -> `2 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase2_api.py::test_runtime_env_preset_enables_paper_kis_gates_without_live_order -q -p no:cacheprovider --basetemp $env:TEMP\stock_settings_kis_token_quote_preset` -> `1 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_project_reset_telegram_kis_bot.py backend/tests/test_frontend_api_contracts.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_search_settings_contract` -> `9 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_order_service.py backend/tests/test_project_reset_telegram_kis_bot.py backend/tests/test_kis_paper_adapter_contract.py::test_kis_paper_adapter_submit_cancel_query_sync_with_mock_http backend/tests/test_kis_paper_adapter_contract.py::test_kis_paper_adapter_maps_domestic_market_order_to_market_division -q -p no:cacheprovider --basetemp $env:TEMP\stock_market_order_open_orders` -> `16 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_project_reset_telegram_kis_bot.py backend/tests/test_report_automation.py backend/tests/test_report_notify.py backend/tests/test_paper_sync.py backend/tests/test_paper_portfolio_api.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_telegram_sync_related` -> `18 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider --basetemp $env:TEMP\stock_reset_full_after_market_orders` -> `534 passed in 477.90s`.
- [x] `.\.venv\Scripts\python.exe tools\secret_scan.py` -> `NO_SECRET_FINDINGS`.
- [x] `cd frontend; npm.cmd run lint`, `npm.cmd exec tsc -- --noEmit`, `npm.cmd run build` -> 모두 통과.
- [x] launcher 재기동 후 `/api/settings/runtime-env`, `/api/settings/runtime-env/preset`, `/settings` Playwright screenshot smoke 통과.
- [x] `git diff --check` -> exit 0, CRLF warning만 출력.
- [x] PowerShell 실행 채널 재검증 -> backend pytest와 shell command 정상 실행. `CreateProcessAsUserW failed: 1312` 재현 안 됨.

## 남은 작업

- [ ] KIS 국내 정정취소가능주문조회/매도가능수량조회 paper TR ID를 KIS 포털/운영 문서 또는 paper host 기준으로 추가 확인한다.

## 주의 사항

- `.env.local`과 Windows User env 값은 출력하지 않는다.
- `.cache/kis/token.json`은 local runtime artifact이며 Git에 포함하지 않는다.
- `KIS_MARKET_QUOTE_ENABLED=false`이면 종목 상세 API는 DB 최신 OHLCV fallback을 정상 경로로 사용한다.
- `PAPER_TRADING_NETWORK_ENABLED=true`여도 token, broker mode, kill switch, idempotency, quote freshness, risk gate가 모두 통과해야 KIS paper adapter 호출이 가능하다.
- `live_disabled` 정책 때문에 live base URL이 설정되어 있어도 실계좌 주문 권한으로 해석하지 않는다.
