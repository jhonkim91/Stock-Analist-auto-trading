# Validation

## 최신 검증 결과

검증 기준일: 2026-05-23

Checkpoint: `Phase C-2 relative_strength_leader Strategy`

기준 브랜치: `main`

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase C-2 targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_strategies.py backend/tests/test_backtest.py -q`: 37 passed |
| Backend full pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests`: 115 passed |
| Frontend lint | 통과 | `cd frontend && npm.cmd run lint` |
| Frontend typecheck | 통과 | `cd frontend && npm.cmd exec tsc -- --noEmit` |
| Frontend production build | 통과 | `cd frontend && npm.cmd run build`: Next.js 16.2.6 production build |
| Strategy registry contract | 통과 | 기본 전략은 `trend_breakout`, `vcp_breakout`, `canslim_lite` 3개 유지. `momentum_rank`, `relative_strength_leader`는 available registry와 명시 실행 경로에만 추가 |
| Screener/Backtest explicit execution | 통과 | `strategy_name="relative_strength_leader"` 또는 `strategies=["relative_strength_leader"]` 명시 실행 가능 |
| Screener explanation contract | 통과 | `triggered_conditions`, `failed_conditions`, `score_breakdown`, `data_quality_flags`, `explanation`, `rationale` 유지 |
| API/DB contract | 통과 | DB schema, screener/backtest API response shape, backtest metrics key/type 변경 없음 |
| Safety invariant | 통과 | 실주문, paper mutation, KIS/KRX network, token/cache/credential 저장 구현 없음 |

## 표준 검증 명령

Phase C-2 targeted suite:

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

## Phase C-2 relative_strength_leader Strategy

변경 범위:

- `backend/app/strategies/relative_strength_leader.py`에 `RelativeStrengthLeaderStrategy`를 추가했다.
- `relative_strength_leader`는 `indicator_snapshot` 기존 필드만 사용하며 DB schema 변경이 없다.
- 사용 조건은 `rs_percentile`, `relative_strength_score`, `sector_rs_score`, `close >= high_52w * near_high_52w_threshold`, `close > sma50`, `sma50 > sma150`, `sma200_slope > 0`, `volume_ratio_50`이다.
- `high_52w`가 없으면 `near_high_52w` 조건은 fail이고 `data_quality_flags.high_52w_available=false`로 노출한다.
- `volume_ratio_50`은 재계산하지 않고 snapshot 필드 값을 그대로 사용한다.
- `backend/config/strategies.yaml`에 `relative_strength_leader` threshold를 추가했다.
- `DEFAULT_STRATEGY_NAMES`는 기존 3개를 유지하고, `AVAILABLE_STRATEGY_NAMES` 끝에 `relative_strength_leader`를 추가했다.
- Screener 응답 직렬화 시 `relative_strength_leader` 결과에는 strategy별 `data_quality_flags`를 기존 `data_quality_flags` 객체에 병합한다.

Config:

```yaml
relative_strength_leader:
  rs_percentile_min: 90
  relative_strength_score_min: 0.90
  sector_rs_score_min: 0.70
  near_high_52w_threshold: 0.90
  min_volume_ratio_50: 1.0
```

추가 테스트:

- 강한 RS leader fixture pass.
- `rs_percentile` 부족 fail.
- `sector_rs_score` 부족 fail.
- `high_52w=None` fail 및 `data_quality_flags.high_52w_available=false`.
- `volume_ratio_50` 부족 fail.
- available registry에는 `relative_strength_leader` 포함, default registry와 `ScreenerRunRequest` 기본값은 기존 3개 유지.
- `ScreenerService.run(strategies=["relative_strength_leader"])` 명시 실행과 응답 contract 확인.
- `BacktestService.run("relative_strength_leader")` 명시 실행.

## Safety Contract

| 항목 | 상태 |
|---|---|
| DB table/column 변경 | 없음 |
| Alembic revision 추가 | 없음 |
| screener/backtest API contract 변경 | 기존 필드 제거 없음 |
| backtest 실행/체결 모델 변경 | 없음 |
| 기존 3개 전략 기본 실행 목록 변경 | 없음 |
| 실주문, 주문 취소, 체결, 계좌 이동 | 없음 |
| paper order/fill/position/audit mutation | 없음 |
| KIS/KRX/yfinance network call | 없음 |
| token/cache/credential 저장 | 없음 |

## 제외 범위

- `relative_strength_leader`를 기본 실행 전략으로 추가하지 않았다.
- DB schema 변경과 migration을 만들지 않았다.
- broker, paper, KIS, KRX runtime 동작을 추가하지 않았다.
- 기존 backtest metrics key/type을 변경하지 않았다.
- frontend dropdown 추가는 이번 범위에 포함하지 않았다.
