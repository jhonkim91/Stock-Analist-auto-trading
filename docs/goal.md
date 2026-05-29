# KIS 모의투자 전용 자동매매 봇 목표

## 핵심 요약

현재 MVP는 분석, 스크리닝, 백테스트, 리포트, paper preview 중심이다. 이번 목표는 `jhonkim91/Stock-Analist-auto-trading` 저장소를 KIS 모의투자 전용 자동매매 봇으로 확장하되, 기본값은 계속 disabled/fail-closed/dry-run으로 유지하는 것이다.

## 목표

- KIS paper/sandbox 환경에서만 시세 수신, 후보 선정, 리스크 검증, 주문 제출, 주문/체결/포지션/계좌 동기화, 감사 로그, 운영 상태 조회를 수행한다.
- 실전투자 주문, 실계좌 주문취소, 신용, 공매도, 파생상품, live fallback은 구현하지 않는다.
- CI와 일반 테스트는 mock/fake client만 사용하고 실제 KIS 호출은 runbook의 수동 절차로 분리한다.

## 범위

| 구분 | 포함 | 제외 |
|---|---|---|
| Phase 1 | KIS paper 설정, env 계약, token lifecycle metadata/issue gate, `KisHttpClient`, KIS 상태 API 보강 | 기본 자동 token 발급, raw token 저장 |
| Phase 2 | KIS paper broker adapter, DTO, mock submit/cancel/status/account 조회, capability 표시 | live adapter, paper-to-live fallback |
| Phase 3 | `paper_orders`, `paper_fills`, `paper_positions`, `paper_account_snapshots`, `paper_audit_events`, idempotency, paper API alias | 기존 API key 제거, legacy `orders` 생성 |
| Phase 4 | realtime worker skeleton, polling quote cache, heartbeat/stale 상태, `/api/paper/realtime/status`, stale quote 신규 주문 차단 | 실전 WebSocket 운영, live 체결 통보 |
| Phase 5 | bot executor, 후보 선정, sizing, 주문 전 risk gate, dry-run/run 분리, run/decision 저장 | 실전 주문, 임의 후보 생성 |
| Phase 6 | paper dashboard, paper trading report section, Telegram `/report daily|weekly` 요약, 운영 metrics, runbook/README/status/validation 갱신 | 운영 알림 자동 발송, live monitoring |

## 안전 조건

- `KIS_ENV=paper`, `PAPER_TRADING_ENABLED=true`, `PAPER_BOT_CONFIRM=true`, kill switch off 상태가 모두 충족될 때만 KIS 모의투자 주문 경로가 열릴 수 있다.
- 기본 설정은 항상 `enabled=false`, `network_enabled=false`, `preview_only=true`, `kill_switch_enabled=true`다.
- `ENABLE_REAL_ORDER=true`, live base URL, live fallback, live adapter submit은 항상 차단한다.
- secret, token, account number 원문은 로그, API 응답, DB에 저장하지 않는다.
- 기존 API 응답 key는 제거하지 않고 additive 필드와 route만 추가한다.
- 실제 KIS 네트워크 호출은 테스트에서 금지하고 수동 runbook으로만 수행한다.

## Phase

### Phase 1: 설정, Secret, Token

- `paper.yaml`, `broker.yaml`, `data_sources.yaml`에 KIS paper 전용 설정을 추가한다.
- `.env.example`에 `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO`, `KIS_PRODUCT_CODE`, `KIS_ENV=paper`, `PAPER_BOT_CONFIRM=false`를 정의한다.
- KIS token lifecycle은 발급/갱신 요청 객체와 만료 metadata를 지원하되, raw token은 메모리 metadata fingerprint만 남긴다.
- HTTP 호출은 `KisHttpClient`를 통해 timeout, retry, rate-limit, transport/domain error mapping을 수행한다.
- `/api/kis/status`, `/api/kis/config`, `/api/kis/config/validate`는 secret 미노출 상태를 유지한다.

### Phase 2: KIS Paper Broker Adapter

- `backend/app/services/brokers/kis_paper_adapter.py`를 추가해 서비스 계층 명명 계약을 제공한다.
- account summary, cash available, positions, submit order, cancel order, order status를 paper-only adapter capability로 노출한다.
- KIS paper endpoint, headers, transaction id, base URL은 상수/설정으로 분리한다.
- DTO는 `PaperAccountSnapshot`, `PaperOrderSubmitRequest`, `PaperOrderSubmitResult`, `PaperExecution`을 추가한다.
- KIS/HTTP 오류는 domain error payload로 변환한다.

### Phase 3: 주문, 체결, 포지션 저장 계약

- Alembic migration으로 `paper_account_snapshots`를 추가하고 기존 paper persistence와 분리한다.
- 주문 상태는 `pending_submitted`, `submitted`, `partially_filled`, `filled`, `cancelled`, `rejected`, `expired`, `failed`를 표준 상태로 둔다.
- API는 기존 route를 유지하면서 `POST /api/paper/orders`, `POST /api/paper/orders/{order_id}/cancel`, `GET /api/paper/orders/{order_id}`, `GET /api/paper/account`를 추가한다.
- Telegram `/cancel paper_order_id confirm`은 paper-only local cancel gate를 재사용한다.
- `idempotency_key`는 submit/cancel mutation에서 필수로 유지한다.
- 주문 수량, 금액, 전략, 세션, 리스크 판단 근거, adapter 응답 요약은 raw secret 없이 저장한다.
- 성공 mutation은 audit event를 저장하고, 거부 mutation은 side effect 없이 reason code를 반환한다.

### Phase 4: 실시간 시세/체결 Worker

- `backend/app/workers/realtime_market_worker.py`를 추가한다.
- 관심종목 universe는 최근 screener 통과 종목, 보유 paper position, open paper order 기준으로 구성한다.
- KIS WebSocket 운영 전까지 polling 기반 latest quote cache와 heartbeat 상태를 제공한다.
- 체결/포지션/계좌 동기화는 기존 `PaperSyncService`를 통해 mock/fake adapter 기반으로 검증한다.
- `POST /api/paper/sync-worker/run-loop`는 confirm gate와 `PAPER_SYNC_WORKER_MAX_ITERATIONS_CAP` 안에서만 bounded 반복 동기화를 수행한다.
- stale quote threshold를 초과하면 신규 주문은 `PAPER_REALTIME_STALE_QUOTE`로 차단한다.

### Phase 5: Bot Executor/Risk Gate

- `backend/app/services/paper_bot_executor.py`를 추가한다.
- API는 `POST /api/paper/bot/preview`, `POST /api/paper/bot/run`, `GET /api/paper/bot/runs/{run_id}`를 제공한다.
- 입력은 `trade_date`, `strategies`, `watchlist_symbols`, `max_candidates`, `dry_run`이며 기존 `auto_submit` key는 호환만 유지한다.
- 후보는 `passed=true`, 유효한 `risk_metadata`, 통과한 `data_quality_flags`를 가진 screener 결과만 사용한다.
- sizing은 risk per trade, max order notional, max positions, cash available, current exposure, stop price, risk per share를 반영한다.
- 주문 전 gate는 kill switch, market session, stale quote, duplicate order, daily loss limit, symbol/sector/strategy concentration, cash/order notional limit를 확인한다.
- dry-run은 주문 row를 만들지 않고 `paper_bot_runs`, `paper_bot_decisions`에 preview 결과만 저장한다.

### Phase 6: 모니터링/리포트/문서

- `GET /api/paper/dashboard`는 account, positions, open orders, fills, realized/unrealized PnL, risk, worker status, metrics를 반환한다.
- daily/weekly report에는 `## Paper Trading` section을 추가해 주문 수, 체결 수, reject reason, realized/unrealized PnL, stale data event, risk gate 차단 내역을 표시한다.
- Telegram `/report daily|weekly`는 해당 Markdown report를 생성하고 reply-safe 요약 메시지로 반환한다.
- 운영 metrics는 token refresh, websocket reconnect, order submit latency, reject count, sync lag를 secret 없이 집계한다.
- `docs/RUNBOOK_PAPER_TRADING.md`, `README.md`, `docs/PROJECT_STATUS.md`, `docs/VALIDATION.md`, `Memory.md`를 Phase 5/6 기준으로 갱신한다.

## 완료 기준

- `docs/goal.md`와 `docs/RUNBOOK_PAPER_TRADING.md`가 존재한다.
- 기본 설정에서는 모든 주문 기능이 disabled/fail-closed다.
- paper env와 confirm 조건이 모두 충족될 때만 KIS 모의투자 adapter mock 주문이 가능하다.
- 주문, 체결, 포지션, 계좌 snapshot, audit 로그가 paper 전용 테이블에 저장된다.
- bot preview와 bot run은 분리되어 있고 auto-submit은 별도 gate 뒤에 있다.
- bot run 결과는 submitted/skipped/rejected와 reason code로 저장 및 조회된다.
- paper dashboard와 daily/weekly report paper section이 제공된다.
- 실전투자 경로는 계속 차단된다.
- `python -m pytest backend/tests -q`, `alembic upgrade head`, `git diff --check` 검증 결과를 문서화한다.
