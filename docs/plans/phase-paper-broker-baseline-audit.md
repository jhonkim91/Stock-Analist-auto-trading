# KIS Paper Broker Phase 0 Baseline Audit

## 목적

KIS paper-trading 구현을 시작하기 전 현재 `main` 기준선을 확정하고, stale 문서 충돌을 명시적으로 정리한다. 이 문서는 Phase 0 산출물이며 Phase 1 구현 범위를 포함하지 않는다.

## 범위

- 기준 브랜치: `main`
- 기준 HEAD: `bfcb1691e56dbdbbfc18b043bc65ec447acafa3e`
- 검토 문서: `goal.md`, `README.md`, `docs/PROJECT_STATUS.md`, `docs/VALIDATION.md`, `docs/DB_MIGRATION.md`, `docs/plans/README.md`, `Memory.md`
- 검토 코드: broker/paper/KIS router, safety service, paper table model, Alembic head

## 소스 오브 트루스

| 항목 | 기준 |
|---|---|
| 현재 제품 상태 | `docs/PROJECT_STATUS.md` |
| 최신 검증 상태 | `docs/VALIDATION.md` |
| 실행/운영 주의사항 | `Memory.md` |
| Phase 0 목표와 금지 범위 | `goal.md` |
| KIS paper endpoint 세부값 | 공식 문서에서 완전 확인된 항목만 사용, 미확인은 `확인 필요` |

`README.md`와 `docs/plans/README.md`가 위 문서와 충돌하면 `docs/PROJECT_STATUS.md`와 `docs/VALIDATION.md`를 우선한다.

## 기준선 요약

| 항목 | 현재 확인 결과 |
|---|---|
| Version | `MVP v0.24.0` |
| Phase | `Factor/Filter Attribution Minimal Integration` |
| 거래 상태 | fail-closed, preview-only, 실거래 미구현 |
| KIS 상태 | read-only foundation만 구현, 실제 KIS API 호출/토큰 발급/credential 저장 없음 |
| Broker 상태 | `/api/broker/status`, `/api/broker/orders/preview`만 fail-closed dry-run |
| Paper 상태 | `/api/paper/status`, `/api/paper/orders/preview`만 fail-closed dry-run |
| 미등록 execution route | `POST /api/paper/orders`, `POST /api/paper/fill-simulator/run`, `/api/kis/orders/*`, `/api/kis/broker/*`, `/api/kis/websocket/*`는 404 유지 |
| DB 상태 | `paper_orders`, `paper_fills`, `paper_positions`, `paper_audit_events` 모델은 있으나 현재 service는 write disabled |
| Alembic head | `f7a8b9c0d1e2_add_strategy_parameter_snapshots` |

## Stale 문서 조정

| 문서 | 확인된 stale 항목 | Phase 0 조치 |
|---|---|---|
| `README.md` | `MVP v0.21.0`, `Validation Framework Scaffold`, `287 passed`, 이전 next phase 표기 | 현재 source of truth인 `MVP v0.24.0`, `Factor/Filter Attribution Minimal Integration`, 최신 검증/다음 단계 표기로 갱신 |
| `docs/plans/README.md` | 현재 기준선이 `Validation Framework Scaffold`로 남아 있고 최신 단계가 누락됨 | Phase index에 최근 validation 단계와 KIS paper Phase 0 산출물을 추가 |
| `docs/DB_MIGRATION.md` | Alembic head가 `e5f6a7b8c9d0`로 남아 있음 | 실제 `alembic heads` 결과인 `f7a8b9c0d1e2`로 갱신, Phase 0 schema 변경 없음 명시 |
| `docs/PROJECT_STATUS.md` | paper broker baseline audit 상태가 없음 | Phase 0 완료 상태와 Phase 1 미착수 경계를 추가 |
| `docs/VALIDATION.md` | Phase 0 safety suite 결과가 없음 | Phase 0 지정 검증 결과를 최신 검증 결과로 기록 |
| `Memory.md` | Phase 0 baseline audit가 없음 | 다음 작업자가 이어갈 수 있도록 현재 상태와 검증 결과만 압축 갱신 |

## KIS 공식 문서 확인 정책

- 2026-05-27 기준 공식 KIS Developers 포털은 REST 방식, WebSocket 방식, OAuth, 국내주식 주문/계좌 문서 카테고리를 제공한다.
- 정적 문서 화면에서 `Method`, `URL`, `실전 Domain`, `모의 Domain`, `실전 TR ID`, `모의 TR ID` 항목 존재는 확인되지만, Phase 0에서는 각 paper request/response field를 구현 사양으로 채택하지 않는다.
- 미확인 항목은 `docs/KIS_PAPER_API_MATRIX.md`에 `확인 필요`로 표시한다.
- 비공식 블로그, 기억 기반 TR-ID, 샘플 코드 추정값은 구현 근거로 사용하지 않는다.

## Phase 0 안전 결론

- 런타임 코드, API endpoint, DB schema는 변경하지 않았다.
- 기존 preview-only/fail-closed 동작을 완화하지 않았다.
- paper submit/cancel/sync, notification, scheduler, frontend paper controls 구현은 시작하지 않았다.
- Phase 1 진입은 별도 실행에서만 가능하다.

## Phase 0 검증 명령

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3c_kis_readonly.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3d_broker_safety.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3e_paper_safety.py -q
git diff --check
```

최신 실행 결과는 `docs/VALIDATION.md`를 기준으로 본다.
