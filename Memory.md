# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `KIS Paper Balance Inquiry Read-only`
- [x] 현재 version: `MVP v0.26.0`
- [x] 현재 branch: `feature/kis-paper-goal-phases` (baseline: `main`)
- [x] 최신 backend pytest: `342 passed`
- [x] 최신 frontend 검증: lint, typecheck, build 통과
- [x] 최신 secret scan: `NO_SECRET_FINDINGS`
- [x] 최신 diff check: `git diff --check` exit 0, CRLF warning만 있음

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, external daily OHLCV preview/confirm, KIS read-only foundation, broker safety scaffold, paper trading local lifecycle, report notification, paper bot scheduler, validation/report/backtest 기능.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/settings`.
- Paper trading은 여전히 실거래가 아니다. 실제 주문, 주문 취소, 체결, 계좌 자금 이동, live broker, websocket은 구현하지 않는다.
- `/api/paper/orders/submit`은 local `paper_orders` 전용이며 `confirm=true`, `idempotency_key`, kill-switch/config gate가 필요하다.
- `/api/paper/sync`는 KIS sync가 아니라 fail-closed no-op이다.
- `/api/paper/portfolio`는 기본 disabled/mock 상태에서 기존 `paper_portfolio_snapshots` fallback을 유지한다.
- KIS paper balance 조건이 모두 만족될 때만 `/uapi/domestic-stock/v1/trading/inquire-balance`를 `tr_id=VTTC8434R`로 read-only 호출한다.
- KIS paper balance 성공 응답은 `holdings`, `account_summary`, 기존 UI 호환 `snapshot`, `positions_summary`를 반환한다.
- KIS balance 경로는 `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCESS_TOKEN`, `KIS_ACCOUNT_NO`, `KIS_PRODUCT_CODE`를 env에서만 읽고 응답/로그/문서에는 raw 값을 남기지 않는다.
- `ENABLE_REAL_ORDER=true`이면 KIS balance client를 호출하지 않고 local snapshot fallback으로 차단한다.
- 실전투자 TR ID와 live base URL 경로는 사용하지 않는다.

## 최근 변경 요약

- `backend/app/services/kis_paper_balance.py`: KIS 모의투자 잔고조회 GET client, env credential 로딩, 실전 base URL 차단, output1/output2 mapping 추가.
- `backend/app/services/paper_sync_service.py`: `/api/paper/portfolio`에서 KIS paper balance 조건부 호출, 실패/비활성 시 local snapshot fallback 유지.
- `backend/app/services/paper_trading_service.py`, `backend/config/paper.yaml`: paper balance inquiry enable flag와 official balance endpoint confirmation flag 추가. 기본값은 모두 disabled.
- `.env.example`: `ENABLE_REAL_ORDER=false`, KIS access token/account/product/base URL placeholder 추가.
- `frontend/lib/api.ts`: KIS balance `holdings`, `account_summary`, `kis_balance` optional response type 추가.
- `backend/tests/test_kis_paper_balance.py`: required header/query mapping, disabled fallback, enabled paper mode client 호출, secret log 비노출, `ENABLE_REAL_ORDER` 차단 테스트 추가.
- `docs/VALIDATION.md`: 이번 KIS paper balance 검증 결과 추가.

## 최신 검증 결과

- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_kis_paper_balance.py backend/tests/test_paper_portfolio_api.py -q`: 7 passed in 0.96s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_no_live_trading_regression.py backend/tests/test_secret_redaction.py backend/tests/test_kis_paper_adapter.py -q`: 13 passed in 1.20s.
- 2026-05-27 `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 342 passed in 631.22s.
- 2026-05-27 `.\.venv\Scripts\python.exe tools\secret_scan.py`: `NO_SECRET_FINDINGS`.
- 2026-05-27 frontend `npm.cmd run lint`, `npm.cmd exec tsc -- --noEmit`, `npm.cmd run build`: 통과.
- 2026-05-27 `git diff --check`: 통과, CRLF warning만 있음.

## 주의 사항

- `paper.yaml`의 KIS balance 관련 flag는 기본 disabled다. 실제 KIS paper balance 조회를 켜려면 paper mode, network, balance inquiry, adapter enable, official balance endpoint confirmation을 모두 명시해야 한다.
- KIS credential과 access token은 env에서만 주입한다. 코드, fixture, 문서, 로그에 raw 값을 남기지 않는다.
- KIS balance 조회는 read-only다. 주문 API, 취소 API, 체결 조회 sync, paper fill/position mutation으로 확장하지 않는다.
- `ENABLE_REAL_ORDER=false`를 유지한다. true이면 KIS balance 조회도 차단된다.
- `.cache/kis/token.json` 같은 token cache 파일을 생성하지 않는다.
- frontend build 중 `.next\launcher-backend.err.log` EBUSY가 나면 오래 켜진 로컬 uvicorn/next 서버가 `.next` 로그를 잡고 있는지 먼저 확인한다.
- 테스트 실행으로 `backend/reports/strategy_validation_252d.json`이 갱신될 수 있으나, 이번 작업 범위 산출물이 아니면 남기지 않는다.

## 남은 작업

- [ ] KIS paper submit/cancel/sync network 구현은 계속 보류한다.
- [ ] 실제 KIS paper balance 운영 전 env credential 주입 방식과 token 발급/갱신 운영 절차를 별도 승인 후 정리한다.
- [ ] UI에서 KIS balance holdings 상세 목록을 보여줄지 별도 범위로 검토한다.
