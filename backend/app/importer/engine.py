"""Turn raw rows plus column choices into checked transaction candidates.

The same inputs always give the same output, so the preview you see and the
import that runs afterwards match exactly."""
import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal

from . import classify, columns, values

AMOUNT_SIGNS = ("negative_is_debit", "positive_is_debit")


@dataclass
class Options:
    header_row: int | None = None          # 0-based index into rows; None = detect
    mapping: dict[str, int | None] | None = None
    date_format: str | None = None
    amount_sign: str | None = None


@dataclass
class Row:
    row_number: int                        # 1-based, as in the spreadsheet
    status: str                            # ready | duplicate | invalid | unrecognised
    message: str | None = None
    transaction_date: date | None = None
    time: str | None = None
    description: str | None = None
    merchant_name: str | None = None
    amount: Decimal | None = None
    direction: str | None = None
    transaction_type: str | None = None
    category_id: int | None = None
    reference: str | None = None
    upi_reference: str | None = None
    funding_source: str | None = None
    fingerprint: str | None = None
    raw: list[str] = field(default_factory=list)


@dataclass
class Result:
    header_row: int | None
    columns: list[str]
    mapping: dict[str, int | None]
    date_format: str | None
    date_format_options: list[str]
    date_format_ambiguous: bool
    amount_sign: str | None
    needs_amount_sign: bool
    suggested_source: str
    problems: list[str]
    rows: list[Row]

    def counts(self) -> dict[str, int]:
        c = Counter(r.status for r in self.rows)
        return {"detected": len(self.rows), "ready": c["ready"], "duplicate": c["duplicate"],
                "invalid": c["invalid"], "unrecognised": c["unrecognised"]}

    def date_range(self) -> tuple[date | None, date | None]:
        ds = [r.transaction_date for r in self.rows if r.transaction_date and r.status in ("ready", "duplicate")]
        return (min(ds), max(ds)) if ds else (None, None)

    def as_dict(self) -> dict:
        d = asdict(self)
        for r in d["rows"]:  # money goes out as exact strings, never floats
            if r["amount"] is not None:
                r["amount"] = f"{r['amount']:.2f}"
        d["counts"] = self.counts()
        d["date_from"], d["date_to"] = self.date_range()
        return d


def _cell(row: list[str], idx: int | None) -> str:
    return row[idx].strip() if idx is not None and idx < len(row) and row[idx] else ""


def fingerprint(account_id: int, d: date, amount: Decimal, direction: str, key: str, occurrence: int) -> str:
    raw = f"{account_id}|{d.isoformat()}|{amount:.2f}|{direction}|{key}|{occurrence}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _norm_key(reference: str | None, description: str | None) -> str:
    if reference and reference.strip("0 ") and len(reference.strip()) >= 4:
        return "ref:" + reference.strip().lower()
    return "desc:" + " ".join((description or "").lower().split())


def analyse(rows: list[list[str]], filename: str, opts: Options, *, account_id: int, today: date,
            other_refs: dict[str, str] | None = None,
            account_type: str | None, existing: set[str], learned: dict[str, int],
            categories_by_name: dict[str, int]) -> Result:
    problems: list[str] = []
    header_row = opts.header_row if opts.header_row is not None else columns.find_header(rows)
    if header_row is None or header_row >= len(rows):
        return Result(None, [], {f: None for f in columns.FIELDS}, None, [], False, None, False,
                      columns.suggest_source(filename, [], rows),
                      ["Koshio couldn't find the column headings (like Date, Narration, Debit, Credit). "
                       "Choose the heading row below."], [])
    header = [c.strip() for c in rows[header_row]]
    mapping = {f: None for f in columns.FIELDS}
    mapping.update(columns.suggest_mapping(header) if opts.mapping is None else opts.mapping)
    for f, i in mapping.items():
        if i is not None and not (0 <= i < len(header)):
            mapping[f] = None
    source = columns.suggest_source(filename, header, rows)

    if mapping["date"] is None:
        problems.append("Choose which column has the date.")
    has_split = mapping["debit"] is not None or mapping["credit"] is not None
    if not has_split and mapping["amount"] is None:
        problems.append("Choose the amount column, or the debit and credit columns.")

    body = list(enumerate(rows[header_row + 1:], start=header_row + 2))
    body = [(n, r) for n, r in body if any(c.strip() for c in r)]

    # Dates
    date_vals = [_cell(r, mapping["date"]) for _, r in body if values.looks_like_date(_cell(r, mapping["date"]))]
    best, options = values.detect_date_format(date_vals, today)
    date_format = opts.date_format or best
    ambiguous = opts.date_format is None and values.is_ambiguous(options)
    if ambiguous:
        problems.append("Some dates could be day-first or month-first (like 04/05/2026). Choose the date format.")
    if date_format is None and mapping["date"] is not None:
        problems.append("Koshio couldn't recognise the date format. Check the date column or pick a format.")

    needs_sign = not has_split and mapping["amount"] is not None and mapping["dr_cr"] is None
    amount_sign = opts.amount_sign or ("positive_is_debit" if account_type == "credit_card" else "negative_is_debit")

    if problems and (mapping["date"] is None or (not has_split and mapping["amount"] is None)):
        return Result(header_row, header, mapping, date_format, options, ambiguous, amount_sign, needs_sign,
                      source, problems, [])

    out: list[Row] = []
    seen: Counter = Counter()
    for n, r in body:
        out.append(_row(n, r, mapping, date_format, amount_sign, needs_sign, account_id, account_type,
                        existing, learned, categories_by_name, seen, other_refs or {}))
    return Result(header_row, header, mapping, date_format, options, ambiguous, amount_sign, needs_sign,
                  source, problems, out)


def _row(n, r, mapping, date_format, amount_sign, needs_sign, account_id, account_type,
         existing, learned, cats, seen, other_refs) -> Row:
    raw = list(r)
    date_txt = _cell(r, mapping["date"])
    desc = _cell(r, mapping["description"]) or None
    row = Row(row_number=n, status="ready", raw=raw, description=desc)

    def amount_of(idx):
        return values.parse_amount(_cell(r, idx)) if idx is not None else (None, None)

    if not values.looks_like_date(date_txt):
        # Opening balance lines, totals, page footers and the like.
        row.status = "unrecognised"
        note = (desc or "").split(":", 1)[0]
        row.message = (note + "." if note.startswith(("Summary line", "Not a completed payment"))
                       else "No date in this row, so it doesn't look like a transaction.")
        return row

    try:
        debit, d_hint = amount_of(mapping["debit"])
        credit, c_hint = amount_of(mapping["credit"])
        amt, a_hint = amount_of(mapping["amount"])
    except ValueError as e:
        row.status, row.message = "invalid", f"Amount couldn't be read: {e}."
        return row

    d = values.parse_date(date_txt, date_format) if date_format else None
    if d is None:
        row.status, row.message = "invalid", f"Date '{date_txt}' couldn't be read."
        return row
    row.transaction_date = d
    _, row.time = values.split_time(date_txt)
    if mapping["time"] is not None and _cell(r, mapping["time"]):
        _, row.time = values.split_time("x " + _cell(r, mapping["time"]))

    # Work out amount and direction.
    if debit and credit:
        row.status, row.message = "invalid", "Both debit and credit have an amount."
        return row
    if debit:
        amount, direction = abs(debit), "debit"
    elif credit:
        amount, direction = abs(credit), "credit"
    elif amt:
        amount = abs(amt)
        flag = _cell(r, mapping["dr_cr"]).lower()
        if flag.startswith(("d", "w")) or flag in ("dr", "debit", "withdrawal", "paid", "sent"):
            direction = "debit"
        elif flag.startswith("c") or flag in ("credit", "deposit", "received"):
            direction = "credit"
        elif a_hint:
            direction = a_hint
        elif mapping["dr_cr"] is not None and flag:
            row.status, row.message = "invalid", f"'{flag}' doesn't say whether money went out or came in."
            return row
        else:
            negative = amt < 0
            direction = ("debit" if negative else "credit") if amount_sign == "negative_is_debit" \
                else ("credit" if negative else "debit")
    else:
        hint = d_hint or c_hint or a_hint
        row.status = "invalid"
        row.message = "No amount in this row." if not hint else "Amount is zero."
        return row
    if amount > Decimal("999999999999.99"):
        row.status, row.message = "invalid", "Amount is too large."
        return row

    row.amount, row.direction = amount, direction
    row.reference = _cell(r, mapping["reference"]) or None
    row.funding_source = (_cell(r, mapping["funding"]) or None) if "funding" in mapping else None
    merchant, upi_ref = classify.guess_merchant(desc or "", _cell(r, mapping["merchant"]) or None)
    if not upi_ref and row.reference and re.fullmatch(r"\d{12}", row.reference):
        upi_ref = row.reference  # UTR / UPI reference given in its own column (UPI app statements)
    row.merchant_name, row.upi_reference = merchant, upi_ref
    text = " ".join(filter(None, [desc, _cell(r, mapping["merchant"])]))
    row.transaction_type = classify.guess_type(direction, text, account_type)
    row.category_id = classify.guess_category(text, row.transaction_type, learned, merchant, cats)

    key = _norm_key(row.reference, desc)
    base = (d, amount, direction, key)
    occurrence = seen[base]
    seen[base] += 1
    row.fingerprint = fingerprint(account_id, d, amount, direction, key, occurrence)
    if row.fingerprint in existing:
        row.status, row.message = "duplicate", "Already in Koshio from an earlier import."
    elif upi_ref and upi_ref in other_refs:
        # The same UPI payment, already imported from another statement (e.g. the bank's).
        row.status = "duplicate"
        row.message = f"Same UPI payment (ref {upi_ref}) is already in Koshio from {other_refs[upi_ref]}."
    return row


def mapping_json(result: Result) -> str:
    return json.dumps({"header_row": result.header_row, "mapping": result.mapping,
                       "date_format": result.date_format, "amount_sign": result.amount_sign})
