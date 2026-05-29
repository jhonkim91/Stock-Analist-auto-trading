# goal.md

## Project Goal

본 프로젝트의 목표는 한국투자증권 KIS Open API 기반의 자동 주식 분석, 모의투자, 거래 알림, 리포트 자동화 시스템을 단계적으로 구현하는 것이다.

최종 추진 순서는 다음과 같다.

1. KIS 모의투자 API 기반 paper 운영 안정화
2. Telegram 거래 및 리포트 알림
3. 일간/주간 리포트 자동화
4. 모의투자 운영 루프와 장애 대응 절차 확립
5. 실전매매 준비도 설계
6. 별도 승인형 live canary

현재 프로젝트는 실거래 자동매매 엔진이 아니라 분석, 스크리닝, 백테스트, 리포트, paper-only 운영 보조 MVP다. 실계좌 주문, 실계좌 주문취소, WebSocket 체결, live fallback은 최종 목표로만 기록하고, 실제 구현이나 실행은 별도 명시 승인 전까지 금지한다.

## Current Baseline

| 항목 | 현재 기준 |
|---|---|
| Version | `MVP v0.26.0` |
| Branch | `feature/kis-paper-goal-phases` |
| Baseline HEAD | `251db45` |
| 상태 | KIS paper token/WebSocket approval network 성공, US WebSocket subscribe ACK 성공, 미국 정규장 AAPL 1주 paper submit/follow-up sync completion 확인, premarket/daytime/extended는 paper host 거부 확인 후 API 호출 전 차단, paper/bot/report/notification 수동 기능 활성화, live/real order/fallback/scheduler loop 차단 |
| Backend | FastAPI + SQLite + Alembic |
| Frontend | Next.js App Router |
| 최신 backend full pytest | `416 passed` |
| 최신 secret scan | `NO_SECRET_FINDINGS` |
| Telegram | notifier/template/outbox 존재, 기본값 disabled + dry-run |
| KIS paper adapter | submit/cancel/list/query-balance/sync mock HTTP 검증 완료 |
| Phase 12C | KIS paper submit endpoint 도달 후 `40580000` / `모의투자 장종료 입니다.`로 중단 |
| Live trading | disabled, no route, no fallback, no WebSocket execution |

권위 있는 상태 확인 순서는 `docs/PROJECT_STATUS.md`, `docs/VALIDATION.md`, `Memory.md`, `README.md` 순서다. `검토결과2.md`는 개발 방향 입력으로 사용하되, 최신 구현 상태와 충돌하면 상태 문서를 우선한다.

## Official Source Targets

KIS endpoint, TR ID, request field, response field, Telegram message contract는 구현 전에 아래 기준으로 재확인한다.

| 영역 | 기준 |
|---|---|
| KIS Developers | `https://apiportal.koreainvestment.com/intro` |
| KIS official samples | `https://github.com/koreainvestment` |
| Telegram Bot API | `https://core.telegram.org/bots/api` |

공식 문서나 공식 샘플로 확인되지 않은 KIS paper capability는 `확인 필요`로 남긴다. 추정 endpoint, 추정 TR ID, 추정 request field는 production code에 넣지 않는다.

## Non-Negotiable Safety Contract

### Live 금지

아래 작업은 별도 명시 승인 전까지 구현하거나 실행하지 않는다.

- 실계좌 주문 전송
- 실계좌 주문 취소
- 실계좌 정정 주문
- 실계좌 잔고 기반 자동 주문
- 실계좌 체결 처리
- live broker fallback
- WebSocket 기반 주문/체결 실행
- `ENABLE_LIVE_SUBMIT=true` 기본값 설정
- `KIS_BROKER_KILL_SWITCH=0` 기본값 설정

### Secret 보호

아래 값은 코드, 문서, 로그, DB, API 응답, 테스트 출력, notification payload에 원문으로 남기지 않는다.

- KIS app key
- KIS app secret
- access token
- refresh token
- approval key
- hashkey raw payload 중 민감 필드
- 계좌번호 원문
- Telegram bot token
- Telegram chat id
- Discord webhook URL
- HTTP raw authorization header

### Fail-Closed 원칙

```text
unknown state = deny
missing config = deny
network error = deny
risk check failed = deny
kill switch on = deny
unconfirmed endpoint = deny
unconfirmed TR ID = deny
live fallback requested = deny
```

### 변경 원칙

- 기존 API key를 제거하지 않고 additive로 확장한다.
- paper-only table과 legacy/synthetic `positions`를 broker truth로 섞지 않는다.
- notification 실패는 report/trading state commit을 rollback하지 않는다.
- Telegram/report message는 plain text 기본값, 4096자 분할, secret/account/token 원문 미노출, outbox non-blocking을 유지한다.
- Phase 20 전까지 live 관련 public route를 추가하지 않는다.
- Phase 19는 disabled scaffold와 no-live regression만 허용한다.

## Phase Status

| Phase | 상태 | 기준 |
|---|---|---|
| 조회/보고 1단계 | 완료 | 종목 상세 검색, 계좌/포트폴리오 리포트, 보유 종목 리스트, 랭킹, 차트, CSV 매매일지를 local read-only API/UI로 추가. 주문, KIS network, live 경로 변경 없음 |
| 모의투자 주문 엔진 2단계 | 완료 | local paper order 생성/취소, 미체결 조회, gated fill simulator, `paper_positions` 갱신, stop-loss/trailing-stop local exit trigger 구현. live/real order 경로와 legacy `orders` table은 변경 없음 |
| Phase 0 | 완료 | baseline audit |
| Phase 1 | 완료 | KIS paper API confirmation matrix |
| Phase 2 | 완료 | paper broker adapter hardening |
| Phase 3 | 완료 | token/hashkey request signing scaffold |
| Phase 4 | 완료 | paper order preview/submit/cancel local lifecycle |
| Phase 5 | 완료 | paper fills/positions/portfolio sync boundary |
| Phase 6 | 완료 | Telegram-first notification channel decision |
| Phase 7 | 완료 | notification implementation/outbox |
| Phase 8 | 완료 | report portfolio alerts |
| Phase 9 | 완료 | paper bot activation |
| Phase 10 | 완료 | frontend integration |
| Phase 11 | 완료 | end-to-end mock validation |
| Phase 12A | 완료 | KIS paper read-only balance dry-run path |
| Phase 12B | 완료 | KIS paper submit/cancel/query/sync adapter mock verification |
| Phase 12C | 완료 | KIS 장종료 거부 응답 redacted record와 현재 fail-closed preflight 확인 |
| GUI checkpoint | 완료 | frontend app chrome tone match |
| Telegram notifier checkpoint | 완료 | template rendering, disabled/dry-run default |
| Phase 13 | 완료 | final paper safety hardening regression 추가 |
| Phase 14 | 완료 | Telegram live opt-in dry-run/redaction 검증 |
| Phase 15 | 완료 | daily/weekly report automation API/CLI와 outbox event 추가 |
| Phase 16 | 완료 | paper bot once/loop gate와 no-submit soak 확인 |
| Phase 16A | 부분 해소 | `.env.local` KIS paper readiness와 dry_run preview/status 확인 후 repo paper/bot config는 수동 활성 상태로 전환. 실제 submit은 credential/token/fresh quote/정규장/risk gate 통과 시에만 가능하며 live 경로는 계속 차단 |
| Phase 17 | 완료 | KIS paper operations runbook 추가 |
| Phase 18 | 완료 | live trading readiness design-only 문서 추가 |
| Phase 19 | 완료 | disabled live adapter scaffold와 no-live regression 강화 |
| Phase 20 | preflight 차단 | controlled live canary runbook/preflight record 추가, live 실행 조건 미충족 |
| Phase 21 | 완료 | KIS paper token 발급, WebSocket approval/smoke, US price lookup, 정규장 AAPL 1주 paper submit, sync, fill/position persistence 확인. submit은 `/uapi/overseas-stock/v1/trading/order`, `tr_id=VTTT1002U`, `status_code=200`으로 broker order와 `paper_orders`를 만들었고 follow-up read-only sync에서 `paper_fills_count=1`, `paper_positions_count=1`, `orders_count=0` 확인. premarket/daytime/extended는 실제 paper host 거부 확인 후 adapter/network 전 차단 |

## KIS Paper Auto Bot Phase 1-6 진행 상태

아래 6단계는 `docs/goal.md`의 KIS 모의투자 전용 자동매매 봇 목표를 루트 `goal.md` 기준 실행 단위로 승격한 것이다. 모든 단계는 기본 disabled/fail-closed, no-live, no-secret-output 조건을 유지한다.

| Phase | 상태 | 현재 증거 |
|---|---|---|
| Phase 1: 설정/secret/token 기반 구축 | 완료 | `backend/config/paper.yaml`, `.env.example`, `KisHttpClient`, `KisTokenManager`, `/api/kis/status`, `/api/kis/config`, `/api/kis/config/validate` |
| Phase 2: KIS paper broker adapter | 완료 | `KisPaperBrokerAdapter`, service alias, paper endpoint/TR-ID mapper, mock HTTP adapter tests, live fallback 차단 |
| Phase 3: paper order/fill/position DB 및 API | 완료 | `paper_orders`, `paper_fills`, `paper_positions`, `paper_account_snapshots`, `paper_audit_events`, `/api/paper/orders`, `/api/paper/account`, `/api/paper/sync` |
| Phase 4: 실시간 시세/체결 worker | 완료 | `RealtimeMarketWorker`, polling quote cache, heartbeat/stale 상태, `/api/paper/realtime/status`, stale quote 주문 차단 |
| Phase 5: bot executor 및 리스크 가드 | 완료 | `PaperBotExecutor`, `/api/paper/bot/preview`, `/api/paper/bot/run`, `/api/paper/bot/runs/{run_id}`, 후보 필터/sizing/risk gate |
| Phase 6: 모니터링/리포트/운영 runbook | 완료 | `/api/paper/dashboard`, `PaperOperationalMetricsService`, daily/weekly `## Paper Trading`, `docs/RUNBOOK_PAPER_TRADING.md`, `docs/VALIDATION.md`, `Memory.md` |

검증 기준:

- 기본 runtime은 paper/broker/bot/report/notification을 수동 실행 가능 상태로 노출하되, live trading/fallback/scheduler loop는 disabled를 유지한다.
- `dry_run=true` bot preview는 주문 row를 생성하지 않는다.
- `dry_run=false` paper run도 kill switch, session, stale quote, duplicate, loss, concentration, cash/notional gate를 통과해야만 submit을 시도한다.
- 실제 KIS paper network 호출은 별도 승인 전까지 열지 않는다.
- live 주문, live cancel, live fallback, scheduler auto-start, unattended loop는 금지 상태를 유지한다.

## Phase Plan

### Phase 0: Latest Baseline Audit

- 목적: main 기준선과 현재 작업 브랜치 차이를 확인하고 fail-closed 상태를 문서화한다.
- 수정 허용 범위: `goal.md`, `docs/research/kis-paper-baseline-audit.md`, 상태 문서.
- 금지 사항: runtime code, DB schema, API route 변경 금지.
- 검증 명령: targeted KIS/broker/paper safety pytest, `git diff --check`.
- 완료 기준: baseline 충돌과 stale 문서가 명시되고 다음 Phase 조건이 정리된다.
- 다음 Phase 진입 조건: KIS paper capability matrix를 만들 수 있을 만큼 기준선이 명확하다.

### Phase 1: KIS Paper API Confirmation Matrix

- 목적: 공식 KIS 포털과 공식 GitHub 샘플 기준으로 paper capability를 확정한다.
- 수정 허용 범위: `docs/research/kis-paper-api-confirmation-matrix.md`.
- 금지 사항: production code, API route, DB schema 변경 금지.
- 검증 명령: 문서 heading/confirmed/unconfirmed 항목 확인, safety regression.
- 완료 기준: endpoint/path/TR ID/request field가 confirmed와 `확인 필요`로 분리된다.
- 다음 Phase 진입 조건: adapter 설계가 추정 없이 진행 가능하다.

### Phase 2: Paper Broker Adapter Hardening

- 목적: paper-only adapter 경계와 disabled live adapter 경계를 만든다.
- 수정 허용 범위: broker adapter service boundary, adapter contract tests.
- 금지 사항: live implementation, real network order execution 금지.
- 검증 명령: `test_kis_paper_adapter_contract.py`, `test_no_live_adapter.py`, no-live regression.
- 완료 기준: live adapter가 hard-disabled 상태이고 paper adapter만 service 경계로 노출된다.
- 다음 Phase 진입 조건: token/signing scaffold를 adapter와 분리해 붙일 수 있다.

### Phase 3: Token Hashkey Request Signing

- 목적: KIS token metadata와 hashkey signing 전제조건을 secret-safe로 정리한다.
- 수정 허용 범위: token manager, request signer, credential redaction.
- 금지 사항: raw token 저장, token 발급/refresh/cache 구현, secret logging 금지.
- 검증 명령: token/signing/redaction pytest, secret scan.
- 완료 기준: token raw value 없이 configured/status metadata만 제공한다.
- 다음 Phase 진입 조건: submit prerequisite가 fail-closed로 판단된다.

### Phase 4: Paper Order Submit Cancel

- 목적: local paper submit/cancel lifecycle을 명시적 confirm/idempotency gate 뒤에 둔다.
- 수정 허용 범위: `/api/paper/orders/submit`, `/api/paper/orders/cancel`, paper order service.
- 금지 사항: live route, live base URL, paper-to-live fallback 금지.
- 검증 명령: paper submit/cancel API pytest, no-live regression, secret scan.
- 완료 기준: 기본 config에서는 차단되고, 명시 조건에서만 local paper order가 생성된다.
- 다음 Phase 진입 조건: fill/position/portfolio sync 경계를 추가할 수 있다.

### Phase 5: Order Fills Positions Portfolio Sync

- 목적: paper 전용 fills, positions, portfolio snapshot 조회와 sync 경계를 만든다.
- 수정 허용 범위: paper repository, paper sync service, additive migration.
- 금지 사항: legacy `positions`를 broker truth로 사용하거나 raw credential column을 만들지 않는다.
- 검증 명령: paper sync/portfolio pytest, Alembic pytest, no-live regression.
- 완료 기준: paper 전용 table만 조회/갱신하고 synthetic state와 분리된다.
- 다음 Phase 진입 조건: notification/report/bot이 paper state를 안전하게 참조한다.

### Phase 6: Notification Channel Decision

- 목적: primary notification channel을 Telegram-first로 확정한다.
- 수정 허용 범위: `docs/research/notification-channel-decision.md`.
- 금지 사항: notifier code, route, migration 구현 금지.
- 검증 명령: 문서 검토, secret placeholder 검토.
- 완료 기준: Telegram primary, Discord follow-up, non-blocking/security constraints가 명시된다.
- 다음 Phase 진입 조건: notification pipeline 구현이 가능하다.

### Phase 7: Notification Implementation

- 목적: non-blocking notification service와 outbox를 구현한다.
- 수정 허용 범위: notification service, Telegram notifier, delivery logs, status/test API.
- 금지 사항: notifier 실패로 trading/report state rollback 금지.
- 검증 명령: notification service/outbox/API pytest, secret scan.
- 완료 기준: delivery 실패가 retry 상태로 남고 caller transaction을 깨지 않는다.
- 다음 Phase 진입 조건: report notification과 bot event 전달에 연결 가능하다.

### Phase 8: Report Portfolio Alerts

- 목적: saved report와 local paper portfolio snapshot 요약을 notifier로 전달한다.
- 수정 허용 범위: report notify endpoint, report notification service.
- 금지 사항: report/notification에 secret, account raw value, full credential dump 금지.
- 검증 명령: report notify pytest, report quality regression, secret scan.
- 완료 기준: daily/weekly report summary와 paper portfolio snapshot이 안전하게 전달된다.
- 다음 Phase 진입 조건: bot event와 report alert가 같은 outbox contract를 공유한다.

### Phase 9: Paper Bot Activation

- 목적: paper-only bot decision loop와 run-once/scheduler shell을 만든다.
- 수정 허용 범위: paper bot service, bot API, bot run/decision persistence.
- 금지 사항: default auto-submit, scheduler auto-start, live submit 금지.
- 검증 명령: paper bot scheduler/decision pytest, no-live regression.
- 완료 기준: bot은 preview decision을 만들고, explicit gate 없이는 submit하지 않는다.
- 다음 Phase 진입 조건: frontend가 backend safety API만 호출해 paper workflow를 조작한다.

### Phase 10: Frontend Integration

- 목적: `/paper`, `/bot`, `/reports`, `/settings`에서 paper-only 상태와 controls를 노출한다.
- 수정 허용 범위: frontend paper/bot/report/settings UI, typed API client.
- 금지 사항: live readiness로 오해되는 문구, live submit UI, secret 입력 UI 금지.
- 검증 명령: frontend lint, typecheck, build, local UI smoke.
- 완료 기준: UI가 `모의투자`, `실거래 아님`, `paper only`를 명확히 표시한다.
- 다음 Phase 진입 조건: mock-only E2E로 전체 흐름을 검증한다.

### Phase 11: End-to-End Mock Validation

- 목적: KIS credential 없이 preview, local submit, fill/portfolio, outbox, report notify 흐름을 검증한다.
- 수정 허용 범위: E2E mock test, validation docs.
- 금지 사항: real KIS credentials, real KIS network calls 금지.
- 검증 명령: `test_e2e_paper_mock_flow.py`, backend full pytest, secret scan.
- 완료 기준: full mock paper flow가 deterministic하게 통과한다.
- 다음 Phase 진입 조건: controlled KIS paper dry-run을 별도 승인 하에 검토한다.

### Phase 12A: KIS Paper Read-only Balance Dry-run

- 목적: KIS paper balance read-only path를 submit/cancel 없이 확인한다.
- 수정 허용 범위: dry-run checklist, redacted validation record.
- 금지 사항: submit/cancel/sync mutation, live endpoint, `.env`/`.env.local` 수정 금지.
- 검증 명령: KIS paper balance pytest, no-live regression, secret scan.
- 완료 기준: read-only balance 결과가 redacted metadata로만 문서화된다.
- 다음 Phase 진입 조건: paper submit/cancel/query/sync adapter mock implementation으로 진행 가능하다.

### Phase 12B: KIS Paper Submit/Cancel/Query/Sync Adapter Implementation

- 목적: KIS paper submit/cancel/list/query-balance/sync adapter를 paper-only gate 뒤에 구현한다.
- 수정 허용 범위: `backend/app/brokers/kis_paper.py`, paper order/sync service, adapter tests.
- 금지 사항: real KIS dry-run 실행, live endpoint, live fallback, WebSocket execution 금지.
- 검증 명령: paper adapter/runtime/no-live pytest, backend full pytest, secret scan.
- 완료 기준: mocked HTTP adapter tests가 통과하고 기본 runtime은 fail-closed다.
- 다음 Phase 진입 조건: human confirmation으로 controlled dry-run을 시도할 수 있다.

### Phase 12C: Controlled KIS Paper Submit/Cancel/Query/Sync Dry-run

- 목적: KIS 모의투자 계좌에서 minimum-size paper submit/cancel/query/sync를 controlled dry-run으로 검증한다.
- 수정 허용 범위: `tools/kis_paper_phase12c_dry_run.py`, dry-run checklist, redacted validation record.
- 금지 사항: Phase 13 작업, live endpoint, unattended auto-submit, `.env`/`.env.local` 수정, raw secret 출력 금지.
- 구현 조건:
  - 현재 프로세스 env만 사용한다.
  - 장중 확인을 먼저 수행한다.
  - kill switch 차단 증명을 먼저 기록한다.
  - minimum-size paper submit을 시도한다.
  - submit 성공 시 query, sync, cancel 순서로 진행한다.
  - KIS가 장종료/거부 응답을 반환하면 즉시 중단하고 redacted 결과만 기록한다.
- 검증 명령:
  - `.\.venv\Scripts\python.exe tools\kis_paper_phase12c_dry_run.py`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_paper_runtime_flags.py backend/tests/test_no_live_trading_regression.py -q`
  - `.\.venv\Scripts\python.exe tools\secret_scan.py` -> `NO_SECRET_FINDINGS`
  - `git diff --check` -> exit 0, CRLF warning only
- 완료 기준: submit/cancel/query/sync 성공 또는 KIS 거부 응답이 redacted record로 남고 live path가 사용되지 않는다.
- 다음 Phase 진입 조건: Phase 12C 결과가 안전하게 문서화되고 raw secret 노출이 없다.

### Phase 13: Final Paper Safety Hardening

- 목적: paper-only 구현을 동결하고 accidental live drift를 방지한다.
- 수정 허용 범위: no-live regression tests, `.env.example` placeholder 정리, docs/validation/memory.
- 금지 사항: feature creep, live route, live adapter 활성화 금지.
- 검증 명령: backend full pytest, frontend lint/typecheck/build, secret scan, `git diff --check`.
- 완료 기준: paper-only 상태가 문서/테스트/CI 기준으로 잠긴다.
- 다음 Phase 진입 조건: Telegram live delivery opt-in 검증을 별도 범위로 진행한다.

### Phase 14: Telegram Live Delivery Opt-in Validation

- 목적: Telegram 실제 전송을 config/env opt-in 조건에서만 검증한다.
- 수정 허용 범위: notification config validation, redacted delivery log, Telegram notifier tests/docs.
- 금지 사항: token/chat_id 원문 출력, 기본 enabled 전환, trading state rollback 금지.
- 구현 조건:
  - 기본 config는 `enabled=false`, `mode=disabled`, `dry_run=true`를 유지한다.
  - 실제 Telegram 전송은 명시 확인, env configured boolean, config opt-in이 모두 있을 때만 허용한다.
  - status API는 credential presence boolean과 channel alias만 반환한다.
- 검증 명령:
  - targeted notification pytest
  - `.\.venv\Scripts\python.exe tools\secret_scan.py` -> `NO_SECRET_FINDINGS`
  - `git diff --check` -> exit 0, CRLF warning only
- 완료 기준: dry-run과 live delivery opt-in 경로가 분리되고 secret 원문이 노출되지 않는다.
- 다음 Phase 진입 조건: report automation completion/failure event를 Telegram outbox로 보낼 수 있다.

### Phase 15: Daily/Weekly Report Automation

- 목적: 일간/주간 리포트 생성과 notification을 disabled-by-default run-once automation으로 묶는다.
- 수정 허용 public surface:
  - `GET /api/reports/automation/status`
  - `POST /api/reports/automation/run-once`
  - `tools/report_automation_runner.py`
  - notification event `daily_report_automation_completed`
  - notification event `weekly_report_automation_completed`
  - notification event `report_automation_failed`
- 금지 사항: scheduler auto-start, 기존 report contract 파괴, notification 실패로 report rollback 금지.
- 구현 조건:
  - daily/weekly report 생성은 기존 `ReportService` 계약을 재사용한다.
  - run-once는 명시 요청에서만 실행한다.
  - automation status는 secret 없이 enabled/mode/dry_run/last_run summary만 반환한다.
  - 실패는 outbox와 validation docs에 남기고 report row를 임의 삭제하지 않는다.
- 검증 명령:
  - report automation targeted pytest
  - report notify pytest
  - backend full pytest
  - frontend 변경 시 lint/typecheck/build
  - secret scan
- 완료 기준: run-once로 daily/weekly report automation과 notification event가 안전하게 검증된다.
- 다음 Phase 진입 조건: paper bot operating loop와 report automation을 soak할 수 있다.

### Phase 16: Paper Bot Operating Loop And Soak

- 목적: paper bot run-once/loop를 운영 관점에서 일정 기간 안정성 검증한다.
- 수정 허용 범위: bot run logs, bounded loop runner, validation docs, operational metrics.
- 금지 사항: default scheduler auto-start, default auto-submit, live submit 금지.
- 구현 조건:
  - loop는 explicit CLI/API invocation에서만 시작한다.
  - max run count, max order count, max notional, duplicate guard를 적용한다.
  - soak 결과는 paper-only counts와 notification delivery status 중심으로 기록한다.
- 검증 명령: bot scheduler pytest, no-live regression, secret scan, optional local smoke.
- 완료 기준: paper loop가 반복 실행되어도 duplicate submit과 secret exposure가 없다.
- 다음 Phase 진입 조건: 장애 대응 runbook과 monitoring event를 정리한다.

### Phase 16A: Controlled KIS Paper Bot Run Validation

- 목적: `dry_run=true` preview, dashboard/status 확인, `max_candidates=1` paper run, 실제 KIS paper 최소 주문 수동 검증 흐름을 live 금지 조건 안에서 문서화하고 수행한다.
- 수정 허용 범위: `goal.md`, `docs/VALIDATION.md`, `Memory.md`, 필요 시 runbook의 redacted 결과 기록.
- 금지 사항: live 주문, live cancel, live fallback, scheduler auto-start, unattended loop, `.env`/`.env.local` 수정, raw secret 출력 금지.
- 구현 조건:
  - Step 1 dry-run preview: `POST /api/paper/bot/preview`에 `trade_date`, `strategies`, `max_candidates=1`, `dry_run=true`를 전달한다.
  - Step 1 성공 기준: `paper_order_submitted=false`, `live_order_created=false`, 주문 row 생성 없음, decision/reason code 저장.
  - Step 2 dashboard/status 확인: `/api/kis/config/validate`, `/api/kis/status`, `/api/broker/status`, `/api/paper/status`, `/api/paper/realtime/status`, `/api/paper/dashboard`를 확인한다.
  - Step 2 성공 기준: secret/account/token 원문 미노출, `KIS_ENV=paper`, live disabled, kill switch 상태 명확.
  - Step 3 paper run: 현재 PowerShell 프로세스에만 `KIS_ENV=paper`, `ENABLE_REAL_ORDER=false`, `PAPER_TRADING_ENABLED=true`, `PAPER_TRADING_CAN_CREATE=true`, `PAPER_BOT_CONFIRM=true`, `PAPER_TRADING_KILL_SWITCH=false`를 주입한다.
  - Step 3 network gate: 실제 KIS paper network 호출이 승인된 경우에만 `PAPER_TRADING_NETWORK_ENABLED=true`, `BROKER_MODE=paper_kis`, `PAPER_ORDER_SUBMIT_ENABLED=true`를 추가한다.
  - Step 3 실행: `POST /api/paper/bot/run`에 `max_candidates=1`, `dry_run=false`를 전달하며 submit은 최대 1건으로 제한한다.
  - Step 4 minimum paper order: 장중, 최소 수량, 단일 symbol, 단일 strategy만 허용하고 주문 생성 시 status 조회, sync, 필요 시 cancel 순서로 확인한다.
  - KIS가 장종료, 인증 실패, rate limit, payload 오류, stale quote를 반환하면 재시도 루프 없이 즉시 중단하고 redacted 결과만 기록한다.
- 검증 명령:
  - `rg -n "Phase 16A|Controlled KIS Paper Bot Run Validation|dry_run=true|max_candidates=1|PAPER_TRADING_KILL_SWITCH" goal.md`
  - `git diff --check`
  - `.\.venv\Scripts\python.exe tools\secret_scan.py`
- 완료 기준: 성공 또는 KIS 거부/장종료/stale/auth/rate-limit 결과가 redacted record로 남고 live path 미사용이 확인된다.
- 실행 결과:
  - `POST /api/paper/bot/preview`, `max_candidates=1`, `dry_run=true` -> `run_id=paper-bot-0439a452f5b84f40`, `status=disabled`, `submitted_count=0`, `network_call_performed=false`.
  - dashboard/status API 확인 완료. raw secret/account/token 원문 미노출, `orders_count=0`, `paper_orders_count=0`.
  - 현재 PowerShell 프로세스 env에만 paper gate를 주입하고 network gate는 미개방한 `POST /api/paper/bot/run`, `max_candidates=1`, `dry_run=false` -> `run_id=paper-bot-7a43c3c83f3244f7`, `status=disabled`, `PAPER_BOT_DISABLED`, `PAPER_BOT_KILL_SWITCH_ACTIVE`, `KILL_SWITCH_ACTIVE`, `network_call_performed=false`.
  - `.env.local`에 `KIS_ENV=paper` 추가 후 현재 Python 검증 프로세스에만 로드해 재확인: `POST /api/kis/config/validate` -> `configured=true`, `kis_env_paper=true`, `network_call_performed=false`; `POST /api/paper/bot/preview`, `max_candidates=1`, `dry_run=true` -> `run_id=paper-bot-fb740345fe7f4608`, `status=disabled`, `PAPER_BOT_DISABLED`, `KILL_SWITCH_ACTIVE`, `submitted_count=0`, `network_call_performed=false`.
  - redacted 결과는 `docs/research/kis-paper-phase16a-bot-run-redacted-record.json`에 기록했다.
- 다음 Phase 진입 조건: 실제 KIS paper 최소 주문/조회/sync/cancel은 별도 network 승인, 계좌/product code 준비, config/bot kill switch 해제 절차가 있을 때만 진행한다.

### Phase 17: KIS Paper Monitoring And Incident Runbook

- 목적: KIS paper 운영 중단, 토큰 오류, 장종료, rate limit, notification 실패 대응 절차를 문서화한다.
- 수정 허용 범위: docs/runbook, status endpoint metadata, validation docs.
- 금지 사항: live trading enablement, destructive DB operation, secret 출력 금지.
- 구현 조건:
  - incident 유형별 탐지 신호, 차단 기준, 수동 복구 순서, rollback 순서를 기록한다.
  - status/notification payload는 redacted summary만 사용한다.
- 검증 명령: docs heading check, targeted status/notification pytest, secret scan.
- 완료 기준: 다음 작업자가 paper 운영 장애를 재현/진단/중단할 수 있다.
- 다음 Phase 진입 조건: live readiness design-only 검토로 넘어갈 수 있다.

### Phase 18: Live Trading Readiness Design Only

- 목적: 실전매매 전환에 필요한 설계, 승인 조건, 위험 통제, 검증 계획만 작성한다.
- 수정 허용 범위: design docs, risk checklist, validation plan.
- 금지 사항: live code, live endpoint, live route, live submit 가능 상태 금지.
- 구현 조건:
  - live canary 전제조건을 문서화한다.
  - 계좌/주문/취소/체결/정정/리스크/감사/롤백 기준을 설계만 한다.
  - broker compliance와 human approval gate를 명시한다.
- 검증 명령: docs check, no-live static scan, secret scan.
- 완료 기준: live 전환 조건과 금지 조건이 decision-complete로 문서화된다.
- 다음 Phase 진입 조건: 별도 명시 승인 후 disabled scaffold만 진행한다.

### Phase 19: Disabled Live Adapter Scaffold

- 목적: live adapter의 비활성 placeholder와 no-live regression을 강화한다.
- 승인 조건: 사용자의 별도 명시 승인 필요.
- 수정 허용 범위: disabled live adapter scaffold, no-live tests, docs.
- 금지 사항: live endpoint 호출, live submit/cancel 구현, live route 추가, live fallback 금지.
- 구현 조건:
  - 모든 method는 disabled/fail-closed 응답만 반환한다.
  - 테스트는 live route 부재와 live submit 불가능 상태를 검증한다.
- 검증 명령: no-live regression, backend full pytest, secret scan, `git diff --check`.
- 완료 기준: live scaffold가 있어도 실행 가능성이 0임을 테스트로 증명한다.
- 다음 Phase 진입 조건: 별도 승인형 controlled live canary 요청이 있어야 한다.

### Phase 20: Controlled Live Canary

- 목적: 별도 승인된 조건에서만 최소 범위 live canary를 수행한다.
- 승인 조건: 사용자의 별도 명시 승인, 환경 분리, required reviewer, live kill switch rollback 절차 필요.
- 수정 허용 범위: 승인된 canary checklist와 redacted validation record.
- 금지 사항:
  - 승인 없는 live endpoint 호출
  - 자동 live submit
  - unattended canary
  - secret/account raw output
  - paper-to-live fallback
- 구현 조건:
  - Phase 18 설계와 Phase 19 disabled scaffold 검증이 완료되어야 한다.
  - canary는 단일 전략, 단일 market, minimum-size, 수동 확인 기반으로 제한한다.
  - 즉시 kill switch, scheduler stop, notifier-only rollback 경로를 준비한다.
- 검증 명령: canary checklist, no-live/static guard, post-canary redacted audit, secret scan.
- 완료 기준: approved live canary 결과가 redacted record로 남고 rollback 경로가 검증된다.
- 다음 Phase 진입 조건: 별도 운영 승인 없이는 없음.
- 현재 결과: `tools/live_canary_preflight.py --write-record`는 live adapter disabled, live route 부재, reviewer/환경분리/rollback 증거 미충족으로 `status=blocked`를 반환했다. 실계좌 주문, live endpoint 호출, WebSocket 체결은 수행하지 않았다.

### Phase 21: KIS Paper Network Activation

- 목적: preview-only 단계를 넘어 KIS paper 전용 token 발급, WebSocket approval key 발급, minimum paper submit, 주문 조회, sync, cancel, 체결/포지션 persistence까지 확인한다.
- 수정 허용 범위: KIS paper token route, paper realtime WebSocket approval/status/subscription route, process-only activation record, validation docs.
- 금지 사항:
  - live 주문, live cancel, live fallback
  - `/api/kis/websocket/*` live성 route 추가
  - unattended WebSocket loop
  - `.env`/`.env.local` 수정
  - raw token, approval key, account, app secret 출력
- 구현 결과:
  - `POST /api/kis/token/issue`, `POST /api/kis/token/refresh`, `GET /api/kis/token/status` 추가. token 발급은 `confirm=true`, `KIS_TOKEN_ISSUE_ENABLED=true`, `KIS_ENV=paper`, `ENABLE_REAL_ORDER=false` 조건에서만 수행한다.
  - `GET /api/paper/realtime/websocket/status`, `POST /api/paper/realtime/websocket/approval`, `POST /api/paper/realtime/websocket/subscription/preview` 추가. WebSocket approval은 paper endpoint `/oauth2/Approval`만 허용한다.
  - `POST /api/paper/realtime/websocket/smoke` 추가. `PAPER_WEBSOCKET_CONNECT_ENABLED=true`와 `confirm=true`일 때만 bounded connect 1회 수행하고 unattended loop는 실행하지 않는다.
  - KIS paper adapter에 공식 KIS 샘플 기준 해외주식/미국장 endpoint 분기를 추가했다. 정규 세션은 미국 paper 주문 `VTTT1002U`/`VTTT1006U`, 취소 `VTTT1004U`, 체결조회 `VTTS3035R`, 잔고조회 `VTTS3012R`을 사용한다. `order_session=premarket/aftermarket/daytime/extended`는 실제 paper host가 미국주간주문 `TTTS6036U`를 거부한 뒤 `KIS_PAPER_US_DAYTIME_ORDER_UNSUPPORTED`로 네트워크 전 차단한다.
  - `PaperConfigService`가 `PAPER_TRADING_MARKET`, `KIS_OVERSEAS_EXCHANGE_CODE`, `KIS_OVERSEAS_CURRENCY`, `KIS_OVERSEAS_ORDER_SESSION`을 runtime config로 노출하고 `PaperOrderService` network submit이 `market=US`, `venue/exchange=NASD`, `currency=USD`, 선택적 `order_session` metadata를 adapter에 전달하도록 보강했다.
  - `KIS_US_ORDER_CAPABILITIES`를 추가해 paper는 미국 정규장 `regular`만, real은 `regular/premarket/aftermarket/daytime` capability로 분리했다. real live adapter는 기존 disabled scaffold를 유지한다.
  - paper + US + non-regular session은 API 호출 전 `"KIS paper trading does not support US extended/daytime order session. Blocked before API call."`로 차단하고, 차단/실패 trace에 `tr_id`, `host`, `market`, `symbol`, `order_session`, `rt_cd`, `msg_cd`, `msg1`을 남긴다.
  - `PaperSyncService`가 broker sync fill을 기존 `paper_orders.broker_order_id`로 조회해 내부 `paper_order_id`에 귀속하도록 보강했다. broker submit -> sync mock lifecycle에서 order filled status, fill, position persistence 연결을 확인했다.
  - `tools/kis_paper_phase12c_dry_run.py`는 submit -> list -> sync 후 완전 체결이 확인되면 cancel을 호출하지 않고 `cancel_skipped_after_fill`과 `lifecycle_evidence`를 남긴다. 정규장 실제 주문이 즉시 체결되는 경우를 주문 생성/체결/포지션 변경 성공 record로 보존하기 위한 처리다.
  - `tools/kis_paper_phase21_service_lifecycle.py`를 추가했다. 정규장 gate 통과 후 `PaperOrderService.submit_order`로 `paper_orders`를 만들고 `PaperSyncService.sync`로 `paper_fills`/`paper_positions` persistence를 확인한다. fill/position이 확인되지 않으면 broker order id 기반 paper cancel을 1회 시도한다. 프리마켓은 API 호출 전 차단한다.
  - `tools/kis_paper_phase12c_dry_run.py`에 `--market US --exchange NASD --currency USD` 옵션을 추가해 다음 실제 1회 재시도 때 kill-switch proof -> submit -> list -> sync -> cancel이 미국장 metadata/config로 실행되도록 보강했다. 일반 프리마켓 주문과 daytime-order가 모두 paper host에서 거부되어 현재 helper는 US submit을 정규장 전용으로 제한한다.
  - `tools/kis_paper_phase21_us_activation.py`를 추가해 token 발급, WebSocket approval/subscription/smoke, controlled US submit/list/sync/cancel을 하나의 redacted record로 묶도록 보강했다. 이후 `--execute-service-lifecycle` 옵션을 추가해 token/WebSocket proof와 `PaperOrderService.submit_order` -> `PaperSyncService.sync` persistence proof를 같은 record에 담을 수 있게 했다. 중복 주문 방지를 위해 `--execute-submit`과 `--execute-service-lifecycle` 동시 사용은 차단한다. `completion_audit`를 추가해 token/network/WebSocket/order/fill/position/no-live/no-secret 요구사항과 누락 항목을 명시한다. `status=completed`라도 `completion_audit.complete=false`면 전체 목표 완료로 보지 않는다. `--load-env-local`은 `.env.local`을 수정하지 않고 현재 helper process에만 allowlist key를 로드하며 raw 값과 secret-like key name은 기록하지 않는다. `--derive-limit-from-price`는 정규장 gate 통과 뒤에만 read-only 해외 현재가 `HHDFS00000300`를 호출해 제한가를 산정한다.
  - 공식 Open API 미국주간주문 샘플의 `/uapi/overseas-stock/v1/trading/daytime-order`, `TTTS6036U`/`TTTS6037U`와 주간정정취소 `TTTS6038U`를 확인했다. 다만 공식 legacy 지원표에서 모의투자 지원 표시가 없고 실제 paper host도 `EGW02006`으로 거부해 paper adapter에서는 차단한다. live base URL, live fallback, 실전 주문은 계속 차단한다.
- 실행 결과:
  - process-only gate로 `POST /oauth2/tokenP` 1회 성공, `token_issued=true`, raw token 미출력/미기록.
  - process-only gate로 `POST /oauth2/Approval` 1회 성공, `approval_key_issued=true`, raw approval key 미출력/미기록.
  - temporary paper config와 process-only network gate로 `POST /uapi/domestic-stock/v1/trading/order-cash`, `tr_id=VTTC0012U` 1회 도달.
  - KIS 응답: `40580000`, `모의투자 장종료 입니다.`. 재시도하지 않고 중단.
  - 사용자 지시로 미국장 AAPL/NASD paper 경로를 추가 진행했다. `HDFSCNT0`/`DNASAAPL` WebSocket bounded smoke는 `SUBSCRIBE SUCCESS` ACK를 수신했다.
  - 해외 price 조회와 해외잔고 조회는 성공했다. 사전 해외잔고는 `70070000`, `모의투자 조회할 내역(자료)이 없습니다.`로 반환됐다.
  - `POST /uapi/overseas-stock/v1/trading/order`, `tr_id=VTTT1002U` 1회 도달 후 HTTP 500 / `KIS_PAPER_RESPONSE_ERROR`로 중단했다. 재시도하지 않았다.
  - 프리마켓 `VTTT1002U` submit은 `40570000`, `모의투자 장시작전 입니다.`로 중단했다. 원인은 premarket을 일반 해외주식 주문 경로로 보낸 점으로 확인했다. 이후 `/daytime-order`, `TTTS6036U`를 실제 paper host에 1회 검증했지만 `EGW02006`, `모의투자 TR 이 아닙니다.`로 중단했다. broker order id 없음, list/sync/cancel 미실행, 재시도 없음.
  - 2026-05-28 06:39 New York 기준 현재 세션은 premarket이라 최신 helper가 `US_REGULAR_SESSION_REQUIRED`로 adapter 호출 전 중단했다. `network_call_performed=false`, raw secret 미출력, `next_regular_session_start=2026-05-28T09:30:00-04:00`, record: `docs/research/kis-paper-phase21-us-regular-session-required-redacted-record.json`.
  - 2026-05-28 07:34 New York 기준 통합 activation helper의 `--load-env-local --execute-service-lifecycle --derive-limit-from-price`도 premarket이라 `US_REGULAR_SESSION_REQUIRED`로 price lookup과 service submit 전 중단했다. `.env.local` raw 값과 secret-like key name은 record에 남기지 않았고, `network_call_performed=false`, raw secret 미출력, `next_regular_session_start=2026-05-28T09:30:00-04:00`, record: `docs/research/kis-paper-phase21-us-service-lifecycle-regular-session-required-redacted-record.json`.
  - 2026-05-28 09:53 New York 기준 local command runner 복구 후 existing-token service lifecycle을 실행했다. WebSocket approval/smoke는 성공했고, read-only price lookup은 KIS가 `EXCD=NASD`를 `OPSQ2001`로 거부해 price endpoint 전용 `NASD -> NAS` mapping을 추가한 뒤 성공했다. service submit은 `/uapi/overseas-stock/v1/trading/order`, `tr_id=VTTT1002U`, `order_session=regular`, derived limit `320.53`까지 도달했으나 KIS가 `EGW00123`, `기간이 만료된 token 입니다.`로 거부했다. 주문번호/fill/position 없음, cancel 미실행, 재시도 없음. `completion_audit.complete=false`, record: `docs/research/kis-paper-phase21-us-service-lifecycle-existing-token-redacted-record.json`.
  - 2026-05-28 10:05 New York 기준 process-only gate로 token 발급, WebSocket approval/smoke, price lookup, service lifecycle을 실행했다. submit은 `/uapi/overseas-stock/v1/trading/order`, `tr_id=VTTT1002U`, `status_code=200`, `order_session=regular`, derived limit `320.32`로 broker order와 `paper_orders`를 생성했다. 즉시 sync는 `/inquire-ccnl` `VTTS3035R`, `/inquire-balance` `VTTS3012R` 200으로 `paper_positions_count=1`을 확인했으나 `paper_fills_count=0`이라 completion은 false였다. cancel은 `/order-rvsecncl`, `tr_id=VTTT1004U`까지 1회 도달했지만 KIS가 `40330000`, `모의투자 정정/취소할 수량이 없습니다.`로 거부해 재시도하지 않았다. record: `docs/research/kis-paper-phase21-us-service-lifecycle-token-issue-regular-redacted-record.json`.
  - 2026-05-28 10:12 New York 기준 새 주문/취소 없이 `tools/kis_paper_phase21_followup_sync.py --load-env-local --issue-token --scope all`을 실행했다. read-only sync는 `/inquire-ccnl` `VTTS3035R`, `/inquire-balance` `VTTS3012R` 200으로 완료했고 `paper_fills_count=1`, `paper_positions_count=1`, `orders_count=0`, `submit_performed=false`, `cancel_performed=false`, `live_order_created=false`, `completion_audit.complete=true`를 확인했다. record: `docs/research/kis-paper-phase21-us-followup-sync-redacted-record.json`.
  - submit 재시도 없이 read-only 주문체결조회 `GET /uapi/overseas-stock/v1/trading/inquire-ccnl`, `tr_id=VTTS3035R`를 1회 수행했고 open order/fill 0개를 확인했다.
  - 이어진 read-only sync의 balance leg는 `EGW00201`, `초당 거래건수를 초과하였습니다.`로 중단했다. 재시도하지 않았다.
  - submit 실패로 broker order id가 없어 query/sync/cancel과 `paper_orders`/`paper_fills`/`paper_positions` persistence는 미완료.
  - redacted 결과는 `docs/research/kis-paper-phase21-activation-redacted-record.json`, `docs/research/kis-paper-phase21-us-redacted-record.json`에 기록했다.
- 검증 명령:
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_token_websocket_activation.py backend/tests/test_kis_paper_adapter_contract.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_us_targeted2`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_kis_paper_token_websocket_activation.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_us_route_fix`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_order_service.py backend/tests/test_kis_paper_adapter_contract.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_us_service_metadata`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_sync_service.py backend/tests/test_paper_order_service.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_lifecycle_persistence`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_paper_order_service.py backend/tests/test_paper_sync_service.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_us_helper_options`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase21_us_activation_tool.py backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_kis_paper_token_websocket_activation.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_activation_helper`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase21_us_activation_tool.py backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_kis_paper_token_websocket_activation.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_kis_token_lifecycle_phase1.py backend/tests/test_kis_token_manager.py backend/tests/test_paper_order_service.py backend/tests/test_paper_order_api.py backend/tests/test_paper_sync_service.py backend/tests/test_paper_realtime_worker.py backend/tests/test_paper_dashboard_report_phase6.py backend/tests/test_api_smoke.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_final_safety_hardening.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_activation_helper_regression`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_token_websocket_activation.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_kis_token_lifecycle_phase1.py backend/tests/test_kis_token_manager.py backend/tests/test_paper_order_service.py backend/tests/test_paper_order_api.py backend/tests/test_paper_sync_service.py backend/tests/test_paper_realtime_worker.py backend/tests/test_paper_dashboard_report_phase6.py backend/tests/test_api_smoke.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_final_safety_hardening.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_us_regression_after_fix`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_token_websocket_activation.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_kis_token_lifecycle_phase1.py backend/tests/test_kis_token_manager.py backend/tests/test_paper_order_service.py backend/tests/test_paper_order_api.py backend/tests/test_paper_sync_service.py backend/tests/test_paper_realtime_worker.py backend/tests/test_paper_dashboard_report_phase6.py backend/tests/test_api_smoke.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_final_safety_hardening.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_us_service_regression`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_token_websocket_activation.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_kis_token_lifecycle_phase1.py backend/tests/test_kis_token_manager.py backend/tests/test_paper_order_service.py backend/tests/test_paper_order_api.py backend/tests/test_paper_sync_service.py backend/tests/test_paper_realtime_worker.py backend/tests/test_paper_dashboard_report_phase6.py backend/tests/test_api_smoke.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_final_safety_hardening.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_lifecycle_regression`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_token_websocket_activation.py backend/tests/test_kis_token_lifecycle_phase1.py backend/tests/test_kis_token_manager.py backend/tests/test_no_live_trading_regression.py backend/tests/test_final_safety_hardening.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_token_ws_targeted`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_token_websocket_activation.py backend/tests/test_kis_token_lifecycle_phase1.py backend/tests/test_kis_token_manager.py backend/tests/test_paper_realtime_worker.py backend/tests/test_paper_dashboard_report_phase6.py backend/tests/test_api_smoke.py backend/tests/test_phase3c_kis_readonly.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_phase3f2_kis_daily_ohlcv_adapter.py backend/tests/test_phase3f3_krx_fixture_contract.py backend/tests/test_phase3f4_data_quality_summary.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_final_safety_hardening.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_token_ws_regression`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_kis_paper_phase21_us_activation_tool.py backend/tests/test_paper_order_service.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_daytime_unsupported_patch_recheck` -> `34 passed in 0.92s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_adapter_contract.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_kis_capability_adapter_aftermarket` -> `15 passed in 0.75s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_kis_paper_phase21_us_activation_tool.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_paper_order_service.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_next_regular_phase_targeted` -> `39 passed in 1.03s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_kis_paper_phase21_us_activation_tool.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_fill_skip_targeted` -> `22 passed in 0.21s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_kis_paper_phase21_us_activation_tool.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_paper_order_service.py backend/tests/test_paper_sync_service.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_fill_skip_phase_targeted` -> `45 passed in 2.58s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase21_service_lifecycle_tool.py -q` -> `3 passed in 1.73s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase21_us_activation_tool.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_completion_audit_activation` -> `13 passed in 0.82s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase21_us_activation_tool.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_price_exchange_code` -> `13 passed in 0.78s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase21_service_lifecycle_tool.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_completion_audit_service_retry` -> `3 passed in 0.70s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase21_us_activation_tool.py backend/tests/test_kis_paper_phase21_service_lifecycle_tool.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_audit_pair_retry` -> `16 passed in 2.66s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_order_service.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_paper_order_network_trace_retry_single` -> `5 passed in 1.62s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase21_service_lifecycle_tool.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_followup_record_fix` -> `5 passed in 0.79s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase21_us_activation_tool.py backend/tests/test_kis_paper_phase21_service_lifecycle_tool.py backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_paper_order_service.py backend/tests/test_paper_sync_service.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_followup_final_targeted` -> `59 passed in 1.57s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_paper_order_service.py backend/tests/test_paper_sync_service.py backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_kis_paper_phase21_us_activation_tool.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_kis_paper_phase21_service_lifecycle_tool.py -q` -> `48 passed in 2.93s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase21_us_activation_tool.py -q` -> `13 passed in 1.23s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase21_us_activation_tool.py backend/tests/test_kis_paper_phase21_service_lifecycle_tool.py backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_paper_order_service.py backend/tests/test_paper_sync_service.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_capability_targeted` -> `56 passed in 2.67s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase21_us_activation_tool.py backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_kis_paper_phase21_service_lifecycle_tool.py backend/tests/test_kis_paper_token_websocket_activation.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_kis_token_lifecycle_phase1.py backend/tests/test_kis_token_manager.py backend/tests/test_paper_order_service.py backend/tests/test_paper_order_api.py backend/tests/test_paper_sync_service.py backend/tests/test_paper_realtime_worker.py backend/tests/test_paper_dashboard_report_phase6.py backend/tests/test_api_smoke.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_final_safety_hardening.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_service_lifecycle_regression` -> `86 passed in 99.90s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase21_us_activation_tool.py backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_kis_paper_phase21_service_lifecycle_tool.py backend/tests/test_kis_paper_token_websocket_activation.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_kis_token_lifecycle_phase1.py backend/tests/test_kis_token_manager.py backend/tests/test_paper_order_service.py backend/tests/test_paper_order_api.py backend/tests/test_paper_sync_service.py backend/tests/test_paper_realtime_worker.py backend/tests/test_paper_dashboard_report_phase6.py backend/tests/test_api_smoke.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_final_safety_hardening.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_price_derived_integrated_regression` -> `93 passed in 56.12s`
  - `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; .\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase21_us_activation_tool.py backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_kis_paper_phase21_service_lifecycle_tool.py backend/tests/test_kis_paper_token_websocket_activation.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_kis_token_lifecycle_phase1.py backend/tests/test_kis_token_manager.py backend/tests/test_paper_order_service.py backend/tests/test_paper_order_api.py backend/tests/test_paper_sync_service.py backend/tests/test_paper_realtime_worker.py backend/tests/test_paper_dashboard_report_phase6.py backend/tests/test_api_smoke.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_final_safety_hardening.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_followup_final_regression` -> `97 passed in 36.45s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase21_us_activation_tool.py backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_kis_paper_token_websocket_activation.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_kis_token_lifecycle_phase1.py backend/tests/test_kis_token_manager.py backend/tests/test_paper_order_service.py backend/tests/test_paper_order_api.py backend/tests/test_paper_sync_service.py backend/tests/test_paper_realtime_worker.py backend/tests/test_paper_dashboard_report_phase6.py backend/tests/test_api_smoke.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_final_safety_hardening.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_daytime_unsupported_regression` -> `77 passed in 36.67s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase21_us_activation_tool.py backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_kis_paper_token_websocket_activation.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_kis_token_lifecycle_phase1.py backend/tests/test_kis_token_manager.py backend/tests/test_paper_order_service.py backend/tests/test_paper_order_api.py backend/tests/test_paper_sync_service.py backend/tests/test_paper_realtime_worker.py backend/tests/test_paper_dashboard_report_phase6.py backend/tests/test_api_smoke.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_final_safety_hardening.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_regular_gate_regression` -> `77 passed in 110.66s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase21_us_activation_tool.py backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_kis_paper_token_websocket_activation.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_kis_token_lifecycle_phase1.py backend/tests/test_kis_token_manager.py backend/tests/test_paper_order_service.py backend/tests/test_paper_order_api.py backend/tests/test_paper_sync_service.py backend/tests/test_paper_realtime_worker.py backend/tests/test_paper_dashboard_report_phase6.py backend/tests/test_api_smoke.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_final_safety_hardening.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_kis_capability_regression` -> `81 passed in 99.14s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase21_us_activation_tool.py backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_kis_paper_token_websocket_activation.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_kis_token_lifecycle_phase1.py backend/tests/test_kis_token_manager.py backend/tests/test_paper_order_service.py backend/tests/test_paper_order_api.py backend/tests/test_paper_sync_service.py backend/tests/test_paper_realtime_worker.py backend/tests/test_paper_dashboard_report_phase6.py backend/tests/test_api_smoke.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_final_safety_hardening.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_next_regular_regression` -> `82 passed in 62.02s`
  - `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_phase21_us_activation_tool.py backend/tests/test_kis_paper_phase12c_tool.py backend/tests/test_kis_paper_token_websocket_activation.py backend/tests/test_kis_paper_adapter_contract.py backend/tests/test_kis_token_lifecycle_phase1.py backend/tests/test_kis_token_manager.py backend/tests/test_paper_order_service.py backend/tests/test_paper_order_api.py backend/tests/test_paper_sync_service.py backend/tests/test_paper_realtime_worker.py backend/tests/test_paper_dashboard_report_phase6.py backend/tests/test_api_smoke.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_no_live_adapter.py backend/tests/test_no_live_trading_regression.py backend/tests/test_final_safety_hardening.py -q -p no:cacheprovider --basetemp $env:TEMP\stock_phase21_fill_skip_regression` -> `83 passed in 98.53s`
  - `.\.venv\Scripts\python.exe tools\secret_scan.py`
  - `git diff --check`
- 현재 상태: `진행 중`. token/network/WebSocket approval/US bounded WebSocket과 service-level mock persistence는 완료됐지만 실제 KIS 주문 생성, 체결, 포지션 변경은 KIS 거부로 아직 미완료다. 프리마켓/애프터마켓/미국주간주문은 paper host 지원 불확실 또는 비지원 확인으로 현재 adapter/network 전 차단한다.
- 다음 조건: 별도 승인 후 KIS paper 주문이 가능한 미국 정규장 시간/상품 조건에서 minimum submit -> query -> sync -> cancel을 1회 재시도한다. 거부/auth/rate-limit/stale 응답이면 재시도하지 않는다.

## Reusable Codex Phase Prompt

### Common Prompt

```text
AGENTS.md, Memory.md, docs/PROJECT_STATUS.md, docs/VALIDATION.md, goal.md를 먼저 읽고 현재 작업트리 상태를 확인해. goal.md의 다음 미완료 Phase <PHASE_ID>만 수행해. 실계좌/live 주문, live cancel, live fallback, WebSocket 체결, secret 출력은 금지한다. 구현 후 지정 테스트, secret scan, git diff --check를 실행하고 docs/VALIDATION.md와 Memory.md를 최신 상태로 압축 갱신해. 커밋/푸시는 요청 전까지 하지 마.
```

### Phase 12C Prompt

```text
goal.md Phase 12C controlled KIS paper dry-run만 수행해. 현재 프로세스 env만 사용하고 .env/.env.local은 수정하지 마. 장중 확인, kill switch 차단 증명, minimum-size paper submit, query, sync, cancel 순서로 진행하되 KIS가 장종료/거부 응답을 주면 즉시 중단하고 redacted 결과만 문서화해.
```

### Phase 14 Prompt

```text
goal.md Phase 14 Telegram live delivery opt-in만 수행해. 기본 config는 disabled/dry-run 유지하고, 실제 Telegram 전송은 env/config opt-in과 명시 확인이 있을 때만 허용해. token/chat_id 원문은 출력하지 말고 status boolean, redacted delivery log, 템플릿 렌더링 검증만 남겨.
```

### Phase 15 Prompt

```text
goal.md Phase 15 daily/weekly report automation만 수행해. 기존 report 생성/notify 계약을 깨지 말고 run-once API와 CLI를 disabled-by-default로 추가해. 스케줄러 자동 시작은 금지하고, 실패는 notification/report 상태를 rollback하지 않게 outbox로 분리해.
```

### Phase 16A Prompt

```text
goal.md Phase 16A controlled KIS paper bot run validation만 수행해. 먼저 dry_run=true preview를 실행하고 dashboard/status를 확인한 뒤, 현재 PowerShell 프로세스 env에만 paper gate를 주입해 max_candidates=1 paper run을 시도해. 실제 KIS paper network 호출은 별도 승인된 경우에만 열고, 장종료/거부/stale/auth/rate-limit 응답은 재시도하지 말고 redacted 결과로 기록해. live 주문, live cancel, live fallback, scheduler auto-start, unattended loop, .env/.env.local 수정, raw secret 출력은 금지한다.
```

### Phase 18-20 Prompt

```text
goal.md Phase 18부터 live readiness만 검토해. Phase 18은 설계/문서/검증 계획만, Phase 19는 disabled scaffold만, Phase 20은 사용자의 별도 명시 승인 없이는 시작하지 마. live submit 가능 상태, live endpoint 호출, 실계좌 주문/취소/체결은 금지한다.
```

## Validation Plan For This Goal Update

문서 갱신만 수행할 때는 아래 명령으로 충분하다.

```powershell
rg -n "Phase 12C|Phase 13|Phase 14|Phase 15|Phase 16A|Phase 18|Controlled Live Canary|Non-Negotiable Safety Contract|Reusable Codex Phase Prompt" goal.md
git diff --check
```

Phase 실행 시에는 각 Phase의 검증 명령을 우선한다. backend/frontend 코드, API contract, DB schema, UI가 바뀌면 관련 pytest와 frontend lint/typecheck/build를 함께 실행한다.

## Current Assumptions

- `docs/research/deep-research-report (1).md`는 현재 작업 경로에 없으므로 이번 goal 갱신 입력에서 제외한다.
- 현재 dirty worktree에는 사용자가 만든 변경이 섞여 있을 수 있으므로 Phase 실행과 무관한 파일은 수정하지 않는다. 문서 계획 반영 시에는 `goal.md` 중심으로 갱신하고 `docs/VALIDATION.md`, `Memory.md`에는 최신 상태만 압축 기록한다.
- 실전매매는 최종 목표로 기록하되 실제 live 주문 기능은 별도 승인 전까지 구현하지 않는다.
- KIS endpoint/TR ID/request field는 repo matrix와 공식 문서가 일치할 때만 사용하고, 불확실한 항목은 `확인 필요`로 유지한다.
