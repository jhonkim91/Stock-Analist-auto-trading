from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

KST = timezone(timedelta(hours=9), "Asia/Seoul")
DEFAULT_VENUE = "KRX"
MAX_NEXT_SESSION_LOOKAHEAD_DAYS = 14


@dataclass(frozen=True)
class SessionWindow:
    venue: str
    name: str
    kind: str
    label: str
    order_acceptance_start: time
    order_acceptance_end: time
    trading_start: time
    trading_end: time
    order_preview_allowed: bool
    paper_preview_allowed: bool
    note: str

    def to_dict(self, trade_date: date) -> dict[str, object]:
        """지정 거래일의 세션 시간을 API payload에 넣을 수 있는 dict로 변환한다."""
        return {
            "venue": self.venue,
            "name": self.name,
            "kind": self.kind,
            "label": self.label,
            "order_acceptance_start": self.order_acceptance_start.isoformat(),
            "order_acceptance_end": self.order_acceptance_end.isoformat(),
            "trading_start": self.trading_start.isoformat(),
            "trading_end": self.trading_end.isoformat(),
            "order_acceptance_start_at": _combine_kst(trade_date, self.order_acceptance_start).isoformat(),
            "order_acceptance_end_at": _combine_kst(trade_date, self.order_acceptance_end).isoformat(),
            "trading_start_at": _combine_kst(trade_date, self.trading_start).isoformat(),
            "trading_end_at": _combine_kst(trade_date, self.trading_end).isoformat(),
            "order_preview_allowed": self.order_preview_allowed,
            "paper_preview_allowed": self.paper_preview_allowed,
            "note": self.note,
        }

    def contains_trading_time(self, local_dt: datetime) -> bool:
        current = local_dt.timetz().replace(tzinfo=None)
        return self.trading_start <= current < self.trading_end

    def contains_order_acceptance_time(self, local_dt: datetime) -> bool:
        current = local_dt.timetz().replace(tzinfo=None)
        return self.order_acceptance_start <= current < self.order_acceptance_end

    def starts_after(self, local_dt: datetime) -> bool:
        return _combine_kst(local_dt.date(), self.order_acceptance_start) > local_dt


@dataclass(frozen=True)
class VenueDefinition:
    venue: str
    label: str
    source_note: str
    windows: tuple[SessionWindow, ...]


VENUE_DEFINITIONS: dict[str, VenueDefinition] = {
    "KRX": VenueDefinition(
        venue="KRX",
        label="Korea Exchange",
        source_note="KRX securities market public trading-hours guide; static local schedule, no network calendar feed.",
        windows=(
            SessionWindow(
                venue="KRX",
                name="pre_hours",
                kind="pre_market",
                label="KRX pre-hours session",
                order_acceptance_start=time(7, 30),
                order_acceptance_end=time(9, 0),
                trading_start=time(7, 30),
                trading_end=time(9, 0),
                order_preview_allowed=True,
                paper_preview_allowed=True,
                note="KRX off-hours pre-hours window; order rules differ from regular continuous auction.",
            ),
            SessionWindow(
                venue="KRX",
                name="regular",
                kind="regular",
                label="KRX regular session",
                order_acceptance_start=time(8, 0),
                order_acceptance_end=time(15, 30),
                trading_start=time(9, 0),
                trading_end=time(15, 30),
                order_preview_allowed=True,
                paper_preview_allowed=True,
                note="KRX regular cash equity session.",
            ),
            SessionWindow(
                venue="KRX",
                name="after_hours",
                kind="after_hours",
                label="KRX after-hours session",
                order_acceptance_start=time(15, 30),
                order_acceptance_end=time(18, 0),
                trading_start=time(15, 40),
                trading_end=time(18, 0),
                order_preview_allowed=True,
                paper_preview_allowed=True,
                note="KRX after-hours trading uses separate off-hours execution rules.",
            ),
        ),
    ),
    "NXT": VenueDefinition(
        venue="NXT",
        label="Nextrade",
        source_note="NXT public market-structure guide; static local schedule, no network calendar feed.",
        windows=(
            SessionWindow(
                venue="NXT",
                name="pre_market",
                kind="pre_market",
                label="NXT pre-market",
                order_acceptance_start=time(8, 0),
                order_acceptance_end=time(8, 50),
                trading_start=time(8, 0),
                trading_end=time(8, 50),
                order_preview_allowed=True,
                paper_preview_allowed=True,
                note="NXT pre-market regular-market segment.",
            ),
            SessionWindow(
                venue="NXT",
                name="main",
                kind="regular",
                label="NXT main market",
                order_acceptance_start=time(9, 0, 30),
                order_acceptance_end=time(15, 20),
                trading_start=time(9, 0, 30),
                trading_end=time(15, 20),
                order_preview_allowed=True,
                paper_preview_allowed=True,
                note="NXT main-market regular-market segment.",
            ),
            SessionWindow(
                venue="NXT",
                name="after_market",
                kind="after_hours",
                label="NXT after-market",
                order_acceptance_start=time(15, 30),
                order_acceptance_end=time(20, 0),
                trading_start=time(15, 40),
                trading_end=time(20, 0),
                order_preview_allowed=True,
                paper_preview_allowed=True,
                note="NXT after-market regular-market segment.",
            ),
        ),
    ),
}


class MarketSessionService:
    def session_windows(self, venue: str | None = None, trade_date: date | None = None) -> list[dict[str, object]]:
        """venue별 주문 접수/거래 세션 window를 반환한다."""
        local_date = trade_date or datetime.now(KST).date()
        definition = self._venue_definition(venue)
        return [window.to_dict(local_date) for window in definition.windows]

    def trading_calendar(
        self,
        *,
        start_date: date,
        end_date: date,
        venue: str | None = None,
        extra_holidays: set[date] | None = None,
    ) -> list[dict[str, object]]:
        """정적 휴장 규칙과 주입된 휴일 목록으로 venue별 거래일 상태를 반환한다."""
        if end_date < start_date:
            raise ValueError("end_date must be on or after start_date")
        days: list[dict[str, object]] = []
        current = start_date
        while current <= end_date:
            days.append(self.trading_day_status(current, venue=venue, extra_holidays=extra_holidays))
            current += timedelta(days=1)
        return days

    def trading_day_status(
        self,
        trade_date: date,
        *,
        venue: str | None = None,
        extra_holidays: set[date] | None = None,
    ) -> dict[str, object]:
        """네트워크 없이 판정 가능한 범위의 거래일 상태를 반환한다."""
        definition = self._venue_definition(venue)
        extra_holidays = extra_holidays or set()
        is_open = True
        reason_code = "OPEN_WEEKDAY"
        holiday_name: str | None = None

        if trade_date.weekday() >= 5:
            is_open = False
            reason_code = "WEEKEND"
            holiday_name = "Weekend"
        elif trade_date in extra_holidays:
            is_open = False
            reason_code = "CONFIGURED_HOLIDAY"
            holiday_name = "Configured holiday"
        elif trade_date.month == 1 and trade_date.day == 1:
            is_open = False
            reason_code = "NEW_YEAR_HOLIDAY"
            holiday_name = "New Year"
        elif trade_date.month == 5 and trade_date.day == 1:
            is_open = False
            reason_code = "LABOR_DAY"
            holiday_name = "Labor Day"
        elif self._is_year_end_market_holiday(trade_date):
            is_open = False
            reason_code = "YEAR_END_MARKET_HOLIDAY"
            holiday_name = "Year-end market holiday"

        return {
            "venue": definition.venue,
            "date": trade_date.isoformat(),
            "is_open": is_open,
            "reason_code": reason_code,
            "holiday_name": holiday_name,
            "calendar_quality": "static_weekend_fixed_holiday_rules",
            "calendar_source": "local_static_no_network",
        }

    def session_at(
        self,
        *,
        as_of: datetime | None = None,
        venue: str | None = None,
        extra_holidays: set[date] | None = None,
    ) -> dict[str, object]:
        """특정 시점의 venue-aware 세션 상태와 다음 세션 window를 반환한다."""
        local_dt = self._normalize_datetime(as_of)
        requested_venue = (venue or DEFAULT_VENUE).strip().upper()
        unknown_venue = bool(venue) and requested_venue not in VENUE_DEFINITIONS
        definition = self._venue_definition(requested_venue)
        day_status = self.trading_day_status(local_dt.date(), venue=definition.venue, extra_holidays=extra_holidays)
        windows = list(definition.windows)
        reason_codes: list[str] = ["UNKNOWN_VENUE_DEFAULTED"] if unknown_venue else []

        if not day_status["is_open"]:
            reason_codes.append(str(day_status["reason_code"]))
            current_session = self._closed_session(reason_codes)
        else:
            current_session = self._current_session(local_dt, windows, reason_codes)

        next_session = self._next_session(local_dt, definition, extra_holidays=extra_holidays)
        allowed_sessions = {
            "pre_market": any(window.kind == "pre_market" and window.order_preview_allowed for window in windows),
            "regular": any(window.kind == "regular" and window.order_preview_allowed for window in windows),
            "after_hours": any(window.kind == "after_hours" and window.order_preview_allowed for window in windows),
        }
        current_allows_preview = (
            bool(day_status["is_open"])
            and current_session["state"] in {"open", "order_acceptance"}
            and bool(current_session["order_preview_allowed"])
            and not unknown_venue
        )

        return {
            "requested_venue": requested_venue,
            "venue": definition.venue,
            "venue_label": definition.label,
            "timezone": "Asia/Seoul",
            "as_of": local_dt.isoformat(),
            "trade_date": local_dt.date().isoformat(),
            "calendar": day_status,
            "is_trading_day": bool(day_status["is_open"]),
            "session": current_session["name"],
            "session_kind": current_session["kind"],
            "session_state": current_session["state"],
            "current_session": current_session,
            "is_trading_session": bool(current_session["is_trading_session"]),
            "is_order_receiving": bool(current_session["is_order_receiving"]),
            "current_session_allows_preview": current_allows_preview,
            "allowed_preview_sessions": allowed_sessions,
            "session_windows": [window.to_dict(local_dt.date()) for window in windows],
            "next_session": next_session,
            "reason_codes": reason_codes,
            "source_note": definition.source_note,
        }

    def preview_metadata(
        self,
        *,
        as_of: datetime | None = None,
        venue: str | None = None,
        extra_holidays: set[date] | None = None,
    ) -> dict[str, object]:
        """order preview/paper simulator가 공유할 세션·운영 메타데이터를 반환한다."""
        metadata = self.session_at(as_of=as_of, venue=venue, extra_holidays=extra_holidays)
        metadata["execution_timing"] = {
            "assumption": "venue_session_aware_preview_only",
            "legacy_single_session_assumption": "replaced_next_open_shortcut",
            "next_order_window": metadata["next_session"],
        }
        metadata["operational_layer"] = {
            "session_checked": True,
            "token_lifecycle_required": False,
            "token_issued": False,
            "rate_limit_checked": False,
            "call_budget_checked": False,
            "network_call_allowed": False,
            "websocket_allowed": False,
            "live_submit_allowed": False,
            "paper_submit_allowed": False,
            "reason": "preview_only_local_session_metadata",
        }
        return metadata

    def _current_session(
        self,
        local_dt: datetime,
        windows: list[SessionWindow],
        reason_codes: list[str],
    ) -> dict[str, object]:
        for window in windows:
            if window.contains_trading_time(local_dt):
                return self._session_payload(window, local_dt.date(), state="open", is_trading_session=True)
            if window.contains_order_acceptance_time(local_dt):
                return self._session_payload(window, local_dt.date(), state="order_acceptance", is_trading_session=False)
        reason_codes.append("OUTSIDE_SESSION_WINDOW")
        return self._closed_session(reason_codes)

    def _next_session(
        self,
        local_dt: datetime,
        definition: VenueDefinition,
        *,
        extra_holidays: set[date] | None,
    ) -> dict[str, object] | None:
        cursor_date = local_dt.date()
        for offset in range(MAX_NEXT_SESSION_LOOKAHEAD_DAYS + 1):
            candidate_date = cursor_date + timedelta(days=offset)
            day_status = self.trading_day_status(
                candidate_date,
                venue=definition.venue,
                extra_holidays=extra_holidays,
            )
            if not day_status["is_open"]:
                continue
            for window in definition.windows:
                order_start_at = _combine_kst(candidate_date, window.order_acceptance_start)
                trading_start_at = _combine_kst(candidate_date, window.trading_start)
                if order_start_at > local_dt or (
                    trading_start_at > local_dt and not window.contains_trading_time(local_dt)
                ):
                    payload = window.to_dict(candidate_date)
                    payload["state"] = "scheduled"
                    return payload
            if offset == 0:
                continue
        return None

    @staticmethod
    def _session_payload(
        window: SessionWindow,
        trade_date: date,
        *,
        state: str,
        is_trading_session: bool,
    ) -> dict[str, object]:
        payload = window.to_dict(trade_date)
        payload.update(
            {
                "state": state,
                "is_trading_session": is_trading_session,
                "is_order_receiving": state in {"open", "order_acceptance"},
            }
        )
        return payload

    @staticmethod
    def _closed_session(reason_codes: list[str]) -> dict[str, object]:
        return {
            "venue": None,
            "name": "closed",
            "kind": "closed",
            "label": "No active session",
            "state": "closed",
            "is_trading_session": False,
            "is_order_receiving": False,
            "order_preview_allowed": False,
            "paper_preview_allowed": False,
            "reason_codes": reason_codes,
        }

    @staticmethod
    def _normalize_datetime(as_of: datetime | None) -> datetime:
        current = as_of or datetime.now(KST)
        if current.tzinfo is None:
            return current.replace(tzinfo=KST)
        return current.astimezone(KST)

    @staticmethod
    def _venue_definition(venue: str | None) -> VenueDefinition:
        normalized = (venue or DEFAULT_VENUE).strip().upper()
        if normalized not in VENUE_DEFINITIONS:
            return VENUE_DEFINITIONS[DEFAULT_VENUE]
        return VENUE_DEFINITIONS[normalized]

    @staticmethod
    def _is_year_end_market_holiday(trade_date: date) -> bool:
        last_day = date(trade_date.year, 12, 31)
        if last_day.weekday() < 5:
            return trade_date == last_day
        previous_business_day = last_day
        while previous_business_day.weekday() >= 5:
            previous_business_day -= timedelta(days=1)
        return trade_date == previous_business_day


def _combine_kst(day: date, value: time) -> datetime:
    return datetime.combine(day, value, tzinfo=KST)
