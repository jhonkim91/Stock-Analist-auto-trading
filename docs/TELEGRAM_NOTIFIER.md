# Telegram Notifier

## 핵심 요약

Telegram notifier는 `backend/config/notifications.yaml`과 로컬 환경 변수만 사용한다. 기본값은 `enabled: false`, `mode: disabled`, `dry_run: true`이므로 설정을 추가해도 주문, live submit, WebSocket, KIS token 발급을 활성화하지 않는다.

## 설정 원칙

| 항목 | 기준 |
|---|---|
| primary channel | `telegram_main` |
| secret 위치 | 환경 변수 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| 기본 delivery | disabled / dry-run |
| 메시지 형식 | plain text, `parse_mode: null` |
| 실패 처리 | trading/report 상태 변경을 막지 않고 delivery 상태만 기록 |

`.env.example`에는 placeholder만 둔다. 실제 bot token과 chat id는 로컬 환경 변수나 배포 secret에만 저장하고, 문서/로그/API 응답/DB에는 원문을 남기지 않는다.

## notifications.yaml 예시

```yaml
notifications:
  enabled: false
  default_dry_run: true
  channels:
    telegram_main:
      type: telegram
      enabled: false
      mode: disabled
      bot_token_env: TELEGRAM_BOT_TOKEN
      chat_id_env: TELEGRAM_CHAT_ID
      dry_run: true
      parse_mode: null
  templates:
    paper_order_submitted: |
      [Paper Order Submitted]
      symbol: {symbol}
      side: {side}
      qty: {qty}
      status: {status}
```

`mode: mock`은 네트워크 없이 delivery 성공 흐름만 검증한다. `mode: live`는 `enabled: true`, channel enabled, dry-run 해제, credential configured 조건이 모두 충족될 때만 Telegram `sendMessage`를 호출한다.

## 안전 계약

- KIS 주문 API, live submit, WebSocket 실행과 연결하지 않는다.
- token/chat id/account/header 원문은 template payload에서 제거하거나 redaction 처리한다.
- 템플릿 placeholder가 없으면 `not_available`로 채운다.
- Telegram message는 4096자 한도 안에서 plain text로 만든다.

## 로컬 검증

```powershell
python -m pytest backend/tests/test_notifications.py backend/tests/test_notification_service.py backend/tests/test_notification_templates.py backend/tests/test_notification_outbox.py
```

전체 backend 검증:

```powershell
python -m pytest backend/tests
```
