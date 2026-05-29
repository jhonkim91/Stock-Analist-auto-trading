# Live Trading Readiness Design

## 핵심 요약

이 문서는 `goal.md` Phase 18 범위의 설계 전용 산출물이다. 현재 저장소에서 live trading은 구현, 실행, endpoint 호출 모두 금지된다. Phase 19와 Phase 20은 별도 명시 승인 전까지 진행하지 않는다.

## 현재 금지 상태

| 항목 | 상태 |
|---|---|
| live submit route | 없음 |
| live cancel route | 없음 |
| live broker fallback | 없음 |
| WebSocket execution | 없음 |
| 실계좌 체결 처리 | 없음 |
| token raw persistence | 없음 |
| paper-to-live fallback | 금지 |

## Live 전환 전 필수 조건

| 영역 | 조건 |
|---|---|
| 승인 | 사용자 별도 명시 승인, 실행 직전 human confirmation |
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

현재 live token refresh는 `KisLiveTokenRefreshService`에 gated scaffold만 있으며 real KIS 호출 proof가 없다. live adapter는 submit/cancel safety boundary를 반환하지만 `enabled=false`, `can_submit=false`, `can_cancel=false`, `network_enabled=false`로 고정되어 있고, live public route도 없으므로 3단계 완료 조건은 충족되지 않는다.

기존 `POST /api/broker/orders/preview`는 새 live route 없이 주문 후보별 안전장치 판정만 반환한다. optional `idempotency_key`를 받아 후보 주문의 blacklist, max notional, cooldown, idempotency blocker를 `live_order_safety`에 포함하며, `order_created=false`, `network_call_performed=false`를 유지한다.

`LiveRateLimiter`, `LiveIdempotencyGuard`, `LiveCooldownGuard`, `LiveOrderAuditService`는 실제 live 주문 adapter가 붙기 전에도 단위 검증 가능하도록 분리되어 있다. 현재 이 helper들은 process-local 평가와 redacted audit event 생성을 제공하며, audit DB 저장은 명시 호출 시에만 수행한다. 주문 route, live submit/cancel network call, live token refresh network call은 기본값에서 열지 않는다.

## Phase 19 허용 범위

Phase 19는 disabled live adapter scaffold와 no-live regression만 허용한다. live endpoint URL, live order mapper, live route, live network call은 넣지 않는다.

## Phase 20 허용 범위

Phase 20은 별도 승인형 controlled live canary다. 승인 없이는 시작하지 않는다. 승인 후에도 단일 전략, 단일 market, minimum-size, 수동 확인, 즉시 rollback 기준으로 제한한다.

## 완료 판정

Phase 18 완료는 live 기능 구현이 아니라, 전환 조건과 금지 조건이 decision-complete로 문서화되고 no-live 상태가 유지되는 것으로 판정한다.
