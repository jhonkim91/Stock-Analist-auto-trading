from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.paths import CONFIG_DIR
from backend.app.models.tables import PaperAuditEvent, PaperPosition
from backend.app.services.account_service import AccountService
from backend.app.services.market_realtime_service import MarketRealtimeService
from backend.app.services.paper_bot_service import PaperBotService
from backend.app.services.paper_trading_service import PaperTradingService
from backend.app.services.report_service import ReportService
from backend.app.services.token_manager import TokenLifecycleService

SUPPORTED_TELEGRAM_COMMANDS = {
    "/start",
    "/help",
    "/status",
    "/search",
    "/report",
    "/portfolio",
    "/rank",
    "/stop",
    "/bot",
    "/buy",
    "/sell",
    "/orders",
    "/cancel",
}


@dataclass(frozen=True)
class TelegramCommand:
    command: str
    args: list[str]
    raw_text: str


class TelegramBotService:
    """Telegram command를 기존 분석/paper 서비스에 연결하는 thin dispatcher다."""

    def __init__(self, db: Session, *, config_dir: Path = CONFIG_DIR) -> None:
        self.db = db
        self.config_dir = config_dir

    def status(self) -> dict[str, object]:
        """Telegram bot 설정 상태를 secret 없이 반환한다."""
        return {
            "enabled": _env_true("TELEGRAM_BOT_ENABLED"),
            "polling_enabled": _env_true("TELEGRAM_POLLING_ENABLED"),
            "webhook_enabled": _env_true("TELEGRAM_WEBHOOK_ENABLED"),
            "token_configured": _configured(os.getenv("TELEGRAM_BOT_TOKEN", "")),
            "chat_id_configured": _configured(os.getenv("TELEGRAM_CHAT_ID", "")),
            "paper_trade_confirm_enabled": _env_true("TELEGRAM_PAPER_TRADE_CONFIRM"),
            "supported_commands": sorted(SUPPORTED_TELEGRAM_COMMANDS),
            "scheduler": {
                "enabled": _env_true("TELEGRAM_REPORT_SCHEDULER_ENABLED"),
                "pre_market_enabled": _env_true("TELEGRAM_PRE_MARKET_REPORT_ENABLED"),
                "post_market_enabled": _env_true("TELEGRAM_POST_MARKET_REPORT_ENABLED"),
            },
            "network_call_performed": False,
            "secrets_redacted": True,
        }

    def parse_command(self, text: str) -> TelegramCommand:
        """Telegram message text를 command와 args로 분리한다."""
        raw_text = str(text or "").strip()
        if not raw_text:
            return TelegramCommand(command="", args=[], raw_text="")
        parts = raw_text.split()
        command = parts[0].split("@", 1)[0].lower()
        return TelegramCommand(command=command, args=parts[1:], raw_text=raw_text)

    def handle_text(self, text: str, *, chat_id: str | None = None) -> dict[str, Any]:
        """단일 Telegram command를 실행하고 전송 가능한 요약 메시지를 만든다."""
        parsed = self.parse_command(text)
        if parsed.command not in SUPPORTED_TELEGRAM_COMMANDS:
            result = self._response(
                parsed,
                status="unsupported_command",
                message="지원하지 않는 명령입니다. /help 를 입력하세요.",
                reason_codes=["TELEGRAM_COMMAND_UNSUPPORTED"],
            )
            self._audit(parsed, result, chat_id=chat_id)
            return result

        handlers = {
            "/start": self._handle_help,
            "/help": self._handle_help,
            "/status": self._handle_status,
            "/search": self._handle_search,
            "/report": self._handle_report,
            "/portfolio": self._handle_portfolio,
            "/rank": self._handle_rank,
            "/stop": self._handle_stop,
            "/bot": self._handle_bot,
            "/buy": lambda command: self._handle_order(command, side="buy", chat_id=chat_id),
            "/sell": lambda command: self._handle_order(command, side="sell", chat_id=chat_id),
            "/orders": self._handle_orders,
            "/cancel": lambda command: self._handle_cancel(command, chat_id=chat_id),
        }
        result = handlers[parsed.command](parsed)
        self._audit(parsed, result, chat_id=chat_id)
        return result

    def handle_update(self, update: dict[str, Any]) -> dict[str, Any]:
        """Telegram webhook update를 command dispatcher 입력으로 변환한다."""
        message = _message_from_update(update)
        text = str(message.get("text") or "").strip()
        chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
        chat_id = str(chat.get("id") or "").strip() or None
        if not text:
            result = self._response(
                TelegramCommand(command="", args=[], raw_text=""),
                status="ignored",
                message="처리할 Telegram text command가 없습니다.",
                reason_codes=["TELEGRAM_UPDATE_TEXT_NOT_FOUND"],
            )
            self._audit(TelegramCommand(command="", args=[], raw_text=""), result, chat_id=chat_id)
            return {**result, "webhook_update_received": True, "update_id": update.get("update_id")}
        result = self.handle_text(text, chat_id=chat_id)
        return {**result, "webhook_update_received": True, "update_id": update.get("update_id")}

    def _handle_help(self, command: TelegramCommand) -> dict[str, Any]:
        message = (
            "명령: /status, /search 종목코드, /report [daily|weekly], /portfolio, /rank, "
            "/bot status|enable|disable|auto|run|stop, "
            "/buy 종목 qty|amount=금액 [price] confirm, /sell 종목 qty|all [price] confirm, "
            "/orders, /cancel 주문ID confirm, /stop"
        )
        return self._response(command, status="ok", message=message)

    def _handle_status(self, command: TelegramCommand) -> dict[str, Any]:
        paper = self._paper_trading_service().status()
        token = TokenLifecycleService().status()
        message = (
            f"mode={paper.get('mode')} can_create={paper.get('can_create')} "
            f"kill_switch={paper.get('kill_switch', {}).get('blocking')} "
            f"token_issued={token.get('token_issued')}"
        )
        return self._response(command, status="ok", message=message, payload={"paper": paper, "token": token})

    def _handle_search(self, command: TelegramCommand) -> dict[str, Any]:
        if not command.args:
            return self._response(
                command,
                status="bad_request",
                message="사용법: /search 종목코드",
                reason_codes=["TELEGRAM_SEARCH_SYMBOL_REQUIRED"],
            )
        symbol = command.args[0].upper()
        try:
            detail = MarketRealtimeService(self.db).symbol_detail(symbol)
        except ValueError:
            return self._response(
                command,
                status="not_found",
                message=f"{symbol} 종목을 찾을 수 없습니다.",
                reason_codes=["TELEGRAM_SEARCH_NOT_FOUND"],
            )
        message = self._search_summary(detail)
        return self._response(command, status="ok", message=message, payload=detail)

    def _handle_report(self, command: TelegramCommand) -> dict[str, Any]:
        report_mode = self._parse_report_mode(command)
        if report_mode is None:
            return self._response(
                command,
                status="bad_request",
                message="사용법: /report, /report daily, /report weekly",
                reason_codes=["TELEGRAM_REPORT_TYPE_UNSUPPORTED"],
            )
        report_service = ReportService(self.db)
        try:
            if report_mode == "daily":
                generated = report_service.generate_daily_report()
                report = report_service.get_report(str(generated["report_id"]), include_markdown=True)
            elif report_mode == "weekly":
                generated = report_service.generate_weekly_report()
                report = report_service.get_report(str(generated["report_id"]), include_markdown=True)
            else:
                report = report_service.latest_markdown()
                generated = None
        except ValueError:
            return self._response(
                command,
                status="not_found",
                message="생성된 리포트가 없습니다.",
                reason_codes=["TELEGRAM_REPORT_NOT_FOUND"],
            )
        summary = self._report_summary(report)
        payload = {
            "report_mode": report_mode,
            "generated": generated is not None,
            "generated_report": generated or {},
            "report": report,
            "report_id": report.get("report_id"),
            "report_type": report.get("report_type"),
            "network_call_performed": False,
        }
        return self._response(command, status="ok", message=summary or str(report["report_id"]), payload=payload)

    def _handle_portfolio(self, command: TelegramCommand) -> dict[str, Any]:
        report = AccountService(self.db).report()
        account = report.get("account") or {}
        message = (
            f"portfolio source={report.get('source')} "
            f"equity={account.get('total_equity')} holdings={len(report.get('holdings') or [])}"
        )
        return self._response(command, status="ok", message=message, payload=report)

    def _handle_rank(self, command: TelegramCommand) -> dict[str, Any]:
        metric = command.args[0] if command.args else "total_score"
        try:
            ranking = MarketRealtimeService(self.db).rankings(metric=metric, limit=10)
        except ValueError as exc:
            return self._response(command, status="bad_request", message=str(exc), reason_codes=["TELEGRAM_RANK_BAD_METRIC"])
        lines = [f"{item['rank']}. {item['symbol']} {item.get('name')} {item.get('metric_value')}" for item in ranking["items"]]
        return self._response(command, status="ok", message="\n".join(lines) or "ranking 없음", payload=ranking)

    def _handle_stop(self, command: TelegramCommand) -> dict[str, Any]:
        stop = PaperBotService(self.db).stop()
        return self._response(command, status="stopped", message="paper bot stop 요청을 수신했습니다.", payload=stop)

    def _handle_bot(self, command: TelegramCommand) -> dict[str, Any]:
        action = command.args[0].lower() if command.args else "status"
        confirm = any(arg.lower() in {"confirm", "confirmed", "확인"} for arg in command.args[1:])
        service = PaperBotService(self.db)
        if action in {"status", "상태"}:
            status = service.status()
            message = (
                f"bot enabled={status.get('enabled')} auto_submit={status.get('auto_submit')} "
                f"kill_switch={status.get('kill_switch_enabled')} loop_allowed={status.get('loop_allowed')}"
            )
            return self._response(command, status="ok", message=message, payload=status)
        if action in {"enable", "on", "start", "켜기"}:
            if not confirm:
                return self._response(
                    command,
                    status="blocked",
                    message="사용법: /bot enable confirm",
                    reason_codes=["TELEGRAM_BOT_CONTROL_CONFIRM_REQUIRED"],
                )
            os.environ["PAPER_BOT_ENABLED"] = "true"
            status = service.status()
            return self._response(command, status="updated", message="paper bot enabled=true", payload=status)
        if action in {"disable", "off", "끄기"}:
            if not confirm:
                return self._response(
                    command,
                    status="blocked",
                    message="사용법: /bot disable confirm",
                    reason_codes=["TELEGRAM_BOT_CONTROL_CONFIRM_REQUIRED"],
                )
            os.environ["PAPER_BOT_ENABLED"] = "false"
            os.environ["PAPER_BOT_AUTO_SUBMIT"] = "false"
            stop = service.stop()
            return self._response(command, status="updated", message="paper bot disabled; auto_submit=false", payload=stop)
        if action in {"auto", "autosubmit", "auto-submit"}:
            value = command.args[1].lower() if len(command.args) >= 2 else ""
            if value not in {"on", "off", "true", "false"} or not confirm:
                return self._response(
                    command,
                    status="blocked",
                    message="사용법: /bot auto on confirm 또는 /bot auto off confirm",
                    reason_codes=["TELEGRAM_BOT_CONTROL_CONFIRM_REQUIRED"],
                )
            enabled = value in {"on", "true"}
            os.environ["PAPER_BOT_AUTO_SUBMIT"] = "true" if enabled else "false"
            status = service.status()
            return self._response(command, status="updated", message=f"paper bot auto_submit={enabled}", payload=status)
        if action in {"run", "once", "실행"}:
            if not confirm:
                return self._response(
                    command,
                    status="blocked",
                    message="사용법: /bot run confirm [auto_submit=true]",
                    reason_codes=["TELEGRAM_BOT_RUN_CONFIRM_REQUIRED"],
                )
            values = _key_values(command.args[1:])
            auto_submit = _bool_or_none(values.get("auto_submit") or values.get("autosubmit"))
            result = service.run_once(auto_submit=auto_submit)
            message = f"bot run {result.get('status')} decisions={result.get('decision_count')} submitted={result.get('submitted_count')}"
            return self._response(command, status=str(result.get("status") or "ok"), message=message, payload=result)
        if action in {"stop", "중지"}:
            return self._handle_stop(command)
        return self._response(
            command,
            status="bad_request",
            message="사용법: /bot status|enable|disable|auto|run|stop",
            reason_codes=["TELEGRAM_BOT_ACTION_UNSUPPORTED"],
        )

    def _handle_orders(self, command: TelegramCommand) -> dict[str, Any]:
        status = command.args[0] if command.args else None
        if self._orders_open_requested(status):
            orders = self._paper_trading_service().list_open_orders()
        else:
            orders = self._paper_trading_service().list_orders(status=status)
        lines = [
            f"{row['paper_order_id']} {row['symbol']} {row['side']} {row['qty']} {row['status']}"
            for row in orders.get("orders", [])[:10]
        ]
        return self._response(command, status="ok", message="\n".join(lines) or "주문 없음", payload=orders)

    def _handle_cancel(self, command: TelegramCommand, *, chat_id: str | None) -> dict[str, Any]:
        paper_order_id = self._parse_cancel_order_id(command)
        if paper_order_id is None:
            return self._response(
                command,
                status="bad_request",
                message="사용법: /cancel paper_order_id confirm",
                reason_codes=["TELEGRAM_CANCEL_ORDER_ID_REQUIRED"],
            )
        confirm = any(arg.lower() in {"confirm", "confirmed", "확인"} for arg in command.args)
        if not confirm:
            return self._response(
                command,
                status="blocked",
                message="사용법: /cancel paper_order_id confirm",
                payload={"paper_order_id": paper_order_id, "network_call_performed": False},
                reason_codes=["TELEGRAM_CANCEL_CONFIRM_REQUIRED"],
            )
        result = self._paper_trading_service().cancel_order(
            paper_order_id=paper_order_id,
            confirm=True,
            idempotency_key=self._idempotency_key(command.raw_text, chat_id=chat_id),
            command_source="telegram",
        )
        status = "cancelled" if result.get("order_cancelled") else str(result.get("status") or "blocked")
        message = f"cancel {status} {paper_order_id} reason={result.get('reason')}"
        return self._response(
            command,
            status=status,
            message=message,
            payload=result,
            reason_codes=list(result.get("reason_codes") or []),
        )

    def _handle_order(self, command: TelegramCommand, *, side: str, chat_id: str | None) -> dict[str, Any]:
        order = self._parse_order_args(command, side=side, chat_id=chat_id)
        if not order["ok"]:
            return self._response(
                command,
                status="bad_request",
                message=str(order["message"]),
                reason_codes=list(order["reason_codes"]),
            )
        service = self._paper_trading_service()
        if not bool(order["confirm"]):
            preview = service.preview_order(
                symbol=str(order["symbol"]),
                side=side,
                qty=int(order["qty"]),
                limit_price=order["limit_price"],
                strategy_tag="telegram",
            )
            message = f"{side} preview {order['symbol']} qty={order['qty']} reason={preview.get('reason')}"
            return self._response(command, status="preview", message=message, payload=preview)
        result = service.submit_order(
            symbol=str(order["symbol"]),
            side=side,
            qty=int(order["qty"]),
            limit_price=order["limit_price"],
            strategy_tag="telegram",
            confirm=True,
            idempotency_key=str(order["idempotency_key"]),
            command_source="telegram",
        )
        status = "created" if result.get("paper_order_created") else str(result.get("status") or "blocked")
        message = f"{side} {status} {order['symbol']} qty={order['qty']} reason={result.get('reason')}"
        return self._response(command, status=status, message=message, payload=result, reason_codes=result.get("reason_codes") or [])

    def _parse_order_args(self, command: TelegramCommand, *, side: str, chat_id: str | None) -> dict[str, Any]:
        if not command.args:
            return {"ok": False, "message": f"사용법: {command.command} 종목 qty [price] [confirm]", "reason_codes": ["TELEGRAM_ORDER_SYMBOL_REQUIRED"]}
        symbol = command.args[0].upper()
        values = _key_values(command.args[1:])
        confirm = _env_true("TELEGRAM_PAPER_TRADE_CONFIRM") or any(arg.lower() in {"confirm", "confirmed", "확인"} for arg in command.args[1:])
        limit_price = _float_or_none(values.get("price") or values.get("limit_price"))
        positional = [arg for arg in command.args[1:] if "=" not in arg and arg.lower() not in {"confirm", "confirmed", "확인"}]
        qty = _int_or_none(values.get("qty"))
        amount = _float_or_none(values.get("amount") or values.get("notional"))
        sell_all_requested = side == "sell" and self._sell_all_requested(values=values, positional=positional)
        if sell_all_requested:
            qty = self._open_position_qty(symbol)
            if qty is None:
                return {
                    "ok": False,
                    "message": "전량 매도할 paper position이 없습니다.",
                    "reason_codes": ["TELEGRAM_SELL_ALL_POSITION_NOT_FOUND"],
                }
        if qty is None and positional:
            qty = _int_or_none(positional[0])
        if limit_price is None and len(positional) >= 2:
            limit_price = _float_or_none(positional[1])
        if qty is None and amount is not None:
            price = limit_price or self._latest_price(symbol)
            qty = int(amount // price) if price and price > 0 else None
        if qty is None or qty <= 0:
            return {"ok": False, "message": "수량 또는 amount를 확인하세요.", "reason_codes": ["TELEGRAM_ORDER_QTY_REQUIRED"]}
        return {
            "ok": True,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "limit_price": limit_price,
            "confirm": confirm,
            "idempotency_key": self._idempotency_key(command.raw_text, chat_id=chat_id),
        }

    @staticmethod
    def _sell_all_requested(*, values: dict[str, str], positional: list[str]) -> bool:
        all_tokens = {"all", "full", "전량", "전체"}
        qty_value = str(values.get("qty") or "").strip().lower()
        sell_all_value = str(values.get("sell_all") or values.get("all") or "").strip().lower()
        return (
            qty_value in all_tokens
            or sell_all_value in {"1", "true", "yes", "on", "y", "전량", "전체"}
            or any(str(item).strip().lower() in all_tokens for item in positional)
        )

    def _open_position_qty(self, symbol: str) -> int | None:
        qty = self.db.scalar(
            select(func.coalesce(func.sum(PaperPosition.qty), 0)).where(
                PaperPosition.symbol == symbol.strip().upper(),
                PaperPosition.qty > 0,
            )
        )
        return int(qty or 0) or None

    @staticmethod
    def _parse_cancel_order_id(command: TelegramCommand) -> str | None:
        values = _key_values(command.args)
        explicit = str(values.get("paper_order_id") or values.get("order_id") or "").strip()
        if explicit:
            return explicit
        for arg in command.args:
            normalized = arg.strip()
            if not normalized or "=" in normalized or normalized.lower() in {"confirm", "confirmed", "확인"}:
                continue
            return normalized
        return None

    @staticmethod
    def _orders_open_requested(status: str | None) -> bool:
        normalized = str(status or "").strip().lower()
        return normalized in {"open", "pending", "submitted", "unfilled", "working", "미체결", "대기"}

    def _paper_trading_service(self) -> PaperTradingService:
        return PaperTradingService(self.db, config_dir=self.config_dir)

    def _latest_price(self, symbol: str) -> float | None:
        try:
            detail = MarketRealtimeService(self.db).symbol_detail(symbol)
        except ValueError:
            return None
        quote = detail.get("quote") or {}
        value = quote.get("current_price") or quote.get("close")
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_report_mode(command: TelegramCommand) -> str | None:
        values = _key_values(command.args)
        requested = str(values.get("type") or values.get("report_type") or "").strip().lower()
        if not requested:
            positional = [arg for arg in command.args if "=" not in arg]
            requested = str(positional[0] if positional else "latest").strip().lower()
        aliases = {
            "": "latest",
            "latest": "latest",
            "recent": "latest",
            "last": "latest",
            "최근": "latest",
            "daily": "daily",
            "day": "daily",
            "일간": "daily",
            "일일": "daily",
            "weekly": "weekly",
            "week": "weekly",
            "주간": "weekly",
            "주간리뷰": "weekly",
        }
        return aliases.get(requested)

    @staticmethod
    def _report_summary(report: dict[str, Any]) -> str:
        markdown = str(report.get("markdown") or "")
        summary = "\n".join(line.strip() for line in markdown.splitlines() if line.strip())[:1200]
        report_type = str(report.get("report_type") or "report")
        report_id = str(report.get("report_id") or "")
        prefix = f"[{report_type}] {report_id}".strip()
        return f"{prefix}\n{summary}".strip() if summary else prefix

    @staticmethod
    def _search_summary(detail: dict[str, Any]) -> str:
        summary = detail.get("summary") if isinstance(detail.get("summary"), dict) else {}
        symbol = detail.get("symbol") if isinstance(detail.get("symbol"), dict) else {}
        quote = detail.get("quote") if isinstance(detail.get("quote"), dict) else {}
        indicator = detail.get("indicator") if isinstance(detail.get("indicator"), dict) else {}
        screens = detail.get("screener") if isinstance(detail.get("screener"), list) else []
        passed_names = list(summary.get("passed_strategies") or [])
        if not passed_names:
            passed_names = [
                str(row.get("strategy_name") or row.get("strategy_tag") or "")
                for row in screens
                if isinstance(row, dict) and row.get("passed")
            ]
        strategy_text = ", ".join(name for name in passed_names[:5] if name) or "없음"
        if len(passed_names) > 5:
            strategy_text = f"{strategy_text} 외 {len(passed_names) - 5}개"
        source = str(summary.get("quote_source") or quote.get("source") or detail.get("source") or "unknown")
        fallback_reasons = list(summary.get("fallback_reason_codes") or quote.get("fallback_reason_codes") or [])
        fallback_text = f" fallback={','.join(str(item) for item in fallback_reasons[:3])}" if fallback_reasons else ""
        major_indicators = summary.get("major_indicators") if isinstance(summary.get("major_indicators"), dict) else indicator
        return "\n".join(
            [
                f"{symbol.get('symbol') or summary.get('symbol')} {symbol.get('name') or summary.get('name')}",
                "현재가 "
                f"{_format_number(summary.get('current_price') or quote.get('current_price') or quote.get('close'))} "
                f"등락률 {_format_percent(summary.get('change_pct') or quote.get('change_pct'))}",
                "시가 "
                f"{_format_number(summary.get('open') or quote.get('open'))} "
                f"고가 {_format_number(summary.get('high') or quote.get('high'))} "
                f"저가 {_format_number(summary.get('low') or quote.get('low'))}",
                "거래량 "
                f"{_format_number(summary.get('volume') or quote.get('volume'), decimals=0)} "
                f"거래대금 {_format_number(summary.get('turnover_value') or quote.get('turnover_value'), decimals=0)}",
                "주요지표 "
                f"SMA20={_format_number(major_indicators.get('sma20'))} "
                f"SMA50={_format_number(major_indicators.get('sma50'))} "
                f"SMA200={_format_number(major_indicators.get('sma200'))} "
                f"RS={_format_number(major_indicators.get('relative_strength_score'))} "
                f"ATR20%={_format_percent(major_indicators.get('atr20_pct'))}",
                "통과전략 "
                f"{summary.get('strategy_passed_count', len(passed_names))}/{summary.get('strategy_total_count', len(screens))}: "
                f"{strategy_text}",
                f"데이터 {source}{fallback_text}",
            ]
        )

    @staticmethod
    def _idempotency_key(raw_text: str, *, chat_id: str | None) -> str:
        basis = f"{chat_id or 'telegram'}:{raw_text.strip().lower()}"
        return f"telegram-{hashlib.sha256(basis.encode('utf-8')).hexdigest()[:24]}"

    @staticmethod
    def _response(
        command: TelegramCommand,
        *,
        status: str,
        message: str,
        payload: dict[str, Any] | None = None,
        reason_codes: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": status not in {"bad_request", "unsupported_command", "not_found"},
            "status": status,
            "command": command.command,
            "args": command.args,
            "message": message[:3900],
            "payload": payload or {},
            "reason_codes": reason_codes or [],
            "network_call_performed": bool((payload or {}).get("network_call_performed", False)),
            "live_order_created": False,
            "secrets_redacted": True,
        }

    def _audit(self, command: TelegramCommand, result: dict[str, Any], *, chat_id: str | None) -> None:
        payload = {
            "command": command.command,
            "args_count": len(command.args),
            "chat_id_configured": bool(chat_id) or _configured(os.getenv("TELEGRAM_CHAT_ID", "")),
            "status": result.get("status"),
            "message_length": len(str(result.get("message") or "")),
        }
        self.db.add(
            PaperAuditEvent(
                event_type="telegram_command",
                paper_order_id=str((result.get("payload") or {}).get("paper_order_id") or "") or None,
                decision="allow" if result.get("ok") else "deny",
                reason_codes_json=json.dumps(result.get("reason_codes") or [], ensure_ascii=False),
                payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            )
        )
        self.db.commit()


def _key_values(args: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for arg in args:
        if "=" not in arg:
            continue
        key, value = arg.split("=", 1)
        result[key.strip().lower()] = value.strip()
    return result


def _int_or_none(value: object) -> int | None:
    if value in {None, ""}:
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return None


def _float_or_none(value: object) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: object) -> bool | None:
    if value in {None, ""}:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _format_number(value: object, *, decimals: int = 2) -> str:
    if value in {None, ""}:
        return "N/A"
    try:
        numeric = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return str(value)
    if decimals <= 0:
        return f"{numeric:,.0f}"
    return f"{numeric:,.{decimals}f}".rstrip("0").rstrip(".")


def _format_percent(value: object) -> str:
    if value in {None, ""}:
        return "N/A"
    try:
        numeric = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return str(value)
    text = f"{numeric * 100:.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _configured(value: str) -> bool:
    stripped = value.strip()
    return bool(stripped) and "placeholder" not in stripped.lower()


def _message_from_update(update: dict[str, Any]) -> dict[str, Any]:
    for key in ("message", "edited_message"):
        value = update.get(key)
        if isinstance(value, dict):
            return value
    callback = update.get("callback_query")
    if isinstance(callback, dict) and isinstance(callback.get("message"), dict):
        return callback["message"]
    return {}
