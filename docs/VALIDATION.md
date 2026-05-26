# Validation

## 최신 검증 결과

검증 기준일: 2026-05-26

Checkpoint: `Validate hardened strategy suite`

기준 브랜치: `main`

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Strategy targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_strategies.py -q`: 113 passed in 22.76s |
| Indicator regression pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_indicators.py -q`: 3 passed in 2.45s |
| KIS/broker/paper safety pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3c_kis_readonly.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py -q`: 17 passed in 3.21s |
| Backend full pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 213 passed in 75.70s (0:01:15) |
| Diff whitespace check | 통과 | `git diff --check`: exit 0, CRLF 변환 경고만 출력 |
| Registry order contract | 통과 | `DEFAULT_STRATEGY_NAMES`: `trend_breakout`, `vcp_breakout`, `canslim_lite`, `new_high_breakout`, `pullback_20ema`; `AVAILABLE_STRATEGY_NAMES`: default 5개 + `momentum_rank`, `relative_strength_leader`, `darvas_box`, `stage_analysis_weekly` |
| Screener/backtest API contract | 통과 | full backend suite에서 screener response, backtest API/metrics, explicit strategy selection 회귀 확인 |
| Strategy metadata contract | 통과 | 모든 전략 metadata의 `triggered_conditions`, `failed_conditions`, `score_breakdown`, `data_quality_flags`, `explanation`, `rationale` 유지 |
| Optional/required filter contract | 통과 | config-disabled optional filter는 default pass surface를 과도하게 좁히지 않고, required filter는 전략 의미상 필수 조건에서만 fail-closed |
| Safety invariant | 통과 | broker/paper/KIS safety suite 기준 real order, paper mutation, KIS execution route, token/cache/network call 추가 없음 |

## Validate hardened strategy suite

검증 대상:

- `trend_breakout`
- `vcp_breakout`
- `canslim_lite`
- `new_high_breakout`
- `pullback_20ema`
- `momentum_rank`
- `relative_strength_leader`
- `darvas_box`
- `stage_analysis_weekly`

필수 확인 결과:

- `DEFAULT_STRATEGY_NAMES` 순서는 변경하지 않았다.
- `AVAILABLE_STRATEGY_NAMES` 순서는 변경하지 않았다.
- 기존 `StrategyResult` 필드와 screener/backtest API response field 제거는 확인되지 않았다.
- screener explanation metadata는 `triggered_conditions`, `failed_conditions`, `score_breakdown`, `data_quality_flags`, `explanation`, `rationale`를 유지한다.
- 신규 optional filter는 config에서 꺼져 있으면 기존 default 동작을 최대한 유지한다.
- 신규 required filter는 `canslim_lite`의 기술 추세/거래량 확인, `pullback_20ema`의 EMA pullback/ATR 제한, `darvas_box`의 box/risk/long-trend 검증, `stage_analysis_weekly`의 주봉 availability처럼 전략 의미상 필수인 경우에만 적용된다.
- broker/paper/KIS safety contract는 preview-only, fail-closed, no token/cache/network/no paper mutation 기준을 유지한다.

## 재현 명령

Strategy targeted suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_strategies.py -q
```

Indicator regression suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_indicators.py -q
```

KIS/broker/paper safety suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase3c_kis_readonly.py backend/tests/test_phase3d_broker_safety.py backend/tests/test_phase3e_paper_safety.py -q
```

Backend full suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

Diff check:

```powershell
git diff --check
```

## Safety Contract

| 항목 | 상태 |
|---|---|
| 실제 주문용 stop order 생성 | 없음 |
| BacktestService 변경 | 없음 |
| 주문/주문 취소/체결/계좌 이동 | 없음 |
| broker/paper/KIS/KRX/yfinance runtime 변경 | 없음 |
| DB table/column 변경 | 없음 |
| Alembic revision 추가 | 없음 |
| screener/backtest API breaking change | 없음 |
| strategy registry 순서 변경 | 없음 |
| `orders_count == 0` 정책 변경 | 없음 |

## 제외 범위 유지

- 실제 주문용 stop order 생성.
- BacktestService 변경.
- DB migration 또는 API contract 변경.
- 주문, broker, paper, KIS/KRX/yfinance runtime 동작 추가.
