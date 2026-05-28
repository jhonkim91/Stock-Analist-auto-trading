# Stock Analyst Auto Trading Memory

## 현재 체크포인트

- [x] 현재 branch: `feature/kis-paper-goal-phases`.
- [x] 현재 작업: `docs/goal.md` 기준 KIS 모의투자 전용 자동매매 봇 Phase 1-6 구현 완료.
- [x] 기본 실행 주소: backend `http://127.0.0.1:8000`, frontend `http://127.0.0.1:3000/dashboard`.
- [x] 로컬 launcher는 검증 전 중지 상태로 유지했다. 필요 시 `py launcher.py run --no-browser` 후 `py launcher.py check`로 확인한다.
- [x] 현재 셸의 `python --version`은 `Python`만 출력하고 exit 1이다. 검증은 `.\.venv\Scripts\python.exe`로 수행한다.
- [x] `alembic` 실행 파일은 PATH에 없으므로 `.\.venv\Scripts\python.exe -m alembic ...`를 사용한다.

## KIS Paper Auto Bot Phase 1-6 상태

- [x] `docs/goal.md`: 목표, 범위, 안전조건, Phase 1-6, 완료기준 문서화.
- [x] `docs/RUNBOOK_PAPER_TRADING.md`: env 설정, DB migration, backend 실행, worker 상태, dry-run, paper run, kill switch, 장애 복구 절차 문서화.
- [x] Phase 1-4: KIS paper 설정/token/http client, adapter facade, account snapshot/API, realtime stale quote gate 구현.
- [x] Phase 5: `backend/app/services/paper_bot_executor.py`, `/api/paper/bot/preview`, `/api/paper/bot/run`, `/api/paper/bot/runs/{run_id}` 추가.
- [x] Phase 5 후보 필터: `passed=true`, 유효한 `risk_metadata`, 통과한 `data_quality_flags`만 사용.
- [x] Phase 5 sizing/gate: risk per trade, max order notional, max positions, cash, exposure, stop/risk per share, kill switch, session, stale quote, duplicate order, daily loss, concentration, cash/notional limit 반영.
- [x] Phase 6: `/api/paper/dashboard`, `PaperOperationalMetricsService`, daily/weekly report `## Paper Trading` section 추가.
- [x] Alembic head: `d1e2f3a4b5c6_extend_paper_bot_run_contract`.
- [x] 신규/확장 table 계약: `paper_account_snapshots`, `paper_bot_runs.trade_date/dry_run/preview_count/skipped_count/rejected_count/request_json/result_json`.

## 안전 계약

- [x] 실전투자, live trading, 실계좌 주문/취소/체결, 신용/공매도/파생상품 구현 없음.
- [x] 기본값은 disabled/fail-closed/dry-run.
- [x] KIS paper submit은 `KIS_ENV=paper`, `PAPER_TRADING_ENABLED=true`, `PAPER_BOT_CONFIRM=true`, kill switch off, `confirm=true`, idempotency, risk gate, no-live 조건이 필요하다.
- [x] `dry_run=true` bot run은 주문 row를 생성하지 않고 run/decision preview만 저장한다.
- [x] `ENABLE_REAL_ORDER=true`, live base URL, live fallback은 차단.
- [x] `orders_count == 0` 정책 유지. paper order는 `paper_orders`에만 저장.
- [x] secret, token, account number 원문은 API 응답/DB/log/docs에 저장하지 않는다.
- [x] CI/pytest는 mock/fake client 기반. 실제 KIS 호출은 runbook 수동 절차만 사용.

## 최신 검증 결과

- [x] Backend full: `.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider --basetemp $env:TEMP\stock_kis_paper_phase56_pytest_final2` -> `416 passed in 310.50s`.
- [x] Phase 5/6 targeted: `test_paper_bot_executor_phase5.py`, `test_paper_dashboard_report_phase6.py`, migration tests -> `12 passed`.
- [x] Paper regression: bot/order/report/no-live subset -> `27 passed`.
- [x] Alembic: `.\.venv\Scripts\python.exe -m alembic upgrade head` -> `c0d1e2f3a4b5 -> d1e2f3a4b5c6` 적용.
- [x] Secret scan: `.\.venv\Scripts\python.exe tools\secret_scan.py` -> `NO_SECRET_FINDINGS`.
- [x] Diff check: `git diff --check` -> exit 0, CRLF warning only.
- [x] Frontend 영향 없음. frontend lint/typecheck/build는 이번 변경에서 생략.

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite + Alembic, sample seed, CSV import, KIS read-only foundation, broker safety scaffold, paper trading lifecycle, KIS paper adapter mock, report notification/automation, paper bot scheduler, Phase 5 bot executor, realtime quote worker skeleton.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/sessions`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/bot`, `/settings`.
- Notification: `backend/config/notifications.yaml` 기본값은 disabled/dry-run.
- Paper/KIS execution: fail-closed 기본값. live broker, live websocket, 실계좌 주문/취소/체결은 활성화하지 않는다.

## 최근 변경 요약

- `PaperBotExecutor`, bot preview/run/get-run API, request/result persistence 추가.
- `PaperDashboardService`, `PaperOperationalMetricsService`, realtime reconnect metric 상태 추가.
- report daily/weekly에 `## Paper Trading` section 추가.
- `paper_bot_runs` additive migration과 migration 테스트 갱신.
- README, `docs/PROJECT_STATUS.md`, `docs/VALIDATION.md`, `docs/DB_MIGRATION.md`, runbook 갱신.

## 남은 작업

- [ ] 실제 KIS paper 호출은 `docs/RUNBOOK_PAPER_TRADING.md` 절차와 현재 프로세스 env에서만 수행한다.
- [ ] 로컬 서버가 필요하면 `py launcher.py run --no-browser` 후 `py launcher.py check`로 확인한다.
- [ ] `python` launcher 문제가 계속 필요하면 Windows PATH/App execution alias를 별도 환경 작업으로 정리한다.
