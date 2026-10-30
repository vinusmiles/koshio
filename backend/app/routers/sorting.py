"""Quick sort: uncategorised payments grouped by who was paid, one choice per group.
A choice is saved as a rule, applied to every matching payment you already have,
and used automatically on future imports."""
import re
from collections import Counter, defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..analytics import SPEND_TYPES, money
from ..db import get_db
from ..importer.classify import readable_name
from ..models import Category, PayeeRule, Transaction, User
from ..security import current_user
from .common import get_owned

router = APIRouter(prefix="/sorting", tags=["sorting"])
SORTABLE = SPEND_TYPES | {"refund"}


def _display_name(name: str | None, key: str) -> str:
    """'TEA (xxxratpe.x@unitype)' -> 'TEA'; a fully masked name falls back to the UPI ID."""
    base = re.sub(r"\s*\([^)]*\)\s*$", "", name or "").strip()
    if base and not re.fullmatch(r"x{3,}\w{0,4}", base, re.I):
        return re.sub(r"^x{3,}", "", base, flags=re.I) or base
    return readable_name(name) or key


def _time_of_day(ts) -> str | None:
    return None if ts is None else ("morning" if ts.hour < 12 else "afternoon" if ts.hour < 17 else "evening")


@router.get("/groups")
def groups(limit: int = Query(default=40, ge=1, le=200), user: User = Depends(current_user),
           db: Session = Depends(get_db)):
    rows = db.execute(
        select(Transaction.payee_key, Transaction.payee_kind, Transaction.merchant_name, Transaction.description,
               Transaction.amount, Transaction.transaction_date, Transaction.transaction_timestamp,
               Transaction.funding_source)
        .where(Transaction.user_id == user.id, Transaction.category_id.is_(None),
               Transaction.payee_key.is_not(None), Transaction.duplicate_of_id.is_(None),
               Transaction.transaction_type.in_(SORTABLE))).all()
    g: dict[str, dict] = defaultdict(lambda: {"count": 0, "total": Decimal("0"), "amounts": Counter(),
                                              "dates": [], "times": Counter(), "names": Counter(), "kind": None,
                                              "sample": None})
    for key, kind, merchant, desc, amount, d, ts, _f in rows:
        x = g[key]
        x["count"] += 1
        x["total"] += money(amount)
        x["amounts"][money(amount)] += 1
        x["dates"].append(d)
        if ts is not None:
            x["times"][_time_of_day(ts)] += 1
        x["names"][merchant or ""] += 1
        x["kind"] = x["kind"] or kind
        x["sample"] = x["sample"] or desc
    out = []
    for key, x in g.items():
        common_amount, common_n = x["amounts"].most_common(1)[0]
        name = x["names"].most_common(1)[0][0] or None
        out.append({
            "payee_key": key,
            "name": _display_name(name, key),
            "upi_id": key if "@" in key else None,
            "kind": x["kind"],
            "count": x["count"],
            "total": f"{x['total']:.2f}",
            "typical_amount": f"{common_amount:.2f}" if common_n > 1 else None,
            "first_date": min(x["dates"]).isoformat(),
            "last_date": max(x["dates"]).isoformat(),
            "usual_time": x["times"].most_common(1)[0][0] if x["times"] else None,
            "sample": x["sample"],
        })
    # Most useful first: the payees that account for the most money and the most payments.
    out.sort(key=lambda o: (Decimal(o["total"]) * o["count"]), reverse=True)
    remaining_payments = sum(o["count"] for o in out)
    return {"groups": out[:limit], "group_count": len(out), "payment_count": remaining_payments}


class ApplyIn(BaseModel):
    payee_key: str = Field(min_length=1, max_length=160)
    category_id: int
    only_uncategorised: bool = True


@router.post("/apply")
def apply(body: ApplyIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    cat = get_owned(db, Category, body.category_id, user.id, "Category")
    if cat.kind != "expense":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose a spending category.")
    rule = db.scalar(select(PayeeRule).where(PayeeRule.user_id == user.id, PayeeRule.payee_key == body.payee_key))
    if rule:
        rule.category_id = cat.id
    else:
        db.add(PayeeRule(user_id=user.id, payee_key=body.payee_key, category_id=cat.id))
    conds = [Transaction.user_id == user.id, Transaction.payee_key == body.payee_key,
             Transaction.transaction_type.in_(SORTABLE)]
    if body.only_uncategorised:
        conds.append(Transaction.category_id.is_(None))
    changed = db.execute(update(Transaction).where(*conds)
                         .values(category_id=cat.id, is_reviewed=True)).rowcount
    db.commit()
    return {"updated": changed, "category": cat.name}


@router.get("/payee-count")
def payee_count(payee_key: str = Query(min_length=1, max_length=160), user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    """How many of your payments go to this payee (for 'apply to all N' when editing)."""
    from sqlalchemy import func
    n = db.scalar(select(func.count(Transaction.id)).where(
        Transaction.user_id == user.id, Transaction.payee_key == payee_key,
        Transaction.transaction_type.in_(SORTABLE)))
    return {"count": n}
