# Phase Plans

이 디렉터리는 단계별 개발 계획과 승인 경계를 관리한다. 현재 기준선은 `MVP v0.24.0 / KIS Paper Broker Phase 6 Report Notification`이다.

## 문서 역할

- `docs/plans/README.md`: 전체 Phase 순서, 현재 상태, 문서 링크를 관리한다.
- 상세 Phase 계획은 필요할 때 `docs/plans/phase-*.md`로 분리한다.
- 현재 프로젝트 상태 요약은 `docs/PROJECT_STATUS.md`와 루트 `Memory.md`에 압축 갱신한다.
- 완료 검증 결과는 `docs/VALIDATION.md`에 최신 대표 결과만 남긴다.

## 현재 기준

| 항목 | 값 |
|---|---|
| 현재 checkpoint | `KIS Paper Broker Phase 6 Report Notification` |
| 현재 구현 완료 | Weekly Review Report, Trade Ledger Foundation, Portfolio Risk Guard v2, breadth/Data Reliability 2, Validation Framework Scaffold, Parameter Snapshot Foundation, Walk-forward/PBO/DSR minimal validation, Factor/Filter Attribution, KIS paper broker Phase 0 audit, Phase 1 notification foundation, Phase 2 broker contract, Phase 3 paper persistence, Phase 4 paper order lifecycle, Phase 5 paper sync views, Phase 6 report notification |
| 최신 backend pytest | Phase 6 report notify `8 passed`, notification API `3 passed`, report quality `4 passed`, full backend `293 passed` |
| 다음 권장 Phase | `KIS paper broker Phase 7 Bot Scheduler` |
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
| Phase 4A/4B | 보류 | 별도 승인 필요 | broker 또는 live gate |

## 다음 후보

1. KIS paper broker Phase 7 Bot Scheduler는 default disabled, `PAPER_BOT_AUTO_SUBMIT=false`, kill-switch 우선 기준으로 진행한다.
2. KIS endpoint/path/TR-ID/request field는 `docs/KIS_PAPER_API_MATRIX.md`의 `확인 필요` 항목을 공식 문서로 먼저 보강한다.
3. Monthly report extension은 daily/weekly 공통 persistence contract 위에 additive로만 검토한다.
4. Strategy hardening 조건을 기본 활성화할지는 별도 백테스트와 샘플 영향 검증 후 결정한다.
5. Phase 4A/4B broker 또는 live gate는 현재 안전 기준과 충돌하므로 별도 승인 없이 구현하지 않는다.

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
- paper order/fill/position/audit mutation 구현 금지.
- KIS token 발급/cache/credential 저장 금지.
- 실제 KIS/KRX/yfinance network call 금지.
- `/api/broker/status`, `/api/broker/orders/preview`, `/api/paper/status`, `/api/paper/orders/preview`, `/paper`는 preview-only/fail-closed 상태로 유지한다.
- `POST /api/paper/orders`, fill simulator, paper mutation은 미구현 404 상태를 유지한다.
