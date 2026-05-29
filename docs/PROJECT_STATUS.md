# Project Status

## 현재 기준

| 항목 | 값 |
|---|---|
| 방향 | `Project Reset: Telegram + KIS Paper Trading Bot` |
| 목표 모드 | `paper_kis` |
| 허용 범위 | KIS 모의투자 계좌 기반 주문/체결/잔고/포지션 mirror |
| 차단 범위 | 실계좌 live 주문/취소/체결, live fallback, secret 하드코딩 |
| Backend | FastAPI + SQLite + Alembic |
| Frontend | Next.js App Router |
| 보존 기능 | data, indicator, screener, backtest, report, portfolio, paper state |

## 실행 모드 정책

| 모드 | 상태 | 설명 |
|---|---|---|
| `analysis_only` | 지원 | 기존 로컬 분석/스크리너/백테스트/리포트 |
| `telegram_report` | 진행 중 | Telegram command/webhook/polling dispatcher와 report scheduler 구조 |
| `paper_kis` | 진행 중 | KIS paper token/cache, quote fallback, paper order guard, sync worker wrapper |
| `live_disabled` | 유지 | live endpoint/config가 있어도 실계좌 주문은 비활성 |

## 이번 리셋 반영 항목

- `goal.md`를 Telegram + KIS paper trading bot 기준으로 압축 갱신.
- `.env.example`에 `EXECUTION_MODE`, KIS token cache, KIS quote, Telegram command/report scheduler, paper blacklist/cooldown 변수를 추가.
- KIS paper token manager에 opt-in token cache와 refresh/cache-hit skeleton 추가.
- `/api/stocks/search`, `/api/stocks/{symbol}` 추가.
- `MarketRealtimeService.symbol_detail()`가 KIS paper quote를 우선 시도하고 실패/비활성 시 DB 최신 OHLCV로 fallback.
- 종목 상세 API 응답에 `summary`를 추가해 현재가, 등락률, 시가/고가/저가, 거래량, 거래대금, 주요 지표, 전략 통과 여부를 한 번에 확인할 수 있게 했다.
- `/api/telegram/status`, `/api/telegram/command` 추가.
- `/api/telegram/webhook`, `/api/telegram/scheduler/status`, `/api/telegram/scheduler/run-once` 추가. Scheduler는 기본 OFF, auto-start false, `confirm=true` gate 뒤에서 daily/weekly report summary를 Telegram channel로 dry-run/send한다.
- `/api/telegram/polling/status`, `/api/telegram/polling/run-once`와 `backend.app.jobs.telegram_polling_runner` 추가. Polling은 기본 OFF, auto-start false, `confirm=true`와 env gate 통과 시에만 `getUpdates`를 1회 조회하고 command dispatch를 수행한다.
- Telegram command dispatcher가 `/start`, `/help`, `/status`, `/search`, `/report`, `/portfolio`, `/rank`, `/bot`, `/stop`, `/buy`, `/sell`, `/orders`, `/cancel`을 파싱.
- Telegram `/search 종목코드`는 종목 상세 `summary`를 사용해 가격/거래/지표/통과전략을 한국어 메시지로 요약한다.
- Telegram `/report daily|weekly`와 `/report type=daily|weekly`는 해당 Markdown 리포트를 생성한 뒤 Telegram reply-safe 요약 메시지로 반환한다.
- `/bot status|enable|disable|auto|run|stop`으로 paper bot process env를 명시 제어한다. enable/disable/auto/run은 `confirm`이 필요하고 live 주문은 만들지 않는다.
- Telegram `/buy`는 `amount`/`notional` 금액 기반 수량 계산을 지원하고, `/sell 종목 all`은 현재 `paper_positions` 보유 수량을 사용해 전량 매도 preview/submit을 만든다.
- Telegram `/orders open` 또는 `/orders 미체결`은 paper 미체결 전용 조회를 사용한다.
- Telegram `/cancel paper_order_id confirm`은 paper-only local cancel gate를 사용해 live/network 호출 없이 `paper_orders` 상태와 audit log를 갱신한다.
- `/api/paper/sync-worker/status`, `/api/paper/sync-worker/run-once`, `/api/paper/sync-worker/run-loop` 추가. Worker는 기본 OFF이며 `PAPER_SYNC_WORKER_ENABLED=true`, `confirm=true`, paper network gate 통과 시에만 `PaperSyncService.sync()`를 호출한다. loop는 `PAPER_SYNC_WORKER_MAX_ITERATIONS_CAP` 안에서만 bounded 실행된다.
- `/api/paper/bot/preview`, `/api/paper/bot/run`은 기본 screener 결과 후보 외에 요청의 `watchlist_symbols`로 후보 universe를 제한할 수 있다.
- paper risk gate에 `blacklist`, `cooldown_seconds`, `max_open_positions` 검사를 추가.
- paper risk gate는 시장가 주문의 `max_order_notional`을 DB 최신 종가 기준 추정 주문금액으로 평가한다. 최신 가격이 없으면 금액 한도 우회를 막기 위해 market notional 평가 실패로 차단한다.
- `backend/config/bot.yaml`과 `.env.example`에서 paper bot 자동매매는 기본 OFF(`enabled=false`, `auto_submit=false`, scheduler false)로 정렬.
- Settings runtime env 버튼은 클릭 시 현재 backend 프로세스에 즉시 반영되며, hover/focus 시 한국어 설명 tooltip을 표시한다. 개별 ON/OFF 외에 `모의 주문 준비`, `자동매매 ON`, `텔레그램 리포트 ON`, `봇/주문 정지` preset을 제공한다. runtime env 상태 조회가 늦어져도 preset fallback 버튼은 렌더링되어 같은 preset API를 호출한다. `모의 주문 준비`와 `자동매매 ON`은 KIS token issue/cache, KIS quote, paper sync worker bounded loop gate도 함께 맞추고, `ENABLE_REAL_ORDER`는 클릭해도 `false`로만 강제 적용된다.
- 공식 `koreainvestment/open-trading-api` sample commit `33e0e1e65cd1c8c8b639531483ec0b327087bab1` 기준으로 KIS paper domestic/overseas regular endpoint/TR ID를 재확인하고 stale Phase 0 matrix 문서를 갱신했다.
- 국내 정정취소가능주문조회/매도가능수량조회는 공식 샘플에서 real `TTTC0084R`/`TTTC8408R` only로 확인되어, paper TR 확인 전 구현 보류와 fail-closed 정책을 유지한다.
- `backend.app.jobs.paper_bot_runner` loop는 자동 시작 없이 `PAPER_BOT_MAX_ITERATIONS`, `PAPER_BOT_MAX_ITERATIONS_CAP`, `PAPER_BOT_STOP_FILE` 기준의 bounded runner로만 동작한다.
- `/api/paper/risk/exit-check`는 stop-loss, trailing stop에 더해 fast/slow 이동평균 하향 교차를 paper-only local exit trigger로 처리한다.
- `.cache/`를 `.gitignore`에 추가해 local token cache가 공개 저장소에 포함되지 않도록 차단.

## 보존한 기존 기능

- 기존 OHLCV seed/import, indicator recompute, screener, strategy registry, backtest, daily/weekly report, portfolio risk, paper order/fill/position 테이블은 유지한다.
- legacy `orders` table은 계속 live/mock broker 주문 저장소로 사용하지 않는다.
- paper 주문 상태는 `paper_orders`, 체결은 `paper_fills`, 포지션은 `paper_positions`, 판단 기록은 `paper_audit_events`에 기록한다.

## 현재 API 표면

| API | 상태 |
|---|---|
| `GET /api/stocks/search` | 종목 검색 alias |
| `GET /api/stocks/{symbol}` | KIS quote 우선, DB fallback 종목 상세와 `summary` |
| `GET /api/telegram/status` | Telegram token/chat id redacted status |
| `POST /api/telegram/command` | Telegram command local dispatcher. `/search`는 종목 상세 요약, `/orders open|미체결`은 미체결 조회, `/report daily|weekly`는 Markdown report 생성 후 요약 응답, `/cancel`은 paper-only 주문 취소 |
| `POST /api/telegram/webhook` | Telegram webhook update command dispatcher |
| `GET /api/telegram/polling/status` | Telegram getUpdates polling status |
| `POST /api/telegram/polling/run-once` | Confirm-gated getUpdates command polling |
| `GET /api/telegram/scheduler/status` | Telegram report scheduler status |
| `POST /api/telegram/scheduler/run-once` | Confirm-gated daily/weekly report Telegram summary |
| `POST /api/paper/orders/preview` | paper risk gate preview |
| `POST /api/paper/orders` / `POST /api/paper/orders/submit` | confirm + idempotency 기반 지정가/시장가 paper order create |
| `GET /api/paper/orders/open` | paper 미체결 주문 조회 |
| `GET /api/paper/sync-worker/status` | paper sync worker status |
| `POST /api/paper/sync-worker/run-once` | confirm-gated KIS paper sync worker wrapper |
| `POST /api/paper/sync-worker/run-loop` | confirm-gated bounded KIS paper sync worker loop |
| `GET /api/settings/runtime-env` | process-only runtime gate/preset status |
| `POST /api/settings/runtime-env/toggle` | allowlist boolean env gate 1개 적용 |
| `POST /api/settings/runtime-env/preset` | paper_kis/Telegram/bot gate 묶음 적용, live lock false 유지 |

## 최신 검증

| 명령 | 결과 |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_project_reset_telegram_kis_bot.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_reset_bot_tests` | `4 passed` |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_token_manager.py backend/tests/test_kis_token_lifecycle_phase1.py backend/tests/test_kis_paper_token_websocket_activation.py backend/tests/test_phase1_read_report_api.py backend/tests/test_paper_order_service.py backend/tests/test_paper_order_api.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_reset_related_tests` | `18 passed` |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_frontend_api_contracts.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_reset_frontend_contract_only` | `2 passed` |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase2_api.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_reset_phase2_only` | `10 passed` |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_bot_scheduler.py backend/tests/test_no_live_trading_regression.py::test_paper_bot_endpoint_does_not_auto_submit_or_start_live_path -q -p no:cacheprovider --basetemp $env:TEMP\stock_reset_bot_default_off` | `5 passed` |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase2_api.py::test_runtime_env_toggle_is_process_only_and_allowlisted backend/tests/test_phase2_api.py::test_runtime_env_toggle_keeps_live_order_locked_false backend/tests/test_phase2_api.py::test_runtime_env_preset_enables_paper_kis_gates_without_live_order backend/tests/test_frontend_api_contracts.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_settings_preset_focused` | `5 passed` |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_telegram_scheduler_and_sync_worker.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_telegram_bot_control_tests` | `10 passed` |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_api_matrix_docs.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_kis_matrix_docs` | `1 passed` |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_bot_scheduler.py backend/tests/test_no_live_trading_regression.py::test_paper_bot_endpoint_does_not_auto_submit_or_start_live_path -q -p no:cacheprovider --basetemp $env:TEMP\stock_paper_bot_bounded_loop_regression` | `7 passed` |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_phase2_engine.py backend/tests/test_no_live_trading_regression.py::test_paper_bot_endpoint_does_not_auto_submit_or_start_live_path -q -p no:cacheprovider --basetemp $env:TEMP\stock_paper_ma_cross_exit_regression` | `6 passed` |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_project_reset_telegram_kis_bot.py backend/tests/test_telegram_scheduler_and_sync_worker.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_telegram_sell_all_related` | `15 passed` |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_bot_executor_phase5.py backend/tests/test_paper_bot_scheduler.py backend/tests/test_project_reset_telegram_kis_bot.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_paper_bot_watchlist_related` | `18 passed` |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_project_reset_telegram_kis_bot.py backend/tests/test_telegram_scheduler_and_sync_worker.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_telegram_report_command` | `16 passed` |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_project_reset_telegram_kis_bot.py backend/tests/test_telegram_scheduler_and_sync_worker.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_telegram_cancel_related` | `17 passed` |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_telegram_scheduler_and_sync_worker.py backend/tests/test_paper_sync.py backend/tests/test_paper_sync_service.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_sync_worker_loop_api` | `19 passed` |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase2_api.py::test_runtime_env_preset_enables_paper_kis_gates_without_live_order backend/tests/test_telegram_scheduler_and_sync_worker.py::test_paper_sync_worker_loop_api_is_confirm_gated_and_bounded -q -p no:cacheprovider --basetemp $env:TEMP\stock_settings_sync_worker_preset` | `2 passed` |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase2_api.py::test_runtime_env_preset_enables_paper_kis_gates_without_live_order -q -p no:cacheprovider --basetemp $env:TEMP\stock_settings_kis_token_quote_preset` | `1 passed` |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_project_reset_telegram_kis_bot.py backend/tests/test_frontend_api_contracts.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_search_settings_contract` | `9 passed` |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_order_service.py backend/tests/test_project_reset_telegram_kis_bot.py backend/tests/test_kis_paper_adapter_contract.py::test_kis_paper_adapter_submit_cancel_query_sync_with_mock_http backend/tests/test_kis_paper_adapter_contract.py::test_kis_paper_adapter_maps_domestic_market_order_to_market_division -q -p no:cacheprovider --basetemp $env:TEMP\stock_market_order_open_orders` | `16 passed in 45.58s` |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_project_reset_telegram_kis_bot.py backend/tests/test_report_automation.py backend/tests/test_report_notify.py backend/tests/test_paper_sync.py backend/tests/test_paper_portfolio_api.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_telegram_sync_related` | `18 passed` |
| `.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider --basetemp $env:TEMP\stock_reset_full_after_market_orders` | `534 passed in 477.90s` |
| `.\.venv\Scripts\python.exe tools\secret_scan.py` | `NO_SECRET_FINDINGS` |
| `cd frontend; npm.cmd run lint` | exit 0 |
| `cd frontend; npm.cmd exec tsc -- --noEmit` | exit 0 |
| `cd frontend; npm.cmd run build` | Next.js build 성공 |
| `git diff --check` | exit 0, CRLF warning만 출력 |

## 남은 작업

- KIS 국내 정정취소가능주문조회/매도가능수량조회 paper TR ID는 공식 샘플에는 없으므로 KIS 포털/운영 문서 또는 paper host 기준 추가 확인 필요.
- Telegram polling `getUpdates` runner는 run-once/CLI 구조까지 추가됨. 장시간 운영 loop는 bounded loop 옵션만 제공하며 auto-start는 false.
- paper fill/order/account sync worker wrapper는 추가됨. 실제 조회는 기존 `PaperSyncService`의 paper network gate를 통과한 경우에만 수행.
