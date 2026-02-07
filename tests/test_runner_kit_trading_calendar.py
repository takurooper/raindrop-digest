from __future__ import annotations

from datetime import date

import pytest

from raindrop_digest.runner_kit.trading_calendar import (
    CsvHolidayCalendar,
    TradingCalendarError,
    is_trading_day,
)


def test_csv_holiday_calendar_parses_file(tmp_path) -> None:
    p = tmp_path / "holidays.txt"
    p.write_text("# comment\n2026-01-01\n\n2026-01-02\n", encoding="utf-8")
    cal = CsvHolidayCalendar.from_file(p)
    assert cal.is_holiday(date(2026, 1, 1))
    assert cal.is_holiday(date(2026, 1, 2))


def test_csv_holiday_calendar_rejects_invalid_lines(tmp_path) -> None:
    p = tmp_path / "holidays.txt"
    p.write_text("not-a-date\n", encoding="utf-8")
    with pytest.raises(TradingCalendarError):
        CsvHolidayCalendar.from_file(p)


def test_is_trading_day_weekday_and_not_holiday() -> None:
    cal = CsvHolidayCalendar(holidays=frozenset({date(2026, 1, 1)}))
    assert is_trading_day(d=date(2026, 1, 2), holiday_calendar=cal) is True
    assert is_trading_day(d=date(2026, 1, 1), holiday_calendar=cal) is False
    assert is_trading_day(d=date(2026, 1, 3), holiday_calendar=cal) is False  # Saturday
