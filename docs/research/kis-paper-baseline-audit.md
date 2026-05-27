# KIS Paper Goal Phase 0 Baseline Audit

## 핵심 요약

이 문서는 루트 `goal.md`의 `Phase 0: Latest Baseline Audit` 산출물이다. 코드 실행 경로를 변경하지 않고, `main` ref와 현재 작업 브랜치의 차이를 분리해 KIS paper 작업의 기준선을 확정한다.

| 항목 | 확인 결과 |
|---|---|
| Phase 범위 | Phase 0 문서 감사만 수행 |
| 기준 main ref | `bfcb1691e56dbdbbfc18b043bc65ec447acafa3e` |
| 현재 작업 브랜치 | `feature/kis-paper-goal-phases` |
| 현재 작업 HEAD | `ffd7f52a4745df2b99c8dae694796eab5e8f024d` |
| 시작 시 dirty file | `goal.md` |
| 코드 변경 | 없음 |
| DB schema 변경 | 없음 |
| submit/cancel 구현 | 없음 |
| `.env` / `.env.local` 변경 | 없음 |

## Phase 0 체크리스트

- [x] `goal.md`의 현재 Phase 목적, 수정 대상, 새 파일, 금지 사항, 구현 조건을 확인했다.
- [x] 기준선 확인은 `git show main:<path>`와 현재 checkout read-only 조회로 수행했다.
- [x] 현재 route, table, service, test, UI 기준선을 문서화했다.
- [x] no-live-trading, preview-only, fail-closed 불변식을 기록했다.
- [x] submit/cancel logic을 추가하지 않았다.
- [x] DB schema, migration, model을 변경하지 않았다.
- [x] secret 원문을 코드, 문서, 로그, DB, API 응답에 저장하지 않았다.

## main 기준선

`main` ref는 현재 작업 브랜치보다 이전 기준선이다. Phase 0 감사는 main tree를 직접 checkout하지 않고 `git show main:<path>`로 확인했다.

### 등록 router

`main`의 `backend/app/main.py`는 다음 router만 등록한다.

| 영역 | router |
|---|---|
| data | `backend.app.api.data` |
| indicators | `backend.app.api.indicators` |
| market | `backend.app.api.market` |
| instruments | `backend.app.api.instruments` |
| screener | `backend.app.api.screener` |
| reports | `backend.app.api.reports` |
| backtest | `backend.app.api.backtest` |
| portfolio | `backend.app.api.portfolio` |
| broker | `backend.app.api.broker` |
| paper | `backend.app.api.paper` |
| kis | `backend.app.api.kis` |
| settings | `backend.app.api.settings` |

`main`에는 `/api/notifications/*`, `/api/paper/orders/submit`, `/api/paper/orders/cancel`, `/api/paper/sync`, `/api/paper/bot/*`, `/api/reports/{report_id}/notify`가 없다.

### KIS / broker / paper route

| route | main 기준 동작 |
|---|---|
| `GET /api/kis/status` | KIS read-only status, secret 원문 미노출 |
| `GET /api/kis/config` | KIS read-only config, env configured boolean만 노출 |
| `POST /api/kis/config/validate` | config format validation, `network_call_performed=false`, `token_issued=false` |
| `GET /api/broker/status` | broker safety scaffold status |
| `POST /api/broker/orders/preview` | deny/fail-closed broker preview |
| `GET /api/paper/status` | paper safety scaffold status |
| `POST /api/paper/orders/preview` | deny/fail-closed paper preview |

### DB table 기준선

`main`의 SQLAlchemy model에는 일반 MVP table과 일부 paper safety shell table이 이미 존재한다.

| 분류 | table |
|---|---|
| market/data | `symbol_master`, `daily_ohlcv`, `data_sources`, `import_runs`, `data_quality_checks`, `external_symbol_mapping`, `corporate_actions`, `trading_calendar`, `index_ohlcv`, `sector_ohlcv`, `fundamentals_pti`, `earnings_events`, `indicator_snapshot`, `screen_results` |
| report/backtest | `reports`, `backtest_runs`, `strategy_parameter_snapshots`, `backtest_trade_ledger` |
| synthetic/existing execution shell | `positions`, `orders`, `paper_orders`, `paper_fills`, `paper_positions`, `paper_audit_events` |

`main`에는 `paper_portfolio_snapshots`, `broker_audit_events`, `notification_events`, `notification_delivery_logs`, `kis_token_status_metadata`가 없다. KIS paper order/fill/portfolio sync를 위한 dedicated 확장 table은 Phase 0 범위에서 추가하지 않는다.

### service 기준선

| service | main 기준 상태 |
|---|---|
| `KisReadOnlyService` | read-only status/config/validate만 제공. token cache, broker, websocket disabled |
| `BrokerService` | `can_submit=false`, `preview_only=true`, `live_trading_enabled=false`, `network_call_performed=false` |
| `PaperTradingService` | `can_create=false`, `can_simulate_fills=false`, `preview_only=true`, `paper_order_supported=false` |
| `TokenLifecycleService` | disabled metadata only. raw token persistence 없음 |
| `BrokerAuditService` | secret/account/token key redaction helper |

`main`에는 `BrokerAdapter`, `KisPaperBrokerAdapter`, `KisLiveBrokerAdapter`, notification service, report notification service, paper bot service, KIS paper balance client가 없다.

### test 기준선

`main`에서 KIS/broker/paper 안전 기준을 직접 다루는 test는 다음 범위다.

| test file | 역할 |
|---|---|
| `backend/tests/test_phase3c_kis_readonly.py` | KIS read-only foundation, no token/network mutation |
| `backend/tests/test_phase3d_broker_safety.py` | broker safety scaffold, no live order route |
| `backend/tests/test_phase3e_paper_safety.py` | paper safety scaffold, no paper mutation route |

Phase 0는 새 backend test를 추가하지 않는다.

### frontend 기준선

`main`의 `/paper` UI는 `/api/paper/status`와 `/api/paper/orders/preview`만 호출한다. 화면은 safety flag, preview result, counts, reason code를 보여주며 submit/cancel/sync/bot/notification control은 없다.

## 현재 작업 브랜치 차이

현재 checkout은 `feature/kis-paper-goal-phases`이며 `main` 이후 KIS paper broker Phase 0-9와 KIS paper balance read-only 작업이 이미 누적돼 있다. 따라서 현재 파일 시스템에는 main에 없는 route, service, table, frontend control이 존재한다.

Phase 0는 이 차이를 되돌리거나 확장하지 않는다. 이후 구현 Phase를 판단할 때는 사용자가 지정한 기준인 `goal.md`와 main ref를 우선해야 하며, 현재 브랜치의 선행 구현을 main 기준 완료로 추정하지 않는다.

## no-live-trading 불변식

- live trading route를 만들지 않는다.
- live adapter가 있더라도 disabled placeholder 외 동작을 허용하지 않는다.
- paper mode에서 live mode fallback을 허용하지 않는다.
- KIS AppKey/AppSecret/access token/refresh token/account number, Telegram token/chat_id, Discord webhook URL 원문을 저장하거나 출력하지 않는다.
- `.env`, `.env.local`, `frontend/.env.local`은 생성하거나 수정하지 않는다.
- kill switch가 blocking이면 submit path는 어떤 주문도 허용하지 않아야 한다.
- bot auto submit은 명시 enable flag 없이는 허용하지 않는다.
- 공식 확인이 없는 KIS endpoint/path/TR-ID/request field는 `확인 필요` 또는 disabled/fail-closed 상태로 남긴다.

## 문서 충돌 정리

| 항목 | 판정 |
|---|---|
| `goal.md` current baseline | main의 route 기준과 대체로 일치하지만, paper table 설명은 실제 main에 존재하는 `paper_orders`, `paper_fills`, `paper_positions`, `paper_audit_events`를 구분해 읽어야 한다. |
| `docs/plans/phase-paper-broker-baseline-audit.md` | 이전 Phase 0 산출물이며 main `bfcb169...` 기준 설명으로 유효하다. 새 goal Phase 0 산출물은 이 문서와 별도로 `docs/research/kis-paper-baseline-audit.md`에 둔다. |
| 현재 `docs/PROJECT_STATUS.md` / `Memory.md` | 현재 feature branch 상태를 설명한다. main 기준선과 혼동하지 않도록 본 감사 문서에서 분리했다. |

## Phase 1 연결

`Phase 1: KIS Paper API Confirmation Matrix`는 `docs/research/kis-paper-api-confirmation-matrix.md`에 기록했다. 확인된 항목과 `확인 필요` 항목을 분리했으며, production code, DB schema, API route, `.env` 계열 파일은 변경하지 않았다.

## 검증 계획

Phase 0의 `goal.md` 검증 명령은 다음이다.

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
cd ..
git diff --check
```

검증 결과는 `docs/VALIDATION.md`와 `Memory.md`에 최신 대표 결과로 기록한다.
