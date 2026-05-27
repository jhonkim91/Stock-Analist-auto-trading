# KIS Paper API Confirmation Matrix

## 핵심 요약

이 문서는 루트 `goal.md`의 `Phase 1: KIS Paper API Confirmation Matrix` 산출물이다. Phase 1에서는 production code를 변경하지 않고, 공식 KIS Developers 포털 및 한국투자증권 공식 GitHub 샘플에서 확인 가능한 KIS 모의투자 capability만 분리 기록한다.

| 항목 | Phase 1 판정 |
|---|---|
| production code 변경 | 없음 |
| KIS 네트워크 호출 | 없음 |
| token 발급/저장 | 없음 |
| submit/cancel/sync 구현 | 없음 |
| secret 원문 기록 | 없음 |
| `.env` / `.env.local` 변경 | 없음 |

## 확인 출처

| 출처 | 확인에 사용한 내용 |
|---|---|
| KIS Developers API 포털: https://apiportal.koreainvestment.com/ | REST, WebSocket, OAuth, 국내주식 주문/계좌 capability가 공식 문서 영역에 존재함을 확인 |
| 공식 GitHub 저장소: https://github.com/koreainvestment/open-trading-api | KIS Developers 공식 샘플 저장소임을 확인 |
| 공식 샘플 `kis_devlp.yaml` | 실전/모의 REST domain, 실전/모의 WebSocket domain placeholder 구조 확인 |
| 공식 샘플 `examples_llm/kis_auth.py` | REST token path, WebSocket approval path, hashkey path, paper mode 전환 방식 확인 |
| 공식 샘플 `examples_llm/domestic_stock/*` | 국내주식 주문/정정취소/잔고/주문체결/가능조회 endpoint와 일부 TR ID 확인 |
| Telegram Bot API: https://core.telegram.org/bots/api | Phase 6 notification primary channel 결정을 위해 HTTPS Bot API와 `sendMessage` text contract 확인 |
| Discord Webhooks: https://docs.discord.com/developers/platform/webhooks | Phase 6 follow-up channel 결정을 위해 incoming webhook one-way delivery contract 확인 |
| Discord Webhook Resource: https://docs.discord.com/developers/resources/webhook | Phase 6 follow-up channel 제약 확인. content length, required payload, `allowed_mentions` 고려 |

## 공식 확인 항목

| capability | 확인 상태 | 공식 샘플 근거 | Phase 1 해석 |
|---|---|---|---|
| 실전 REST base URL | 확인 | `prod: https://openapi.koreainvestment.com:9443` | live base URL은 문서상 존재하나 현재 구현 금지 |
| 모의 REST base URL | 확인 | `vps: https://openapivts.koreainvestment.com:29443` | paper-only adapter 설계 시 base URL 후보 |
| 실전 WebSocket base URL | 확인 | `ops: ws://ops.koreainvestment.com:21000` | live WebSocket trading/order execution은 구현 금지 |
| 모의 WebSocket base URL | 확인 | `vops: ws://ops.koreainvestment.com:31000` | Phase 1에서는 사용하지 않음 |
| REST token path | 확인 | `/oauth2/tokenP` | raw token persistence 금지, 추후 token manager는 metadata only |
| WebSocket approval path | 확인 | `/oauth2/Approval` | order execution WebSocket 구현 금지 |
| hashkey path | 확인 | `/uapi/hashkey` | 공식 샘플은 주문 API hashkey helper를 제공하나, Phase 3 전까지 사용 금지 |
| paper mode selector | 확인 | `svr="vps"`, `_isPaper=True` | paper mode는 live fallback 없이 독립 처리해야 함 |
| paper credential keys | 확인 | `paper_app`, `paper_sec`, `my_paper_stock`, `my_paper_future` placeholder | raw 값은 env/local secret에서만 읽고 문서/DB/API 응답 저장 금지 |

## 국내주식 주문/계좌 capability matrix

| capability | method | endpoint/path | paper TR ID | request field 확인 | implementation policy |
|---|---:|---|---|---|---|
| 현금 매수 주문 | POST | `/uapi/domestic-stock/v1/trading/order-cash` | `VTTC0012U` | 샘플 기준 필수 body field 확인 | Phase 4 전까지 disabled. 구현 시 paper-only, kill-switch, idempotency, duplicate guard 필수 |
| 현금 매도 주문 | POST | `/uapi/domestic-stock/v1/trading/order-cash` | `VTTC0011U` | 샘플 기준 필수 body field 확인 | Phase 4 전까지 disabled. live TR ID 사용 금지 |
| 주문 정정/취소 | POST | `/uapi/domestic-stock/v1/trading/order-rvsecncl` | `VTTC0013U` | 샘플 기준 필수 body field 확인 | 취소 전 가능주문조회 확인 필요. 미확인 상태에서는 fail-closed |
| 잔고/포지션 조회 | GET | `/uapi/domestic-stock/v1/trading/inquire-balance` | `VTTC8434R` | 샘플 기준 query field와 output1/output2 구조 확인 | read-only만 허용. raw 계좌번호 응답 금지 |
| 매수가능조회 | GET | `/uapi/domestic-stock/v1/trading/inquire-psbl-order` | `VTTC8908R` | 샘플 기준 query field 확인 | sizing/risk guard 입력 후보. submit 권한을 의미하지 않음 |
| 정정취소가능주문조회 | GET | `/uapi/domestic-stock/v1/trading/inquire-psbl-rvsecncl` | 확인 필요 | 샘플은 path와 query field를 제공하나 paper TR 직접값은 별도 확인 필요 | cancel 구현 전 paper TR 직접 확인 필요 |
| 매도가능수량조회 | GET | `/uapi/domestic-stock/v1/trading/inquire-psbl-sell` | 확인 필요 | 샘플은 path와 query field를 제공하나 paper TR 직접값은 별도 확인 필요 | oversell guard 후보. paper TR 확인 전 fail-closed |
| 일별 주문체결조회 | GET | 확인 필요 | 확인 필요 | 공식 샘플 path/TR ID 직접 확인 필요 | fill/order sync 구현 전 확인 필요 |
| 계좌/포트폴리오 summary sync | GET | 부분 확인 | `VTTC8434R` 기반 잔고조회만 확인 | cash/portfolio field 해석은 output2 mapping 범위 내에서만 사용 | 확인되지 않은 cash lock, realized PnL, margin field는 추정 금지 |

## Hashkey와 signing 상태

| 항목 | 상태 | 정책 |
|---|---|---|
| hashkey endpoint | 공식 샘플에서 `/uapi/hashkey` 확인 |
| hashkey 필수 여부 | 공식 샘플 주석상 주문 API에서 사용할 수 있으나 현재 필수 여부는 구현 근거로 확정하지 않음 |
| Phase 3 signer 정책 | request signing prerequisites가 완전하지 않으면 submit을 reject하는 fail-closed utility만 허용 |
| raw body logging | 금지 |

## Phase 6 Notification Channel Decision

| 항목 | 결정 | 근거/정책 |
|---|---|---|
| primary notifier | Telegram-first | 공식 Telegram Bot API는 HTTPS 기반 `sendMessage` text delivery를 제공하며 짧은 trading/report alert에 적합 |
| follow-up notifier | Discord incoming webhook | 공식 Discord 문서는 one-way incoming webhook POST를 지원하지만 webhook URL 자체가 bearer secret이므로 mirror/fallback 후보로 둔다 |
| 구현 범위 | 문서 결정만 수행 | Phase 6에서는 notifier service/route/migration/config를 추가하지 않는다 |
| secret handling | env-only | Telegram token/chat identifier와 Discord webhook URL 원문은 코드/문서/DB/API/log에 저장하지 않는다 |
| formatting policy | plain text first | Telegram `parse_mode=null`, Discord `allowed_mentions.parse=[]`를 후속 구현 기준으로 둔다 |
| failure policy | non-blocking | notifier 실패가 paper submit/sync/portfolio snapshot 상태를 rollback하거나 변경하면 안 된다 |
| 상세 결정 문서 | `docs/research/notification-channel-decision.md` | Telegram-first 결정, Discord follow-up path, constraints, security handling 기록 |

## mock-only 제한 및 미확인 항목

| 항목 | 상태 | 처리 |
|---|---|---|
| KIS paper order 실제 체결 timing | 확인 필요 | sync/polling은 fail-closed 또는 mock/local 상태로 시작 |
| order/fill sync endpoint | 확인 필요 | 공식 path/TR ID 확인 전 네트워크 fetch 금지 |
| cancelable/open order paper TR ID | 확인 필요 | cancel route는 확인 전 disabled |
| sellable quantity paper TR ID | 확인 필요 | oversell guard는 local/risk fail-closed 우선 |
| rate limit 및 retry contract | 확인 필요 | retry는 보수적으로 disabled 또는 bounded |
| error code별 재시도 가능성 | 확인 필요 | 주문 상태 변경 전에 audit-only로 남김 |
| 실전/모의 fallback | 금지 | paper failure가 live call로 이어지면 안 됨 |

## 다음 Phase 진입 판정

Phase 2는 실제 submit/cancel/network 구현이 아니라 adapter boundary hardening이다. 따라서 위 matrix의 미확인 항목은 adapter capability에서 `confirmation_required` 또는 disabled 상태로 표현하고, KIS endpoint/TR ID/request field를 추정해 호출하지 않는 조건으로 Phase 2 진입이 가능하다.
