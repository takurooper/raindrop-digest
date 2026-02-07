from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path


class TradingCalendarError(ValueError):
    pass


def is_weekday(d: date) -> bool:
    return d.weekday() < 5


@dataclass(frozen=True)
class CsvHolidayCalendar:
    """Holiday calendar loaded from a CSV-like text file.

    Accepts one date per line in YYYY-MM-DD. Empty lines and lines starting with
    # are ignored.
    """

    holidays: frozenset[date]

    @staticmethod
    def from_file(path: str | Path) -> "CsvHolidayCalendar":
        p = Path(path)
        if not p.exists():
            raise TradingCalendarError(f"Holiday file not found: {p}")
        raw = p.read_text(encoding="utf-8").splitlines()
        parsed: set[date] = set()
        for line in raw:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            try:
                y, m, d = s.split("-", 2)
                parsed.add(date(int(y), int(m), int(d)))
            except ValueError as exc:
                raise TradingCalendarError(f"Invalid date line in {p}: {s!r}") from exc
        return CsvHolidayCalendar(holidays=frozenset(parsed))

    def is_holiday(self, d: date) -> bool:
        return d in self.holidays


def is_trading_day(
    *, d: date, holiday_calendar: CsvHolidayCalendar | None = None
) -> bool:
    if not is_weekday(d):
        return False
    if holiday_calendar and holiday_calendar.is_holiday(d):
        return False
    return True
