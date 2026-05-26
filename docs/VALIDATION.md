# Validation

## 최신 검증 결과

검증 기준일: 2026-05-26

Checkpoint: `Strategy validation 252d summary`

기준 브랜치: `main`

| 항목 | 결과 | 명령/근거 |
|---|---|---|
| Backtest/API targeted pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_phase2_api.py -q`: 34 passed in 78.72s |
| Backend full pytest | 통과 | `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 252 passed in 192.44s |
| Frontend lint | 통과 | `cd frontend; npm.cmd run lint`: exit 0 |
| Frontend typecheck | 통과 | `cd frontend; npm.cmd exec tsc -- --noEmit`: exit 0 |
| Frontend build | 통과 | `cd frontend; npm.cmd run build`: Next.js 16.2.6, `/backtest` 포함 10개 app route build 성공 |
| Strategy validation artifact | 생성 | `backend/reports/strategy_validation_252d.json` 생성 확인 |

## 검증 범위

- `GET /api/backtest/strategy-summary?lookback_days=252` endpoint를 추가했다.
- endpoint는 최근 `indicator_snapshot.trade_date` 기준 최대 252 trading days의 available window를 계산한다.
- screener pass rate는 최근 `screen_results.trade_date` 기준 최대 252 trading days의 available window로 계산한다.
- strategy별 backtest summary는 저장형 run을 만들지 않고 `trade_count`, `win_rate`, `total_return`, `max_drawdown`만 산출한다.
- `baseline_run_id` 또는 `baseline_snapshot`이 없으면 `baseline.status="unspecified"`와 `*_delta=null`을 반환한다.
- JSON 산출물은 `backend/reports/strategy_validation_252d.json`에 저장된다.
- `/backtest` frontend는 summary endpoint를 읽어 252D validation summary 표를 최소 표시한다.

## Validation Report Format

`docs/VALIDATION.md` 자동 갱신 시 최신 1세트만 유지한다.

| 필드 | 기록 내용 |
|---|---|
| `checkpoint` | 현재 검증 기준 이름 |
| `command` | 재현 가능한 PowerShell 명령 |
| `result` | pass/fail과 핵심 count |
| `summary_endpoint` | `/api/backtest/strategy-summary?lookback_days=252` |
| `report_path` | `backend/reports/strategy_validation_252d.json` |
| `baseline_status` | `unspecified`, `run_id`, `snapshot`, `missing`, `unavailable_for_strategy` |
| `safety_contract` | real order/paper mutation/network call 추가 여부 |

## 재현 명령

Backend targeted validation:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_backtest.py backend/tests/test_phase2_api.py -q
```

Frontend validation:

```powershell
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
```

## Safety Contract

| 항목 | 상태 |
|---|---|
| 실제 주문/주문 취소/체결/계좌 이동 | 없음 |
| broker/paper adapter 호출 | 없음 |
| paper order/fill/position mutation | 없음 |
| KIS/KRX/yfinance network call | 없음 |
| credential/token 저장 | 없음 |
| 기존 backtest run/list/detail 응답 필드 제거 | 없음 |
| 실주문 관련 route 추가 | 없음 |
| `orders_count == 0` 정책 변경 | 없음 |

## 남은 검증

- 이번 범위에서는 배포 서버와 브라우저 네트워크 탭 검증은 수행하지 않았다.
