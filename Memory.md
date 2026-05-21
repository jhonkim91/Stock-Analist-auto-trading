# Stock Analyst Auto Trading Memory

## 현재 프로젝트 상태

- [x] Phase 1 Backend Core MVP 구현
- [x] Phase 2 MVP Web Flow 구현
- [x] Phase 2 마감 QA 완료
- [x] Dashboard 카드형 실행 화면 및 CSV import UI
- [x] Screener 필터/정렬/상세 패널
- [x] Reports 목록/상세/preview/raw/download
- [x] Backtest run 목록/metrics/전략 비교 table
- [x] Portfolio mock/synthetic risk 화면
- [x] Settings read-only config 화면
- [x] Backend CORS 로컬 프런트엔드 origin 허용
- [x] pytest 전용 `backend/data/test_app.db` 분리
- [x] npm audit 0 vulnerabilities
- [x] `AGENTS.md` 프로젝트 운영 지침 확장

## 주의 사항

- 외부 API 연동, 실제 주문, paper/live broker, 실시간 websocket, AI 예측 모델은 구현하지 않는다.
- Mock Broker는 preview-only이며 주문 row를 생성하지 않는다.
- `orders_count == 0`은 Phase 2 검증 기준이다.
- 데이터 입력은 deterministic sample seed와 CSV import만 허용한다.
- CSV import 필수 컬럼은 `symbol`, `trade_date`, `open`, `high`, `low`, `close`, `volume`이다.
- CSV import 선택 컬럼은 `turnover_value`, `market`, `provider`, `adj_close`이다.
- 동일 `symbol + trade_date` CSV는 insert가 아니라 update 처리한다.
- `backend/config/*.yaml`은 `/api/settings`에서 read-only로만 보여주며 `.env`는 읽거나 반환하지 않는다.
- 8000/3000 포트 충돌 시 backend 8001, frontend 3001을 사용하고 `frontend/.env.local`의 `NEXT_PUBLIC_API_BASE_URL`을 8001로 맞춘 뒤 다시 build한다.
- Next.js public env는 production build에 포함되므로 `.env.local` 변경 후 `npm.cmd run build`가 필요하다.
- `frontend/package.json`은 `postcss@8.5.15` override로 Next transitive audit advisory를 막는다.

## 최신 검증 결과

- 2026-05-21 Phase 2 browser QA: Dashboard actions, CSV import, Screener, Reports, Backtest, Portfolio, Settings 통과
- 2026-05-21 Preview Mock Order 후 `orders_count == 0`
- 2026-05-21 `.\.venv\Scripts\python.exe -m pytest backend/tests`: 21 passed in 72.11s
- 2026-05-21 `npm.cmd run lint`: 통과
- 2026-05-21 `npm.cmd run build`: Next.js 16.2.6 production build 통과
- 2026-05-21 `npm.cmd audit --audit-level=moderate`: found 0 vulnerabilities
- 2026-05-21 `npm.cmd exec tsc -- --noEmit`: 통과
- 2026-05-21 post-restore browser smoke: `/dashboard`, `/reports`, `/backtest` 통과
- 2026-05-21 `rg -n "Repo Layout|Backend 실행 방법|Frontend 실행 방법|Test / Lint / Build|Coding Conventions|절대 하지 말아야 할 것|완료 기준|검증 방법" AGENTS.md`: AGENTS 필수 섹션 확인 통과

## 최신 DB count

- symbol_count: 15
- daily_ohlcv_count: 4,800
- index_ohlcv_count: 320
- sector_ohlcv_count: 2,880
- fundamentals_count: 30
- indicator_snapshot_count: 4,800
- screen_results_count: 45
- reports_count: 1
- backtest_runs_count: 1
- orders_count: 0
- latest_trade_date: 2026-05-20
- latest_indicator_date: 2026-05-20
- latest_screen_date: 2026-05-20

## 변경 파일 요약

- Backend: `backend/app/main.py`
- Tests: `backend/tests/test_api_smoke.py`, `backend/tests/conftest.py`
- Frontend: `frontend/app/dashboard/DashboardClient.tsx`, `frontend/package.json`, `frontend/package-lock.json`, `frontend/.env.local.example`, `frontend/.env.local`
- Docs/config: `AGENTS.md`, `.gitignore`, `README.md`, `docs/VALIDATION.md`, `Memory.md`

## 다음 작업

- Phase 3은 외부 API, paper/live broker, 실시간 시세, 보안/리스크 정책을 별도 설계 후 진행한다.
- Phase 3 진입 전 실제 주문 기능 없음, preview-only 정책, CSV/sample-only 입력 제약을 유지한다.
