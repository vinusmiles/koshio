"""Reading PDF statements: UPI apps (PhonePe, Google Pay, Paytm), credit cards and banks.

PDFs have no columns, only lines of text, so each statement style gets its own
reader. Every reader produces the same simple table, which then goes through
the same checks as a CSV: Date, Time, Description, Merchant, Reference, Debit, Credit.

The PDF password, when one is needed, is used only to open the file in memory.
It is never stored or logged.
"""
import io
import re

from .readers import ReadError

HEADER = ["Date", "Time", "Description", "Merchant", "Reference", "Debit", "Credit", "Paid by"]
MAX_PAGES = 60

_MON = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
DATE = re.compile(
    rf"^\s*(\d{{4}}-\d{{2}}-\d{{2}}"                       # 2026-10-05
    rf"|\d{{1,2}}[/\-.]\d{{1,2}}[/\-.]\d{{2,4}}"            # 05/10/2026, 05-10-26
    rf"|\d{{1,2}}[ \-]{_MON},?[ \-]\d{{2,4}}"               # 05 Oct, 2026 / 05-Oct-26
    rf"|{_MON} \d{{1,2}},? \d{{4}})(?![\d])", re.I)         # Oct 05, 2026
TIME = re.compile(r"^\s*[|,]?\s*(\d{1,2}:\d{2}(?::\d{2})?\s*(?:[ap]\.?m\.?)?)(?![\d])", re.I)
MONEY = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{2,3})+|\d+)\.(\d{2})(?![\d])")
UPI_AMOUNT = re.compile(r"(?P<sign>[+\-])?\s*(?:₹|rs\.?|inr)\s*(?P<num>\d[\d,]*(?:\.\d{1,2})?)", re.I)
UTR = re.compile(r"(?:utr(?:\s*no)?|upi\s*(?:transaction|ref(?:erence)?)\s*(?:id|no)?|upi\s*ref(?:\s*no)?|reference\s*(?:id|no))"
                 r"\s*[.:#]?\s*(\d{12})", re.I)
TWELVE = re.compile(r"(?<!\d)(\d{12})(?!\d)")
PHONEPE_TXN = re.compile(r"transaction\s*id\s*[:.]?\s*([A-Z0-9]{12,})", re.I)

UPI_OUT = re.compile(r"\b(paid to|sent to|payment to|transfer to|transferred to|money sent|self transfer|"
                     r"bill paid|recharge|paid for|debited)\b", re.I)
UPI_IN = re.compile(r"\b(received from|refund from|refunded|cashback|credited|money received|reversal)\b", re.I)
COUNTERPARTY = re.compile(r"\b(?:paid to|sent to|payment to|transfer(?:red)? to|received from|refund from|"
                          r"money sent to|self transfer to|bill paid to|paid for|requested by)\s+(.+)", re.I)
FUNDING = re.compile(r"\b(?:paid by|credited to|debited from|paid from|received in)\s*[:]?\s*(.+)", re.I)
_DETAIL = re.compile(r"^(transaction id|utr|upi|paid by|credited to|debited from|bharat connect|reference|page \d)", re.I)
SKIP_STATUS = re.compile(r"\b(failed|declined|pending|cancelled|reversed due to failure)\b", re.I)

# Lines on card and bank statements that have a date and an amount but aren't transactions.
SUMMARY = re.compile(
    r"statement\s*date|payment\s*due|due\s*date|total\s*(amount\s*)?due|minimum\s*(amount\s*)?due|"
    r"credit\s*limit|available\s*(credit|cash|limit|balance)|opening\s*balance|previous\s*(statement\s*)?balance|"
    r"closing\s*balance|total\s*outstanding|reward|points?\s*(earned|balance)|statement\s*period|billing\s*period|"
    r"cash\s*limit|last\s*date|account\s*summary|total\s*(debits|credits|purchases|payments)|generated\s*on|"
    r"period\s*:|from\s*\d.*\bto\b\s*\d", re.I)
CREDIT_MARK = re.compile(r"^\s*(cr|c)\b\.?", re.I)
DEBIT_MARK = re.compile(r"^\s*(dr|d)\b\.?", re.I)


class PdfPasswordError(ReadError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _try_open(data: bytes, passwords: list[str]):
    """Open the PDF with the first password that works. Returns (pdf, index of that password).
    Passwords are only tried in memory; none is stored or logged."""
    import pdfplumber
    last_error = None
    for i, pw in enumerate(passwords or [""]):
        try:
            return pdfplumber.open(io.BytesIO(data), password=pw or ""), i
        except Exception as e:
            last_error = e
            if not _is_password_error(e):
                break
    raise last_error


def _is_password_error(e: Exception) -> bool:
    names = {type(x).__name__ for x in (e, e.__cause__, e.__context__) if x is not None}
    text = str(e).lower()
    return any("Password" in n for n in names) or "password" in text or "encrypt" in text


def _open_text(data: bytes, passwords: list[str]) -> tuple[str, int]:
    password = any(passwords)
    try:
        pdf, used = _try_open(data, passwords)
    except Exception as e:  # pdfminer raises several types for encryption problems
        if _is_password_error(e):
            if password:
                raise PdfPasswordError("pdf_password_wrong", "That password didn't open the PDF. Check it and try again.")
            raise PdfPasswordError("pdf_password_required", "This PDF is password-protected. Enter its password to read it.")
        raise ReadError("This PDF couldn't be opened. It may be damaged.")
    try:
        if len(pdf.pages) > MAX_PAGES:
            raise ReadError(f"This PDF has more than {MAX_PAGES} pages. Download a shorter period.")
        pages = [(p.extract_text(x_tolerance=1.5, y_tolerance=3) or "") for p in pdf.pages]
    except ReadError:
        raise
    except Exception as e:
        names = {type(x).__name__ for x in (e, e.__cause__, e.__context__) if x is not None}
        if any("Password" in n for n in names):
            raise PdfPasswordError("pdf_password_required", "This PDF is password-protected. Enter its password to read it.")
        raise ReadError("This PDF couldn't be read.")
    finally:
        pdf.close()
    return "\n".join(pages), used


def detect(text: str) -> str:
    t = text.lower()
    if "phonepe" in t:
        return "phonepe"
    if "pay/collect" in t and "dr/cr" in t:
        return "bhim"
    if "google pay" in t or "gpay" in t:
        return "google_pay"
    if "paytm" in t and ("paid to" in t or "received from" in t):
        return "paytm"
    if re.search(r"credit card|card statement|total amount due|minimum amount due|payment due date|card no", t):
        return "credit_card"
    if "paid to" in t and ("received from" in t or "utr" in t or "upi transaction id" in t):
        return "upi"
    if re.search(r"withdrawal|deposit|closing balance|opening balance|account statement|statement of account", t):
        return "bank"
    return "credit_card"  # date + description + amount lines are the most common remaining shape


SOURCE_FOR = {"phonepe": "phonepe", "bhim": "bhim", "google_pay": "other_upi", "paytm": "other_upi", "upi": "other_upi",
              "credit_card": "credit_card", "bank": "bank"}


def read_pdf(data: bytes, passwords: list[str] | str | None) -> tuple[list[list[str]], str, str, int]:
    """Return (table rows including header, Koshio source, statement style,
    index of the password that opened it)."""
    if isinstance(passwords, str) or passwords is None:
        passwords = [passwords or ""]
    text, used = _open_text(data, passwords)
    if len(text.strip()) < 30:
        raise ReadError("This PDF has no text in it, only pictures of the pages, so Koshio can't read it. "
                        "This often happens when a statement's password is removed by printing or saving a copy. "
                        "Use the original file from the email or app instead: Koshio can open password-protected "
                        "statements and asks for the password.")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    style = detect(text)
    if style == "bhim":
        rows = _bhim(text)
    elif style in ("phonepe", "google_pay", "paytm", "upi"):
        rows = _upi(lines)
    elif style == "bank":
        rows = _bank(lines)
    else:
        rows = _card(lines, has_points=bool(re.search(r"reward\s*points", text, re.I)))
    if not any(r[0] for r in rows):
        raise ReadError("No transactions were found in this PDF. If it is a statement, send feedback with "
                        "the bank or app name so Koshio can learn its layout.")
    return [HEADER] + rows, SOURCE_FOR[style], style, used


def _split_date(line: str) -> tuple[str | None, str, str]:
    """('05/10/2026', '19:32', rest of line) from a line starting with a date."""
    m = DATE.match(line)
    if not m:
        return None, "", line
    rest = line[m.end():]
    t = TIME.match(rest)
    time = ""
    if t:
        time, rest = t.group(1), rest[t.end():]
    return m.group(1), time, rest.strip(" |,")


def _is_period(rest: str) -> bool:
    """'- Oct 24, 2026' or 'to 31/10/2026' after a date: a statement period, not a transaction."""
    m = re.match(r"^\s*(-|–|to)\s*", rest, re.I)
    return bool(m) and bool(DATE.match(rest[m.end():]))


def _row(date="", time="", desc="", merchant="", ref="", debit="", credit="", funding="") -> list[str]:
    return [date, time, " ".join(desc.split())[:500], " ".join(merchant.split()), ref, debit, credit, funding]


# ---------- UPI apps ----------
def _upi(lines: list[str]) -> list[list[str]]:
    records: list[tuple[str, str, list[str]]] = []
    for ln in lines:
        d, time, rest = _split_date(ln)
        if d and _is_period(rest):
            continue
        if d:
            records.append((d, time, [rest]))
        elif records:
            # Times often sit on the line below the date.
            t = TIME.match(ln)
            if t and not records[-1][1]:
                records[-1] = (records[-1][0], t.group(1), records[-1][2] + [ln[t.end():].strip()])
            else:
                records[-1][2].append(ln)
    out = []
    for d, time, parts in records:
        parts = [x for x in parts if x.strip()] or [""]
        first = parts[0]
        body = " ".join(parts)
        if SKIP_STATUS.search(body):
            out.append(_row(desc=f"Not a completed payment, skipped: {d} {first}"))
            continue
        in_first = UPI_AMOUNT.search(first)
        m = in_first or UPI_AMOUNT.search(body)
        word = re.search(r"\b(DEBIT|CREDIT)\b", body)
        desc = (first[:in_first.start()] + " " + first[in_first.end():]) if in_first else first
        desc = re.sub(r"\b(DEBIT|CREDIT)\b", "", desc).strip(" |,")
        cp = COUNTERPARTY.search(desc)
        merchant = cp.group(1).strip(" |,") if cp else ""
        if not merchant and re.search(r"\b(paid to|payment to|received from|requested by)\s*$", desc, re.I) \
                and len(parts) > 1 and not _DETAIL.match(parts[1]):
            merchant = parts[1].strip()  # long names wrap onto the next line
            desc = f"{desc} {merchant}"
        fund_m = next((FUNDING.match(x) for x in parts[1:] if FUNDING.match(x)), None)
        funding = fund_m.group(1).strip() if fund_m else ""
        if not m:
            out.append(_row(d, time, desc, merchant))  # reported as "no amount"
            continue
        amount = f"{float(m.group('num').replace(',', '')):.2f}"
        if word:
            debit = word.group(1) == "DEBIT"
        elif m.group("sign"):
            debit = m.group("sign") == "-"
        else:
            debit = not UPI_IN.search(desc)
        ref_m = UTR.search(body) or TWELVE.search(body)
        ref = ref_m.group(1) if ref_m else ""
        if not ref:
            t = PHONEPE_TXN.search(body)
            ref = t.group(1) if t else ""
        out.append(_row(d, time, desc, merchant, ref, amount if debit else "", "" if debit else amount, funding))
    return out


# ---------- BHIM ----------
BHIM_ROW = re.compile(
    r"(?P<date>\d{2}/\d{2}/\d{4}) (?P<time>\d{2}:\d{2}:\d{2}) (?P<bank>.+?) (?P<acct>[X*\d]{6,}) "
    r"(?P<sender>\S+?\([^)]*\)) (?P<receiver>\S+?\([^)]*\)|N/AN/A) (?P<ref>\d{12}) (?P<kind>PAY|COLLECT) "
    r"(?P<amt>[\d,]+\.\d{2}) (?P<drcr>DR|CR) (?P<status>[A-Z]+)")
_VPA_NAME = re.compile(r"^(?P<vpa>[^(]*)\((?P<name>[^)]*)\)$")


def _bhim(text: str) -> list[list[str]]:
    flat = " ".join(text.split())
    matches = list(BHIM_ROW.finditer(flat))
    # All your own UPI IDs appear as the sender of your payments.
    mine = {(_VPA_NAME.match(m.group("sender")) or _VPA_NAME.match("x()")).group("vpa").lower()
            for m in matches if m.group("drcr") == "DR"}
    out = []
    for m in matches:
        funding = f"{m.group('bank').strip()} {m.group('acct')}"
        amount = m.group("amt").replace(",", "")
        if m.group("status") != "SUCCESS":
            out.append(_row(desc=f"Not a completed payment, skipped: {m.group('date')} {amount} "
                                 f"{m.group('status').lower()}"))
            continue
        debit = m.group("drcr") == "DR"
        other = m.group("receiver") if debit else m.group("sender")
        vm = _VPA_NAME.match(other)
        vpa, name = (vm.group("vpa"), vm.group("name")) if vm else ("", "")
        name = re.sub(r"^x{3,}", "", name).strip()
        if vpa.lower() in mine and debit:
            desc, merchant = f"Transfer to own UPI account {vpa}", ""
        elif not vpa and not name:
            # BHIM hides the receiver for bill payments. From a bank account these are
            # credit card bills (paying one card with another isn't possible), so they're
            # card payments, not spending. From a card, it's some other bill or purchase.
            if debit and not re.search(r"credit card", funding, re.I):
                desc = "Credit card bill payment (receiver not shown in statement)"
            else:
                desc = "Bill or merchant payment (receiver not shown in statement)"
            merchant = ""
        else:
            shown = name if len(re.sub(r"[^A-Za-z]", "", name)) >= 3 else ""
            merchant = f"{shown} ({vpa})" if shown and vpa else (shown or vpa)
            verb = "Paid to" if debit else ("Cashback from" if "bhim" in name.lower() or "cashback" in vpa.lower()
                                            else "Received from")
            desc = f"{verb} {merchant}"
        out.append(_row(m.group("date"), m.group("time"), desc, merchant, m.group("ref"),
                        amount if debit else "", "" if debit else amount, funding))
    return out


# ---------- credit cards ----------
def _card(lines: list[str], has_points: bool = False) -> list[list[str]]:
    out = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        d, time, rest = _split_date(ln)
        i += 1
        if not d or _is_period(rest):
            continue
        if SUMMARY.search(ln):
            if MONEY.search(rest):
                out.append(_row(desc=f"Summary line, not a transaction: {ln}"))
            continue
        amounts = list(MONEY.finditer(rest))
        if not amounts and i < len(lines) and not DATE.match(lines[i]) and MONEY.search(lines[i]):
            rest = rest + " " + lines[i]  # amount wrapped onto the next line
            i += 1
            amounts = list(MONEY.finditer(rest))
        if not amounts:
            continue  # a date with no amount: a heading such as "Statement for 05/10/2026"
        # The amount is the first number marked Dr/Cr. Later columns (Axis "Cashback earned",
        # reward points) come after it; with no marks at all, the last number is the amount.
        marked = [a for a in amounts if re.match(r"\s*(dr|cr)\b", rest[a.end():], re.I)]
        last = marked[0] if marked else amounts[-1]
        amount = f"{last.group(1).replace(',', '')}.{last.group(2)}"
        after, before = rest[last.end():], rest[:last.start()]
        if DEBIT_MARK.match(after):
            credit = False
        else:
            credit = (bool(CREDIT_MARK.match(after)) or before.rstrip().endswith(("+", "Cr", "CR"))
                      or bool(re.search(r"\b(payment received|thank you|refund|reversal|cashback)\b", before, re.I)))
        desc = before.rstrip(" +-|₹").removesuffix("Cr").removesuffix("CR").strip(" |")
        desc = re.sub(r"\s+(₹|Rs\.?|INR)$", "", desc, flags=re.I)
        if has_points:
            desc = re.sub(r"\s+\d{1,5}$", "", desc)  # the reward points column
        out.append(_row(d, time, desc, "", "", "" if credit else amount, amount if credit else ""))
    return out


# ---------- banks ----------
def _bank(lines: list[str]) -> list[list[str]]:
    out: list[list[str]] = []
    prev_balance = None
    m = re.search(r"opening\s*balance[^\d]*([\d,]+\.\d{2})", " ".join(lines[:60]), re.I)
    if m:
        prev_balance = float(m.group(1).replace(",", ""))
    pending: list[str] | None = None
    for ln in lines:
        d, time, rest = _split_date(ln)
        if not d:
            # Narrations often wrap onto following lines.
            if pending is not None and not MONEY.search(ln) and not SUMMARY.search(ln) and len(ln) < 120:
                pending[2] = pending[2] + " " + ln
            continue
        if SUMMARY.search(ln) or _is_period(rest):
            continue
        # A second date right after the first is the value date.
        d2 = DATE.match(rest)
        if d2:
            rest = rest[d2.end():].strip()
        amounts = list(MONEY.finditer(rest))
        if not amounts:
            continue
        nums = [float(a.group(1).replace(",", "") + "." + a.group(2)) for a in amounts]
        desc = rest[:amounts[0].start()].strip(" |")
        debit = credit = ""
        if len(nums) >= 2:
            amt, bal = nums[-2], nums[-1]
            tail = rest[amounts[-2].end():amounts[-1].start()]
            if prev_balance is not None and abs(prev_balance - amt - bal) < 0.005:
                debit = f"{amt:.2f}"
            elif prev_balance is not None and abs(prev_balance + amt - bal) < 0.005:
                credit = f"{amt:.2f}"
            elif CREDIT_MARK.match(tail):
                credit = f"{amt:.2f}"
            elif DEBIT_MARK.match(tail):
                debit = f"{amt:.2f}"
            prev_balance = bal
        else:
            after = rest[amounts[-1].end():]
            if CREDIT_MARK.match(after):
                credit = f"{nums[0]:.2f}"
            elif DEBIT_MARK.match(after):
                debit = f"{nums[0]:.2f}"
        pending = _row(d, time, desc, "", "", debit, credit)
        if not debit and not credit:
            pending[2] += " (Koshio couldn't tell whether this was money in or out)"
        out.append(pending)
    return out
