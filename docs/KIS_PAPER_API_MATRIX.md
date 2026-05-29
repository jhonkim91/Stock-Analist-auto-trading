# KIS Paper API Matrix

## 기준

- 이 문서는 현재 `Project Reset: Telegram + KIS Paper Trading Bot` 기준 KIS 모의투자 API 확인 matrix다.
- 확인 기준은 한국투자증권 공식 GitHub 샘플 저장소 `koreainvestment/open-trading-api` shallow clone이다.
- 확인한 공식 샘플 commit: `33e0e1e65cd1c8c8b639531483ec0b327087bab1`.
- 실제 KIS live 주문, live cancel, live fallback은 계속 금지한다.
- `.env`, `.env.local`, 계좌번호, AppKey/AppSecret, access token 원문은 문서/응답/로그에 기록하지 않는다.

## 공식 샘플 확인 범위

| 구분 | 공식 샘플 파일 | 확인 내용 |
|---|---|---|
| 국내 현금 주문 | `examples_llm/domestic_stock/order_cash/order_cash.py` | `/uapi/domestic-stock/v1/trading/order-cash`, paper buy/sell `VTTC0012U`/`VTTC0011U`, body field |
| 국내 정정/취소 | `examples_llm/domestic_stock/order_rvsecncl/order_rvsecncl.py` | `/uapi/domestic-stock/v1/trading/order-rvsecncl`, paper `VTTC0013U`, body field |
| 국내 일별 주문체결 | `examples_llm/domestic_stock/inquire_daily_ccld/inquire_daily_ccld.py` | `/uapi/domestic-stock/v1/trading/inquire-daily-ccld`, paper inner `VTTC0081R`, before `VTSC9215R` |
| 국내 잔고 | `examples_llm/domestic_stock/inquire_balance/inquire_balance.py` | `/uapi/domestic-stock/v1/trading/inquire-balance`, paper `VTTC8434R` |
| 국내 매수가능 | `examples_llm/domestic_stock/inquire_psbl_order/inquire_psbl_order.py` | `/uapi/domestic-stock/v1/trading/inquire-psbl-order`, paper `VTTC8908R` |
| 해외 regular 주문 | `examples_llm/overseas_stock/order/order.py` | `/uapi/overseas-stock/v1/trading/order`, US paper buy/sell `VTTT1002U`/`VTTT1006U`, paper는 `ORD_DVSN=00` 중심 |
| 해외 정정/취소 | `examples_llm/overseas_stock/order_rvsecncl/order_rvsecncl.py` | `/uapi/overseas-stock/v1/trading/order-rvsecncl`, paper `VTTT1004U` |
| 해외 주문체결 | `examples_llm/overseas_stock/inquire_ccnl/inquire_ccnl.py` | `/uapi/overseas-stock/v1/trading/inquire-ccnl`, paper `VTTS3035R` |
| 해외 잔고 | `examples_llm/overseas_stock/inquire_balance/inquire_balance.py` | `/uapi/overseas-stock/v1/trading/inquire-balance`, paper `VTTS3012R` |
| 미국주간주문 | `examples_llm/overseas_stock/daytime_order/daytime_order.py` | `/uapi/overseas-stock/v1/trading/daytime-order`, `TTTS6036U`/`TTTS6037U`, paper `env_dv` 없음 |
| 미국주간정정취소 | `examples_llm/overseas_stock/daytime_order_rvsecncl/daytime_order_rvsecncl.py` | `/uapi/overseas-stock/v1/trading/daytime-order-rvsecncl`, `TTTS6038U`, paper `env_dv` 없음 |

## 현재 구현 Matrix

| Capability | Endpoint/path | Paper TR ID | 현재 구현 상태 | 정책 |
|---|---|---|---|---|
| KIS paper OAuth/token lifecycle | `/oauth2/tokenP` | 해당 없음 | `KisTokenManager` 구현 | `KIS_TOKEN_ISSUE_ENABLED=true`, `KIS_ENV=paper`, `confirm=true` 필요. raw token 응답/문서 미노출 |
| Paper order preview | KIS API 아님 | 해당 없음 | 구현 | DB write/token/network call 없음 |
| 국내 현금 매수 | `/uapi/domestic-stock/v1/trading/order-cash` | `VTTC0012U` | 구현 | paper_kis gate, confirm, idempotency, kill switch, risk cap 필요 |
| 국내 현금 매도 | `/uapi/domestic-stock/v1/trading/order-cash` | `VTTC0011U` | 구현 | live TR ID 사용 금지 |
| 국내 주문 정정/취소 | `/uapi/domestic-stock/v1/trading/order-rvsecncl` | `VTTC0013U` | 구현 | `paper_orders`에 저장된 paper order만 취소 대상. 확인/중복 방지/audit 필수 |
| 국내 일별 주문체결 | `/uapi/domestic-stock/v1/trading/inquire-daily-ccld` | `VTTC0081R` | 구현 | sync/fill mirror 전용. before 3개월 이전 `VTSC9215R`은 현재 미사용 |
| 국내 잔고/포지션 | `/uapi/domestic-stock/v1/trading/inquire-balance` | `VTTC8434R` | 구현 | read-only 조회 후 local snapshot/position mirror |
| 국내 매수가능조회 | `/uapi/domestic-stock/v1/trading/inquire-psbl-order` | `VTTC8908R` | 확인됨, 미구현 | sizing/risk guard 후보. submit 권한으로 해석하지 않음 |
| 국내 정정취소가능주문조회 | `/uapi/domestic-stock/v1/trading/inquire-psbl-rvsecncl` | 확인 필요 | 미구현 | 현재 cancel은 저장된 paper order와 KIS cancel 응답 기준 |
| 국내 매도가능수량조회 | `/uapi/domestic-stock/v1/trading/inquire-psbl-sell` | 확인 필요 | 미구현 | oversell guard 후보. paper TR 확인 전 fail-closed |
| 해외 US regular 매수 | `/uapi/overseas-stock/v1/trading/order` | `VTTT1002U` | 구현 | `market=US`, regular session, NASD/NYSE/AMEX, paper-only gate 필요 |
| 해외 US regular 매도 | `/uapi/overseas-stock/v1/trading/order` | `VTTT1006U` | 구현 | paper 샘플은 지정가 `ORD_DVSN=00` 중심. live fallback 금지 |
| 해외 정정/취소 | `/uapi/overseas-stock/v1/trading/order-rvsecncl` | `VTTT1004U` | 구현 | KIS가 취소 불가 응답을 주면 재시도 없이 audit |
| 해외 주문체결조회 | `/uapi/overseas-stock/v1/trading/inquire-ccnl` | `VTTS3035R` | 구현 | read-only order/fill sync |
| 해외 잔고조회 | `/uapi/overseas-stock/v1/trading/inquire-balance` | `VTTS3012R` | 구현 | read-only balance/position mirror |
| 미국주간주문 | `/uapi/overseas-stock/v1/trading/daytime-order` | 공식 샘플 `TTTS6036U`/`TTTS6037U` only | 차단 | 공식 샘플에 paper `env_dv` 없음. 실제 paper host도 `EGW02006 / 모의투자 TR 이 아닙니다.`로 거부 |
| 미국주간정정취소 | `/uapi/overseas-stock/v1/trading/daytime-order-rvsecncl` | 공식 샘플 `TTTS6038U` only | 차단 | paper adapter는 `KIS_PAPER_US_DAYTIME_ORDER_UNSUPPORTED`로 API 호출 전 차단 |
| Broker audit events | KIS API 아님 | 해당 없음 | 구현 | 주문/취소/체결/sync/bot 판단은 audit log 기록 |
| Telegram report/bot command | KIS API 아님 | 해당 없음 | 구현 | Telegram token/chat id는 env only, raw 값 미노출 |
| KIS live broker adapter | 현재 범위 제외 | 해당 없음 | disabled scaffold | 실계좌 주문/취소/체결 금지 |

## 현재 Adapter Constants

| 상수 | 값 |
|---|---|
| `KIS_ORDER_CASH_PATH` | `/uapi/domestic-stock/v1/trading/order-cash` |
| `KIS_ORDER_CANCEL_PATH` | `/uapi/domestic-stock/v1/trading/order-rvsecncl` |
| `KIS_DAILY_CCLD_PATH` | `/uapi/domestic-stock/v1/trading/inquire-daily-ccld` |
| `KIS_BALANCE_PATH` | `/uapi/domestic-stock/v1/trading/inquire-balance` |
| `KIS_OVERSEAS_ORDER_PATH` | `/uapi/overseas-stock/v1/trading/order` |
| `KIS_OVERSEAS_ORDER_CANCEL_PATH` | `/uapi/overseas-stock/v1/trading/order-rvsecncl` |
| `KIS_OVERSEAS_CCLD_PATH` | `/uapi/overseas-stock/v1/trading/inquire-ccnl` |
| `KIS_OVERSEAS_BALANCE_PATH` | `/uapi/overseas-stock/v1/trading/inquire-balance` |
| `KIS_PAPER_BUY_TR_ID` | `VTTC0012U` |
| `KIS_PAPER_SELL_TR_ID` | `VTTC0011U` |
| `KIS_PAPER_CANCEL_TR_ID` | `VTTC0013U` |
| `KIS_PAPER_DAILY_CCLD_TR_ID` | `VTTC0081R` |
| `KIS_PAPER_BALANCE_TR_ID` | `VTTC8434R` |
| `KIS_PAPER_US_BUY_TR_ID` | `VTTT1002U` |
| `KIS_PAPER_US_SELL_TR_ID` | `VTTT1006U` |
| `KIS_PAPER_OVERSEAS_CANCEL_TR_ID` | `VTTT1004U` |
| `KIS_PAPER_OVERSEAS_CCLD_TR_ID` | `VTTS3035R` |
| `KIS_PAPER_OVERSEAS_BALANCE_TR_ID` | `VTTS3012R` |

## 남은 확인 필요 항목

- 국내 정정취소가능주문조회 paper TR ID와 field.
- 국내 매도가능수량조회 paper TR ID와 field.
- 국내 3개월 이전 체결조회 `VTSC9215R` 적용 여부와 현재 adapter 사용 범위.
- KIS error code별 재시도 가능성. 현재 주문/취소 실패는 재시도하지 않고 audit만 기록한다.
