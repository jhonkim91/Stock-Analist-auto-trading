# 개선 계획 (전략 엔진 · 프론트엔드 UI)

코드베이스 정밀 분석 결과를 바탕으로 한 우선순위별 개선 로드맵.
원칙: **live 안전게이트(실계좌 차단)와 기존 pytest(521건)를 깨지 않는 추가형(additive)·config 게이트 변경**만 권장.

---

## A. 이번에 반영한 변경 (프론트엔드, 자체 완결형)

1. **`frontend/components/mini-chart.tsx` 신규** — 의존성 없는 인라인 시각화 컴포넌트(`AllocationBars`). 평가금액 기준 비중 막대 + 손익률 색상.
2. **`frontend/app/portfolio/page.tsx`** — 그동안 받아오면서도 표시 안 하던 `holdings`(보유 종목)를 **포트폴리오 비중 카드**로 시각화. 상단에 **새로고침 버튼** 추가.

> API 계약·백엔드 무변경. `npm run lint && npm run build`로 최종 확인 권장(작업환경 파일동기화 제약으로 자동 검증은 생략).

---

## B. 전략 / 분석 엔진 개선 (백엔드, 우선순위순)

각 항목은 추가형 + config 기본 OFF로 설계해 기존 테스트를 보존하도록 권장.

1. **일별 시가평가(MTM) 에쿼티 커브** — `backend/app/services/backtest_service.py::_run_single_position_backtest` / `_metrics`.
   현재 에쿼티는 **청산일에만** 기록돼 `max_drawdown`·`sharpe`·`sortino`가 과소평가됨. 보유 구간 일별 종가 평가로 커브를 만들어 `max_drawdown_mtm` 등 **추가 지표**로 노출(기존 값 유지). → 정확도 개선 + 프론트 에쿼티 커브 차트의 데이터 소스가 됨.
2. **트레일링/본전 스탑** — `_exit_decision` + `RiskService`.
   API에 `trailing_stop_pct`/`trailing_high_price` 필드는 이미 있으나 **미구현**. 추세추종 전략 취지에 핵심. `risk.yaml` 플래그로 기본 OFF.
3. **스코어링 가중치 외부화** — `scoring_service.py::score`의 인라인 가중치(0.20/0.10 …)·정규화 상수를 `strategies.yaml`로 이동(기본값 동일 → 동작 불변).
4. **다종목 동시 보유 백테스트 일반화** — 단일 포지션 전략도 `_run_rank_portfolio_backtest`로 N개 동시 보유 가능하게(`max_positions` opt-in). 현재 7/9 전략이 매일 top-1만 사용해 신호 낭비.
5. **포트폴리오 히트/섹터 집중 한도** — `_portfolio_sized_risk`·`RiskService`에 총위험·섹터별 노출 상한(기본 무제한, config 게이트).
6. **레짐 전환 강제청산** — `_simulate_trade` 루프에서 보유 중 레짐이 bear로 바뀌면 청산(옵션).
7. **지표 추가(RSI/ADX/MACD)** — `_compute_symbol_indicators` + `IndicatorSnapshot` 컬럼(마이그레이션 필요). 순수 추가형.
8. **Sharpe/Sortino 무위험수익률 반영** — 현재 raw mean/std.

검증: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_strategies.py backend/tests/test_risk.py -q` (전체 suite는 ~14분).

---

## C. 프론트엔드 UI 개선 (추가 권장, 우선순위순)

1. **에쿼티 커브 + 드로다운 차트** (`app/backtest/page.tsx`) — 단, 현재 `/api/backtest/runs`는 집계 지표만 반환하므로 **백엔드에서 trade ledger/에쿼티 시계열을 노출하는 엔드포인트 추가가 선행**되어야 함(B-1과 연계).
2. **공용 상태 컴포넌트** — `LoadingState`/`ErrorState`/`EmptyState`로 페이지별 `-` 플레이스홀더·임시 문자열 대체(스켈레톤·재시도 버튼).
3. **`globals.css` 정리** — `~1125행` 이후 "목업 override" 블록이 앞부분 정의(button/.topbar/body 등)를 덮어씀. 중복 제거 또는 tokens/components 분리.
4. **원시 필드명 → 사람친화 라벨** — `close_vs_200dma`, `proposed_notional` 등을 매핑하는 `lib/labels.ts` 헬퍼. 한/영 카피 혼용 정리.
5. **수동 새로고침 + 폴링 훅** — 6개 페이지에 반복되는 `useEffect`+`loadX`를 `useApiResource` 훅으로 추출.
6. **사이드바 배지 라이브 연동** — `app-chrome.tsx` 43·50·197행 하드코딩(`"7 pass"`, `"!"`, `orders_count == 0`)을 실데이터로.
7. **다크 모드** — 기존 CSS 변수 위에 `prefers-color-scheme` 블록 추가(대부분 컴포넌트가 변수 사용 중).
8. **테이블 개선** — 정렬/페이지네이션/컬럼 툴팁, `run_id` 등 말줄임 silent truncation 보완.

---

## 안전 원칙 (필수)
- `paper_kis`에서만 주문 허용, live 차단 게이트(Phase 19/20) 절대 유지.
- 백엔드 변경은 추가형 + config 기본 OFF로 기존 테스트 보존.
- 키/토큰/계좌/chat id 하드코딩 금지(.env).
