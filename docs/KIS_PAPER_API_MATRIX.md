# KIS Paper API Matrix

## 기준

- 이 문서는 Phase 0 확인 matrix이며 구현 사양서가 아니다.
- 공식 KIS Developers 문서에서 완전 확인되지 않은 endpoint/path/TR-ID/request field는 모두 `확인 필요`로 표시한다.
- Phase 0에서는 KIS 호출, token 발급, credential 저장, paper submit/cancel/sync 구현을 하지 않는다.
- 현재 구현 상태는 `feature/kis-paper-goal-phases` Phase 5 기준이다. `/api/paper/orders/submit`은 local `paper_orders` 전용이고 `/api/paper/sync`는 no-op disabled contract이며 KIS paper endpoint/TR-ID/request field는 여전히 추정 구현하지 않는다.

## 공식 문서 확인 범위

2026-05-27 기준 공식 KIS Developers API 문서 navigation을 확인했다. 정적 문서 화면에서 국내주식 주문/계좌 capability 목록과 `Method`, `URL`, `실전 Domain`, `모의 Domain`, `실전 TR ID`, `모의 TR ID` 항목 존재는 확인되지만, Phase 0에서는 각 paper request/response field를 구현 근거로 확정하지 않는다.

| 출처 | 확인한 내용 | Phase 0 해석 |
|---|---|---|
| [KIS Developers API portal](https://apiportal.koreainvestment.com/) | REST 방식은 AppKey/AppSecret 기반 token으로 API를 호출한다고 설명함 | token lifecycle 자체는 공식 문서 영역이나 paper 구현 endpoint/field는 별도 확인 필요 |
| [KIS Developers API portal](https://apiportal.koreainvestment.com/) | WebSocket 방식은 접속키 발급 후 실시간 데이터를 수신한다고 설명함 | live WebSocket trading은 현재 목표의 non-goal이며 구현 금지 |
| [KIS Developers API 문서 navigation](https://apiportal.koreainvestment.com/apiservice-apiservice%3F/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice) | OAuth, 국내주식 주문/계좌의 주문, 정정취소, 주문체결조회, 잔고조회, 매수/매도 가능조회 항목이 존재함 | capability 존재는 확인되나 paper endpoint/path/TR-ID와 request/response field는 확인 필요 |
| [공식 `koreainvestment/open-trading-api` sample repository](https://github.com/koreainvestment/open-trading-api) | KIS가 제공하는 샘플 코드 저장소가 존재함 | 샘플은 참고 자료이며 endpoint/path/TR-ID 완전 확인 근거로 단독 사용하지 않음 |

## Matrix

| Planned capability | 공식 문서 확인 상태 | Endpoint/path/TR-ID 상태 | 현재 구현 상태 | 비고 |
|---|---|---|---|---|
| KIS paper OAuth/token lifecycle | 부분 확인 | 확인 필요 | 미구현. 현재 token service는 disabled/status-only | raw token persistence 금지 |
| KIS hashkey/request signing | 확인 필요 | 확인 필요 | 미구현 | 공식 request field 확인 전 사용 금지 |
| Paper order preview | KIS API 아님 | 해당 없음 | 구현됨. `/api/paper/orders/preview` deny preview only | DB write, token, network call 없음 |
| Paper cash order submit | 국내주식 주문/계좌 category는 확인 | 확인 필요 | local-only 구현 | `/api/paper/orders/submit`은 confirm/idempotency/kill-switch gated local `paper_orders` 저장만 수행. KIS paper domain/TR-ID/request field 확인 전 broker submit disabled |
| Paper order cancel/modify | 국내주식 `주식주문(정정취소)` category는 확인 | 확인 필요 | safely disabled | `/api/paper/orders/cancel`은 `KIS_PAPER_CANCEL_CONFIRMATION_REQUIRED`로 응답하며 cancel payload 추정 금지 |
| Cancelable/open order inquiry | 국내주식 `주식정정취소가능주문조회` category는 확인 | 확인 필요 | 미구현 | sync/cancel 전제 데이터 확인 필요 |
| Daily order/fill inquiry | 국내주식 `주식일별주문체결조회` category는 확인 | 확인 필요 | safely disabled + local view 구현 | `/api/paper/fills`는 `paper_fills`만 조회. KIS fetch/sync는 공식 field 확인 전 disabled |
| Balance/position inquiry | 국내주식 `주식잔고조회` category는 확인 | 확인 필요 | safely disabled + local view 구현 | `/api/paper/positions`, `/api/paper/portfolio`는 paper tables만 조회하고 synthetic `positions`와 분리 |
| Buyable amount inquiry | 국내주식 `매수가능조회` category는 확인 | 확인 필요 | 미구현 | cash lock/available cash field 확인 필요 |
| Sellable quantity inquiry | 국내주식 `매도가능수량조회` category는 확인 | 확인 필요 | 미구현 | short/oversell guard field 확인 필요 |
| Paper portfolio/account snapshot | 관련 계좌 조회 category는 확인 | 확인 필요 | local view 구현 | `/api/paper/portfolio`는 `paper_portfolio_snapshots`와 `paper_positions` 요약만 반환. raw account number 노출 금지 |
| Broker audit events | KIS API 아님 | 해당 없음 | local paper submit audit opt-in 구현 | raw account/token/webhook redaction 필수 |
| Notification delivery | KIS API 아님 | 해당 없음 | disabled/mock/live adapter foundation 구현 | Discord/Telegram secret은 env only |
| Report notification | KIS API 아님 | 해당 없음 | 구현 | `/api/reports/{report_id}/notify`, channel-safe split, optional attachment metadata, sanitized delivery logs |
| Paper bot scheduler | KIS API 아님 | 해당 없음 | 미구현 | default scheduler disabled, `PAPER_BOT_AUTO_SUBMIT=false` |
| KIS live broker adapter | 현재 범위 제외 | 해당 없음 | 미구현 | disabled placeholder only |
| KIS WebSocket trading | 공식 WebSocket 방식은 확인 | 확인 필요 | 미구현 | live WebSocket trading은 non-goal |

## 다음 단계 진입 조건

- Phase 1은 notification foundation만 다루며 KIS paper submit/sync를 구현하지 않는다.
- KIS paper broker contract 단계에서는 이 matrix의 `확인 필요` 항목을 공식 문서 기준으로 먼저 보강해야 한다.
- 공식 문서에서 확인되지 않은 request field, endpoint, TR-ID를 코드나 문서에 확정값으로 쓰지 않는다.
