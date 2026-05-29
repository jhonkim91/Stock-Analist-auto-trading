# Stock Analyst Auto Trading Memory

## 현재 체크포인트

- [x] 현재 branch: `feature/kis-paper-goal-phases`.
- [x] 기본 실행 주소: backend `http://127.0.0.1:8000`, frontend `http://127.0.0.1:3000/dashboard`.
- [x] backend 8000은 `.env.local`을 process-only로 로드한 uvicorn 프로세스지만, 최신 `KIS_REFRESH_TOKEN` 추가 전 시작돼 `/api/live/status`에는 refresh token blocker가 남아 있다.
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
- 사용자 승인 범위에 따라 `/api/live/status`, `/api/kis/orders`, `/api/kis/orders/status`, `/api/kis/orders/preview`, `/api/kis/orders/submit`, `/api/kis/orders/cancel` disabled scaffold를 추가했다. 모든 응답은 `live_order_created=false`, `network_call_performed=false`, `endpoint_called=false`를 유지한다.
- `/api/kis/broker/*`, `/api/kis/websocket/*`는 계속 미등록 404다.
- `tools/live_phase3_completion_audit.py`는 3단계 완료 조건과 live env Process/User/Machine 설정 여부를 항목별로 판정한다. 현재 record는 `complete=false`, `network_call_performed_by_audit=false`, `live_order_created=false`이며 required live env, token refresh proof, live submit/cancel authority가 미충족이다. `docs/research/live-phase3-process-env-template.ps1`는 placeholder-only process env 템플릿이다.
- `tools/env_file_loader.py`와 `--load-env-local` 옵션을 live token preflight/completion audit에 추가했다. `.env.local`을 수정하지 않고 현재 helper process에만 allowlist key를 로드하며 raw value와 secret-like key name은 record에서 redaction한다.
- 최신 재확인 기준 `KIS_REFRESH_TOKEN`은 `.env.local`과 Windows User env에서 감지된다. helper/process-only 검증에서는 `refresh_token_configured=true`지만, 기존 backend 8000은 재시작 전까지 새 User env를 상속하지 않는다.
- process-only gate dry-run에서는 token refresh control과 kill switch/rate limiter/idempotency/audit/max notional/blacklist/cooldown이 통과했지만, 실제 network call은 실행하지 않았고 live submit/cancel adapter는 계속 disabled다.
- `.env.local`의 `KIS_ACCESS_TOKEN`은 `2026-05-28T12:15:08+00:00` 기준 만료 상태다. 현재 3단계 미충족 항목은 `token_refresh_real_call_proof`, `live_submit_authority_present`, `live_cancel_authority_present`다.
- `tools/live_phase3_completion_audit.py`는 `proof_gap_summary`로 token refresh real-call proof, live submit authority, live cancel authority, adapter disabled 여부를 분리해 기록한다.
- `tools/live_phase3_completion_audit.py --token-refresh-record-path ...`는 별도 승인 후 생성된 redacted token refresh proof record를 읽을 수 있다. 현재 process-only dry-run record는 preview-only라 로드는 되지만 `token_refresh_real_call_proof`를 충족하지 않는다.
- `tools/live_phase3_completion_audit.py --authority-record-path ...`는 별도 승인된 redacted submit/cancel approval record를 읽을 수 있다. 이 record는 증거 요약용이며 live adapter가 disabled인 동안 `live_submit_authority_present`/`live_cancel_authority_present`를 충족하지 않는다.
- live adapter와 public route payload는 `authority_contract.present=true`, `status=disabled_pending_external_approval`, `submit_authority_present=false`, `cancel_authority_present=false`, `network_authority_present=false`를 반환한다.

## 최신 검증 결과

- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_token_diagnostics.py backend/tests/test_env_file_loader.py backend/tests/test_kis_live_token_refresh_preflight_tool.py backend/tests/test_live_phase3_completion_audit.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_live_token_expiry_tests` -> `16 passed`.
- [x] process-only gate dry-run으로 `tools\kis_live_token_refresh_preflight.py --load-env-local --write-record --record-path docs\research\kis-live-token-refresh-process-gate-dry-run.json` 실행 -> `can_refresh=true`, `refresh_token_configured=true`, `execute_requested=false`, `network_call_performed=false`, `live_order_created=false`.
- [x] process-only gate dry-run으로 `tools\live_phase3_completion_audit.py --load-env-local --write-record --record-path docs\research\live-phase3-process-gate-dry-run.json --token-refresh-record-path docs\research\kis-live-token-refresh-process-gate-dry-run.json` 실행 -> proof record 로드, safety/control gate 통과, `proof_gap_summary.safety_controls_blocked=false`, `complete=false`, 미충족 `token_refresh_real_call_proof`, `live_submit_authority_present`, `live_cancel_authority_present`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_live_phase3_completion_audit.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_live_token_proof_record` -> `8 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_live_phase3_completion_audit.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_live_authority_proof_record` -> `10 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_live_canary_preflight.py backend/tests/test_kis_live_token_refresh_preflight_tool.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_live_token_proof_record_canary` -> `8 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_live_phase3_completion_audit.py backend/tests/test_live_canary_preflight.py backend/tests/test_kis_live_token_refresh_preflight_tool.py backend/tests/test_live_public_route_scaffold.py backend/tests/test_no_live_adapter.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_live_authority_record_regression` -> `25 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_live_phase3_completion_audit.py backend/tests/test_live_canary_preflight.py backend/tests/test_kis_live_token_refresh_preflight_tool.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_live_phase3_proof_gap` -> `14 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_live_phase3_completion_audit.py backend/tests/test_live_canary_preflight.py backend/tests/test_no_live_adapter.py::test_service_live_adapter_is_hard_disabled backend/tests/test_no_live_adapter.py::test_broker_service_reports_disabled_live_adapter_without_secrets backend/tests/test_no_live_adapter.py::test_broker_preview_includes_order_specific_live_safety_without_live_route -q -p no:cacheprovider --basetemp $env:TEMP\stock_live_authority_contract_unit` -> `12 passed`.
- [x] stale pytest DB lock 해소 후 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_live_public_route_scaffold.py backend/tests/test_no_live_adapter.py::test_live_execution_routes_are_registered_but_hard_disabled -q -p no:cacheprovider --basetemp $env:TEMP\stock_live_authority_contract_routes` -> `4 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_live_canary_preflight.py backend/tests/test_live_public_route_scaffold.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_final_safety_hardening.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_live_route_canary_contracts` -> `30 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3f_readonly_provider_contract.py::test_read_only_provider_contract_does_not_mutate_execution_tables_or_routes -q -p no:cacheprovider --basetemp $env:TEMP\stock_live_public_route_phase3f_route` -> `1 passed`.
- [x] `.\.venv\Scripts\python.exe -m pytest backend/tests/test_live_phase3_completion_audit.py backend/tests/test_live_canary_preflight.py backend/tests/test_live_public_route_scaffold.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_live_phase3_completion_audit` -> `20 passed`.
- [x] `.\.venv\Scripts\python.exe tools\live_phase3_completion_audit.py --write-record --fail-on-incomplete` -> expected nonzero, `complete=false`, token refresh proof/live submit authority 미충족.
- [x] `.\.venv\Scripts\python.exe tools\live_canary_preflight.py` -> `status=blocked`, public route present, `canary_execution_allowed=false`, `live_order_created=false`, `network_call_performed=false`.
- [x] `.\.venv\Scripts\python.exe tools\kis_live_token_refresh_preflight.py` -> preview-only, `network_call_performed=false`, `live_order_created=false`, refresh token 미설정으로 blocked.
- [x] `GET /api/kis/status` -> `process_access_token_configured=true`, `token_issued=false`, `token_cache_enabled=false`, `token_raw_value_persisted=false`; raw token 미출력/미기록.
- [x] `.\.venv\Scripts\python.exe tools\secret_scan.py` -> `NO_SECRET_FINDINGS`; `git diff --check` -> exit 0, CRLF warning only.
- [x] pytest 병렬 실행은 `backend/data/test_app.db` 잠금으로 실패할 수 있어 순차 실행과 workspace-external basetemp를 사용한다.

## 남은 작업

- [x] 2단계 커밋/푸시는 `5d33512`로 완료했다.
- [ ] 3단계 안전 preflight 체크포인트는 커밋/푸시 가능하지만 단계 완료 커밋은 아래 미충족 항목 해소 전까지 보류한다.
- [ ] 3단계 실계좌 주문 연동은 live token refresh real-call proof와 live submit authority가 구현/검증되기 전까지 완료로 보지 않는다.
- [ ] 3단계 live 주문 실행/취소는 별도 live canary 조건과 사용자 승인, 정규장/소액/단일 주문/즉시 중단 절차 없이는 수행하지 않는다.
