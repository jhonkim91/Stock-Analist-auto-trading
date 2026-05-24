# Project Status

## 현재 기준

| 항목 | 값 |
|---|---|
| Version | `MVP v0.16` |
| Phase | `Phase C-6 pullback_20ema Strategy` |
| Branch | `main` |
| 상태 | 분석/스크리닝/백테스트/리포트 중심 자동매매 보조 MVP |
| 거래 상태 | 실거래 미구현, fail-closed, preview-only |
| 다음 권장 Phase | `Phase 3I Weekly Review Report` |

## 구현 완료 항목

- Phase 1: Backend Core MVP.
- Phase 2: MVP Web Flow.
- Phase 3A: CSV data quality validation and preview-confirm import.
- Phase 3B: provider-neutral external daily OHLCV preview-confirm flow.
- Phase 3C: KIS read-only foundation.
- Phase 3D: broker safety scaffold.
- Phase 3E-1: paper trading safety shell.
- Phase 3F: read-only data reliability, provider contract, KRX fixture contract, data quality summary.
- Phase 3G-1: backtest execution model hardening.
- Phase 3G-2: liquidity participation cap and partial fill model.
- Phase 3G-3: adjusted price option, delisted symbol forced exit, missing data forced exit metrics.
- Phase 3H: strategy explanation contract, conservative optional strategy filters, fixture tests, strategy registry.
- Phase C-1: `momentum_rank` available-only strategy.
- Phase C-2: `relative_strength_leader` available-only strategy.
- Phase C-3: `new_high_breakout` default and available strategy.
- Phase C-4: `darvas_box` available-only strategy.
- Phase C-5: `stage_analysis_weekly` available-only strategy and nullable weekly indicator fields.
- Phase C-6: `pullback_20ema` default and available strategy, nullable `low`/`ema20` indicator fields.
- GitHub Actions CI: backend pytest, frontend lint/typecheck/build.
- Alembic migration scaffold: initial schema, weekly indicator fields, pullback EMA fields.

## Phase C 전략 상태

- 기본 screener 전략은 `trend_breakout`, `vcp_breakout`, `canslim_lite`, `new_high_breakout`, `pullback_20ema` 5개다.
- `pullback_20ema`는 상승 추세 정배열, 20EMA 눌림목 touch, 종가 EMA20 회복, RS percentile, pullback volume, ATR risk 조건을 평가한다.
- `momentum_rank`, `relative_strength_leader`, `darvas_box`, `stage_analysis_weekly`는 available registry에 포함되며 명시 선택 시 screener/backtest에서 실행 가능하다.
- `IndicatorService`는 `ema20`을 `close.ewm(span=20, adjust=False, min_periods=20).mean()`으로 계산한다.
- `indicator_snapshot`에는 nullable `weekly_close`, `weekly_sma30`, `weekly_sma30_slope`, `low`, `ema20`이 추가되어 있다.
- 최신 Alembic head는 `f6d4a2c9e8b1_add_indicator_pullback_ema_fields`다.
- Screener 응답은 기존 explanation contract 필드를 제거하지 않는다.

## 미구현 항목

- 실제 주문, 주문 취소, 체결, 계좌, 예수금, websocket, live broker.
- paper order create, paper fill simulator, paper position mutation.
- KIS credential/token 저장, token 발급/refresh/cache, 실제 KIS API 호출.
- 실제 KRX/yfinance network fetch.
- 자동매매 scheduler, live broker adapter, AI prediction model.
- portfolio cash/position state, walk-forward validation.
- frontend strategy selector의 Phase C 전략 확장.

## 안전 제약사항

- broker/paper는 기본 deny, fail-closed, preview-only 정책을 유지한다.
- `orders_count == 0`을 유지한다.
- `paper_orders`, `paper_fills`, `paper_positions`, `paper_audit_events` row count는 0을 유지한다.
- `POST /api/paper/orders`, `POST /api/paper/fill-simulator/run`, `/api/kis/orders/*`, `/api/kis/broker/*`, `/api/kis/websocket/*`는 미등록 404 상태를 유지한다.
- KIS token cache 파일 `.cache/kis/token.json`은 생성하지 않는다.
- secret, token, account/header/raw credential 값을 코드, 문서, 로그, API 응답에 노출하지 않는다.

## 검증 명령

Backend:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

Phase C strategy:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_indicators.py backend/tests/test_strategies.py backend/tests/test_alembic_migrations.py -q
```

Broker/paper/KIS/backtest safety:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3c_kis_readonly.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py backend/tests/test_phase3g_backtest_execution_model.py -q
```

Frontend:

```powershell
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
```

Alembic migration:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_alembic_migrations.py -q
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

## 다음 권장 Phase

Phase 3I에서 weekly review report를 검토한다. 기존 API, safety contract, no real-order 정책은 유지하고 fixture 기반 검증을 우선한다.
