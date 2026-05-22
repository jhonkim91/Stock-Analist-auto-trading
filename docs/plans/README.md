# Phase Plan Index

이 디렉터리는 단계별 개발 계획과 승인 경계를 관리한다.

## 관리 원칙

- `docs/plans/README.md`: 전체 Phase 순서, 현재 상태, 문서 링크를 관리한다.
- Phase별 상세 문서: 해당 Phase의 목표, 범위, 제외 범위, API/DB 변경, 테스트, 완료 기준을 관리한다.
- 완료 검증 결과는 `docs/VALIDATION.md`에 최신 대표 결과만 남긴다.
- 현재 프로젝트 상태 요약은 루트 `Memory.md`에 압축 갱신한다.
- 실주문, 주문 취소, 체결, websocket, live broker, token 발급/cache, KIS credential 저장은 별도 승인 전까지 금지한다.

## 현재 기준

| 항목 | 값 |
|---|---|
| 현재 checkpoint | `MVP v0.8 Phase 3F-1 read-only data provider contract` |
| 현재 구현 완료 | Phase 3F-1 |
| 다음 구현 후보 | Phase 3F-2 |
| 핵심 안전 기준 | `orders_count == 0`, `paper_orders/fills/positions/audit_events == 0` |
| 상세 검증 문서 | `docs/VALIDATION.md` |

## Phase 문서

| Phase | 상태 | 문서 | 핵심 범위 |
|---|---|---|---|
| Phase 3E-1 | 완료 | `README.md`, `docs/VALIDATION.md` | Paper trading safety shell |
| Phase 3F | 진행 중 | `docs/plans/phase-3f-readonly-data-reliability.md` | 실데이터 read-only adapter 기반 데이터 신뢰성 보강 |
| Phase 3G | 대기 | 추후 작성 | 백테스트 현실성 보강 |
| Phase 3H | 대기 | 추후 작성 | 전략 확장 |
| Phase 3I | 대기 | 추후 작성 | Weekly review report |
| Phase 3J | 대기 | 추후 작성 | Portfolio-level risk guard |
| Phase 4A | 대기 | 추후 작성 | Broker paper adapter |
| Phase 4B | 대기 | 추후 작성 | Live gate design |

## 전체 우선순위

1. Phase 3F: 실데이터 read-only adapter 기반 데이터 신뢰성 보강
2. Phase 3G: 백테스트 현실성 보강
3. Phase 3H: 전략 확장
4. Phase 3I: weekly review report
5. Phase 3J: portfolio-level risk guard
6. Phase 4A: broker paper adapter
7. Phase 4B: live gate design
8. Backlog: earnings/event calendar, Alembic migration 검토, config registry/experiment tracking, 알림/운영 자동화

## 안전 불변 조건

- `/api/paper/status`, `/api/paper/orders/preview`, `/paper`는 유지한다.
- `POST /api/paper/orders`, fill simulator, paper mutation은 미구현 상태를 유지한다.
- KIS 주문, 계좌, 잔고, 체결, websocket, live broker route는 구현하지 않는다.
- token 발급, token cache, KIS credential 저장, broker network call은 금지한다.
- `orders_count == 0`을 유지한다.
- `paper_orders`, `paper_fills`, `paper_positions`, `paper_audit_events`는 0을 유지한다.
