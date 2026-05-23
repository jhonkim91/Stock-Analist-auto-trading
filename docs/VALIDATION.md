# Validation

## 최신 검증 결과

검증 기준일: 2026-05-23

Checkpoint: `Phase C-3 new_high_breakout Strategy`

기준 브랜치: `main`

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase C-3 targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_strategies.py backend/tests/test_backtest.py -q`: 44 passed |
| Backend full pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests`: 122 passed |
| Frontend lint | 통과 | `cd frontend && npm.cmd run lint` |
| Frontend typecheck | 통과 | `cd frontend && npm.cmd exec tsc -- --noEmit` |
| Frontend production build | 통과 | `cd frontend && npm.cmd run build`: Next.js 16.2.6 production build |
| Strategy registry contract | 통과 | 기본 전략은 `trend_breakout`, `vcp_breakout`, `canslim_lite`, `new_high_breakout` 4개. `momentum_rank`, `relative_strength_leader`는 available registry와 명시 실행 경로 유지 |
| Screener/Backtest execution | 통과 | `new_high_breakout` 기본 screener 실행, `strategies=["new_high_breakout"]`, `strategy_name="new_high_breakout"` 실행 가능 |
| Screener explanation contract | 통과 | `triggered_conditions`, `failed_conditions`, `score_breakdown`, `data_quality_flags`, `explanation`, `rationale` 유지 |
| API/DB contract | 통과 | DB schema, screener/backtest API response shape, backtest metrics key/type 변경 없음 |
| Safety invariant | 통과 | 실주문, paper mutation, KIS/KRX network, token/cache/credential 저장 구현 없음 |

## 표준 검증 명령

Phase C strategy targeted suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_strategies.py backend/tests/test_backtest.py -q
```

Backend full suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests
```

Frontend:

```powershell
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
```

## Phase C-3 new_high_breakout Strategy

변경 범위:

- `backend/app/strategies/new_high_breakout.py`에 `NewHighBreakoutStrategy`를 추가했다.
- `new_high_breakout`은 `indicator_snapshot` 기존 필드만 사용하며 DB schema 변경이 없다.
- 사용 조건은 `high_52w` 존재, `close >= high_52w * new_high_threshold`, `breakout=true`, `volume >= volume_ma50 * volume_surge_multiple`, `rs_percentile`, `close > sma50 > sma150 > sma200`이다.
- `turnover_value`는 전략 내부 조건이 아니라 기존 common filter의 `liquidity_ok`에서 처리한다.
- `distance_from_52w_high`, `volume_ratio_50`은 재계산하지 않고 strategy별 `data_quality_flags`로 노출한다.
- `backend/config/strategies.yaml`에 `new_high_breakout` threshold를 추가했다.
- `DEFAULT_STRATEGY_NAMES`와 `ScreenerRunRequest` 기본값은 4개 전략으로 확장했다.
- Screener 응답 직렬화 시 `new_high_breakout` 결과에는 strategy별 `data_quality_flags`를 기존 `data_quality_flags` 객체에 병합한다.

Config:

```yaml
new_high_breakout:
  new_high_threshold: 0.995
  volume_surge_multiple: 1.5
  rs_percentile_min: 80
```

추가 테스트:

- 신고가 근접 breakout fixture pass.
- `close == high_52w * 0.995` threshold boundary pass.
- `high_52w=None` fail 및 `data_quality_flags.high_52w_available=false`.
- volume surge 부족 fail.
- breakout false fail.
- default registry와 `ScreenerRunRequest` 기본값에 `new_high_breakout` 포함.
- available registry에는 `new_high_breakout`, `momentum_rank`, `relative_strength_leader` 포함.
- `ScreenerService.run()` 기본 실행에 `new_high_breakout` 포함.
- `ScreenerService.run(strategies=["new_high_breakout"])` 명시 실행과 응답 contract 확인.
- `BacktestService.run("new_high_breakout")` 명시 실행.

## Safety Contract

| 항목 | 상태 |
|---|---|
| DB table/column 변경 | 없음 |
| Alembic revision 추가 | 없음 |
| screener/backtest API contract 변경 | 기존 필드 제거 없음 |
| backtest 실행/체결 모델 변경 | 없음 |
| 기본 screener 전략 | 4개로 확장: `trend_breakout`, `vcp_breakout`, `canslim_lite`, `new_high_breakout` |
| 실주문, 주문 취소, 체결, 계좌 이동 | 없음 |
| paper order/fill/position/audit mutation | 없음 |
| KIS/KRX/yfinance network call | 없음 |
| token/cache/credential 저장 | 없음 |

## 제외 범위

- DB schema 변경과 migration을 만들지 않았다.
- broker, paper, KIS, KRX runtime 동작을 추가하지 않았다.
- 기존 backtest metrics key/type을 변경하지 않았다.
- `BacktestRunRequest.strategy_name` 기본값은 `trend_breakout`으로 유지했다.
- frontend dropdown 추가는 이번 범위에 포함하지 않았다.
