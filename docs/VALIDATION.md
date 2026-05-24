# Validation

## 최신 검증 결과

검증 기준일: 2026-05-24

Checkpoint: `Phase C-6 pullback_20ema Strategy`

기준 브랜치: `main`

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Phase C-6 targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_indicators.py backend/tests/test_strategies.py backend/tests/test_alembic_migrations.py -q`: 51 passed |
| Backend full pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 144 passed |
| Diff whitespace check | 통과 | `git diff --check` |
| Indicator contract | 통과 | `indicator_snapshot.low`, `indicator_snapshot.ema20` nullable 저장 및 Pandas EWM 값 일치 확인 |
| Alembic migration smoke | 통과 | `.\.venv\Scripts\python.exe -m alembic heads`: `f6d4a2c9e8b1 (head)`, upgrade/downgrade smoke 테스트 통과 |
| Strategy registry contract | 통과 | 기본 전략 5개: `trend_breakout`, `vcp_breakout`, `canslim_lite`, `new_high_breakout`, `pullback_20ema` |
| Screener/Backtest execution | 통과 | `strategies=["pullback_20ema"]`, `strategy_name="pullback_20ema"` 실행 가능 |
| Screener explanation contract | 통과 | `triggered_conditions`, `failed_conditions`, `score_breakdown`, `data_quality_flags`, `explanation`, `rationale` 유지 |
| API/DB contract | 통과 | 기존 screener/backtest API 필드 제거 없음, backtest metrics key/type 유지 |
| Frontend lint/typecheck/build | 미실행 | frontend 파일 변경 없음 |
| Safety invariant | 통과 | 실주문, paper mutation, KIS/KRX/yfinance network, token/cache/credential 저장 구현 없음 |

## 표준 검증 명령

Phase C strategy targeted suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_indicators.py backend/tests/test_strategies.py backend/tests/test_alembic_migrations.py -q
```

Backend full suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

Frontend:

```powershell
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
```

## Phase C-6 pullback_20ema Strategy

변경 범위:

- `backend/app/strategies/pullback_20ema.py`에 `Pullback20EmaStrategy`를 추가했다.
- `pullback_20ema`는 기본 screener 전략 목록 끝에 append되어 기존 기본 전략 순서를 유지한다.
- `IndicatorService`는 `close.ewm(span=20, adjust=False, min_periods=20).mean()` 기반 `ema20`을 계산한다.
- `IndicatorSnapshot`에는 `low`, `ema20` nullable 컬럼을 추가했다.
- Alembic revision `f6d4a2c9e8b1_add_indicator_pullback_ema_fields.py`가 `low`, `ema20` upgrade/downgrade를 관리한다.
- 전일 종가 momentum 필드는 추가하지 않았다.
- broker, paper, KIS/KRX/yfinance network, real order 경로는 변경하지 않았다.

전략 조건:

- `close > sma50`
- `sma50 > sma150`
- `sma150 > sma200`
- `sma200_slope > 0`
- `ema20_available`
- `low_available`
- `low <= ema20 * pullback_touch_buffer`
- `close >= ema20`
- `rs_percentile >= rs_percentile_min`
- `volume_ratio_50 <= max_pullback_volume_ratio`
- `atr20_pct <= max_atr20_pct`

Config:

```yaml
pullback_20ema:
  pullback_touch_buffer: 1.01
  rs_percentile_min: 70
  max_pullback_volume_ratio: 1.2
  max_atr20_pct: 0.08
```

추가 테스트:

- seeded daily data 기반 `ema20`, `low` snapshot 저장 및 Pandas EWM 값 일치.
- EMA20 touch 후 `close >= ema20`이면 pass.
- `ema20=None`이면 fail 및 `data_quality_flags.ema20_available=false`.
- 추세 정배열 깨짐 fail.
- pullback volume 과도 fail.
- `atr20_pct` 과도 fail.
- registry/default order와 `ScreenerRunRequest` 기본 전략 목록 갱신 확인.
- Screener/Backtest에서 `pullback_20ema` 실행 가능 확인.

## Safety Contract

| 항목 | 상태 |
|---|---|
| DB table/column 변경 | `indicator_snapshot.low`, `indicator_snapshot.ema20` nullable 추가 |
| Alembic revision 추가 | `f6d4a2c9e8b1_add_indicator_pullback_ema_fields` |
| screener/backtest API contract 변경 | 기존 필드 제거 없음 |
| backtest 실행/체결 모델 변경 | 없음 |
| 기본 screener 전략 | 5개: `trend_breakout`, `vcp_breakout`, `canslim_lite`, `new_high_breakout`, `pullback_20ema` |
| 실주문, 주문 취소, 체결, 계좌 이동 | 없음 |
| paper order/fill/position/audit mutation | 없음 |
| KIS/KRX/yfinance network call | 없음 |
| token/cache/credential 저장 | 없음 |

## 제외 범위

- 전일 종가 momentum 필드 추가.
- broker, paper, KIS, KRX runtime 동작 추가.
- frontend strategy selector 변경.
- 기존 backtest metrics key/type 변경.
