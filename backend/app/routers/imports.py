import hashlib
import json
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..importer import classify, engine
from ..importer.pdf import PdfPasswordError
from ..importer.readers import MAX_PDF_BYTES, ReadError, read_statement
from ..periods import today_ist
from ..models import Account, Category, ImportBatch, ImportIssue, Transaction, User
from ..schemas import REQUIRED_DIRECTION, TxnType
from ..security import current_user
from .common import get_owned

router = APIRouter(prefix="/imports", tags=["imports"])

Source = Literal["phonepe", "bhim", "other_upi", "bank", "credit_card", "debit_card", "cash_ledger", "other"]
SOURCE_FROM_ACCOUNT = {"bank": "bank", "credit_card": "credit_card", "debit_card": "debit_card",
                       "cash": "cash_ledger", "upi": "other_upi", "wallet": "other_upi"}
METHOD_FOR = {"credit_card": "credit_card", "debit_card": "debit_card", "cash": "cash", "upi": "upi", "wallet": "upi"}


class OptionsIn(BaseModel):
    header_row: int | None = None
    mapping: dict[str, int | None] | None = None
    date_format: str | None = None
    amount_sign: Literal["negative_is_debit", "positive_is_debit"] | None = None


class Override(BaseModel):
    skip: bool = False
    category_id: int | None = None
    transaction_type: TxnType | None = None


def _parse_json(text: str | None, model, label: str):
    if not text:
        return model() if model is not dict else {}
    try:
        return model.model_validate_json(text) if model is not dict else json.loads(text)
    except (ValidationError, ValueError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"The {label} sent were not valid.")


async def _read_upload(file: UploadFile) -> tuple[bytes, str]:
    data = await file.read(MAX_PDF_BYTES + 1)  # each reader then applies its own limit
    return data, hashlib.sha256(data).hexdigest()


MAX_PASSWORD_TRIES = 20


def _passwords(password: str | None, passwords: str | None) -> list[str]:
    """One typed password, or a JSON list of candidates built on your device from your
    saved name and date of birth. Used only to open the file in memory."""
    out = [password] if password else []
    if passwords:
        try:
            extra = json.loads(passwords)
        except ValueError:
            extra = None
        if not isinstance(extra, list) or not all(isinstance(p, str) and 0 < len(p) <= 128 for p in extra):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The passwords sent were not valid.")
        out += extra
    if len(out) > MAX_PASSWORD_TRIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"At most {MAX_PASSWORD_TRIES} passwords can be tried.")
    return out


def _analyse(db: Session, user: User, acc: Account, filename: str, data: bytes, opts: OptionsIn,
             password: list[str] | None = None):
    try:
        rows, pdf_source, used = read_statement(filename, data, password or None, with_password_index=True)
    except PdfPasswordError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, {"code": e.code, "message": str(e)})
    except ReadError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    existing = set(db.scalars(select(Transaction.fingerprint).where(
        Transaction.user_id == user.id, Transaction.account_id == acc.id,
        Transaction.fingerprint.is_not(None))).all())
    # Your own past choices: the latest category you gave each merchant.
    learned: dict[str, int] = {}
    for merchant, cat in db.execute(
            select(Transaction.merchant_name, Transaction.category_id)
            .where(Transaction.user_id == user.id, Transaction.merchant_name.is_not(None),
                   Transaction.category_id.is_not(None), Transaction.is_reviewed.is_(True))
            .order_by(Transaction.updated_at)).all():
        learned[merchant.lower()] = cat
    cats = dict(db.execute(select(Category.name, Category.id).where(Category.user_id == user.id)).all())
    # UPI references already imported into your other accounts, to spot the same payment twice.
    other_refs = {ref: name for ref, name in db.execute(
        select(Transaction.upi_reference, Account.name).join(Account, Account.id == Transaction.account_id)
        .where(Transaction.user_id == user.id, Transaction.account_id != acc.id,
               Transaction.upi_reference.is_not(None), Transaction.duplicate_of_id.is_(None))).all()}
    result = engine.analyse(rows, filename, engine.Options(**opts.model_dump()), account_id=acc.id,
                            account_type=acc.account_type, today=today_ist(), other_refs=other_refs, existing=existing, learned=learned,
                            categories_by_name=cats)
    if pdf_source:
        result.suggested_source = pdf_source
    elif result.suggested_source == "other" or acc.account_type in ("credit_card", "debit_card", "cash"):
        result.suggested_source = SOURCE_FROM_ACCOUNT.get(acc.account_type, result.suggested_source)
    result.password_index = used
    return result, rows


@router.post("/preview")
async def preview(file: UploadFile = File(...), account_id: int = Form(...), options: str | None = Form(None),
                  password: str | None = Form(None, max_length=128), passwords: str | None = Form(None, max_length=4000),
                  user: User = Depends(current_user), db: Session = Depends(get_db)):
    acc = get_owned(db, Account, account_id, user.id, "Account")
    opts = _parse_json(options, OptionsIn, "column choices")
    tries = _passwords(password, passwords)
    data, file_hash = await _read_upload(file)
    result, rows = _analyse(db, user, acc, file.filename or "", data, opts, tries)
    before = db.scalar(select(ImportBatch).where(ImportBatch.user_id == user.id, ImportBatch.file_hash == file_hash)
                       .order_by(ImportBatch.created_at.desc()))
    out = result.as_dict()
    out["top_rows"] = rows[:40]
    # Which candidate opened the PDF (the website keeps the password itself; it is never sent back).
    out["password_index"] = result.password_index if tries else None  # lets you pick a different heading row
    out["previous_import"] = None if before is None else {
        "id": before.id, "created_at": before.created_at, "records_imported": before.records_imported}
    return out


@router.post("/commit", status_code=201)
async def commit(file: UploadFile = File(...), account_id: int = Form(...), source_provider: Source = Form(...),
                 options: str | None = Form(None), overrides: str | None = Form(None),
                 password: str | None = Form(None, max_length=128), user: User = Depends(current_user), db: Session = Depends(get_db)):
    acc = get_owned(db, Account, account_id, user.id, "Account")
    opts = _parse_json(options, OptionsIn, "column choices")
    raw_over = _parse_json(overrides, dict, "row changes")
    try:
        over = {int(k): Override.model_validate(v) for k, v in raw_over.items()}
    except (ValueError, ValidationError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The row changes sent were not valid.")
    data, file_hash = await _read_upload(file)
    result, _ = _analyse(db, user, acc, file.filename or "", data, opts, _passwords(password, None))
    if result.problems:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, " ".join(result.problems))

    for o in over.values():
        get_owned(db, Category, o.category_id, user.id, "Category")

    batch = ImportBatch(user_id=user.id, account_id=acc.id, filename=(file.filename or "statement")[:255],
                        file_hash=file_hash, file_size=len(data), source_provider=source_provider,
                        mapping=engine.mapping_json(result))
    db.add(batch)
    db.flush()

    method = METHOD_FOR.get(acc.account_type)
    imported = skipped = 0
    for r in result.rows:
        if r.status in ("invalid", "unrecognised"):
            db.add(ImportIssue(batch_id=batch.id, user_id=user.id, row_number=r.row_number, kind=r.status,
                               message=r.message or "", raw=json.dumps(r.raw, ensure_ascii=False)))
            continue
        if r.status != "ready":
            continue
        o = over.get(r.row_number, Override())
        if o.skip:
            skipped += 1
            continue
        ttype = o.transaction_type or r.transaction_type
        required = REQUIRED_DIRECTION[ttype]
        if required and required != r.direction:
            db.rollback()
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                f"Row {r.row_number}: a {ttype} must be money "
                                f"{'out' if required == 'debit' else 'in'}.")
        db.add(Transaction(
            user_id=user.id, transaction_date=r.transaction_date, amount=r.amount, direction=r.direction,
            transaction_type=ttype, source_provider=source_provider,
            payment_method=classify.payment_method_for(
                r.funding_source,
                method or ("upi" if r.upi_reference else "bank_transfer" if acc.account_type == "bank" else "other")),
            funding_source=(r.funding_source or None) and r.funding_source[:120],
            description=r.description, raw_description=r.description,
            merchant_name=r.merchant_name, original_merchant_name=r.merchant_name,
            category_id=o.category_id if "category_id" in o.model_fields_set else r.category_id,
            account_id=acc.id, transaction_reference=r.reference, upi_reference=r.upi_reference,
            fingerprint=r.fingerprint, is_reviewed=False, import_batch_id=batch.id,
        ))
        imported += 1

    counts = result.counts()
    batch.records_detected = counts["detected"]
    batch.records_imported = imported
    batch.records_duplicate = counts["duplicate"]
    batch.records_failed = counts["invalid"]
    batch.records_unrecognised = counts["unrecognised"]
    batch.records_skipped = skipped
    batch.date_from, batch.date_to = result.date_range()
    batch.status = ("nothing_new" if imported == 0 and not counts["invalid"]
                    else "completed_with_issues" if counts["invalid"] else "completed")
    try:
        db.commit()  # all rows or none
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Some of these rows were imported at the same moment by another request. Try again.")
    return _batch_out(batch)


def _batch_out(b: ImportBatch, account_name: str | None = None) -> dict:
    return {k: getattr(b, k) for k in (
        "id", "filename", "source_provider", "status", "account_id", "records_detected", "records_imported",
        "records_duplicate", "records_failed", "records_unrecognised", "records_skipped",
        "date_from", "date_to", "created_at")} | {"account_name": account_name}


@router.get("")
def history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(ImportBatch, Account.name).outerjoin(Account, Account.id == ImportBatch.account_id)
                      .where(ImportBatch.user_id == user.id).order_by(ImportBatch.created_at.desc())).all()
    open_issues = dict(db.execute(select(ImportIssue.batch_id, func.count()).where(
        ImportIssue.user_id == user.id, ImportIssue.resolved.is_(False), ImportIssue.kind == "invalid")
        .group_by(ImportIssue.batch_id)).all())
    return [_batch_out(b, name) | {"open_issues": open_issues.get(b.id, 0)} for b, name in rows]


@router.get("/{batch_id}/issues")
def issues(batch_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    get_owned(db, ImportBatch, batch_id, user.id, "Import")
    rows = db.scalars(select(ImportIssue).where(ImportIssue.batch_id == batch_id)
                      .order_by(ImportIssue.kind, ImportIssue.row_number)).all()
    return [{"id": i.id, "row_number": i.row_number, "kind": i.kind, "message": i.message,
             "raw": json.loads(i.raw), "resolved": i.resolved} for i in rows]


class IssueUpdate(BaseModel):
    resolved: bool


@router.patch("/issues/{issue_id}")
def update_issue(issue_id: int, body: IssueUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    issue = get_owned(db, ImportIssue, issue_id, user.id, "Problem row")
    issue.resolved = body.resolved
    db.commit()
    return {"id": issue.id, "resolved": issue.resolved}


@router.delete("/{batch_id}", status_code=204)
def delete_import(batch_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Removes the import and every transaction it added."""
    batch = get_owned(db, ImportBatch, batch_id, user.id, "Import")
    db.execute(delete(Transaction).where(Transaction.import_batch_id == batch.id, Transaction.user_id == user.id))
    db.delete(batch)
    db.commit()
    return Response(status_code=204)
