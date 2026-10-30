from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Account, Category, Transaction, User
from ..schemas import AccountIn, AccountOut, AccountUpdate, CategoryOut
from ..security import current_user
from ..seed import ensure_categories
from .common import get_owned

router = APIRouter(tags=["accounts"])


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Account).where(Account.user_id == user.id).order_by(Account.name)).all()


@router.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(body: AccountIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    acc = Account(user_id=user.id, **body.model_dump())
    db.add(acc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have an account with this name.")
    return acc


@router.patch("/accounts/{account_id}", response_model=AccountOut)
def update_account(account_id: int, body: AccountUpdate, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    acc = get_owned(db, Account, account_id, user.id, "Account")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(acc, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have an account with this name.")
    return acc


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    acc = get_owned(db, Account, account_id, user.id, "Account")
    in_use = db.scalar(select(exists().where(
        (Transaction.account_id == acc.id) | (Transaction.counterparty_account_id == acc.id))))
    if in_use:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "This account has transactions. Delete or move them first.")
    db.delete(acc)
    db.commit()
    return Response(status_code=204)


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_categories(db, user.id)
    db.commit()
    return db.scalars(select(Category).where(Category.user_id == user.id)
                      .order_by(Category.kind, Category.name)).all()
