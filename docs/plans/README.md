# Phase Plans

이 디렉터리는 단계별 개발 계획과 승인 경계를 관리한다. 현재 기준선은 `Project Reset: Telegram + KIS Paper Trading Bot`이다.

## 문서 역할

- `docs/plans/README.md`: 전체 Phase 순서, 현재 상태, 문서 링크를 관리한다.
- 상세 Phase 계획은 필요할 때 `docs/plans/phase-*.md`로 분리한다.
- 현재 프로젝트 상태 요약은 `docs/PROJECT_STATUS.md`와 루트 `Memory.md`에 압축 갱신한다.
- 완료 검증 결과는 `docs/VALIDATION.md`에 최신 대표 결과만 남긴다.

## 현재 기준

| 항목 | 값 |
|---|---|
| 현재 checkpoint | `Telegram + KIS Paper Trading Bot reset` |
| 현재 구현 완료 | 기존 분석/스크리너/백테스트/리포트/포트폴리오 보존, Telegram command/webhook/polling/report scheduler, `/bot` 명시 제어, KIS token cache skeleton, stock detail KIS quote fallback, paper order guard, paper sync worker wrapper, Settings one-click runtime presets, KIS paper official sample matrix 재확인, paper bot bounded runner |
| 최신 backend pytest | full backend `521 passed in 823.78s`, bounded bot regression `7 passed`, Telegram polling/bot-control/scheduler/sync worker targeted suites, Settings preset focused suite, KIS matrix docs suite 통과 |
| 다음 권장 Phase | KIS 포털/운영 문서 또는 paper host 기준 국내 정정취소가능/매도가능수량조회 paper TR ID 확인 |
| 상태 요약 문서 | `docs/PROJECT_STATUS.md` |
| 상세 검증 문서 | `docs/VALIDATION.md` |
| 프로젝트 메모리 | `Memory.md` |

## Phase Index

| Phase | 상태 | 문서 | 전달 범위 |
|---|---|---|---|
| Phase 1 | 완료 | `README.md`, `docs/VALIDATION.md` | Backend Core MVP |
| Phase 2 | 완료 | `README.md`, `docs/VALIDATION.md` | MVP Web Flow |
| Phase 3A | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md` | CSV validate/confirm import |
| Phase 3B | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md` | provider-neutral external daily OHLCV |
| Phase 3C | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md` | KIS read-only foundation |
| Phase 3D | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md` | Broker safety scaffold |
| Phase 3E-1 | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md` | Paper preview safety scaffold |
| Phase 3F | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md` | Read-only data reliability |
| Phase 3G | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md` | Backtest execution realism and liquidity model |
| Phase 3H | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md` | Strategy explanation contract and registry |
| Phase C-1 | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md` | `momentum_rank` available-only strategy |
| Phase C-2 | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md` | `relative_strength_leader` available-only strategy |
| Phase C-3 | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md` | `new_high_breakout` default and available strategy |
| Phase C-4 | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md` | `darvas_box` available-only strategy |
| Phase C-5 | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md` | `stage_analysis_weekly` available-only strategy |
| Phase C-6 | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md` | `pullback_20ema` default and available strategy |
| Phase C hardening | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md`, `Memory.md` | 9개 전략 hardening foundation, `data_quality_flags`, `risk_metadata` |
| Phase 3I | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md` | Weekly Review Report |
| Trade Ledger Foundation | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md`, `Memory.md` | `backtest_trade_ledger`, saved trade 조회, weekly realized PnL/win rate/failed trades review |
| Portfolio Risk Guard v2 | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md`, `Memory.md` | synthetic gross/sector/symbol/strategy exposure, daily loss budget, gap risk preview |
| Breadth/Data Reliability 2 | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md`, `Memory.md` | incremental indicator recompute, breadth-aware regime, earnings/corporate-action as-of, adjusted/raw price contract |
| Validation Framework Scaffold | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md`, `Memory.md` | validation service split, baseline comparator, JSON report writer, walk-forward/PBO/DSR placeholders |
| Parameter Snapshot Foundation | 완료 | `docs/PROJECT_STATUS.md`, `docs/VALIDATION.md`, `Memory.md` | strategy config snapshot 저장/조회/diff, weekly parameter drift check |
| Walk-forward/PBO/DSR Minimal Validation | 완료 | `docs/PROJECT_STATUS.md`, `docs/VALIDATION.md`, `Memory.md` | OOS summary, PBO/DSR fail-closed calculation |
| Factor/Filter Attribution Minimal Integration | 완료 | `docs/PROJECT_STATUS.md`, `docs/VALIDATION.md`, `Memory.md` | ledger/screen join 기반 realized PnL attribution과 filter failure counts |
| KIS Paper Broker Phase 0 | 완료 | `docs/plans/phase-paper-broker-baseline-audit.md`, `docs/KIS_PAPER_API_MATRIX.md`, `docs/VALIDATION.md`, `Memory.md` | baseline audit, stale docs reconciliation, official-doc confirmation matrix |
| KIS Paper Broker Phase 1 | 완료 | `backend/config/notifications.yaml`, `/api/notifications/status`, `/api/notifications/test`, `docs/VALIDATION.md`, `Memory.md` | disabled/mock notification abstraction, Discord/Telegram adapter skeleton, settings redacted summary |
| KIS Paper Broker Phase 2 | 완료 | `backend/app/brokers/base.py`, `backend/app/brokers/kis_paper.py`, `backend/app/brokers/kis_live.py`, `backend/app/services/token_manager.py` | adapter contract, confirmation-required KIS paper skeleton, disabled live placeholder, in-memory token metadata |
| KIS Paper Broker Phase 3 | 완료 | `backend/alembic/versions/a8b9c0d1e2f3_paper_trading_persistence.py`, `backend/app/models/tables.py` | additive paper persistence schema, broker audit, notification outbox, token status metadata |
| KIS Paper Broker Phase 4 | 완료 | `backend/app/services/paper_order_service.py`, `/api/paper/orders/submit`, `/api/paper/orders/cancel`, `/api/paper/orders` | local paper order lifecycle, confirm/idempotency/kill-switch gate, cancel disabled pending official KIS payload |
| KIS Paper Broker Phase 5 | 완료 | `backend/app/services/paper_sync_service.py`, `/api/paper/fills`, `/api/paper/positions`, `/api/paper/portfolio`, `/api/paper/sync` | paper_* table views, fail-closed idempotent sync no-op, synthetic positions separation |
| KIS Paper Broker Phase 6 | 완료 | `backend/app/services/report_notification_service.py`, `/api/reports/{report_id}/notify` | channel-safe summary/file notification, sanitized delivery logs, failure isolation |
| KIS Paper Broker Phase 7 | 완료 | `backend/app/services/paper_bot_service.py`, `backend/app/jobs/paper_bot_runner.py`, `/api/paper/bot/status`, `/api/paper/bot/run` | disabled scheduler, safe once/loop runner, explicit auto-submit gate |
| KIS Paper Broker Phase 8 | 완료 | `frontend/app/paper/page.tsx`, `frontend/components/paper-mode-banner.tsx`, `backend/tests/test_frontend_api_contracts.py` | paper-only UI boundary, backend-gated submit/cancel/sync/notify controls, contract tests |
| KIS Paper Broker Phase 9 | 완료 | `tools/secret_scan.py`, `backend/tests/test_secret_redaction.py`, `docs/PAPER_TRADING_OPERATION.md`, `.github/workflows/ci.yml` | full validation, CI secret scan, key-name redaction hardening, operation guide |
| KIS Paper Balance Inquiry | 완료 | `backend/app/services/kis_paper_balance.py`, `backend/tests/test_kis_paper_balance.py`, `docs/VALIDATION.md` | `/api/paper/portfolio` 조건부 read-only KIS balance 조회, disabled/mock local fallback |
| Project Reset: Telegram + KIS Paper Bot | 진행 중 | `goal.md`, `backend/app/api/telegram.py`, `backend/app/api/settings.py`, `backend/app/jobs/paper_bot_runner.py`, `backend/app/services/telegram_polling_service.py`, `backend/app/services/telegram_report_scheduler_service.py`, `backend/app/services/paper_sync_worker_service.py`, `backend/app/services/settings_service.py`, `docs/PROJECT_STATUS.md` | 실행 모드 재정의, Telegram webhook/polling/report scheduler, `/bot` 명시 제어, paper sync worker wrapper, Settings one-click presets, bounded paper bot runner, live disabled 유지 |
| Phase 4A/4B | 보류 | 별도 승인 필요 | broker 또는 live gate |

## 다음 후보

1. 국내 정정취소가능주문조회/매도가능수량조회 paper TR ID는 공식 샘플에 없고 real `TTTC0084R`/`TTTC8408R` only이므로 KIS 포털/운영 문서 또는 paper host 검증 전 구현하지 않는다.
2. Phase 4A/4B live gate는 현재 목표 밖이므로 별도 승인 없이 구현하지 않는다.

## Report 기준

| Report | 상태 | 생성 API | 기준 데이터 | unavailable 정책 |
|---|---|---|---|---|
| Daily Market Report | 완료 | `POST /api/reports/daily` | 단일 `screen_results.trade_date` | 기존 sample/mock-only 표기 유지 |
| Weekly Strategy Review | 완료 | `POST /api/reports/weekly` | 최근 available `screen_results.trade_date` 최대 5개 + `backtest_trade_ledger.exit_date` | ledger가 없거나 미계약 항목은 `not_available_in_current_mvp` |

## Backtest Ledger 기준

| 항목 | 기준 |
|---|---|
| 저장 테이블 | `backtest_trade_ledger` |
| 생성 경로 | 저장형 `POST /api/backtest/run` |
| 조회 경로 | `GET /api/backtest/runs/{run_id}`, `GET /api/backtest/runs/{run_id}/trades` |
| weekly 계산 가능 | realized trade count, realized PnL, realized return, win rate, average holding days, setup별 trade hit rate, failed trade count/reason |
| 여전히 unavailable | realized drawdown/exposure/open position risk, regime segment return, realized factor/filter PnL attribution, MAE/MFE, parameter drift |
| 안전 경계 | 실제 주문, paper order, broker/KIS route와 연결하지 않는다 |

## 고정 안전 경계

- 실주문, 주문 취소, 체결, 계좌 이동, websocket, live broker 구현 금지.
- KIS/broker paper order, paper fill/position simulator mutation 구현 금지. local `paper_orders`는 confirm/idempotency/kill-switch gate 통과 시에만 허용한다.
- KIS token 발급/cache/credential 저장 금지.
- 실제 KIS/KRX/yfinance network call 금지.
- `/api/broker/status`, `/api/broker/orders/preview`, `/api/paper/status`, `/api/paper/orders/preview`, `/paper`는 paper-only/fail-closed 경계를 명시한다.
- `POST /api/paper/orders`, fill simulator, KIS/live order mutation은 미구현 404 또는 disabled 상태를 유지한다.
