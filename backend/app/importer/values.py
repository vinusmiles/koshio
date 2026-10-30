"""Reading dates and amounts the many ways Indian statements write them."""
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

# Day-first formats are listed before month-first ones: Indian statements are day-first.
DATE_FORMATS = {
    "DD/MM/YYYY": ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"],
    "DD/MM/YY": ["%d/%m/%y", "%d-%m-%y", "%d.%m.%y"],
    "MM/DD/YYYY": ["%m/%d/%Y", "%m-%d-%Y"],
    "MM/DD/YY": ["%m/%d/%y", "%m-%d-%y"],
    "YYYY-MM-DD": ["%Y-%m-%d", "%Y/%m/%d"],
    "DD MMM YYYY": ["%d %b %Y", "%d-%b-%Y", "%d/%b/%Y", "%d %B %Y", "%d-%B-%Y", "%d %b, %Y", "%d-%b-%Y"],
    "DD MMM YY": ["%d %b %y", "%d-%b-%y", "%d/%b/%y"],
    "MMM DD, YYYY": ["%b %d, %Y", "%B %d, %Y", "%b %d %Y"],
}
DAY_MONTH_PAIRS = [("DD/MM/YYYY", "MM/DD/YYYY"), ("DD/MM/YY", "MM/DD/YY")]
_TIME = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp][Mm])?")


def split_time(value: str) -> tuple[str, str | None]:
    """'05/10/2026 14:32:10' -> ('05/10/2026', '14:32:10')."""
    v = value.strip().replace("T", " ") if re.match(r"^\d{4}-\d{2}-\d{2}T", value.strip()) else value.strip()
    m = _TIME.search(v)
    if not m:
        return v, None
    h, mi, se, ampm = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0), m.group(4)
    if ampm:
        h = h % 12 + (12 if ampm.lower() == "pm" else 0)
    rest = (v[:m.start()] + v[m.end():]).strip(" ,")
    if h > 23 or mi > 59:
        return v, None
    return rest, f"{h:02d}:{mi:02d}:{se:02d}"


def parse_date(value: str, fmt_name: str) -> date | None:
    text, _ = split_time(value)
    text = " ".join(text.replace("'", " ").split())
    text = re.sub(r"\bSept\b", "Sep", text, flags=re.I)
    for f in DATE_FORMATS.get(fmt_name, []):
        try:
            d = datetime.strptime(text, f).date()
        except ValueError:
            continue
        if 1990 <= d.year <= 2100:
            return d
    return None


def looks_like_date(value: str) -> bool:
    v = value.strip()
    return bool(v) and bool(re.search(r"\d", v)) and len(v) <= 40 and (
        bool(re.search(r"\d{1,4}[/\-.]\d{1,2}[/\-.]\d{2,4}", v))
        or bool(re.search(r"[A-Za-z]{3}", v) and re.search(r"\d{2}", v)))


def detect_date_format(values: list[str], today: date | None = None) -> tuple[str | None, list[str]]:
    """Return (best format, all formats that read every value).

    A reading that puts any transaction more than a day in the future is ruled
    out. If both day-first and month-first still read every date, the caller
    must ask the user which one is right."""
    vals = [v for v in values if v.strip()][:500]
    if not vals:
        return None, []
    limit = (today or date.today()) + timedelta(days=1)

    def fits_all(name: str) -> bool:
        ds = [parse_date(v, name) for v in vals]
        return all(d is not None and d <= limit for d in ds)

    fits = [name for name in DATE_FORMATS if fits_all(name)]
    if not fits:
        # Allow a few odd rows; they'll be reported as invalid.
        scored = sorted(((sum(1 for v in vals if parse_date(v, n)), n) for n in DATE_FORMATS), reverse=True)
        best_n, best = scored[0]
        return (best if best_n >= max(1, int(len(vals) * 0.8)) else None), []
    return fits[0], fits


def is_ambiguous(candidates: list[str]) -> bool:
    return any(a in candidates and b in candidates for a, b in DAY_MONTH_PAIRS)


_AMOUNT_JUNK = re.compile(r"(₹|rs\.?|inr|\s)", re.I)


def parse_amount(value: str) -> tuple[Decimal | None, str | None]:
    """'1,23,456.78' -> (123456.78, None); '500.00 Dr' -> (500.00, 'debit');
    '(250)' -> (-250, None); '-' or '' -> (None, None)."""
    v = (value or "").strip()
    if not v or v in {"-", "--", "0", "0.0", "0.00", "nil", "NIL"}:
        return None, None
    hint = None
    m = re.search(r"\b(dr|cr|debit|credit)\.?$", v, re.I)
    if m:
        hint = "debit" if m.group(1).lower().startswith("d") else "credit"
        v = v[:m.start()].strip()
    neg = False
    if v.startswith("(") and v.endswith(")"):
        neg, v = True, v[1:-1]
    v = _AMOUNT_JUNK.sub("", v).replace(",", "")
    if v.startswith("+"):
        v = v[1:]
    if v.startswith("-") or v.endswith("-"):
        neg, v = True, v.strip("-")
    if not re.fullmatch(r"\d+(\.\d+)?", v):
        raise ValueError(f"'{value}' isn't an amount")
    try:
        amt = Decimal(v)
    except InvalidOperation:
        raise ValueError(f"'{value}' isn't an amount")
    if amt == 0:
        return None, hint
    amt = amt.quantize(Decimal("0.01"))
    return (-amt if neg else amt), hint
