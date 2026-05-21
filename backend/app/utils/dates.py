from __future__ import annotations

from datetime import date, datetime


def coerce_date(value: date | datetime | str) -> date:
    """문자열/datetime/date 값을 date로 정규화한다."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()
