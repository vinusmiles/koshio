"""Guessing what each imported row means, who the merchant is, and its category.
Everything here is a suggestion: imported rows stay 'to review' until you check them."""
import re

_UPI_REF = re.compile(r"\b(\d{12})\b")
_VPA = re.compile(r"[\w.\-]{2,}@[a-zA-Z][\w]{1,30}")

CARD_PAYMENT = re.compile(
    r"(credit ?card|cc ?payment|card ?bill|card ?payment|cred club|autopay.*card|billdesk.*card|"
    r"payment received|payment - thank you|thank you for (your )?payment|payment thank you|bbps.*card)", re.I)
ATM = re.compile(r"\b(atm|atw|cash withdrawal|nwd|cash wdl)\b", re.I)
SELF = re.compile(r"\b(self|own account|own upi account|sweep|fd booking|transfer to fd|imps.*self)\b"
                  r"|add money|upi lite|wallet (top ?up|load)|transfer to x{4,}\d+", re.I)
FEE = re.compile(r"\b(charges?|fee|gst|annual fee|late payment|sms alert|amc|penalty|dc annual)\b", re.I)
INTEREST = re.compile(r"\b(interest|finance charge)\b", re.I)
REFUND = re.compile(r"\b(refund|reversal|reversed|rev\b|chargeback|cashback|cash back)\b", re.I)
SALARY = re.compile(r"\b(salary|sal\b|payroll)\b", re.I)

# Keyword -> category name (must match the seeded category names).
KEYWORDS: list[tuple[str, str]] = [
    (r"fastag|\btoll\b", "Travel"),  # before Utilities, which matches "recharge"
    (r"swiggy|zomato|eatsure|domino|pizza|kfc|mcdonald|burger|restaurant|cafe|biryani|chai|starbucks|haldiram|\bhotel\b|tiffin|bakery|sweets", "Food and restaurants"),
    (r"zepto|blinkit|grofers|bigbasket|bb ?daily|instamart|dmart|avenue supermart|ratnadeep|more retail|reliance fresh|jiomart|supermarket|kirana|vegetable|milk|farm fresh|fresh to home|vegetables|fruits", "Groceries"),
    (r"petrol|hpcl|bpcl|iocl|indian ?oil|bharat petroleum|hindustan petroleum|shell|fuel|nayara|filling station|petroleum", "Fuel"),
    (r"amazon|flipkart|myntra|ajio|meesho|nykaa|tata cliq|croma|reliance digital|decathlon|ikea", "Shopping"),
    (r"electricity|tsspdcl|tsnpdcl|apspdcl|bescom|tneb|msedcl|power|water board|gas|airtel|jio|vodafone|vi ?postpaid|bsnl|act fibernet|broadband|recharge|dth|tata ?play", "Utilities"),
    (r"netflix|hotstar|spotify|youtube|prime video|sonyliv|zee5|apple\.com|google play|icloud|chatgpt|openai|anthropic|claude", "Subscriptions"),
    (r"uber|\bola\b|rapido|roppen|irctc|makemytrip|goibibo|indigo|air india|vistara|akasa|redbus|metro|fastag|toll|cleartrip|yatra", "Travel"),
    (r"pharma|apollo|medplus|1mg|netmeds|pharmeasy|hospital|clinic|diagnostic|lab|doctor", "Healthcare"),
    (r"\blic\b|insurance|policybazaar|hdfc ergo|icici lombard|star health|acko|digit", "Insurance"),
    (r"zerodha|groww|u?pstox|mutual fund|\bsip\b|\bnps\b|ppf|coin by|kuvera|smallcase|angel one", "Investments"),
    (r"\bemi\b|loan|bajaj finance|home credit|nach.*loan", "Loan and EMI payments"),
    (r"\brent\b|nobroker|maintenance|society", "Rent and housing"),
    (r"school|college|tuition|udemy|coursera|byju|unacademy|fees? payment", "Education"),
    (r"bookmyshow|pvr|inox|cinema|movie|gaming|steam", "Entertainment"),
    (r"salon|spa|barber|urban company|lakme|grooming", "Personal care"),
]
_KEYWORDS = [(re.compile(p, re.I), c) for p, c in KEYWORDS]


def guess_type(direction: str, text: str, account_type: str | None) -> str:
    t = text or ""
    if direction == "credit":
        if account_type == "credit_card":
            return "card_payment" if CARD_PAYMENT.search(t) else "refund"
        if REFUND.search(t):
            return "refund"
        if INTEREST.search(t):
            return "income"
        return "income"
    # money out
    if account_type == "credit_card":
        if INTEREST.search(t):
            return "interest"
        if FEE.search(t):
            return "fee"
        return "expense"
    if CARD_PAYMENT.search(t):
        return "card_payment"
    if ATM.search(t) or SELF.search(t):
        return "transfer"
    if FEE.search(t) and not re.search(r"\bupi\b", t, re.I):
        return "fee"
    return "expense"


def extract_upi(text: str) -> tuple[str | None, str | None]:
    """Return (merchant or person name, UPI reference) from a UPI narration, if it is one.

    Handles the common shapes, e.g.
      UPI/DR/412345678901/RATNADEEP SUPER/YESB/ratnadeep@ybl/groceries   (SBI style)
      UPI-SWIGGY-swiggy@icici-ICIC0000001-412345678901-Order            (HDFC style)
      UPI/412345678901/Payment from Phone/zomato@hdfcbank/HDFC BANK    (ICICI style)
    """
    t = (text or "").strip()
    if not re.match(r"^(upi|upi[/\-:])", t, re.I) and "@" not in t:
        return None, None
    ref_m = _UPI_REF.search(t)
    ref = ref_m.group(1) if ref_m else None
    parts = [p.strip() for p in re.split(r"[/\-]", t) if p.strip()]
    skip = re.compile(r"^(upi|dr|cr|p2m|p2a|collect|pay|payment|upiintent|upi intent|sent|received)$", re.I)
    for p in parts:
        if skip.match(p) or _UPI_REF.fullmatch(p) or "@" in p or re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", p):
            continue
        if re.fullmatch(r"[A-Z]{4}", p) or re.fullmatch(r"\d+", p):  # bank codes like YESB, bare numbers
            continue
        if _NOISE.search(p):  # "Payment from Phone", "HDFC BANK" and similar
            continue
        if len(p) >= 3 and re.search(r"[A-Za-z]{3}", p):
            return _tidy(p), ref
    vpa = _VPA.search(t)
    return (_tidy(vpa.group(0).split("@")[0]) if vpa else None), ref


_NOISE = re.compile(r"^(payment|paid|sent|money|upi|pay to|transfer)\b|\b(bank|bank ltd|bk)$", re.I)


def _tidy(name: str) -> str:
    name = " ".join(name.replace("_", " ").split())[:120]
    return name.title() if name.isupper() or name.islower() else name


def guess_merchant(description: str, merchant_cell: str | None) -> tuple[str | None, str | None]:
    """(merchant, upi_reference)."""
    if merchant_cell and merchant_cell.strip():
        _, ref = extract_upi(description or "")
        return _tidy(merchant_cell.strip()), ref
    name, ref = extract_upi(description or "")
    if name:
        return name, ref
    d = re.sub(r"\s{2,}", " ", (description or "").strip())
    d = re.sub(r"^(pos|ecom|nfs|imps|neft|rtgs|ach|nach|bil|bbps|vps|ips)[\s/\-:]+(\d+[\s/\-:]+)?", "", d, flags=re.I)
    return (_tidy(d[:60]) if d else None), None


def guess_category(text: str, ttype: str, learned: dict[str, int], merchant: str | None,
                   by_name: dict[str, int]) -> int | None:
    """Your own earlier choice for this merchant wins, then built-in keywords."""
    if ttype in ("transfer", "adjustment"):
        return by_name.get("Transfer between my accounts")
    if ttype == "card_payment":
        return by_name.get("Credit card bill payment")
    if merchant and merchant.lower() in learned:
        return learned[merchant.lower()]
    if ttype == "income":
        return by_name.get("Salary") if SALARY.search(text or "") else None
    for rx, cat in _KEYWORDS:
        if rx.search(text or ""):
            return by_name.get(cat)
    return None


def payment_method_for(funding: str | None, default: str) -> str:
    """How a UPI payment was funded: 'AXIS BANK RUPAY CREDIT CARD 6530…' or a masked
    card number like 653000XXXXXXXX19 means a credit card; UPI Lite and bank accounts are UPI."""
    f = (funding or "").strip()
    if not f:
        return default
    if re.search(r"credit card", f, re.I) or re.fullmatch(r"\d{4,6}X{4,}\d{2,4}", f.replace(" ", "")):
        return "credit_card"
    return "upi"
