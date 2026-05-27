# Validation

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
| frontend paper-mode boundary | `/paper`, `/portfolio`, `/reports`, `/settings`는 `모의투자`, `실거래 아님`, `paper only`를 명시하고 backend safety API만 호출 |
| settings secret key-name exposure | 없음. `/api/settings`는 민감 key 이름도 `redacted_field_*`로 익명화 |
| repo secret scan | `tools/secret_scan.py`와 CI backend job에서 실행 |

## 남은 검증

- Phase 0는 DB schema 변경이 없으므로 Alembic pytest를 재실행하지 않았다.
- `goal.md` 기준 Phase 9까지 완료됐다.
- KIS endpoint/path/TR-ID/request field는 공식 문서에서 완전 확인되기 전까지 `확인 필요` 상태로 유지한다.
