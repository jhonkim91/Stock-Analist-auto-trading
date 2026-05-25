# Phase Plans

이 디렉터리는 단계별 개발 계획과 승인 경계를 관리한다. 현재 기준선은 `Phase C Strategy Hardening Foundation`이다.

## 문서 역할

- `docs/plans/README.md`: 전체 Phase 순서, 현재 상태, 문서 링크를 관리한다.
- 상세 Phase 계획은 필요한 경우 `docs/plans/phase-*.md`로 분리한다.
- 현재 프로젝트 상태 요약은 `docs/PROJECT_STATUS.md`와 루트 `Memory.md`에 압축 갱신한다.
- 완료 검증 결과는 `docs/VALIDATION.md`에 최신 대표 결과만 남긴다.

## 현재 기준

| 항목 | 값 |
|---|---|
| 현재 checkpoint | `Phase C Strategy Hardening Foundation` |
| 현재 구현 완료 | Phase C strategy hardening foundation |
| 다음 권장 Phase | `Phase 3I Weekly Review Report` |
| 상태 요약 문서 | `docs/PROJECT_STATUS.md` |
| 상세 검증 문서 | `docs/VALIDATION.md` |
| 프로젝트 메모리 | `Memory.md` |

## Phase Index

| Phase | 상태 | 문서 | 핵심 범위 |
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
| Phase 3I | 후보 | 신규 계획 문서 필요 | Weekly Review Report |
| Phase 4A/4B | 보류 | 별도 승인 필요 | broker 또는 live gate |

## 다음 후보

1. Phase 3I: weekly review report를 fixture 기반으로 검토한다.
2. Strategy hardening 조건을 기본 활성화할지는 별도 백테스트와 샘플 영향 검증 후 결정한다.
3. `metadata.risk_metadata`와 explanation contract를 frontend에 표시할지는 별도 UI 범위로 검토한다.
4. Phase 4A/4B broker 또는 live gate는 현재 안전 기준과 충돌하므로 별도 승인 없이 구현하지 않는다.

## 고정 안전 경계

- 실주문, 주문 취소, 체결, 계좌 이동, websocket, live broker 구현 금지.
- paper order/fill/position/audit mutation 구현 금지.
- KIS token 발급/cache/credential 저장 금지.
- 실제 KIS/KRX/yfinance network call 금지.
- `/api/broker/status`, `/api/broker/orders/preview`, `/api/paper/status`, `/api/paper/orders/preview`, `/paper`는 preview-only/fail-closed 상태로 유지한다.
- `POST /api/paper/orders`, fill simulator, paper mutation은 미구현 404 상태를 유지한다.
