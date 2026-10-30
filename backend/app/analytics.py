"""All money calculations live here so they can be tested on their own.

Rules (see models.py for the sign convention):
  * Rows confirmed as duplicates (duplicate_of_id set) are never counted.
  * Spending = expense + fee + interest. Refunds reduce spending.
  * Income = income + reimbursement.
  * transfer, card_payment and adjustment are never spending or income.
    Paying a card bill is moving your own money; the purchases on the card
    were already counted as spending when they happened.
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Account, Category, Transaction
from .periods import add_months, first_of_month

SPEND_TYPES = {"expense", "fee", "interest"}
REFUND_TYPES = {"refund"}
INCOME_TYPES = {"income", "reimbursement"}
ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT)


def _canonical_rows(db: Session, user_id: int, start: date, end: date):
    stmt = (
        select(Transaction.transaction_date, Transaction.transaction_type,
               Transaction.amount, Transaction.category_id, Transaction.is_reviewed)
        .where(Transaction.user_id == user_id,
               Transaction.duplicate_of_id.is_(None),
               Transaction.transaction_date >= start,
               Transaction.transaction_date <= end)
    )
    return db.execute(stmt).all()


def summarize(db: Session, user_id: int, start: date, end: date) -> dict:
    spend = refunds = income = ZERO
    unreviewed = 0
    rows = _canonical_rows(db, user_id, start, end)
    for _d, ttype, amount, _cat, reviewed in rows:
        amt = money(amount)
        if ttype in SPEND_TYPES:
            spend += amt
        elif ttype in REFUND_TYPES:
            refunds += amt
        elif ttype in INCOME_TYPES:
            income += amt
        if not reviewed:
            unreviewed += 1
    net_expenses = spend - refunds
    return {
        "total_expenses": spend,
        "total_refunds": refunds,
        "net_expenses": net_expenses,
        "total_income": income,
        "net_cash_flow": income - net_expenses,
        "transaction_count": len(rows),
        "unreviewed_count": unreviewed,
    }


def monthly_series(db: Session, user_id: int, today: date, months: int = 12) -> list[dict]:
    first = add_months(today, -(months - 1))
    buckets: dict[str, dict[str, Decimal]] = {}
    for i in range(months):
        key = add_months(first, i).strftime("%Y-%m")
        buckets[key] = {"expenses": ZERO, "income": ZERO}
    for d, ttype, amount, _cat, _r in _canonical_rows(db, user_id, first, today):
        b = buckets[d.strftime("%Y-%m")]
        amt = money(amount)
        if ttype in SPEND_TYPES:
            b["expenses"] += amt
        elif ttype in REFUND_TYPES:
            b["expenses"] -= amt
        elif ttype in INCOME_TYPES:
            b["income"] += amt
    return [{"month": k, **v} for k, v in buckets.items()]


def category_breakdown(db: Session, user_id: int, start: date, end: date) -> list[dict]:
    """Spending per category, with refunds taken off the category they belong to."""
    totals: dict[int | None, Decimal] = defaultdict(lambda: ZERO)
    for _d, ttype, amount, cat, _r in _canonical_rows(db, user_id, start, end):
        if ttype in SPEND_TYPES:
            totals[cat] += money(amount)
        elif ttype in REFUND_TYPES:
            totals[cat] -= money(amount)
    names = dict(db.execute(select(Category.id, Category.name).where(Category.user_id == user_id)).all())
    out = [{"category_id": c, "name": names.get(c, "Uncategorised") if c else "Uncategorised", "amount": a}
           for c, a in totals.items() if a != ZERO]
    return sorted(out, key=lambda x: x["amount"], reverse=True)


def card_outstanding(db: Session, user_id: int) -> dict:
    """A rough running balance per credit card from what Koshio knows.

    It is always labelled an estimate: without the card's statement balance
    (Phase 5) Koshio cannot know about charges or payments it never saw.
    """
    card_ids = db.scalars(select(Account.id).where(
        Account.user_id == user_id, Account.account_type == "credit_card")).all()
    if not card_ids:
        return {"amount": None, "is_estimate": True,
                "note": "Add a credit card account to see an estimate."}
    balance = ZERO
    rows = db.execute(
        select(Transaction.transaction_type, Transaction.direction, Transaction.amount,
               Transaction.account_id, Transaction.counterparty_account_id)
        .where(Transaction.user_id == user_id, Transaction.duplicate_of_id.is_(None),
               (Transaction.account_id.in_(card_ids)) | (Transaction.counterparty_account_id.in_(card_ids)))
    ).all()
    for ttype, direction, amount, acc, counter in rows:
        amt = money(amount)
        if acc in card_ids:
            # Charges to the card raise what you owe; credits to it lower it.
            balance += amt if direction == "debit" else -amt
        elif counter in card_ids and ttype in ("card_payment", "transfer") and direction == "debit":
            # Money sent from a bank account to pay the card.
            balance -= amt
    return {"amount": balance, "is_estimate": True,
            "note": "Estimate from recorded transactions only. Not your statement balance."}
