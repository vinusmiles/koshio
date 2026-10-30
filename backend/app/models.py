"""Database tables.

Sign convention (important):
  * `amount` is ALWAYS positive (a CHECK constraint enforces it).
  * `direction` says which way money moved for `account_id`:
      "debit"  = money left the account (or was charged to a card)
      "credit" = money came into the account (or a card was paid/credited)
  * `transaction_type` says what the money MEANS, and is what every report uses:
      expense, fee, interest           -> spending
      refund                           -> reduces spending
      income, reimbursement            -> money earned / paid back to you
      transfer, card_payment           -> moving your own money; never spending or income
      adjustment                       -> corrections; ignored by reports
  Reports never look at the sign or direction alone to decide what a row means.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer,
    Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

ACCOUNT_TYPES = ("bank", "credit_card", "debit_card", "upi", "wallet", "cash", "other")
TRANSACTION_TYPES = (
    "expense", "income", "refund", "transfer", "card_payment",
    "fee", "interest", "reimbursement", "adjustment",
)
DIRECTIONS = ("debit", "credit")
PAYMENT_METHODS = ("upi", "credit_card", "debit_card", "bank_transfer", "cash", "other")
SOURCE_PROVIDERS = ("manual", "phonepe", "bhim", "other_upi", "bank", "credit_card", "debit_card", "cash_ledger", "other")
CATEGORY_KINDS = ("expense", "income", "transfer")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    # Ask the AI to suggest categories from merchant names (only works if the server has a key).
    ai_categorise: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_account_user_name"),
        CheckConstraint(_in("account_type", ACCOUNT_TYPES), name="ck_account_type"),
        # Only ever the last four digits of a card or account number.
        CheckConstraint("last4 IS NULL OR length(last4) = 4", name="ck_account_last4"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    account_type: Mapped[str] = mapped_column(String(20))
    institution: Mapped[str | None] = mapped_column(String(80))
    last4: Mapped[str | None] = mapped_column(String(4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_category_user_name"),
        CheckConstraint(_in("kind", CATEGORY_KINDS), name="ck_category_kind"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(10))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)


class ImportBatch(Base):
    """One uploaded statement file. The file itself is never stored, only
    what was read from it."""
    __tablename__ = "import_batches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    filename: Mapped[str] = mapped_column(String(255))
    file_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    file_size: Mapped[int | None] = mapped_column(Integer)
    source_provider: Mapped[str] = mapped_column(String(20))
    # completed | completed_with_issues | nothing_new
    status: Mapped[str] = mapped_column(String(25), default="completed")
    records_detected: Mapped[int] = mapped_column(Integer, default=0)
    records_imported: Mapped[int] = mapped_column(Integer, default=0)
    records_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    records_unrecognised: Mapped[int] = mapped_column(Integer, default=0)
    records_skipped: Mapped[int] = mapped_column(Integer, default=0)
    date_from: Mapped[date | None] = mapped_column(Date)
    date_to: Mapped[date | None] = mapped_column(Date)
    mapping: Mapped[str | None] = mapped_column(Text)  # JSON of the column choices used
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImportIssue(Base):
    """A statement row that was not imported. Kept so nothing is silently lost."""
    __tablename__ = "import_issues"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)  # as seen in the spreadsheet, 1-based
    kind: Mapped[str] = mapped_column(String(15))     # invalid | unrecognised
    message: Mapped[str] = mapped_column(String(300))
    raw: Mapped[str] = mapped_column(Text)            # JSON list of the row's cells
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class PayeeRule(Base):
    """"Payments to this payee are <category>", set by you in Quick sort or when editing.
    Applied to every future import before any other guess."""
    __tablename__ = "payee_rules"
    __table_args__ = (UniqueConstraint("user_id", "payee_key", name="uq_payee_rule"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    payee_key: Mapped[str] = mapped_column(String(160))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AiCategoryCache(Base):
    """The AI's answer for a merchant name, so the same name is never sent twice."""
    __tablename__ = "ai_category_cache"
    __table_args__ = (UniqueConstraint("user_id", "name_key", name="uq_ai_cache"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name_key: Mapped[str] = mapped_column(String(160))
    answer: Mapped[str] = mapped_column(String(60))  # a category name, "Person" or "Unknown"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_txn_amount_positive"),
        CheckConstraint(_in("direction", DIRECTIONS), name="ck_txn_direction"),
        CheckConstraint(_in("transaction_type", TRANSACTION_TYPES), name="ck_txn_type"),
        CheckConstraint(_in("payment_method", PAYMENT_METHODS), name="ck_txn_payment_method"),
        CheckConstraint(_in("source_provider", SOURCE_PROVIDERS), name="ck_txn_source"),
        # Same imported row can never be stored twice for one user (used from Phase 2).
        UniqueConstraint("user_id", "fingerprint", name="uq_txn_user_fingerprint"),
        Index("ix_txn_user_date", "user_id", "transaction_date"),
        Index("ix_txn_user_merchant", "user_id", "merchant_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    transaction_date: Mapped[date] = mapped_column(Date)
    transaction_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    direction: Mapped[str] = mapped_column(String(6))
    transaction_type: Mapped[str] = mapped_column(String(15))
    payment_method: Mapped[str] = mapped_column(String(15))
    source_provider: Mapped[str] = mapped_column(String(15), default="manual")

    # What the user sees and can edit...
    description: Mapped[str | None] = mapped_column(Text)
    merchant_name: Mapped[str | None] = mapped_column(String(120))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), index=True)
    subcategory_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)
    # ...and what the statement originally said, never overwritten.
    raw_description: Mapped[str | None] = mapped_column(Text)
    original_merchant_name: Mapped[str | None] = mapped_column(String(120))

    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"), index=True)
    # For transfers and card payments: the other account of yours involved.
    counterparty_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    card_id: Mapped[int | None] = mapped_column(Integer)  # credit_cards table arrives in Phase 5
    # What actually paid, as the statement shows it: "Axis Bank Ltd. XXXX123456",
    # "AU SFB RUPAY CREDIT CARD 653000XXXXXXXX19", "UPI Lite". Used to match UPI app
    # payments with bank and card statements later.
    funding_source: Mapped[str | None] = mapped_column(String(120))

    transaction_reference: Mapped[str | None] = mapped_column(String(120))
    upi_reference: Mapped[str | None] = mapped_column(String(120))
    original_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"))
    linked_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"))
    # Set when this row was confirmed as a duplicate of another (canonical) row.
    # Reports skip any row where this is set, so a purchase is never counted twice.
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"))
    duplicate_group_id: Mapped[int | None] = mapped_column(Integer)
    fingerprint: Mapped[str | None] = mapped_column(String(64))
    # Who was paid, as a stable key: the UPI ID when the statement shows one, otherwise the
    # merchant name in lower case. Used to group payments and to remember your categories.
    payee_key: Mapped[str | None] = mapped_column(String(160), index=True)
    payee_kind: Mapped[str | None] = mapped_column(String(10))  # shop | person | None (unknown)

    is_reimbursement: Mapped[bool] = mapped_column(Boolean, default=False)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    is_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)

    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id", ondelete="SET NULL"), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    category: Mapped[Category | None] = relationship(foreign_keys=[category_id], lazy="joined")
    account: Mapped[Account | None] = relationship(foreign_keys=[account_id], lazy="joined")

    @property
    def is_transfer(self) -> bool:
        return self.transaction_type in ("transfer", "card_payment")

    @property
    def is_refund(self) -> bool:
        return self.transaction_type == "refund"

    @property
    def origin(self) -> str:
        return "manual" if self.import_batch_id is None else "import"
