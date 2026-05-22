# Phase Plan Index

이 디렉터리는 단계별 개발 계획과 승인 경계를 관리한다. 현재 기준선은 `MVP v0.13 / Phase 3H Strategy Extension`이다.

## 관리 원칙

- `docs/plans/README.md`: 전체 Phase 순서, 현재 상태, 문서 링크를 관리한다.
- Phase별 상세 문서: 해당 Phase의 목표, 범위, 제외 범위, API/DB 변경, 테스트, 완료 기준을 관리한다.
- 현재 프로젝트 상태 요약은 `docs/PROJECT_STATUS.md`와 루트 `Memory.md`에 압축 갱신한다.
- 완료 검증 결과는 `docs/VALIDATION.md`에 최신 대표 결과만 남긴다.
- 실주문, 주문 취소, 체결, websocket, live broker, token 발급/cache, KIS credential 저장은 별도 승인 전까지 금지한다.

## 현재 기준

| 항목 | 값 |
|---|---|
| 현재 checkpoint | `MVP v0.13 Phase 3H Strategy Extension` |
| 현재 구현 완료 | Phase 3H |
| 다음 구현 후보 | Phase 3I |
| 핵심 안전 기준 | `orders_count == 0`, `paper_orders/fills/positions/audit_events == 0`, KIS/paper execution routes 404 |
| 상태 요약 문서 | `docs/PROJECT_STATUS.md` |
| 상세 검증 문서 | `docs/VALIDATION.md` |

## Phase 문서

| Phase | 상태 | 문서 | 핵심 범위 |
|---|---|---|---|
| Phase 3A | 완료 | `README.md`, `docs/VALIDATION.md` | CSV data quality validation and preview-confirm import |
| Phase 3B | 완료 | `README.md`, `docs/VALIDATION.md` | Provider-neutral external daily OHLCV preview-confirm flow |
| Phase 3C | 완료 | `README.md`, `docs/VALIDATION.md` | KIS read-only foundation |
| Phase 3D | 완료 | `README.md`, `docs/VALIDATION.md` | Broker safety scaffold |
| Phase 3E-1 | 완료 | `README.md`, `docs/VALIDATION.md` | Paper trading safety shell |
| Phase 3F | 완료 | `docs/plans/phase-3f-readonly-data-reliability.md` | Read-only data reliability, KIS/KRX fixture contract, data quality summary |
| Phase 3G-1 | 완료 | `README.md`, `docs/VALIDATION.md` | Backtest execution realism hardening |
| Phase 3G-2 | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md` | Liquidity participation cap and partial fill model |
| Phase 3G-3 | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md` | Adjusted price option, delisted/missing data forced exit metrics |
| Phase 3H | 완료 | `README.md`, `docs/VALIDATION.md`, `docs/PROJECT_STATUS.md` | Strategy explanation contract and conservative optional filters |
| Phase 3I | 권장 다음 단계 | 추후 작성 | Weekly review report |
| Phase 3J | 대기 | 추후 작성 | Portfolio-level risk guard |
| Phase 4A | 대기 | 추후 작성 | Broker paper adapter 후보, 별도 승인 필요 |
| Phase 4B | 대기 | 추후 작성 | Live gate design 후보, 별도 승인 필요 |

## 전체 우선순위

1. Phase 3I: weekly review report.
2. Phase 3J: portfolio-level risk guard.
3. Phase 4A: broker paper adapter 후보. 현재 안전 기준과 충돌하므로 별도 승인 없이 구현하지 않는다.
4. Phase 4B: live gate design 후보. 실주문 관련 기능은 별도 승인 없이 구현하지 않는다.
5. Backlog: earnings/event calendar, config registry/experiment tracking, 알림/운영 자동화.

## 안전 불변 조건

- `/api/broker/status`, `/api/broker/orders/preview`, `/api/paper/status`, `/api/paper/orders/preview`, `/paper`는 preview-only/fail-closed 상태로 유지한다.
- `POST /api/paper/orders`, fill simulator, paper mutation은 미구현 404 상태를 유지한다.
- KIS 주문, 계좌, 잔고, 체결, websocket, live broker route는 구현하지 않는다.
- token 발급, token cache, KIS credential 저장, broker network call은 금지한다.
- `orders_count == 0`을 유지한다.
- `paper_orders`, `paper_fills`, `paper_positions`, `paper_audit_events`는 0을 유지한다.
