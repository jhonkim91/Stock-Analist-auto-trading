# Live Trading Readiness Design

## 핵심 요약

이 문서는 `goal.md` Phase 18-20 범위의 live readiness 산출물이다. 현재 저장소에서 REAL KIS LIVE 주문이 활성화되어 있다(사용자 본인 계좌, high risk). 기본값은 fail-closed이며 다중 게이트(`LIVE_TRADING_ENABLED` + `LIVE_ORDER_SUBMIT_ENABLED` + `ENABLE_REAL_ORDER` + live 자격증명 + live host + per-order confirm + kill switch + max-notional) 뒤에서만 실제 주문이 나간다. 대상은 KRX 국내 현금 주문에 한정되며, real KIS API 대비 live 실행은 아직 미검증이므로 첫 주문은 최소 수량으로 확인한다.

이 프로그램은 단일 Windows .exe로 패키징된다: 하나의 FastAPI 프로세스(`app_main.py --host 127.0.0.1 --port 8000`)가 Next.js static export를 same-origin으로 서빙하고, pywebview 네이티브 창으로 표시된다. `launcher.py`는 단일 프로세스이며 별도 frontend 프로세스(`npm run start`/`next start`, :3000)는 없다. UI는 한국어, monospace + beige 라이트 테마에 라이트/다크 토글 슬라이더를 제공한다. 로그인은 로컬 JSON 기반(`backend/data/users.json`, PBKDF2-HMAC-SHA256, HMAC 30일 토큰, 사용자가 생성된 경우에만 인증 강제)이며 `/api/auth/*` 라우트와 프론트엔드 AuthGate/logout으로 동작한다. 설정은 UI에서 토글 가능하고 `backend/data/runtime_env.json`(allowlist 키, 마스킹된 값)에 영속화된다.

## 현재 상태

REAL KIS live 주문이 활성화되어 있으며, 모든 경로는 기본값에서 fail-closed다. `KisLiveOrderExecutor`가 paper mapper를 재사용하고 V->T TR ID로 전환하여 KRX 국내 현금 주문을 처리한다. live 실행은 real KIS API 대비 미검증 상태이므로 첫 주문은 최소 수량으로 검증한다.

| 항목 | 상태 |
|---|---|
| live status route | `/api/live/status` |
| live order status route | `/api/kis/orders/status` |
| live preview route | `/api/kis/orders/preview` |
| live submit route | `/api/kis/orders/submit` (다중 게이트 뒤 활성) |
| live cancel route | `/api/kis/orders/cancel` (다중 게이트 뒤 활성) |
| 실행기 | `KisLiveOrderExecutor` (paper mapper 재사용, V->T TR ID) |
| 대상 시장 | KRX 국내 현금 주문 한정 |
| WebSocket execution | 없음 |
| token raw persistence | 없음 |
| paper-to-live fallback | 없음 (각 모드 명시적) |

## Live 전환 전 필수 조건

| 영역 | 조건 |
|---|---|
| 게이트 | `LIVE_TRADING_ENABLED` + `LIVE_ORDER_SUBMIT_ENABLED` + `ENABLE_REAL_ORDER` + live 자격증명 + live host + per-order confirm + kill switch + max-notional |
| 환경 | paper, prod-readonly, prod-live 분리 |
| secrets | environment-level secret, raw value 출력 금지 |
| 주문 | idempotency key, duplicate guard, kill switch proof |
| 리스크 | 일손실, position, symbol, sector, strategy, notional limit |
| 감사 | redacted broker trace, event id, correlation id |
| 롤백 | kill switch, scheduler stop, notifier-only mode |
| 검증 | no-live regression, secret scan, paper soak 결과 |

## 3단계 선행 안전장치 Preflight

`LiveOrderSafetyService`는 아래 항목을 네트워크 호출 없이 검사한다. 하나라도 미충족이면 `tools/live_canary_preflight.py`는 `status=blocked`를 유지한다.

| 안전장치 | Preflight 입력 |
|---|---|
| Kill Switch | `LIVE_CANARY_KILL_SWITCH_READY` 또는 `LIVE_KILL_SWITCH_READY`, `LIVE_EMERGENCY_STOP_ARMED` |
| RateLimiter | `LIVE_RATE_LIMIT_PER_SECOND`, `LIVE_RATE_LIMIT_BURST` |
| Idempotency Key | `LIVE_IDEMPOTENCY_REQUIRED=true` |
| Audit Log | `LIVE_AUDIT_LOG_ENABLED=true`, `LIVE_AUDIT_REDACTION_ENABLED=true` |
| Max Order Notional | `LIVE_MAX_ORDER_NOTIONAL` |
| Blacklist | `LIVE_BLACKLIST_ENABLED=true`, `LIVE_SYMBOL_BLACKLIST` |
| Cooldown | `LIVE_ORDER_COOLDOWN_SECONDS` |
| Token Refresh | `LIVE_TOKEN_REFRESH_ENABLED=true`, `LIVE_TOKEN_REFRESH_PROCESS_ONLY=true`, live token refresh implementation proof |

`KisLiveOrderExecutor`와 live public route는 위 게이트가 모두 충족될 때 실제 submit/cancel을 수행한다. 게이트 중 하나라도 미충족이면 동일 경로가 fail-closed로 동작하여 `enabled=false`, `can_submit=false`, `can_cancel=false`, `network_call_performed=false`, `live_order_created=false` 형태의 safety boundary를 반환한다.

기존 `POST /api/broker/orders/preview`와 승인된 `/api/kis/orders/*` scaffold는 주문 후보별 안전장치 판정만 반환한다. optional `idempotency_key`를 받아 후보 주문의 blacklist, max notional, cooldown, idempotency blocker를 `live_order_safety`에 포함하며, `order_created=false`, `network_call_performed=false`를 유지한다.

`LiveRateLimiter`, `LiveIdempotencyGuard`, `LiveCooldownGuard`, `LiveOrderAuditService`는 단위 검증 가능하도록 분리되어 있다. 이 helper들은 process-local 평가와 redacted audit event 생성을 제공하며, audit DB 저장은 명시 호출 시에만 수행한다. 주문 route, live submit/cancel network call, live token refresh network call은 위 게이트가 충족된 경우에만 실제로 수행된다.

`LiveCanaryGovernanceService`는 별도 live canary 실행 전에 reviewer, `prod-live-isolated` 환경, rollback ready, kill switch ready, minimum-size 확인, rollback runbook proof를 검사한다. reviewer 원문은 응답에 남기지 않고 fingerprint만 반환한다.

`tools/kis_live_token_refresh_preflight.py`는 live token refresh real-call proof를 만들기 위한 별도 CLI다. 기본 실행은 preview-only이며 `--execute --confirm CONFIRM_KIS_LIVE_TOKEN_REFRESH`와 모든 refresh gate가 있을 때만 network call을 시도한다.

`tools/live_authority_approval_preflight.py`는 live submit/cancel authority 승인 증거를 no-network record로 남기는 CLI다. `--approve --confirm CONFIRM_LIVE_AUTHORITY_APPROVAL --operations submit,cancel`와 governance/safety gate를 통과시키며, 이 record 자체는 증거용 no-network 산출물이므로 `network_call_performed=false`, `live_order_created=false`, `order_cancelled=false`를 유지한다. 실제 주문 실행은 `KisLiveOrderExecutor`와 런타임 게이트가 담당한다.

`tools/live_phase3_completion_audit.py`는 redacted token refresh proof record를 `--token-refresh-record-path`로, submit/cancel authority approval record를 `--authority-record-path`로 읽어 proof gap summary에 반영한다. authority approval record는 증거 요약용이며, `live_submit_authority_present`/`live_cancel_authority_present` 완료 조건의 증빙 입력으로 사용된다.

## Phase 19 허용 범위

Phase 19는 live adapter scaffold와 regression 기반을 도입했다. 이후 이 기반 위에 live endpoint, live order mapper(paper mapper 재사용, V->T TR ID), live network call이 `KisLiveOrderExecutor`로 연결되어 게이트 뒤에서 활성화되었다.

## Phase 20 허용 범위

Phase 20은 controlled live canary다. 현재 REAL KIS live 주문이 활성화되어 있으나 다중 게이트 뒤에서만 동작하며, real KIS API 대비 미검증이므로 단일 전략, 단일 market(KRX 현금), minimum-size, 수동 확인(per-order confirm), 즉시 rollback(kill switch) 기준을 충족해야 한다. 첫 주문은 최소 수량으로 검증한다.

## 완료 판정

Phase 18 완료는 전환 조건과 안전장치 조건이 decision-complete로 문서화되는 것으로 판정한다. 현재는 그 조건 위에서 REAL KIS live 주문이 다중 게이트(fail-closed by default) 뒤로 활성화되어 있으며, real KIS API 대비 live 실행은 미검증이므로 첫 주문은 최소 수량으로 확인한다.
