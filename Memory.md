# Stock Analyst Auto Trading Memory

## Checkpoint

- [x] 현재 상태명: `Harden canslim_lite Strategy`
- [x] Phase 1 Backend Core MVP 구현
- [x] Phase 2 MVP Web Flow 구현
- [x] Phase 3A CSV validate/confirm import 구현
- [x] Phase 3B provider-neutral external daily OHLCV preview/confirm 구현
- [x] Phase 3C KIS read-only foundation 구현
- [x] Phase 3D broker safety scaffold 구현
- [x] Phase 3E-1 paper preview safety scaffold 구현
- [x] Phase 3F read-only data reliability 구현
- [x] Phase 3G hardened backtest execution model 구현
- [x] Phase 3H strategy explanation, optional filters, strategy registry 구현
- [x] Phase C 전략 9개 등록 및 hardening foundation 구현
- [x] Frontend default/available strategy selector 구현
- [x] 현재 브랜치: `main`

## 현재 프로젝트 상태

- Backend: FastAPI + SQLite, sample seed, CSV import, external daily OHLCV preview/confirm, KIS read-only foundation, broker safety scaffold, paper preview scaffold, data quality summary, hardened backtest execution model, strategy explanation contract, strategy metadata endpoint.
- Frontend: Next.js App Router, `/`, `/dashboard`, `/data`, `/screener`, `/reports`, `/backtest`, `/portfolio`, `/paper`, `/settings`; `/screener`, `/dashboard`, `/backtest`는 backend strategy metadata 기반 selector를 사용한다.
- Product state: 실주문 자동매매 엔진이 아니라 분석, 스크리닝, 백테스트, 리포트 중심 자동매매 보조 MVP.
- Strategy default: `trend_breakout`, `vcp_breakout`, `canslim_lite`, `new_high_breakout`, `pullback_20ema`.
- Strategy available: 기본 5개에 `momentum_rank`, `relative_strength_leader`, `darvas_box`, `stage_analysis_weekly`를 더해 명시 선택 시 screener/backtest 실행 가능.
- `trend_breakout`: 추세 정배열, RS, 52주 고점 근접, 실제 `breakout`, `market_regime_not_bear`, 거래량 급증을 기본 pass flag로 평가한다. `allow_neutral_market: true`가 기본이라 `neutral`은 통과, `bear`는 실패한다.
- `vcp_breakout`: 추세 정배열, ATR/std 변동성 축소, volume dry-up, pivot breakout, breakout volume, RS, `market_regime_not_bear`를 평가한다. Optional filter는 `sector_rs_filter_enabled`, `pivot_distance_limit_enabled`, `atr_risk_filter_enabled`로 제어한다.
- `canslim_lite`: EPS/매출 성장, RS, breakout, bull market에 더해 `technical_trend_filter_enabled=true` 기준 SMA 정배열과 `volume_confirmation_enabled=true` 기준 거래량 surge를 기본 평가한다. `sector_rs_filter_enabled=false`라 섹터 leadership은 기본 optional이다.
- `canslim_lite` PTI metadata: `fundamentals_available_asof`, `fundamentals_effective_date_available`, `pti_validation_status=pti_validation_not_available_in_current_mvp`를 additive로 반환한다. 현재 MVP에서는 완전한 point-in-time 검증을 주장하지 않으며 `no_lookahead_claim`은 쓰지 않는다.
- `backend/config/strategies.yaml`의 `common.hardening`은 공통 optional hardening 기본값과 legacy enable flag를 보관한다. 기본 enable flag는 false라 기존 default 동작을 과도하게 바꾸지 않는다.
- `StrategyResult` 기존 필드인 `pass_flags`, `failed_conditions`, `reason_summary`, `metadata` contract는 유지한다.
- `GET /api/screener/strategies`: `name`, `display_name`, `description`, `is_default`, `is_available`, `required_fields`, `limitations`를 반환한다.
- Screener explanation contract: `triggered_conditions`, `failed_conditions`, `score_breakdown`, `risk_flags`, `data_quality_flags`, `explanation`, `rationale`를 유지한다.
- API contract: `/api/screener/run`, `/api/backtest/run`, `/api/backtest/runs`, `/api/backtest/runs/{run_id}` 응답 shape와 metrics key/type은 유지한다.
- DB migration: root `alembic.ini`, initial revision `da9ab5998e36_initial_schema`, weekly column revision `c5b7d9a1e4f2_add_indicator_weekly_fields`, pullback EMA revision `f6d4a2c9e8b1_add_indicator_pullback_ema_fields`.

## 최근 변경 요약

- `backend/app/strategies/canslim_lite.py`: technical trend filter, volume confirmation, optional sector RS filter, ROE availability flag, PTI status metadata를 추가했다.
- `backend/config/strategies.yaml`: `canslim_lite.technical_trend_filter_enabled`, `volume_confirmation_enabled`, `volume_surge_multiple`, `sector_rs_filter_enabled`, `sector_rs_score_min` 기본값을 추가했다.
- `backend/tests/test_strategies.py`: CANSLIM SMA 정배열 실패, volume surge 실패, sector disabled pass, fundamentals missing fail, missing ROE quality flag, PTI metadata 테스트를 추가했다.
- `docs/VALIDATION.md`: Harden canslim_lite Strategy 최신 검증 결과로 압축 갱신했다.
- 제외 범위 유지: `earnings_events` 테이블, Fundamentals schema, provider 호출, 주문/broker 관련 변경 없음.

## 최신 검증 결과

- 2026-05-25 `.\.venv\Scripts\python.exe -m pytest backend/tests/test_strategies.py -q`: 89 passed in 32.42s.
- 2026-05-25 `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 189 passed in 84.04s.
- 2026-05-25 `npm.cmd run lint`: 통과.
- 2026-05-25 `npm.cmd exec tsc -- --noEmit`: 통과.
- 2026-05-25 `npm.cmd run build`: 통과.
- 2026-05-25 `npm.cmd audit --audit-level=moderate`: found 0 vulnerabilities.
- 2026-05-25 `git diff --check`: 통과.

## 불변 조건

- 실주문, 주문 취소, 체결, 계좌 이동, websocket, live broker 구현 금지.
- paper order/fill/position/audit mutation 구현 금지.
- KIS/KRX/yfinance network call, KIS token 발급/cache/credential 저장 금지.
- broker/order adapter import 또는 호출 금지.
- `earnings_events` 테이블 신규 추가 금지.
- Fundamentals schema 변경 금지.
- 신규 DB schema 변경은 Alembic revision과 검증 없이 금지.
- 기존 strategy registry 순서 변경 금지.
- 기존 `StrategyResult` 필드 제거 금지.
- 기존 screener/backtest API breaking change 금지.
- 기존 metrics key 제거, 타입 변경 금지.
- `orders_count == 0`, `paper_* == 0`, KIS/paper execution routes 404 유지.
- `npm audit fix --force`, Next.js downgrade, main 강제 push 금지.

## 다음 작업

- [ ] Phase 3I: weekly review report를 fixture 기반으로 검증한다.
- [ ] `canslim_lite` 강화 조건이 실데이터/백테스트에서 지나치게 좁아지는지 별도 샘플 검증한다.
- [ ] Strategy explanation contract와 `risk_metadata`, CANSLIM PTI metadata를 frontend에 표시할지 별도 범위로 검토한다.
- [ ] Phase 4A/4B broker 또는 live gate는 별도 승인 전까지 구현하지 않는다.
- [ ] 현재 작업트리는 기존 미커밋 변경이 다수 포함되어 있으므로 publish/commit 전 명시 파일 scope를 재확인한다.
