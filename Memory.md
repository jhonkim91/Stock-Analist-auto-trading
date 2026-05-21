# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `MVP v0.2 checkpoint`
- [x] Phase 1 Backend Core MVP 구현
- [x] Phase 2 MVP Web Flow 구현
- [x] Phase 2 마감 QA 완료
- [x] GitHub 초기 publish 완료: `jhonkim91/Stock-Analist-auto-trading`
- [x] local `main` tracks `origin/main`

## 현재 프로젝트 상태

- Dashboard: backend health, data status, seed, indicators, screener, report, backtest, mock preview, CSV import UI
- Screener: `strategy_name`, `passed`, `grade`, `symbol/name` 검색, `total_score`/`reward_risk_ratio` 정렬, row 상세, `pass_flags`/`failed_conditions` 접기/펼치기
- Reports: 목록, 상세, Markdown preview/raw/download, UTF-8 한글 다운로드 확인
- Backtest: run 목록, metrics 카드, 전략 비교 table
- Portfolio: mock/synthetic risk summary
- Settings: `backend/config/*.yaml` read-only 표시, 민감 키워드 미노출
- Backend: 3000/3001 로컬 frontend origin CORS 허용
- Tests: pytest 전용 `backend/data/test_app.db` 사용
- Frontend security: `postcss@8.5.15` override로 `npm audit` 0 vulnerabilities

## Phase 3 전 파일 목록

- 추적 파일 수: 90개
- Root/docs: `.env.example`, `.gitignore`, `AGENTS.md`, `README.md`, `Memory.md`, `requirements.txt`, `deep-research-report.md`, `docs/VALIDATION.md`
- Backend config/data/report placeholders: `backend/config/*.yaml`, `backend/data/.gitkeep`, `backend/reports/.gitkeep`
- Backend app: `backend/app/main.py`, `api/*.py`, `core/*.py`, `models/*.py`, `repositories/*.py`, `services/*.py`, `strategies/*.py`, `utils/*.py`
- Backend tests: `backend/tests/conftest.py`, `backend/tests/test_*.py`, `backend/tests/fixtures/sample_daily_ohlcv.csv`
- Frontend config: `frontend/package.json`, `frontend/package-lock.json`, `frontend/tsconfig.json`, `frontend/next.config.mjs`, `frontend/eslint.config.mjs`, `frontend/next-env.d.ts`
- Frontend env example: `frontend/.env.local.example`만 Git 추적 대상
- Frontend app/lib: `frontend/app/**`, `frontend/lib/api.ts`

## Env / 공유 파일 상태

- `.gitignore`에 `.env*.local`이 포함되어 있다.
- `frontend/.env.local`은 local-only ignored file이며 Git 추적 대상이 아니다.
- Git 추적 env 파일은 `frontend/.env.local.example` 하나뿐이다.
- `backend/data/*.db`, `backend/reports/*.md`, `.next`, `node_modules`, `test-results`, `*.tsbuildinfo`는 ignored 상태다.

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
- 2026-05-21 checkpoint 확인: `frontend/.env.local` ignored, Git 추적 env 파일은 `frontend/.env.local.example` 하나뿐

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

## 주의 사항

- 외부 API 연동, 실제 주문, paper/live broker, 실시간 websocket, AI 예측 모델은 구현하지 않는다.
- Mock Broker는 preview-only이며 주문 row를 생성하지 않는다.
- Phase 2 기준인 `orders_count == 0`을 깨뜨리지 않는다.
- 데이터 입력은 deterministic sample seed와 CSV import만 허용한다.
- CSV import 필수 컬럼은 `symbol`, `trade_date`, `open`, `high`, `low`, `close`, `volume`이다.
- 동일 `symbol + trade_date` CSV는 insert가 아니라 update 처리한다.
- `backend/config/*.yaml`은 `/api/settings`에서 read-only로만 보여주며 `.env`는 읽거나 반환하지 않는다.
- 8000/3000 포트 충돌 시 backend 8001, frontend 3001을 사용하고 `frontend/.env.local`의 `NEXT_PUBLIC_API_BASE_URL`을 8001로 맞춘 뒤 다시 build한다.
- Next.js public env는 production build에 포함되므로 `.env.local` 변경 후 `npm.cmd run build`가 필요하다.

## 다음 작업

- Phase 3은 외부 API, paper/live broker, 실시간 시세, 보안/리스크 정책을 별도 설계 후 진행한다.
- Phase 3 진입 전 실제 주문 기능 없음, preview-only 정책, CSV/sample-only 입력 제약을 유지한다.
