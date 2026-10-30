"""Reporting periods, using the Indian financial year (1 April to 31 March)
and the Asia/Kolkata calendar day."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
PRESETS = ("current_month", "previous_month", "last_3_months", "last_6_months",
           "fy_to_date", "previous_fy", "custom")


def today_ist() -> date:
    return datetime.now(IST).date()


def first_of_month(d: date) -> date:
    return d.replace(day=1)


def add_months(d: date, months: int) -> date:
    """First day of the month `months` away from d's month."""
    idx = d.year * 12 + (d.month - 1) + months
    return date(idx // 12, idx % 12 + 1, 1)


def fy_start(d: date) -> date:
    return date(d.year if d.month >= 4 else d.year - 1, 4, 1)


def fy_label(start: date) -> str:
    return f"FY {start.year}–{str(start.year + 1)[2:]}"


def resolve(preset: str, start: date | None = None, end: date | None = None,
            today: date | None = None) -> tuple[date, date, str]:
    """Return (start, end, label); both dates inclusive."""
    t = today or today_ist()
    if preset == "current_month":
        s = first_of_month(t)
        return s, t, s.strftime("%B %Y")
    if preset == "previous_month":
        s = add_months(t, -1)
        return s, first_of_month(t) - timedelta(days=1), s.strftime("%B %Y")
    if preset == "last_3_months":
        return add_months(t, -2), t, "Last 3 months"
    if preset == "last_6_months":
        return add_months(t, -5), t, "Last 6 months"
    if preset == "fy_to_date":
        s = fy_start(t)
        return s, t, f"{fy_label(s)} to date"
    if preset == "previous_fy":
        s = date(fy_start(t).year - 1, 4, 1)
        return s, date(s.year + 1, 3, 31), fy_label(s)
    if preset == "custom":
        if start is None or end is None:
            raise ValueError("A custom range needs both a start and an end date.")
        if start > end:
            raise ValueError("The start date must be on or before the end date.")
        if (end - start).days > 366 * 10:
            raise ValueError("Choose a range of 10 years or less.")
        return start, end, "Custom range"
    raise ValueError(f"Unknown period '{preset}'.")
