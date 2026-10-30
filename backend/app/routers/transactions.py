from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Account, Category, Transaction, User
from ..schemas import (REQUIRED_DIRECTION, TransactionCreate, TransactionOut, TransactionPage,
                       TransactionUpdate, TxnType)
from ..security import current_user
from .common import get_owned

router = APIRouter(prefix="/transactions", tags=["transactions"])

EDITABLE = ("transaction_date", "amount", "transaction_type", "direction", "payment_method",
            "merchant_name", "description", "category_id", "account_id",
            "counterparty_account_id", "notes", "is_reviewed")


def to_out(t: Transaction) -> TransactionOut:
    out = TransactionOut.model_validate(t)
    out.category_name = t.category.name if t.category else None
    out.account_name = t.account.name if t.account else None
    return out


def _check_links(db: Session, user_id: int, data: dict) -> None:
    get_owned(db, Category, data.get("category_id"), user_id, "Category")
    get_owned(db, Account, data.get("account_id"), user_id, "Account")
    get_owned(db, Account, data.get("counterparty_account_id"), user_id, "Account")


def _clean(data: dict) -> dict:
    for k in ("merchant_name", "description", "notes"):
        if isinstance(data.get(k), str):
            data[k] = data[k].strip() or None
    return data


@router.get("", response_model=TransactionPage)
def list_transactions(
    user: User = Depends(current_user), db: Session = Depends(get_db),
    start: date | None = None, end: date | None = None,
    transaction_type: list[TxnType] | None = Query(default=None),
    category_id: int | None = None, account_id: int | None = None,
    q: str | None = Query(default=None, max_length=100),
    uncategorised: bool = False, unreviewed: bool = False,
    sort: Literal["date_desc", "date_asc", "amount_desc", "amount_asc"] = "date_desc",
    page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=200),
):
    conds = [Transaction.user_id == user.id]
    if start:
        conds.append(Transaction.transaction_date >= start)
    if end:
        conds.append(Transaction.transaction_date <= end)
    if transaction_type:
        conds.append(Transaction.transaction_type.in_(transaction_type))
    if category_id is not None:
        conds.append(Transaction.category_id == category_id)
    if account_id is not None:
        conds.append(or_(Transaction.account_id == account_id,
                         Transaction.counterparty_account_id == account_id))
    if uncategorised:
        conds.append(Transaction.category_id.is_(None))
    if unreviewed:
        conds.append(Transaction.is_reviewed.is_(False))
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        conds.append(or_(func.lower(Transaction.merchant_name).like(like),
                         func.lower(Transaction.description).like(like),
                         func.lower(Transaction.notes).like(like)))
    order = {
        "date_desc": (Transaction.transaction_date.desc(), Transaction.id.desc()),
        "date_asc": (Transaction.transaction_date.asc(), Transaction.id.asc()),
        "amount_desc": (Transaction.amount.desc(), Transaction.id.desc()),
        "amount_asc": (Transaction.amount.asc(), Transaction.id.asc()),
    }[sort]
    total = db.scalar(select(func.count(Transaction.id)).where(*conds))
    rows = db.scalars(select(Transaction).where(*conds).order_by(*order)
                      .offset((page - 1) * page_size).limit(page_size)).unique().all()
    return TransactionPage(items=[to_out(t) for t in rows], total=total, page=page, page_size=page_size)


@router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(body: TransactionCreate, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    data = _clean(body.model_dump())
    _check_links(db, user.id, data)
    txn = Transaction(user_id=user.id, source_provider="manual", **data)
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return to_out(txn)


@router.get("/{txn_id}", response_model=TransactionOut)
def get_transaction(txn_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return to_out(get_owned(db, Transaction, txn_id, user.id, "Transaction"))


@router.patch("/{txn_id}", response_model=TransactionOut)
def update_transaction(txn_id: int, body: TransactionUpdate, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    txn = get_owned(db, Transaction, txn_id, user.id, "Transaction")
    changes = body.model_dump(exclude_unset=True)
    merged = {k: getattr(txn, k) for k in EDITABLE} | changes
    # Changing the meaning without saying the direction: use the natural one.
    if "transaction_type" in changes and "direction" not in changes \
            and REQUIRED_DIRECTION[changes["transaction_type"]] is not None:
        merged["direction"] = None
    try:
        validated = _clean(TransactionCreate(**merged).model_dump())
    except ValidationError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            [{"msg": err["msg"], "loc": err["loc"]} for err in e.errors()])
    _check_links(db, user.id, validated)
    for k in EDITABLE:
        setattr(txn, k, validated[k])
    db.commit()
    db.refresh(txn)
    return to_out(txn)


@router.delete("/{txn_id}", status_code=204)
def delete_transaction(txn_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    txn = get_owned(db, Transaction, txn_id, user.id, "Transaction")
    db.delete(txn)
    db.commit()
    return Response(status_code=204)
