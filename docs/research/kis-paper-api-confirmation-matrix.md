# KIS Paper API Confirmation Matrix

## 핵심 요약

이 문서는 KIS 모의투자 자동매매 프로젝트의 공식 샘플 대조 기록이다. 현재 기준으로 국내/해외 regular paper 주문, 취소, 주문체결조회, 잔고조회에 필요한 endpoint/TR ID는 공식 샘플과 현재 adapter 상수 간 일치한다. 실계좌 live 국내 현금 경로는 게이트로 활성화되어 있고(`KisLiveOrderExecutor`, 다중 게이트·기본 차단·실 API 미검증), 해외 live와 미국주간주문 paper 경로는 계속 차단한다.

| 항목 | 판정 |
|---|---|
| production code 변경 | 없음 |
| KIS 네트워크 호출 | 없음 |
| token 발급/저장 | 없음 |
| submit/cancel/sync 실행 | 없음 |
| secret 원문 기록 | 없음 |
| `.env` / `.env.local` 변경 | 없음 |
| 공식 샘플 commit | `33e0e1e65cd1c8c8b639531483ec0b327087bab1` |

## 확인 출처

| 출처 | 확인에 사용한 내용 |
|---|---|
| `https://github.com/koreainvestment/open-trading-api` | 한국투자증권 KIS Developers 공식 샘플 저장소 |
| `examples_llm/domestic_stock/order_cash/order_cash.py` | 국내 현금 매수/매도 endpoint, paper TR ID, body field |
| `examples_llm/domestic_stock/order_rvsecncl/order_rvsecncl.py` | 국내 정정/취소 endpoint, paper TR ID, body field |
| `examples_llm/domestic_stock/inquire_daily_ccld/inquire_daily_ccld.py` | 국내 일별주문체결 endpoint, paper TR ID |
| `examples_llm/domestic_stock/inquire_balance/inquire_balance.py` | 국내 잔고조회 endpoint, paper TR ID |
| `examples_llm/domestic_stock/inquire_psbl_order/inquire_psbl_order.py` | 국내 매수가능조회 endpoint, paper TR ID |
| `examples_llm/domestic_stock/inquire_psbl_rvsecncl/inquire_psbl_rvsecncl.py` | 국내 정정취소가능주문조회 endpoint, real-only TR ID |
| `examples_llm/domestic_stock/inquire_psbl_sell/inquire_psbl_sell.py` | 국내 매도가능수량조회 endpoint, real-only TR ID |
| `examples_llm/overseas_stock/order/order.py` | 해외 regular 주문 endpoint, US paper TR ID |
| `examples_llm/overseas_stock/order_rvsecncl/order_rvsecncl.py` | 해외 정정/취소 endpoint, paper TR ID |
| `examples_llm/overseas_stock/inquire_ccnl/inquire_ccnl.py` | 해외 주문체결조회 endpoint, paper TR ID |
| `examples_llm/overseas_stock/inquire_balance/inquire_balance.py` | 해외 잔고조회 endpoint, paper TR ID |
| `examples_llm/overseas_stock/daytime_order/daytime_order.py` | 미국주간주문 endpoint와 live TR ID only |
| `examples_llm/overseas_stock/daytime_order_rvsecncl/daytime_order_rvsecncl.py` | 미국주간정정취소 endpoint와 live TR ID only |

## 국내주식 주문/계좌 Capability Matrix

| capability | method | endpoint/path | paper TR ID | request field 확인 | implementation policy |
|---|---:|---|---|---|---|
| 현금 매수 주문 | POST | `/uapi/domestic-stock/v1/trading/order-cash` | `VTTC0012U` | 샘플 기준 body field 확인 | paper-only, kill-switch, idempotency, duplicate guard 필수 |
| 현금 매도 주문 | POST | `/uapi/domestic-stock/v1/trading/order-cash` | `VTTC0011U` | 샘플 기준 body field 확인 | live TR ID 사용 금지 |
| 주문 정정/취소 | POST | `/uapi/domestic-stock/v1/trading/order-rvsecncl` | `VTTC0013U` | 샘플 기준 body field 확인 | 저장된 paper order와 confirm/idempotency gate 필요 |
| 일별 주문체결조회 | GET | `/uapi/domestic-stock/v1/trading/inquire-daily-ccld` | `VTTC0081R` | 샘플 기준 query field 확인 | order/fill sync mirror 전용 |
| 잔고/포지션 조회 | GET | `/uapi/domestic-stock/v1/trading/inquire-balance` | `VTTC8434R` | 샘플 기준 query field 확인 | read-only만 허용. raw 계좌번호 응답 금지 |
| 매수가능조회 | GET | `/uapi/domestic-stock/v1/trading/inquire-psbl-order` | `VTTC8908R` | 샘플 기준 query field 확인 | sizing/risk guard 후보. submit 권한 의미 없음 |
| 정정취소가능주문조회 | GET | `/uapi/domestic-stock/v1/trading/inquire-psbl-rvsecncl` | 공식 샘플 real `TTTC0084R` only, paper 미확인 | 샘플은 `env_dv` 없이 real TR만 사용 | cancel 구현 보강 후보. 추정 `VT*` 변환 금지 |
| 매도가능수량조회 | GET | `/uapi/domestic-stock/v1/trading/inquire-psbl-sell` | 공식 샘플 real `TTTC8408R` only, paper 미확인 | 샘플은 `env_dv` 없이 real TR만 사용 | oversell guard 후보. paper 확인 전 fail-closed |
| 3개월 이전 체결조회 | GET | `/uapi/domestic-stock/v1/trading/inquire-daily-ccld` | `VTSC9215R` | 샘플상 `pd_dv=before`에서 확인 | 현재 adapter는 `VTTC0081R` inner 조회만 사용 |

## 해외주식 주문/계좌 Capability Matrix

| capability | method | endpoint/path | paper TR ID | request field 확인 | implementation policy |
|---|---:|---|---|---|---|
| 미국 regular 매수 주문 | POST | `/uapi/overseas-stock/v1/trading/order` | `VTTT1002U` | 샘플 기준 body field 확인 | `order_session=regular`만 허용 |
| 미국 regular 매도 주문 | POST | `/uapi/overseas-stock/v1/trading/order` | `VTTT1006U` | 샘플 기준 body field 확인 | paper 샘플은 지정가 `ORD_DVSN=00` 중심 |
| 해외 정정/취소 | POST | `/uapi/overseas-stock/v1/trading/order-rvsecncl` | `VTTT1004U` | 샘플 기준 body field 확인 | KIS 취소 불가 응답은 재시도 없이 audit |
| 해외 주문체결조회 | GET | `/uapi/overseas-stock/v1/trading/inquire-ccnl` | `VTTS3035R` | 샘플 기준 query field 확인 | read-only order/fill sync |
| 해외 잔고조회 | GET | `/uapi/overseas-stock/v1/trading/inquire-balance` | `VTTS3012R` | 샘플 기준 query field 확인 | read-only position/balance mirror |
| 미국주간 매수/매도 | POST | `/uapi/overseas-stock/v1/trading/daytime-order` | `TTTS6036U` / `TTTS6037U` | 공식 샘플은 live TR ID only, `env_dv` 없음 | paper adapter에서 API 호출 전 차단 |
| 미국주간 정정/취소 | POST | `/uapi/overseas-stock/v1/trading/daytime-order-rvsecncl` | `TTTS6038U` | 공식 샘플은 live TR ID only, `env_dv` 없음 | paper adapter에서 API 호출 전 차단 |

## 현재 코드 대조

| 항목 | 현재 코드 | 판정 |
|---|---|---|
| 국내 buy/sell/cancel/daily/balance | `backend/app/brokers/kis_paper.py` constants `VTTC0012U`, `VTTC0011U`, `VTTC0013U`, `VTTC0081R`, `VTTC8434R` | 공식 샘플과 일치 |
| 해외 US buy/sell/cancel/ccnl/balance | `VTTT1002U`, `VTTT1006U`, `VTTT1004U`, `VTTS3035R`, `VTTS3012R` | 공식 샘플과 일치 |
| 미국주간주문 | `KIS_PAPER_US_DAYTIME_ORDER_UNSUPPORTED`로 차단 | 공식 샘플에 paper TR ID가 없고 실제 paper host 거부 기록과 일치 |
| live order route | `live_disabled` scaffold | 현재 목표와 일치 |

## Hashkey와 Signing 상태

| 항목 | 상태 | 정책 |
|---|---|---|
| hashkey endpoint | 공식 샘플에서 `/uapi/hashkey` 확인 |
| hashkey 필수 여부 | 현재 adapter는 raw body/hash logging 금지와 fail-closed gate를 우선 |
| request signing | paper submit 전 credential/token/gate 확인 |
| raw body logging | 금지 |

## 남은 미확인 항목

| 항목 | 처리 |
|---|---|
| 국내 정정취소가능주문조회 paper TR ID | 공식 샘플에서는 real `TTTC0084R`만 확인. KIS 포털/운영 문서 또는 paper host 확인 전 구현 보류 |
| 국내 매도가능수량조회 paper TR ID | 공식 샘플에서는 real `TTTC8408R`만 확인. paper TR 확인 전 fail-closed |
| rate limit 및 retry contract | retry는 보수적으로 disabled 또는 bounded |
| error code별 재시도 가능성 | 주문 상태 변경 전 audit-only |
| 실전/모의 fallback | 금지. paper failure가 live call로 이어지면 안 됨 |
