"""Finding the header row and guessing which column holds what."""
import re

FIELDS = ("date", "time", "description", "merchant", "reference", "debit", "credit", "amount", "dr_cr", "balance", "funding")

# Lower-case header text -> field. Checked as whole-header matches first, then as "contains".
SYNONYMS: dict[str, list[str]] = {
    "date": ["txn date", "transaction date", "tran date", "trans date", "date", "posting date",
             "booking date", "value date", "value dt", "date & time", "date and time", "transaction date & time"],
    "time": ["time", "txn time", "transaction time"],
    "description": ["narration", "description", "transaction details", "particulars", "remarks",
                    "transaction remarks", "details", "transaction description", "transaction narration", "info"],
    "merchant": ["merchant", "merchant name", "paid to", "payee", "beneficiary", "name", "to/from"],
    "reference": ["chq./ref.no.", "chq/ref no", "ref no", "ref no./cheque no.", "reference", "reference no",
                  "cheque no", "chq no", "utr", "utr no", "transaction id", "txn id", "upi ref no", "ref"],
    "debit": ["withdrawal amt.", "withdrawal amount", "withdrawal", "withdrawals", "debit", "debit amount",
              "debit amt", "dr amount", "amount debited", "paid out", "money out", "debit(inr)", "withdrawal (dr)"],
    "credit": ["deposit amt.", "deposit amount", "deposit", "deposits", "credit", "credit amount",
               "credit amt", "cr amount", "amount credited", "paid in", "money in", "credit(inr)", "deposit (cr)"],
    "amount": ["amount", "transaction amount", "amount (inr)", "amount(inr)", "amount (in rs.)",
               "amount (rs.)", "amt", "inr", "amount in rs"],
    "dr_cr": ["dr/cr", "cr/dr", "debit/credit", "type", "txn type", "transaction type", "dr / cr", "d/c"],
    "funding": ["paid by", "funding source", "payment instrument", "debited from"],
    "balance": ["closing balance", "balance", "running balance", "available balance", "balance (inr)", "bal"],
}
# Value date is a second date column on bank statements; prefer the transaction date.
SECONDARY_DATE = {"value date", "value dt"}


def _norm(h: str) -> str:
    return " ".join(h.lower().replace("\n", " ").split())


def _field_for(header: str) -> str | None:
    h = _norm(header)
    if not h:
        return None
    for field, names in SYNONYMS.items():
        if h in names:
            return field
    for field in ("debit", "credit", "balance", "description", "reference", "date", "amount"):
        for n in SYNONYMS[field]:
            if len(n) > 3 and n in h:
                return field
    return None


def find_header(rows: list[list[str]]) -> int | None:
    """Index of the header row: the first row (within the top 40) that names a
    date column and some kind of amount column."""
    best, best_score = None, 0
    for i, row in enumerate(rows[:40]):
        fields = {_field_for(c) for c in row}
        if "date" not in fields or not ({"debit", "credit", "amount"} & fields):
            continue
        score = len(fields - {None})
        if score > best_score:
            best, best_score = i, score
    return best


def suggest_mapping(header: list[str]) -> dict[str, int | None]:
    mapping: dict[str, int | None] = {f: None for f in FIELDS}
    for idx, col in enumerate(header):
        field = _field_for(col)
        if field is None:
            continue
        if field == "date" and _norm(col) in SECONDARY_DATE and mapping["date"] is not None:
            continue
        if field == "date" and mapping["date"] is not None and _norm(header[mapping["date"]]) in SECONDARY_DATE:
            mapping["date"] = idx  # a real transaction date beats value date
            continue
        if mapping[field] is None:
            mapping[field] = idx
    if mapping["debit"] is not None or mapping["credit"] is not None:
        # With separate debit/credit columns a generic "Amount" column is usually a duplicate.
        if mapping["debit"] is not None and mapping["credit"] is not None:
            mapping["amount"] = None
    if mapping["description"] is None and mapping["merchant"] is not None:
        mapping["description"] = mapping["merchant"]
    return mapping


def suggest_source(filename: str, header: list[str], rows: list[list[str]]) -> str:
    text = (filename + " " + " ".join(header) + " " + " ".join(" ".join(r) for r in rows[:15])).lower()
    if "phonepe" in text:
        return "phonepe"
    if "bhim" in text:
        return "bhim"
    if re.search(r"paytm|google pay|gpay|amazon pay|cred\b", text):
        return "other_upi"
    if re.search(r"credit card|card no|card number|statement date.*due|total amount due|minimum amount due", text):
        return "credit_card"
    if re.search(r"withdrawal|deposit|closing balance|narration|ifsc|account no", text):
        return "bank"
    return "other"
