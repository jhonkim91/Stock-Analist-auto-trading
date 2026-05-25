# Validation

## 최신 검증 결과

검증 기준일: 2026-05-25

Checkpoint: `Harden canslim_lite Strategy`

기준 브랜치: `main`

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Strategy hardening targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_strategies.py -q`: 89 passed in 32.42s |
| Backend full pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 189 passed in 84.04s |
| Frontend lint | 통과 | `npm.cmd run lint` |
| Frontend typecheck | 통과 | `npm.cmd exec tsc -- --noEmit` |
| Frontend production build | 통과 | `npm.cmd run build` |
| Frontend audit | 통과 | `npm.cmd audit --audit-level=moderate`: found 0 vulnerabilities |
| Diff whitespace check | 통과 | `git diff --check` |
| CANSLIM technical trend contract | 통과 | `technical_trend_filter_enabled=true`에서 SMA 정배열이 깨지면 fail |
| CANSLIM volume confirmation contract | 통과 | `volume_confirmation_enabled=true`에서 `volume < volume_ma50 * volume_surge_multiple`이면 fail |
| CANSLIM sector leadership optional contract | 통과 | `sector_rs_filter_enabled=false`이면 `sector_rs_score=None`만으로 fail하지 않음 |
| CANSLIM fundamentals contract | 통과 | `fundamentals=None`이면 `fundamentals_available_asof` failed condition 표시 |
| CANSLIM earnings quality contract | 통과 | `earnings_quality_enabled=true`에서 `roe=None`이면 `data_quality_flags.roe_available=false` 표시 |
| CANSLIM PTI metadata contract | 통과 | `fundamentals_available_asof`, `fundamentals_effective_date_available`, `pti_validation_status=pti_validation_not_available_in_current_mvp` 포함; `no_lookahead_claim` 미사용 |
| API/DB contract | 통과 | screener/backtest API shape, DB schema, migration 변경 없음 |
| Safety invariant | 통과 | 주문, 체결, paper mutation, broker/KIS/KRX/yfinance 경로 변경 없음 |

## Harden canslim_lite Strategy

변경 범위:

- `canslim_lite`에 `technical_trend_filter_enabled: true`를 추가하고 다음 pass flag를 config-gated 조건으로 평가한다.
  - `close_gt_sma50`
  - `sma50_gt_sma150`
  - `sma150_gt_sma200`
  - `sma200_slope_positive`
- `volume_confirmation_enabled: true`, `volume_surge_multiple: 1.5`를 추가하고 `volume_surge`를 `volume >= volume_ma50 * volume_surge_multiple`로 평가한다.
- `sector_rs_filter_enabled: false`, `sector_rs_score_min: 0.60`을 추가해 섹터 leadership 필터를 optional로 제어한다.
- 기존 `earnings_quality_enabled`, `min_roe` 구조는 유지하고, `roe=None`이면 `data_quality_flags.roe_available=false`로 표시한다.
- `fundamentals=None`이면 fail closed로 처리하고 `failed_conditions`에 `fundamentals_available_asof`를 남긴다.
- PTI metadata는 `fundamentals_available_asof`, `fundamentals_effective_date_available`, `pti_validation_status=pti_validation_not_available_in_current_mvp`만 기록한다.
- 현재 MVP 데이터 모델에서 완전한 point-in-time 검증은 불가하므로 `no_lookahead_claim`은 기록하지 않는다.
- `earnings_events` 테이블, Fundamentals schema, provider 호출, 주문 관련 코드는 변경하지 않았다.

추가/보강 테스트:

- SMA 정배열이 깨지면 `canslim_lite` fail.
- 거래량 surge가 없으면 `canslim_lite` fail.
- 섹터 RS 필터 비활성 상태에서는 `sector_rs_score=None`이어도 기존 pass 유지.
- `fundamentals=None`이면 fail 및 명시적 failed condition 표시.
- `roe=None`이면 `data_quality_flags.roe_available=false` 표시.
- PTI 관련 metadata 상태 포함 및 `no_lookahead_claim` 미사용 확인.

## 재현 명령

Strategy hardening targeted suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_strategies.py -q
```

Backend full suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

Diff check:

```powershell
git diff --check
```

Frontend:

```powershell
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
```

이번 checkpoint push 전 frontend lint/typecheck/build/audit을 재실행했다.

## Safety Contract

| 항목 | 상태 |
|---|---|
| DB table/column 변경 | 없음 |
| Alembic revision 추가 | 없음 |
| Fundamentals schema 변경 | 없음 |
| earnings_events 테이블 추가 | 없음 |
| screener/backtest API contract 변경 | 기존 필드 제거 없음 |
| strategy registry 순서 변경 | 없음 |
| 기본 screener 전략 | 5개: `trend_breakout`, `vcp_breakout`, `canslim_lite`, `new_high_breakout`, `pullback_20ema` |
| available 전략 | 9개: default 5개 + `momentum_rank`, `relative_strength_leader`, `darvas_box`, `stage_analysis_weekly` |
| 실주문, 주문 취소, 체결, 계좌 이동 | 없음 |
| paper order/fill/position/audit mutation | 없음 |
| KIS/KRX/yfinance network call | 없음 |
| token/cache/credential 저장 | 없음 |

## 제외 범위

- `earnings_events` 신규 테이블 추가.
- Fundamentals schema 변경.
- 실제 데이터 provider 호출.
- 주문, broker, paper, KIS, KRX runtime 동작 추가.
- 신규 DB schema 또는 migration.
- 신규 전략 추가 또는 strategy registry 순서 변경.
- 기존 backtest metrics key/type 변경.
