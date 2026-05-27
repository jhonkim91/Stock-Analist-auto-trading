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
| Baseline HEAD | `112f26c` |
| 상태 | KIS paper network adapter mock 검증 완료, Phase 12C~19 완료, Phase 20 preflight 차단 |
| Backend | FastAPI + SQLite + Alembic |
| Frontend | Next.js App Router |
| 최신 backend full pytest | `405 passed` |
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
| Phase 17 | 완료 | KIS paper operations runbook 추가 |
| Phase 18 | 완료 | live trading readiness design-only 문서 추가 |
| Phase 19 | 완료 | disabled live adapter scaffold와 no-live regression 강화 |
| Phase 20 | preflight 차단 | controlled live canary runbook/preflight record 추가, live 실행 조건 미충족 |

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
  - `.\.venv\Scripts\python.exe tools\secret_scan.py`
  - `git diff --check`
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
  - `.\.venv\Scripts\python.exe tools\secret_scan.py`
  - `git diff --check`
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

### Phase 18-20 Prompt

```text
goal.md Phase 18부터 live readiness만 검토해. Phase 18은 설계/문서/검증 계획만, Phase 19는 disabled scaffold만, Phase 20은 사용자의 별도 명시 승인 없이는 시작하지 마. live submit 가능 상태, live endpoint 호출, 실계좌 주문/취소/체결은 금지한다.
```

## Validation Plan For This Goal Update

문서 갱신만 수행할 때는 아래 명령으로 충분하다.

```powershell
rg -n "Phase 12C|Phase 13|Phase 14|Phase 15|Phase 18|Controlled Live Canary|Non-Negotiable Safety Contract|Reusable Codex Phase Prompt" goal.md
git diff --check
```

Phase 실행 시에는 각 Phase의 검증 명령을 우선한다. backend/frontend 코드, API contract, DB schema, UI가 바뀌면 관련 pytest와 frontend lint/typecheck/build를 함께 실행한다.

## Current Assumptions

- `docs/research/deep-research-report (1).md`는 현재 작업 경로에 없으므로 이번 goal 갱신 입력에서 제외한다.
- 현재 dirty worktree에는 사용자가 만든 변경이 섞여 있을 수 있으므로 이 goal 갱신 작업에서는 `goal.md` 외 파일을 수정하지 않는다.
- 실전매매는 최종 목표로 기록하되 실제 live 주문 기능은 별도 승인 전까지 구현하지 않는다.
- KIS endpoint/TR ID/request field는 repo matrix와 공식 문서가 일치할 때만 사용하고, 불확실한 항목은 `확인 필요`로 유지한다.
