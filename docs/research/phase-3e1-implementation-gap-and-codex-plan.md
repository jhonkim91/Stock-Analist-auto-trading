# Phase 3E1 기준 구현 현황·미비점 분석 및 Codex 계획 수립 지시서

## 0. 문서 목적

이 문서는 `deep-research-report.md`의 설계 방향과 현재 `jhonkim91/Stock-Analist-auto-trading` 구현 상태를 비교하여, **Phase 3E1 진행 중인 현재 상황에서 Codex가 다음 개발 계획을 세우기 위한 기준 문서**로 사용한다.

현재 프로젝트는 `MVP v0.6 Phase 3D broker safety scaffold` 이후 단계이며, 사용자는 **Phase 3E1을 기존 방향대로 진행 중**이라고 명시했다. 따라서 본 문서는 기존 Phase 3E1 방향을 무시하고 새 구조로 갈아엎지 않고, 다음 원칙을 따른다.

- 기존 Phase 3A~3D 안전 계약 유지
- Phase 3E1 진행 방향 존중
- 실주문/live broker는 아직 금지
- paper trading 또는 broker 실행 기반을 붙이더라도 preview/safety/fail-closed 원칙 유지
- 데이터 신뢰성, 백테스트 현실성, 리포트 품질, paper trading foundation을 단계적으로 보강
- 기존 테스트와 Secret 정책 유지

---

## 1. 핵심 결론

현재 구현은 “자동매매 완성본”이 아니라 **분석·스크리닝·리포트·백테스트·브로커 안전 스캐폴드 기반의 검증 가능한 MVP** 상태다.

| 영역 | 현재 상태 | 평가 |
|---|---:|---|
| FastAPI/Next.js 앱 골격 | 구현됨 | 양호 |
| 샘플 데이터 + CSV 검증/확정 import | 구현됨 | 양호 |
| 시장 국면/기술지표/스크리너/점수화 | 구현됨 | MVP 수준 |
| 일간 리포트 | 구현됨 | MVP 수준 |
| 백테스트 | 구현됨 | 단순 검증용 |
| KIS/브로커 연동 | 안전 스캐폴드만 구현 | 의도적으로 주문 차단 |
| 실제 자동매매 | 미구현 | live 금지 유지 |
| 실전급 데이터/백테스트 품질 | 미흡 | 우선 보강 필요 |
| Phase 3E1 | 진행 중 | 기존 방향 보존 필요 |

현재 README 기준 프로젝트 checkpoint는 `MVP v0.6 Phase 3D broker safety scaffold`이며, 실제 주문, paper/live broker, cancel, fill, websocket 연결, KIS 실제 API 호출, 자동매매 스케줄러, AI 예측 모델은 구현하지 않는다고 명시되어 있다.

---

## 2. 현재 구현된 주요 기능

### 2.1 백엔드/프론트엔드 기본 구조

현재 백엔드는 FastAPI 기반이며 주요 라우터가 분리되어 있다.

- `data`
- `indicators`
- `market`
- `instruments`
- `screener`
- `reports`
- `backtest`
- `portfolio`
- `broker`
- `kis`
- `settings`

프론트엔드는 다음 화면을 가진다.

- Dashboard
- Data
- Screener
- Reports
- Backtest
- Portfolio
- Settings

대시보드에서 다음 작업을 실행할 수 있다.

- sample data seed
- indicators recompute
- screener run
- daily report generate
- backtest run
- broker order preview

판단:

- 프로젝트 구조는 보고서의 “데이터 → 피처 → 전략/스크리너 → 백테스트 → 리포트 → 실행 어댑터” 구조와 맞다.
- 현재는 실거래 시스템이 아니라 분석/검증 보조 시스템으로 보는 것이 맞다.

---

### 2.2 DB 모델

현재 구현된 주요 테이블은 다음과 같다.

| 테이블 | 상태 | 설명 |
|---|---:|---|
| `symbol_master` | 구현 | 종목 마스터 |
| `daily_ohlcv` | 구현 | 일봉 OHLCV |
| `data_sources` | 구현 | 데이터 소스 설정 |
| `import_runs` | 구현 | CSV/external import run |
| `data_quality_checks` | 구현 | 데이터 품질 검증 결과 |
| `external_symbol_mapping` | 구현 | provider symbol mapping |
| `corporate_actions` | 구현 | 권리/배당/분할용 테이블 |
| `trading_calendar` | 구현 | 거래일 캘린더 |
| `index_ohlcv` | 구현 | 지수 OHLCV |
| `sector_ohlcv` | 구현 | 섹터 OHLCV |
| `fundamentals_pti` | 구현 | point-in-time 재무 |
| `indicator_snapshot` | 구현 | 계산 지표 캐시 |
| `screen_results` | 구현 | 스크리너 결과 |
| `reports` | 구현 | 리포트 메타 |
| `backtest_runs` | 구현 | 백테스트 run |
| `positions` | 구현 | 포지션 스캐폴드 |
| `orders` | 구현 | 주문 스캐폴드 |

판단:

- 분석 MVP 기준으로는 충분하다.
- 실전 paper/live trading으로 확장하려면 아래 테이블이 추가로 필요하다.

권장 추가 테이블:

```text
paper_orders
paper_fills
paper_positions
order_events
broker_audit_logs
portfolio_snapshots
strategy_run_audit
earnings_events
weekly_ohlcv
```

Phase 3E1에서 이 중 일부를 추가한다면, **실주문 테이블과 명확히 분리된 paper 전용 테이블**로 시작하는 것이 안전하다.

---

### 2.3 데이터 import flow

현재 데이터 import는 다음 구조로 되어 있다.

#### CSV flow

```text
POST /api/data/validate-csv
POST /api/data/import-csv-confirmed
```

#### External flow

```text
POST /api/data/external/preview-daily-ohlcv
POST /api/data/external/confirm-import
```

특징:

- Preview 단계는 `daily_ohlcv`를 직접 변경하지 않는다.
- Preview 단계에서 허용되는 write는 `import_runs`, `data_quality_checks` 중심이다.
- Confirm 단계에서만 staged rows를 `daily_ohlcv`에 반영한다.
- symbol mapping이 없으면 external import는 실패 처리한다.
- `network_enabled=false`가 기본이다.
- KIS/yfinance는 기본적으로 mock 또는 disabled 구조다.

판단:

- 데이터 검증 flow는 잘 설계되어 있다.
- 실전 데이터 신뢰성을 위해 read-only adapter 보강이 필요하다.

---

### 2.4 지표/피처 엔진

현재 `IndicatorService`는 다음 피처를 계산한다.

| 피처 | 상태 |
|---|---:|
| SMA 20/50/150/200 | 구현 |
| SMA200 slope | 구현 |
| Volume MA 20/50 | 구현 |
| ATR 14/20 | 구현 |
| ATR% | 구현 |
| STD 20/60 | 구현 |
| 52주 고점 | 구현 |
| 52주 고점 대비 거리 | 구현 |
| 20일 pivot high/low | 구현 |
| breakout | 구현 |
| volume dry-up | 구현 |
| 126일 수익률 기반 RS percentile | 구현 |
| market score | 구현 |
| sector RS score | 구현 |
| trend/volume/pattern score | 구현 |

추가 필요 피처:

```text
EMA 10/20
ADX
OBV
CMF
Donchian 20/55
12-1M momentum
3M/6M momentum
업종 내 RS
market breadth
52w high/low breadth
earnings revision score
gap risk proxy
liquidity participation ratio
```

---

### 2.5 시장 국면 판단

현재 `RegimeService`는 다음을 사용한다.

- index close vs 200DMA
- 50DMA vs 200DMA
- 주봉 30주 이동평균
- 30주선 slope
- `bull / neutral / bear` 분류

현재 benchmark는 `KOSPI_SAMPLE` 중심이다.

보강 필요:

```text
real benchmark support
KOSPI/KOSDAQ/S&P500/Nasdaq benchmark selection
breadth indicator
52-week high-low ratio
sector participation
market regime history table
```

---

### 2.6 전략 레이어

현재 구현된 전략은 3개다.

| 전략 | 상태 | 설명 |
|---|---:|---|
| `trend_breakout` | 구현 | 50/150/200MA, SMA200 slope, RS, 52주 고점 근접, volume surge |
| `vcp_breakout` | 구현 | trend, ATR contraction, STD contraction, volume dry-up, pivot breakout |
| `canslim_lite` | 구현 | EPS growth, sales growth, RS, breakout, bull regime |

보고서 대비 미구현 전략:

```text
momentum_rank
relative_strength_leader
new_high_breakout
darvas_box
stage_analysis_weekly
turtle_donchian
pullback_20ema
multifactor_rank
value_quality_earnings_momentum
```

우선순위:

1. `momentum_rank`
2. `relative_strength_leader`
3. `new_high_breakout`
4. `darvas_box`
5. `stage_analysis_weekly`
6. `turtle_donchian`
7. `pullback_20ema`
8. `multifactor_rank`

---

### 2.7 스크리너/점수화

현재 스크리너는 다음 순서로 동작한다.

```text
latest indicator date 선택
각 종목별 fundamentals as-of 조회
risk 계산
strategy evaluate
공통 유동성/손익비 필터 적용
total score 계산
screen_results 저장
```

현재 점수식은 보고서 권장식과 유사하다.

```text
total_score =
  0.20 * market_score
+ 0.10 * sector_rs_score
+ 0.20 * trend_score
+ 0.15 * relative_strength_score
+ 0.10 * volume_score
+ 0.10 * pattern_score
+ 0.10 * fundamental_score
+ 0.05 * rr_score
```

판단:

- 현재 프로젝트에서 가장 잘 구현된 영역 중 하나다.
- Phase 3E1에서도 이 구조는 유지해야 한다.
- 신규 전략을 추가하더라도 `BaseStrategy.evaluate()` 인터페이스를 유지한다.

---

### 2.8 리스크 계산

현재 `RiskService`는 다음을 계산한다.

```text
entry_price
ATR stop
8% hard stop
pivot low stop
target price
risk per share
reward/risk ratio
position size
position notional
RR score
```

기본 config:

```yaml
portfolio:
  equity: 100000000
  risk_fraction: 0.01
  max_position_fraction: 0.2

risk:
  atr_stop_multiple: 2.0
  hard_stop_pct: 0.08
  target_reward_risk: 2.5
```

보강 필요:

```text
max_open_positions
max_gross_exposure
max_sector_exposure
max_strategy_exposure
max_symbol_notional
max_daily_loss
event_risk_hold
gap_risk_estimate
portfolio_cash_lock
```

---

### 2.9 일간 리포트

현재 daily report는 Markdown으로 생성되며 다음 섹션을 가진다.

```text
Market Regime
Sector Rotation
Triggered Candidates
Rejected But Close
Portfolio Risk
Mock Orders For Review
Audit Trail
```

판단:

- daily report MVP는 구현되어 있다.
- 다음 단계에서는 weekly review report를 추가하는 것이 좋다.

추가 권장 리포트:

```text
weekly strategy review
setup별 win rate
expectancy by strategy
regime별 성과
failed trades review
filter attribution
parameter drift check
```

---

### 2.10 백테스트

현재 백테스트 특징:

```text
strategy별 실행
종가 신호 후 다음 거래일 시가 진입
commission + slippage bps 적용
stop/target/max holding exit
기본 metrics 저장
backtest_runs 저장
config_hash 저장
```

현재 한계:

```text
생존자 편향 미제거
상장폐지 종목 미포함
corporate action 실제 조정 미구현
gap-aware stop 미흡
부분 체결 미구현
유동성 participation limit 미구현
포트폴리오 cash/position state 약함
동시 보유 포지션 제약 약함
walk-forward 미구현
Sharpe/Sortino/Calmar/turnover 등 일부 미구현
```

판단:

- 현재 백테스트는 기능 검증용이다.
- 전략 성능 판단에는 아직 보수적으로 봐야 한다.

---

### 2.11 브로커/KIS 안전 스캐폴드

현재 브로커는 실제 주문이 아니라 안전 차단 구조다.

현재 보장:

```text
can_submit = false
preview_only = true
order_created = false
token_issued = false
network_call_performed = false
adapter_order_call_performed = false
adapter_network_call_performed = false
audit_persistence_enabled = false
orders_count remains 0
KIS orders/broker/websocket routes remain 404
```

판단:

- 이 구조는 유지해야 한다.
- Phase 3E1에서 paper trading을 추가하더라도 기존 `/api/broker/orders/preview`의 안전 계약은 깨면 안 된다.
- paper trading endpoint는 별도 namespace로 두는 것이 안전하다.

권장 namespace:

```text
/api/paper/status
/api/paper/orders/preview
/api/paper/orders/submit
/api/paper/orders/{order_id}/cancel
/api/paper/fills
/api/paper/positions
/api/paper/portfolio
```

단, Phase 3E1이 이미 다른 namespace로 진행 중이면 기존 방향을 우선한다.

---

## 3. Phase 3E1 고려사항

사용자는 현재 Phase 3E1이 진행 중이라고 명시했다. README 기준 Phase 3E 후보는 `paper trading adapter 설계`였으므로, 본 문서는 Phase 3E1을 다음 성격으로 간주한다.

> Phase 3E1 = live trading이 아니라 paper trading 또는 execution foundation을 안전하게 시작하는 단계

### 3.1 Phase 3E1에서 유지해야 할 안전 계약

아래 항목은 절대 깨면 안 된다.

```text
KIS 실제 주문 호출 금지
KIS token 발급/refresh/cache 금지
KIS app key/app secret/account/token 저장 금지
live broker route 등록 금지
/api/kis/orders/* 404 유지
/api/kis/broker/* 404 유지
/api/kis/websocket/* 404 유지
기존 /api/broker/orders/preview는 order row 생성 금지
기존 orders_count after broker preview == 0 유지
Settings API에서 broker.yaml 원문 노출 금지
Secret redaction 유지
```

### 3.2 Phase 3E1에서 허용 가능한 범위

Phase 3E1에서 허용 가능한 것은 다음 정도다.

```text
paper 전용 주문 테이블 생성
paper 전용 체결 테이블 생성
paper 전용 포지션 테이블 생성
paper order state machine 구현
paper fill simulator 구현
paper portfolio snapshot 구현
paper audit log 구현
paper endpoint 추가
paper 테스트 추가
기존 broker safety test 유지
```

### 3.3 Phase 3E1에서 금지할 범위

```text
실제 KIS endpoint 호출
실제 token 발급
실제 계좌/잔고 조회
live order submit
paper/live 혼용
기존 /api/broker/orders/preview에서 order 생성
secret/account 값 저장
websocket 연결
scheduler가 주문 submit까지 자동 실행
```

---

## 4. 미비점 우선순위

### P0 — 현재 Phase 3E1 보호

목표:

```text
기존 Phase 3D safety contract를 깨지 않고 Phase 3E1 범위를 명확히 한다.
```

작업:

```text
1. 현재 브랜치/HEAD/테스트 상태 확인
2. Phase 3E1에서 이미 변경된 파일 목록 확인
3. 기존 broker safety tests 재확인
4. /api/broker/orders/preview 안전 계약 유지
5. KIS execution routes 404 유지
6. secret scan 수행
```

완료 기준:

```text
backend pytest 통과
frontend lint/typecheck/build 통과
orders_count after broker preview == 0
token cache 파일 없음
KIS execution routes 404
```

---

### P1 — Paper Trading Foundation

목표:

```text
실제 주문 없이 paper-only 실행 계층을 만든다.
```

권장 작업:

```text
1. paper 전용 모델 추가
   - PaperOrder
   - PaperFill
   - PaperPosition
   - PaperPortfolioSnapshot
   - PaperAuditLog

2. paper order state 정의
   - previewed
   - accepted
   - rejected
   - submitted
   - partially_filled
   - filled
   - canceled
   - expired

3. paper risk gate 구현
   - symbol validation
   - qty > 0
   - max notional
   - max position fraction
   - max open positions
   - max daily loss placeholder
   - duplicate idempotency key block

4. paper fill simulator 구현
   - next_open fill
   - limit price check
   - stop price check
   - slippage bps
   - commission bps
   - insufficient data handling

5. paper portfolio update
   - cash
   - positions
   - realized/unrealized pnl
   - exposure

6. API 추가
   - GET /api/paper/status
   - POST /api/paper/orders/preview
   - POST /api/paper/orders/submit
   - POST /api/paper/orders/{order_id}/cancel
   - GET /api/paper/orders
   - GET /api/paper/fills
   - GET /api/paper/positions
   - GET /api/paper/portfolio
```

완료 기준:

```text
paper submit은 paper_* 테이블에만 기록
real orders table은 기존 safety contract에 따라 건드리지 않음
paper order 생성 후 paper position 업데이트
idempotency key 중복 submit 차단
broker/KIS live 관련 플래그는 여전히 false
```

---

### P2 — Backtest 현실성 보강

목표:

```text
현재 단순 백테스트를 paper execution과 유사한 체결 모델로 개선한다.
```

작업:

```text
gap-aware stop
next_open / next_vwap mode 분리
limit order fill rule
slippage model by liquidity
commission config
partial fill placeholder
cash/position state
max open positions
sector exposure cap
strategy exposure cap
```

완료 기준:

```text
backtest metrics에 total_cost, turnover, exposure, max_drawdown, profit_factor, expectancy 유지/추가
기존 테스트 깨지지 않음
새 체결 모델 테스트 추가
```

---

### P3 — 신규 전략 확장

목표:

```text
보고서의 전략 커버리지를 단계적으로 확장한다.
```

우선 추가 전략:

```text
momentum_rank
relative_strength_leader
new_high_breakout
darvas_box
stage_analysis_weekly
```

작업 방식:

```text
기존 BaseStrategy 인터페이스 유지
전략별 config yaml 추가
전략별 unit test 추가
ScreenerService strategies registry에 추가
Frontend strategy filter가 동작하도록 type/list 업데이트
```

---

### P4 — Weekly Report

목표:

```text
일간 후보 리포트 외에 전략 품질 점검용 주간 리포트를 추가한다.
```

섹션:

```text
Performance Summary
Risk Summary
Hit Rate By Setup
Regime Diagnostics
Factor/Filter Attribution
Failed Trades Review
Parameter Drift Check
Audit Trail
```

권장 API:

```text
POST /api/reports/weekly
GET /api/reports/latest?type=weekly
GET /api/reports/{report_id}/markdown
```

---

### P5 — Real Read-only Data

목표:

```text
실주문이 아니라 실제 데이터 조회 신뢰성을 먼저 올린다.
```

작업:

```text
KIS read-only market data adapter 설계
network_enabled gate 유지
token 발급은 아직 금지 또는 별도 승인 전까지 금지
real KRX/KIS provider는 config opt-in
data freshness check
provider response audit
```

주의:

- Phase 3E1 중에는 live order와 함께 진행하지 않는다.
- KIS token이 필요한 실제 API 호출은 별도 Phase 승인 후 진행한다.

---

## 5. Codex 작업 지침

### 5.1 Codex가 반드시 지켜야 할 원칙

```text
1. 기존 Phase 3D broker safety contract를 깨지 않는다.
2. 현재 Phase 3E1 진행 중인 변경사항을 먼저 확인한다.
3. 실주문, KIS 실제 주문, live broker, websocket은 구현하지 않는다.
4. paper trading을 하더라도 paper 전용 namespace와 테이블만 사용한다.
5. 기존 /api/broker/orders/preview는 order row를 만들면 안 된다.
6. KIS token 발급/refresh/cache를 만들지 않는다.
7. secret/account/token 값을 저장하거나 로그에 출력하지 않는다.
8. 기존 backend tests와 frontend build를 통과시킨다.
9. 변경 범위는 최소화한다.
10. 새 기능에는 테스트를 추가한다.
```

### 5.2 Codex에게 먼저 시킬 분석 명령

```text
현재 repository 상태를 분석해줘.

조건:
- 현재 Phase 3E1이 진행 중이므로 기존 변경 방향을 먼저 파악한다.
- main 또는 현재 브랜치 기준으로 Phase 3D safety contract가 깨졌는지 확인한다.
- 구현된 기능과 미구현 기능을 아래 분류로 정리한다.

분류:
1. Phase 3A data quality flow
2. Phase 3B external provider preview/confirm
3. Phase 3C KIS read-only foundation
4. Phase 3D broker safety scaffold
5. Phase 3E1 current progress
6. paper trading foundation readiness
7. tests and validation status

반드시 확인:
- git status
- 현재 브랜치
- 최근 커밋
- 변경 파일 목록
- backend/app/services/broker_service.py
- backend/app/api/broker.py
- backend/app/services/kis_service.py
- backend/app/services/backtest_service.py
- backend/app/models/tables.py
- backend/tests/test_phase3d_broker_safety.py
- docs/VALIDATION.md
- README.md

산출물:
- 현재 구현된 것
- 진행 중인 것
- 미비된 것
- Phase 3E1에서 건드리면 안 되는 것
- 다음 작업 우선순위
- 테스트 명령
```

---

## 6. Codex 추천 프롬프트

### 6.1 계획 수립 전용 프롬프트

아래 프롬프트를 Codex에 먼저 전달한다.

```text
현재 이 프로젝트는 주식 분석 및 자동매매 보조 시스템이며, deep-research-report.md의 방향을 기반으로 개발 중이다.

중요:
- 현재 Phase 3E1이 진행 중이다.
- 기존 방향을 무시하고 새로 설계하지 말고, 현재 브랜치/변경사항을 먼저 분석한 뒤 계획을 세워라.
- Phase 3D까지의 broker safety scaffold는 반드시 유지해야 한다.
- 실주문, live broker, KIS 실제 주문, token 발급, websocket 연결은 구현 금지다.
- Phase 3E1은 paper trading 또는 execution foundation 성격으로 보되, 현재 코드에 이미 진행된 방향이 있으면 그 방향을 우선하라.

먼저 아래를 수행해라.

1. git status, 현재 브랜치, 최근 커밋, 변경 파일 목록 확인
2. README.md와 docs/VALIDATION.md 확인
3. backend/app/services/broker_service.py 확인
4. backend/app/api/broker.py 확인
5. backend/app/services/kis_service.py 확인
6. backend/app/services/backtest_service.py 확인
7. backend/app/models/tables.py 확인
8. backend/tests/test_phase3d_broker_safety.py 확인
9. 현재 Phase 3E1에서 이미 구현된 부분을 요약
10. 기존 safety contract가 깨졌는지 확인

그 다음 아래 형식으로 계획을 작성해라.

# Phase 3E1 Plan

## Current Branch / Status
- branch:
- head:
- dirty files:
- existing Phase 3E1 changes:

## Safety Contract Check
- /api/broker/orders/preview order_created false 유지 여부:
- orders_count after preview 0 유지 여부:
- KIS orders/broker/websocket route 404 유지 여부:
- token issued/cache/network call 여부:
- settings secret exposure 여부:

## Implemented
## Partially Implemented
## Missing
## Risks
## Proposed Next Steps

각 next step은 다음 형식으로 작성:
- 목표
- 수정 파일
- 구현 내용
- 테스트
- rollback 방법
- safety impact

절대 바로 대규모 코드를 수정하지 말고, 먼저 계획만 작성해라.
```

---

### 6.2 Phase 3E1 Paper Trading Foundation 구현 프롬프트

계획 검토 후 구현을 맡길 때 사용한다.

```text
Phase 3E1의 목표는 live trading이 아니라 paper trading foundation이다.

아래 안전 조건을 반드시 유지하라.

금지:
- KIS 실제 API 호출 금지
- KIS token 발급/refresh/cache 금지
- live broker 구현 금지
- /api/kis/orders/* route 등록 금지
- /api/kis/broker/* route 등록 금지
- /api/kis/websocket/* route 등록 금지
- 기존 /api/broker/orders/preview에서 orders table row 생성 금지
- secret/account/token 저장 또는 로그 출력 금지

허용:
- paper 전용 테이블/모델 추가
- paper 전용 service/repository/api 추가
- paper 전용 fill simulator 추가
- paper 전용 portfolio snapshot 추가
- paper 전용 audit log 추가
- 테스트 추가

구현 요구:
1. paper 전용 모델을 추가하라.
   - PaperOrder
   - PaperFill
   - PaperPosition
   - PaperPortfolioSnapshot
   - PaperAuditLog
   단, 기존 Order 테이블과 혼동되지 않게 명확히 분리하라.

2. paper API를 추가하라.
   - GET /api/paper/status
   - POST /api/paper/orders/preview
   - POST /api/paper/orders/submit
   - POST /api/paper/orders/{order_id}/cancel
   - GET /api/paper/orders
   - GET /api/paper/fills
   - GET /api/paper/positions
   - GET /api/paper/portfolio

3. paper order lifecycle을 구현하라.
   - previewed
   - accepted
   - rejected
   - submitted
   - filled
   - partially_filled placeholder
   - canceled
   - expired

4. paper risk gate를 구현하라.
   - symbol required
   - side buy/sell only
   - qty > 0
   - limit_price > 0 if provided
   - stop_price > 0 if provided
   - buy stop must be below entry
   - max_order_qty
   - max_order_notional
   - idempotency_key duplicate reject
   - live disabled reason included

5. paper fill simulator를 구현하라.
   - next_open fill
   - commission_bps
   - slippage_bps
   - insufficient next bar handling
   - fill result must update paper position and paper portfolio only

6. 기존 broker safety tests가 모두 통과해야 한다.
7. 신규 paper trading tests를 추가하라.
8. docs/VALIDATION.md와 README.md를 업데이트하라.

수정 후 실행:
- python -m pytest backend/tests
- cd frontend && npm run lint
- cd frontend && npm exec tsc -- --noEmit
- cd frontend && npm run build

산출물:
- 변경 요약
- 수정 파일 목록
- safety contract 유지 확인
- 테스트 결과
- 남은 미비점
```

---

### 6.3 백테스트 현실성 보강 프롬프트

```text
현재 백테스트는 next_open 기반 단순 모델이다. Phase 3E1의 paper execution foundation과 충돌하지 않도록, 백테스트 체결 모델을 보강하는 계획을 세워라.

목표:
- paper fill simulator와 유사한 체결 규칙을 백테스트에 반영
- 기존 backtest API와 tests를 깨지 않음
- 실주문/브로커 호출 없음

보강 항목:
1. gap-aware stop execution
2. limit order fill rule
3. commission/slippage config 유지
4. liquidity participation cap placeholder
5. cash/position state
6. max open positions
7. max gross exposure
8. turnover metric
9. annualized volatility
10. Sharpe/Sortino/Calmar
11. regime-by-regime metrics placeholder

먼저 계획만 작성하고, 수정 파일/테스트/리스크를 제시하라.
```

---

### 6.4 신규 전략 추가 프롬프트

```text
보고서 기준 미구현 전략 중 우선순위가 높은 momentum_rank, relative_strength_leader, new_high_breakout 전략을 추가하는 계획을 세워라.

조건:
- 기존 BaseStrategy 인터페이스를 유지한다.
- 기존 trend_breakout, vcp_breakout, canslim_lite 동작을 깨지 않는다.
- 전략 config는 backend/config/strategies.yaml에 추가한다.
- IndicatorService에 필요한 피처가 없으면 최소 범위로 추가한다.
- ScreenerService registry에 추가한다.
- 테스트를 추가한다.
- 프론트엔드 strategy filter/type에 필요한 최소 변경만 한다.

전략 조건:
1. momentum_rank
   - 12-1M momentum 또는 126일/252일 수익률 기반
   - RS percentile 상위
   - market_regime != bear
   - liquidity_ok

2. relative_strength_leader
   - rs_percentile >= threshold
   - sector_rs_score >= threshold
   - close > sma50
   - close near 52w high

3. new_high_breakout
   - close > previous 252d high
   - volume >= volume_ma50 * multiple
   - turnover_value >= min threshold
   - stop = pivot low or ATR stop

먼저 계획을 작성하고, 그 다음 구현하라.
```

---

### 6.5 Weekly Report 추가 프롬프트

```text
현재 daily report는 구현되어 있다. 전략 품질 점검을 위한 weekly strategy review report를 추가하는 계획을 세워라.

요구:
- 기존 daily report 동작을 깨지 않는다.
- reports 테이블 구조를 가능하면 유지한다.
- report_type="weekly"를 사용한다.
- Markdown 생성
- API 추가
  - POST /api/reports/weekly
  - GET /api/reports?type=weekly optional
- 프론트엔드 Reports 화면에 weekly report 표시를 최소 변경으로 추가한다.

리포트 섹션:
1. Performance Summary
2. Risk Summary
3. Hit Rate By Setup
4. Regime Diagnostics
5. Factor/Filter Attribution
6. Failed Trades Review
7. Parameter Drift Check
8. Audit Trail

먼저 계획만 작성하라.
```

---

## 7. Codex에게 전달할 최종 한 번에 붙여넣기용 프롬프트

```text
이 프로젝트는 deep-research-report.md 기반의 주식 분석 및 자동매매 보조 시스템이다.

현재 상태:
- Phase 3D broker safety scaffold는 main에 반영된 상태다.
- 현재는 Phase 3E1이 진행 중이다.
- 기존 방향을 무시하지 말고, 현재 Phase 3E1 변경사항을 먼저 분석해야 한다.
- 실주문/live broker/KIS 실제 주문/token 발급/websocket은 금지다.
- paper trading 또는 execution foundation을 하더라도 기존 safety contract를 깨면 안 된다.

우선 작업:
1. git status, 현재 브랜치, 최근 커밋, 변경 파일 목록을 확인해라.
2. README.md, docs/VALIDATION.md를 읽어라.
3. 다음 파일을 확인해라.
   - backend/app/main.py
   - backend/app/models/tables.py
   - backend/app/services/broker_service.py
   - backend/app/api/broker.py
   - backend/app/services/kis_service.py
   - backend/app/services/backtest_service.py
   - backend/app/services/screener_service.py
   - backend/app/services/report_service.py
   - backend/tests/test_phase3d_broker_safety.py
4. 현재 Phase 3E1에서 이미 구현된 부분과 미완료 부분을 분리해라.
5. 기존 Phase 3D 안전 계약이 깨졌는지 확인해라.

절대 깨면 안 되는 조건:
- /api/broker/orders/preview는 order_created=false
- /api/broker/orders/preview 후 기존 orders_count는 0
- can_submit=false
- preview_only=true
- token_issued=false
- network_call_performed=false
- adapter_order_call_performed=false
- adapter_network_call_performed=false
- /api/kis/orders/* 404 유지
- /api/kis/broker/* 404 유지
- /api/kis/websocket/* 404 유지
- Settings API에서 broker.yaml 원문/secret/account/token 노출 금지
- KIS token cache 파일 생성 금지

분석 후 아래 형식으로 계획만 작성해라. 아직 코드는 수정하지 마라.

# Phase 3E1 Current-State Analysis and Plan

## 1. Current Git Status
- branch:
- head:
- dirty files:
- changed files:

## 2. Existing Phase 3E1 Work
- implemented:
- partially implemented:
- unclear:
- risk:

## 3. Phase 3D Safety Contract Check
| check | status | evidence |
|---|---|---|

## 4. Gap Against deep-research-report.md
| area | implemented | missing | priority |
|---|---|---|---|

## 5. Recommended Phase 3E1 Scope
- include:
- exclude:
- defer:

## 6. Detailed Implementation Plan
각 task는 아래 형식으로 작성:
- task id
- objective
- files to modify
- implementation detail
- tests
- safety impact
- rollback plan

## 7. Validation Commands
- backend pytest
- frontend lint
- frontend typecheck
- frontend build
- secret scan or grep
- route safety smoke

## 8. Questions / Assumptions
명확하지 않은 부분이 있으면 질문하되, 코드 수정은 하지 마라.
```

---

## 8. 개발 순서 권장안

현재 Phase 3E1을 고려하면 다음 순서가 가장 안전하다.

```text
1. 현재 Phase 3E1 변경사항 분석
2. Phase 3D safety contract 회귀 테스트 고정
3. paper trading scope 확정
4. paper 전용 모델/API/service/test 추가
5. paper fill simulator 추가
6. paper portfolio snapshot 추가
7. README/docs/VALIDATION 업데이트
8. 백테스트 체결 모델 보강
9. 신규 전략 추가
10. weekly report 추가
```

실제 주문 연동은 다음 조건이 만족될 때까지 보류한다.

```text
paper trading 1주 이상 무중단 테스트
paper order lifecycle 안정화
fill simulator와 backtest 체결 모델 정합성 확보
daily/weekly report로 후보와 체결 결과 검증 가능
secret/account/token 저장 정책 검증
kill switch 테스트 통과
duplicate order guard 테스트 통과
```

---

## 9. 완료 기준

Phase 3E1 완료 기준은 아래처럼 두는 것을 권장한다.

```text
1. 기존 Phase 3D safety tests 통과
2. 신규 paper trading tests 통과
3. paper submit은 paper_* 테이블만 변경
4. 기존 orders table은 broker preview에서 여전히 0 유지
5. KIS live/execution route는 여전히 404
6. token/cache/network call 없음
7. frontend build 통과
8. docs/VALIDATION.md에 최신 검증 결과 반영
9. README에 Phase 3E1 범위와 제외 범위 명시
10. Codex 작업 결과에 safety impact 요약 포함
```

---

## 10. 최종 판단

현재 프로젝트는 보고서의 핵심 방향인 **시장 국면 + 후보 스크리너 + 점수화 + 리스크 계산 + 백테스트 + 자동 리포트**는 MVP 수준으로 구현되어 있다.

다만 아직 다음은 미완성이다.

```text
실전 데이터 수집
백테스트 현실성
전략 커버리지
weekly review
paper trading foundation
live broker integration
```

Phase 3E1에서는 live order로 가지 말고, **paper trading foundation을 기존 safety scaffold 위에 안전하게 얹는 방향**이 가장 적절하다.

핵심 원칙:

> 기존 `/api/broker/*` safety contract는 유지하고, paper trading은 별도 namespace와 별도 테이블에서만 시작한다.
