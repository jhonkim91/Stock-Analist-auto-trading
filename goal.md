# Goal: Project Reset - Telegram + KIS Paper Trading Bot

## 목표

이 저장소의 방향을 기존 분석 보조 MVP에서 `종목 분석 + 텔레그램 리포트 + KIS 모의투자 자동매매봇`으로 전환한다. 기존 OHLCV, indicator, screener, backtest, report, portfolio 기능은 보존하고, KIS paper 계좌에서만 주문/체결/잔고/포지션 갱신을 허용한다.

## 실행 모드

| 모드 | 목적 | 주문/체결 허용 |
|---|---|---|
| `analysis_only` | 로컬 DB 기반 분석, 스크리너, 백테스트, 리포트 | 불가 |
| `telegram_report` | Telegram 명령, daily/weekly 리포트 전송 | 불가 |
| `paper_kis` | KIS 모의투자 API 기반 주문, 체결 동기화, 포지션 갱신 | KIS paper만 허용 |
| `live_disabled` | 실계좌 endpoint/config 존재 여부와 무관하게 live 주문 차단 | 불가 |

기본 목표 모드는 `paper_kis`다.

## Legacy Live Gate

이 리셋은 기존 live 안전 작업을 삭제하지 않는다. Phase 19/20의 실계좌 차단 계약은 보존하며, 새 목표의 `paper_kis` 허용 범위와 분리한다.

| Phase | 상태 | 기준 |
|---|---|---|
| Phase 19 | 완료 | disabled live adapter scaffold 유지 |
| Phase 20 | route scaffold 차단 | live public route scaffold는 등록됐지만 network call, live submit 가능 상태, 실계좌 주문/취소/체결은 금지한다 |

실계좌 주문은 사용자의 별도 명시 승인 없이는 계속 `live_disabled`로 차단한다.

## 현재 기준

- Backend: FastAPI + SQLite + Alembic.
- Frontend: Next.js App Router.
- 보존 기능: data, indicators, market, instruments, screener, reports, backtest, portfolio, broker, paper, kis, settings.
- 전략 registry: `trend_breakout`, `vcp_breakout`, `canslim_lite`, `new_high_breakout`, `pullback_20ema`, `momentum_rank`, `relative_strength_leader`, `darvas_box`, `stage_analysis_weekly`.
- paper 저장소: `PaperOrder`, `PaperFill`, `PaperPosition`, `PaperAuditEvent`를 KIS paper 상태 mirror로 재사용한다.
- 실계좌 live 자동매매는 이번 목표가 아니다.

## Phase

| Phase | 상태 | 완료 기준 |
|---|---|---|
| 1. 목표/상태 리셋 | 진행 중 | `goal.md`, `Memory.md`, `docs/PROJECT_STATUS.md`, `.env.example`이 새 실행 모드를 반영 |
| 2. KIS token/config | 진행 중 | paper token issue/refresh/cache skeleton, live endpoint disabled |
| 3. 종목 분석 API | 진행 중 | KIS quote 우선, DB fallback 종목 상세 API |
| 4. Telegram bot | 진행 중 | `/start`, `/help`, `/status`, `/search`, `/report`, `/portfolio`, `/rank`, `/stop`, `/buy`, `/sell`, `/orders` command dispatcher |
| 5. KIS paper 주문 | 진행 중 | buy/sell/order/cancel skeleton, idempotency, audit, paper-only guard |
| 6. 자동매매 loop | 진행 중 | screener/watchlist 후보, stop-loss, trailing stop, MA cross 감시, 기본 OFF, bounded runner/stop-file 정책 |
| 7. 운영 검증 | 진행 중 | backend pytest, secret scan, runbook, Telegram/KIS paper dry-run |

## 안전장치

- `paper_kis` 모드에서만 paper 주문 생성과 KIS paper adapter 호출을 허용한다.
- `kill_switch`, `max_order_notional`, `max_order_qty`, `max_open_positions`, `blacklist`, `cooldown`은 유지한다.
- 안전장치는 paper 주문을 무조건 막는 절대 금지가 아니라 조건부 allow/deny gate로 동작한다.
- 모든 주문/취소/체결/자동매매 판단에는 `idempotency_key`와 audit log를 적용한다.
- legacy `orders` table은 live/mock broker 주문 저장소로 쓰지 않으며, paper 주문은 `paper_orders`에 저장한다.
- KIS/Telegram key, token, account, chat id는 코드와 문서에 하드코딩하지 않는다.

## 검증 기준

- 기존 backend pytest가 깨지지 않아야 한다.
- 신규 테스트는 token config/cache load, Telegram command parsing, stock search DB fallback, mock KIS paper order preview/create, kill switch, blacklist, cooldown을 포함한다.
- 테스트는 실제 KIS live 주문 또는 실계좌 호출을 실행하지 않는다.
- README 또는 docs에는 실행 방법과 환경 변수 기준을 남긴다.
