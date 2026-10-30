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
    # Card statements often print the merchant's category; these words come first.
    (r"\belectronics?\b|croma|reliance digital|vijay sales|bajaj electronics|sangeetha mobiles|\bpoorvika\b|"
     r"apple india|samsung|\boneplus\b|\bxiaomi\b|\bmi store\b|lenovo|\bdell\b|\bhp store\b", "Electronics"),
    (r"apparel|clothing|garments?|textiles?|fashion|footwear|\bshoes?\b|tailor|myntra|ajio|zudio|westside|"
     r"pantaloons|\bmax\b|trends|lifestyle|shoppers stop|\bh&m\b|\buniqlo\b|bata|metro shoes|"
     r"\bjewel|jewellers|tanishq|kalyan|malabar|titan|watches|lenskart|accessor", "Clothing and accessories"),
    (r"swiggy|zomato|eatsure|domino|pizza|kfc|mcdonald|burger|restaurant|cafe|biryani|chai|starbucks|haldiram|\bhotel\b|tiffin|bakery|sweets", "Food and restaurants"),
    (r"zepto|blinkit|grofers|bigbasket|bb ?daily|instamart|dmart|avenue supermart|ratnadeep|more retail|reliance fresh|jiomart|supermarket|kirana|vegetable|milk|farm fresh|fresh to home|vegetables|fruits", "Groceries"),
    (r"petrol|hpcl|bpcl|iocl|indian ?oil|bharat petroleum|hindustan petroleum|shell|fuel|nayara|filling station|petroleum", "Fuel"),
    (r"amazon|flipkart|meesho|nykaa|tata cliq|decathlon|ikea|\bmall\b|departmental", "Shopping"),
    (r"electricity|tsspdcl|tsnpdcl|apspdcl|bescom|tneb|msedcl|power|water board|gas|airtel|jio|vodafone|vi ?postpaid|bsnl|act fibernet|broadband|recharge|dth|tata ?play", "Utilities"),
    (r"netflix|hotstar|spotify|youtube|prime video|sonyliv|zee5|apple\.com|google play|icloud|chatgpt|openai|anthropic|claude", "Subscriptions"),
    (r"uber|\bola\b|rapido|roppen|irctc|makemytrip|goibibo|indigo|air india|vistara|akasa|redbus|metro|fastag|toll|cleartrip|yatra", "Travel"),
    (r"\blic\b|insurance|policybazaar|hdfc ergo|icici lombard|star health|acko|go digit|bajaj allianz|"
     r"tata aig|niva bupa|care health|max life|sbi life|hdfc life|icici pru|renewal premium", "Insurance"),
    (r"pharma|apollo|medplus|1mg|netmeds|pharmeasy|hospital|clinic|diagnostic|\blabs?\b|doctor|medical|"
     r"medicals|chemist|drug|dental|\beye care\b|health", "Healthcare"),
    (r"zerodha|groww|u?pstox|mutual fund|\bsip\b|\bnps\b|ppf|coin by|kuvera|smallcase|angel one", "Investments"),
    (r"\bemi\b|loan|bajaj finance|home credit|nach.*loan", "Loan and EMI payments"),
    (r"\brent\b|nobroker|maintenance|society", "Rent and housing"),
    (r"school|college|tuition|udemy|coursera|byju|unacademy|fees? payment|vidyalaya|academy|"
     r"university|stationery|books?", "Education"),
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
    if re.search(r"receiver not shown", description or "", re.I):
        return None, None  # different payees hidden behind one label: never group them
    if merchant_cell and merchant_cell.strip():
        _, ref = extract_upi(description or "")
        return _tidy(merchant_cell.strip()), ref
    name, ref = extract_upi(description or "")
    if name:
        return name, ref
    d = re.sub(r"\s{2,}", " ", (description or "").strip())
    d = re.sub(r"^(paid to|payment to|sent to|received from|requested by|money sent to)\s+", "", d, flags=re.I)
    d = re.sub(r"^(pos|ecom|nfs|imps|neft|rtgs|ach|nach|bil|bbps|vps|ips)[\s/\-:]+(\d+[\s/\-:]+)?", "", d, flags=re.I)
    return (_tidy(d[:60]) if d else None), None


def guess_category(text: str, ttype: str, learned: dict[str, int], merchant: str | None,
                   by_name: dict[str, int], payee_key: str | None = None,
                   rules: dict[str, int] | None = None) -> tuple[int | None, str | None]:
    """Returns (category id, where it came from). Order: your saved rule for this payee,
    your earlier choice for this payee or merchant, then built-in keywords."""
    if ttype in ("transfer", "adjustment"):
        return by_name.get("Transfer between my accounts"), "type"
    if ttype == "card_payment":
        return by_name.get("Credit card bill payment"), "type"
    if payee_key and rules and payee_key in rules:
        return rules[payee_key], "rule"
    for key in (payee_key, (merchant or "").lower()):
        if key and key in learned:
            return learned[key], "history"
    if ttype == "income":
        return (by_name.get("Salary"), "keyword") if SALARY.search(text or "") else (None, None)
    for rx, cat in _KEYWORDS:
        if rx.search(text or ""):
            return by_name.get(cat), "keyword"
    return None, None


# ---------- who was paid ----------
_SHOP_VPA = re.compile(
    r"(paytmqr|paytm[.\-]|@pty(s|bl)?$|bharatpe|ratpe|@fbpe$|vyapar\.|\.rzp@|razorpay|@rxaxis|\.bqr@|"
    r"@unitype$|^q\d{6,}@|merchant|\bmswipe|pinelabs|@yespay|@ikwik|gpay-\d|\.payu@|cashfree|@kotakpay)", re.I)
_PERSON_VPA = re.compile(r"(@ok(icici|sbi|hdfcbank|axis)$|^\d{10}@)", re.I)
_MASKED = re.compile(r"x{3,}", re.I)


def find_vpa(*texts: str | None) -> str | None:
    for t in texts:
        m = _VPA.search(t or "")
        if m:
            return m.group(0).lower()
    return None


def payee_key_for(merchant: str | None, description: str | None) -> str | None:
    """A stable key for whoever was paid: the UPI ID if any, else the merchant name."""
    vpa = find_vpa(merchant, description)
    if vpa:
        return vpa[:160]
    name = " ".join(re.sub(r"[^a-z0-9& ]", " ", (merchant or "").lower()).split())
    return name[:160] or None


def payee_kind_for(payee_key: str | None, account_type: str | None) -> str | None:
    """'shop', 'person' or None when it can't be told. Card purchases are always shops."""
    if account_type == "credit_card":
        return "shop"
    if not payee_key or "@" not in payee_key:
        return None
    if _SHOP_VPA.search(payee_key):
        return "shop"
    if _PERSON_VPA.search(payee_key):
        return "person"  # a personal UPI ID: a person, or a small shop using one
    return None


def readable_name(merchant: str | None) -> str | None:
    """The merchant name with masked parts and UPI IDs removed, if enough is left to mean something."""
    name = re.sub(r"\([^)]*\)", " ", merchant or "")
    name = _VPA.sub(" ", name)
    name = " ".join(w for w in name.split() if not _MASKED.search(w))
    return name if len(re.sub(r"[^A-Za-z]", "", name)) >= 4 else None


def payment_method_for(funding: str | None, default: str) -> str:
    """How a UPI payment was funded: 'AXIS BANK RUPAY CREDIT CARD 6530…' or a masked
    card number like 653000XXXXXXXX19 means a credit card; UPI Lite and bank accounts are UPI."""
    f = (funding or "").strip()
    if not f:
        return default
    if re.search(r"credit card", f, re.I) or re.fullmatch(r"\d{4,6}X{4,}\d{2,4}", f.replace(" ", "")):
        return "credit_card"
    return "upi"
