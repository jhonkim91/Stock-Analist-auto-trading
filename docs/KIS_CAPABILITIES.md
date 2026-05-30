# KIS Capabilities

## 요약

현재 프로젝트는 KIS 모의투자 환경에서 미국주식 정규장 주문만 submit 가능 세션으로 취급한다. 프리마켓, 애프터마켓, 미국주간거래(daytime)는 실제 KIS paper host에서 거부될 수 있어 API 호출 전에 차단한다.

## Capability Map

| 환경 | 미국주식 주문 허용 세션 | 처리 |
|---|---|---|
| `paper` | `regular` | KIS paper 주문 경로 진입 허용 |
| `paper` | `premarket`, `aftermarket`, `daytime`, `extended` | `KIS_PAPER_US_DAYTIME_ORDER_UNSUPPORTED`로 API 호출 전 차단 |
| `real` | `regular`, `premarket`, `aftermarket`, `daytime` | capability map상 허용. KRX 국내 현금 주문 실계좌 실행이 활성화되어 있으며, fail-closed 다중 게이트(`LIVE_TRADING_ENABLED` + `LIVE_ORDER_SUBMIT_ENABLED` + `ENABLE_REAL_ORDER` + live 자격증명 + live host + 주문별 confirm + kill switch + max-notional) 뒤에서 기본 차단된다. 실계좌 실행은 실제 KIS API 대비 미검증 상태이므로 첫 주문은 최소 수량으로 검증할 것 |

## Guard 정책

주문 직전 아래 조건이면 로컬에서 차단한다.

```text
env == paper
market == US
order_session != regular
```

차단 메시지는 다음 문구로 고정한다.

```text
KIS paper trading does not support US extended/daytime order session. Blocked before API call.
```

## 로그 필드

KIS 주문 차단 또는 실패 trace에는 raw secret 없이 다음 필드를 남긴다.

| 필드 | 의미 |
|---|---|
| `tr_id` | 호출 예정 또는 실제 호출된 KIS TR ID |
| `host` | 호출 대상 host |
| `market` | `US` 또는 `KR` |
| `symbol` | 주문 종목 |
| `order_session` | `regular`, `premarket`, `aftermarket`, `daytime`, `extended` |
| `rt_cd` | KIS 응답 코드. 로컬 차단은 `LOCAL_BLOCK` |
| `msg_cd` | KIS 메시지 코드 또는 로컬 차단 reason code |
| `msg1` | KIS 메시지 또는 로컬 차단 설명 |

## 현재 확인된 KIS Paper 결과

- 미국주식 프리마켓 일반 주문 `VTTT1002U`: `40570000 / 모의투자 장시작전 입니다.`
- 미국주간주문 `/uapi/overseas-stock/v1/trading/daytime-order`, `TTTS6036U`: `EGW02006 / 모의투자 TR 이 아닙니다.`
- 위 결과에 따라 paper 환경에서는 extended/daytime session을 네트워크 전 차단한다.
