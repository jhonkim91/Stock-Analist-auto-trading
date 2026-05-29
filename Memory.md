# Stock Analyst Auto Trading Memory

## 현재 체크포인트

- [x] 현재 branch: `feature/kis-paper-goal-phases`.
- [x] 기본 실행 주소: backend `http://127.0.0.1:8000`, frontend `http://127.0.0.1:3000/dashboard`.
- [x] 현재 로컬 앱은 `py launcher.py run --no-browser` 후 backend 8000/frontend 3000이 launcher-owned 상태다.
- [x] `python --version`은 이 환경에서 불안정할 수 있으므로 검증은 `.\.venv\Scripts\python.exe`를 우선 사용한다.
- [x] `alembic` 실행 파일은 PATH에 없으므로 `.\.venv\Scripts\python.exe -m alembic ...`를 사용한다.

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite + Alembic, sample seed, CSV import, KIS read-only foundation, broker safety scaffold, paper trading lifecycle, KIS paper adapter, token issue route, paper WebSocket approval route, report notification/automation, paper bot scheduler/executor, realtime quote worker skeleton.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/market`, `/data`, `/sessions`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/bot`, `/settings`.
- Paper/KIS: KIS paper token/WebSocket approval, US WebSocket subscribe ACK, 미국 정규장 AAPL 1주 paper submit/follow-up sync completion을 redacted record와 DB로 확인했다. premarket/daytime/extended는 paper host 거부 확인 후 adapter/network 전 차단한다.
- Runtime controls: Settings 화면에 process-only runtime env ON/OFF 버튼이 있다. `.env.local`/config 파일을 수정하지 않고 현재 backend 프로세스 env만 바꾸며 `ENABLE_REAL_ORDER`는 UI/API에서 true로 켤 수 없다.
- Notification/Report: 기본은 manual/dry-run 중심이다. Telegram/notification payload와 logs에는 secret/account/token 원문을 남기지 않는다.

## 안전 계약

- [x] 실전투자, live trading, 실계좌 주문/취소/체결, 신용/공매도/파생상품 구현 없음.
- [x] 기본값은 fail-closed이며 live fallback은 차단.
- [x] KIS paper submit은 `KIS_ENV=paper`, `PAPER_TRADING_ENABLED=true`, `PAPER_BOT_CONFIRM=true`, kill switch off, `confirm=true`, idempotency, risk gate, no-live 조건이 필요하다.
- [x] `dry_run=true` bot run은 주문 row를 생성하지 않고 run/decision preview만 저장한다.
- [x] token/approval key는 process env에만 설치 가능하고 API/문서/record에는 raw value를 남기지 않는다.
- [x] `ENABLE_REAL_ORDER=true`, live base URL, live fallback은 차단.
- [x] `orders_count == 0` 정책 유지. paper order는 `paper_orders`에만 저장한다.
- [x] secret, token, account number 원문은 API 응답/DB/log/docs에 저장하지 않는다.
- [x] CI/pytest는 mock/fake client 기반이다. 실제 KIS 호출은 runbook 수동 절차만 사용한다.

## 최근 변경 요약

- Goal Read/Report Phase 1 완료 후 커밋 `ff1408d`로 `origin/feature/kis-paper-goal-phases`에 푸시했다.
- 모의투자 주문 엔진 2단계 완료 후 커밋 `5d33512`로 `origin/feature/kis-paper-goal-phases`에 푸시했다.
- 2단계 구현 범위: local paper cancel, `GET /api/paper/orders/open`, `POST /api/paper/fill-simulator/run`, `POST /api/paper/risk/exit-check`를 추가했다.
- `PaperFillSimulatorService`가 confirm/idempotency/simulator/no-live gate 통과 시 `paper_fills` 생성, `paper_positions` 갱신, stop-loss/trailing-stop local exit fill을 처리한다.
- `PaperOrderService.cancel_order`는 broker order가 아닌 local paper order를 network call 없이 `cancelled`로 전환하고, broker order cancel은 기존 KIS paper network gate를 유지한다.
- `PaperTradingService.sync()`가 test/runtime patch config_dir를 `PaperSyncService`에 전달하도록 수정했다.
- `README.md`, `docs/VALIDATION.md`, `goal.md`, `Memory.md`를 2단계 모의투자 주문 엔진 상태로 갱신했다.
- 실계좌 주문 연동 3단계는 `LiveOrderSafetyService`, `/api/broker/status.live_order_safety`, `/api/broker/orders/preview.live_order_safety`, `tools/live_canary_preflight.py`에 kill switch/rate limiter/idempotency/audit/max notional/blacklist/cooldown/token refresh preflight를 추가했지만 아직 완료가 아니다.
- `LiveRateLimiter`, `LiveIdempotencyGuard`, `LiveCooldownGuard`, `LiveOrderAuditService`를 추가해 rate 소진, duplicate idempotency, cooldown, redacted audit event를 실제 live 주문 없이 검증한다.
- `KisLiveTokenRefreshService`는 live token refresh를 별도 gated scaffold로 추가했지만 기본 network disabled이며 real KIS refresh proof는 없다.
- `KisLiveBrokerAdapter`는 submit/cancel safety boundary를 반환하지만 `enabled=false`, `can_submit=false`, `can_cancel=false`, `network_enabled=false`로 고정한다.
- `LiveCanaryGovernanceService`는 reviewer/env isolation/rollback runbook proof를 redacted payload로 검사한다.
- `tools/kis_live_token_refresh_preflight.py`는 live token refresh real-call proof용 CLI이며 기본은 preview-only/no-network다.

## 최신 검증 결과

- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_phase2_engine.py backend/tests/test_paper_order_service.py backend/tests/test_paper_order_api.py backend/tests/test_paper_submit_cancel_api.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase2_engine_tests` -> `13 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_sync_service.py backend/tests/test_paper_dashboard_report_phase6.py backend/tests/test_e2e_paper_mock_flow.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase2_paper_sync_tests` -> `8 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_no_live_trading_regression.py backend/tests/test_api_smoke.py backend/tests/test_frontend_api_contracts.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase2_safety_tests` -> `11 passed`.
- [x] `cd frontend; npm.cmd run lint` -> 통과.
- [x] `cd frontend; npm.cmd run build`; `npm.cmd exec tsc -- --noEmit` -> 통과.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_live_order_safety_service.py backend/tests/test_live_canary_preflight.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_api_smoke.py backend/tests/test_frontend_api_contracts.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase3_commit_safety` -> `23 passed`.
- [x] `.\.venv\Scripts\python.exe tools\live_canary_preflight.py` -> `status=blocked`, `canary_execution_allowed=false`, `live_order_created=false`, `network_call_performed=false`.
- [x] `.\.venv\Scripts\python.exe tools\secret_scan.py` -> `NO_SECRET_FINDINGS`; `git diff --check` -> exit 0, CRLF warning only.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_live_order_safety_service.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase3_controls_unit` -> `8 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_live_order_safety_service.py backend/tests/test_live_canary_preflight.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_phase3d_broker_safety.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase3_controls_regression` -> `28 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_live_order_safety_service.py backend/tests/test_live_canary_preflight.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_api_smoke.py backend/tests/test_frontend_api_contracts.py backend/tests/test_phase3d_broker_safety.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase3_controls_full` -> `32 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_live_token_refresh_service.py backend/tests/test_live_order_safety_service.py backend/tests/test_live_canary_preflight.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_api_smoke.py backend/tests/test_frontend_api_contracts.py backend/tests/test_phase3d_broker_safety.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase3_live_token_controls` -> `35 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_no_live_adapter.py backend/tests/test_live_canary_preflight.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase3_live_adapter_unit` -> `7 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_live_token_refresh_service.py backend/tests/test_live_order_safety_service.py backend/tests/test_live_canary_preflight.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_api_smoke.py backend/tests/test_frontend_api_contracts.py backend/tests/test_phase3d_broker_safety.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase3_live_adapter_controls` -> `35 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_live_canary_governance_service.py backend/tests/test_live_canary_preflight.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase3_governance_unit` -> `5 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_live_canary_governance_service.py backend/tests/test_kis_live_token_refresh_service.py backend/tests/test_live_order_safety_service.py backend/tests/test_live_canary_preflight.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_api_smoke.py backend/tests/test_frontend_api_contracts.py backend/tests/test_phase3d_broker_safety.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase3_governance_controls` -> `37 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_live_token_refresh_preflight_tool.py backend/tests/test_live_canary_governance_service.py backend/tests/test_kis_live_token_refresh_service.py backend/tests/test_live_order_safety_service.py backend/tests/test_live_canary_preflight.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_api_smoke.py backend/tests/test_frontend_api_contracts.py backend/tests/test_phase3d_broker_safety.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase3_token_proof_cli` -> `39 passed`.
- [x] pytest 병렬 실행은 `backend/data/test_app.db` 잠금으로 실패할 수 있어 순차 실행과 workspace-external basetemp를 사용한다.

## 남은 작업

- [x] 2단계 커밋/푸시는 `5d33512`로 완료했다.
- [ ] 3단계 안전 preflight 체크포인트는 커밋/푸시 가능하지만 단계 완료 커밋은 아래 미충족 항목 해소 전까지 보류한다.
- [ ] 3단계 실계좌 주문 연동은 live token refresh real-call proof와 live public route가 구현/검증되기 전까지 완료로 보지 않는다.
- [ ] 3단계 live 주문 실행/취소는 별도 live canary 조건과 사용자 승인, 정규장/소액/단일 주문/즉시 중단 절차 없이는 수행하지 않는다.
