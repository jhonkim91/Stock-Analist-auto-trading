# Notification Channel Decision

## 핵심 요약

`goal.md`의 `Phase 6: Notification Channel Decision` 범위에서는 notifier를 구현하지 않고 primary channel과 interface contract만 확정한다. 2026-05-27 기준 primary notifier는 Telegram-first로 결정한다. Discord는 운영 채널 mirror 또는 fallback 후보로 남기되, Phase 7 구현 전까지 delivery code, route, migration, config 변경을 추가하지 않는다.

| 항목 | 결정 |
|---|---|
| primary channel | Telegram |
| follow-up channel | Discord incoming webhook |
| Phase 6 구현 여부 | 없음. 문서 결정만 수행 |
| secret 저장 | 금지. env-only placeholder 이름만 허용 |
| trading 영향 | notifier 실패가 paper submit/sync/portfolio state를 rollback하거나 변경하면 안 됨 |
| 기본 동작 | disabled + dry-run 우선 |

## 공식 근거

| 출처 | 확인 내용 | Phase 6 해석 |
|---|---|---|
| Telegram Bot API: https://core.telegram.org/bots/api | Bot API는 HTTPS 기반이며 `sendMessage`가 text message 전송 method로 제공된다. `sendMessage`는 `chat_id`와 `text`를 핵심 입력으로 받으며 text는 entities parsing 후 1-4096자 범위다. | daily/weekly summary, paper fill/portfolio event처럼 짧은 text alert를 primary로 보내기에 충분하다. |
| Discord Webhooks: https://docs.discord.com/developers/platform/webhooks | incoming webhook은 특정 Discord channel에 연결된 HTTP endpoint이며 POST payload로 message를 게시할 수 있다. Bot user나 persistent connection이 필요하지 않다. | Discord는 one-way ops mirror로 단순하지만 webhook URL 자체가 bearer secret이므로 후속 channel로 둔다. |
| Discord Webhook Resource: https://docs.discord.com/developers/resources/webhook | Execute Webhook은 content/embed/file/poll 중 하나 이상이 필요하며 content는 최대 2000자다. `allowed_mentions`로 예기치 않은 mention을 줄일 수 있다. | 긴 리포트 요약은 splitting/attachment policy가 필요하고 mention 방지가 필수다. |

## Telegram-first 결정 사유

| 기준 | Telegram | Discord | 판단 |
|---|---|---|---|
| alert 단순성 | Bot API `sendMessage` 중심으로 짧은 text alert에 적합 | incoming webhook도 단순하지만 URL 자체가 channel-scoped bearer secret | Telegram 우선 |
| 메시지 길이 | text 1-4096자 | content 2000자 | Telegram 우선 |
| 운영 확장성 | trade event, daily digest, portfolio snapshot을 동일 text contract로 처리 가능 | ops mirror, 파일/embedded report follow-up에 적합 | Telegram primary, Discord follow-up |
| 보안 노출면 | bot token과 chat identifier 관리 필요 | webhook URL 하나로 게시 권한이 열림 | 둘 다 env-only, Discord는 후순위 |
| formatting risk | `parse_mode=null` 기본값으로 plain text 우선 가능 | `allowed_mentions.parse=[]` 필수 | 둘 다 제한 필요 |

## Interface Contract

Phase 7 이후 구현은 다음 shape를 따른다. Phase 6에서는 코드로 구현하지 않는다.

| interface | contract |
|---|---|
| status | channel alias, type, enabled, mode, dry_run, credential configured boolean만 반환 |
| send test | sanitized text payload를 dry-run 또는 mock으로 검증하고 raw token/chat identifier/webhook URL은 반환하지 않음 |
| event outbox | event id, event type, channel alias, status, payload hash, redacted summary만 저장 |
| delivery log | attempt count, sanitized status/error code, delivered timestamp만 저장 |
| dispatch result | notifier 실패는 caller transaction과 trading state를 rollback하지 않음 |

## Security Handling

- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DISCORD_OPS_WEBHOOK_URL`은 env에서만 읽고 코드, 문서, DB, API 응답, 로그에 원문을 기록하지 않는다.
- `.env`와 `.env.local`은 생성하거나 수정하지 않는다. 필요한 경우 `.env.example` placeholder만 허용한다.
- Telegram은 `parse_mode=null` plain text를 기본값으로 사용하고, user mention link나 HTML/Markdown formatting은 후속 명시 승인 전까지 사용하지 않는다.
- Discord는 `allowed_mentions.parse=[]`를 강제해 unexpected mention을 막는다.
- notification payload에는 KIS AppKey/AppSecret/access token/refresh token/account number, Telegram token/chat identifier, Discord webhook URL 원문을 포함하지 않는다.
- notification status API는 secret presence boolean과 channel alias만 제공한다.
- report/portfolio/order summary는 account alias, symbol, status, numeric summary처럼 운영상 필요한 최소값만 전달한다.

## Constraints And Non-goals

- Phase 6에서는 notifier service, route, migration, scheduler, UI를 구현하지 않는다.
- KIS paper submit/cancel/sync network path를 열지 않는다.
- live trading, real account submit/cancel/balance mutation, WebSocket order execution은 notifier 결정과 무관하게 계속 금지한다.
- notifier 실패는 paper order, fill, position, portfolio snapshot commit을 실패시키면 안 된다.
- retry는 bounded outbox 기반으로만 허용하고 synchronous trading path에서 무한 재시도하지 않는다.

## 다음 Phase 진입 판정

Primary channel은 Telegram으로 확정됐다. Phase 7은 이 문서의 interface contract를 기준으로 notification pipeline을 구현할 수 있다. 다만 기본값은 disabled/dry-run이어야 하며, raw secret persistence와 trading state rollback은 금지된다.
