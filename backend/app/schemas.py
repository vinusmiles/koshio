from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

TxnType = Literal["expense", "income", "refund", "transfer", "card_payment",
                  "fee", "interest", "reimbursement", "adjustment"]
Direction = Literal["debit", "credit"]
PaymentMethod = Literal["upi", "credit_card", "debit_card", "bank_transfer", "cash", "other"]
AccountType = Literal["bank", "credit_card", "debit_card", "upi", "wallet", "cash", "other"]

# Which way the money must move for each meaning. None = either way is valid.
REQUIRED_DIRECTION: dict[str, str | None] = {
    "expense": "debit", "fee": "debit", "interest": "debit",
    "income": "credit", "refund": "credit", "reimbursement": "credit",
    "transfer": None, "card_payment": None, "adjustment": None,
}
MAX_AMOUNT = Decimal("999999999999.99")


# ---------- auth ----------
class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str


# ---------- accounts & categories ----------
def only_last_four(v: str | None) -> str | None:
    if v in (None, ""):
        return None
    if not (len(v) == 4 and v.isdigit()):
        raise ValueError("Enter only the last 4 digits. Never enter a full card or account number.")
    return v


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    account_type: AccountType
    institution: str | None = Field(default=None, max_length=80)
    last4: str | None = None

    @field_validator("last4")
    @classmethod
    def _last4(cls, v: str | None) -> str | None:
        return only_last_four(v)


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    institution: str | None = Field(default=None, max_length=80)
    last4: str | None = None

    @field_validator("last4")
    @classmethod
    def _last4(cls, v: str | None) -> str | None:
        return only_last_four(v)


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    account_type: str
    institution: str | None
    last4: str | None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    kind: str
    parent_id: int | None


# ---------- transactions ----------
class TransactionBase(BaseModel):
    transaction_date: date
    amount: Decimal = Field(gt=0, le=MAX_AMOUNT, decimal_places=2)
    transaction_type: TxnType
    direction: Direction | None = None  # filled in from the type when it is obvious
    payment_method: PaymentMethod
    merchant_name: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    category_id: int | None = None
    account_id: int | None = None
    counterparty_account_id: int | None = None
    notes: str | None = Field(default=None, max_length=2000)
    is_reviewed: bool = True  # things you type yourself are already reviewed


class TransactionCreate(TransactionBase):
    @model_validator(mode="after")
    def check_direction(self):
        required = REQUIRED_DIRECTION[self.transaction_type]
        if self.direction is None:
            if required is None:
                raise ValueError("Choose whether money went out or came in for this transfer.")
            self.direction = required
        elif required and self.direction != required:
            raise ValueError(f"A {self.transaction_type} must be a {required}.")
        if self.counterparty_account_id is not None and self.counterparty_account_id == self.account_id:
            raise ValueError("A transfer needs two different accounts.")
        return self


class TransactionUpdate(BaseModel):
    """Every field optional; the merged result is re-validated in the router."""
    transaction_date: date | None = None
    amount: Decimal | None = Field(default=None, gt=0, le=MAX_AMOUNT, decimal_places=2)
    transaction_type: TxnType | None = None
    direction: Direction | None = None
    payment_method: PaymentMethod | None = None
    merchant_name: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    category_id: int | None = None
    account_id: int | None = None
    counterparty_account_id: int | None = None
    notes: str | None = Field(default=None, max_length=2000)
    is_reviewed: bool | None = None


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    transaction_date: date
    amount: Decimal
    currency: str
    direction: str
    transaction_type: str
    payment_method: str
    source_provider: str
    origin: str
    merchant_name: str | None
    original_merchant_name: str | None
    description: str | None
    raw_description: str | None
    category_id: int | None
    category_name: str | None = None
    account_id: int | None
    account_name: str | None = None
    counterparty_account_id: int | None
    funding_source: str | None = None
    payee_key: str | None = None
    payee_kind: str | None = None
    notes: str | None
    is_transfer: bool
    is_refund: bool
    is_reviewed: bool
    import_batch_id: int | None
    created_at: datetime
    updated_at: datetime


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int
    page: int
    page_size: int


# ---------- dashboard ----------
class Period(BaseModel):
    preset: str
    start: date
    end: date
    label: str


class CardOutstanding(BaseModel):
    amount: Decimal | None
    is_estimate: bool
    note: str


class Summary(BaseModel):
    period: Period
    total_expenses: Decimal      # expenses + fees + interest, before refunds
    total_refunds: Decimal
    net_expenses: Decimal        # total_expenses - total_refunds
    total_income: Decimal        # income + reimbursements
    net_cash_flow: Decimal       # total_income - net_expenses
    transaction_count: int
    unreviewed_count: int
    credit_card_outstanding: CardOutstanding


class MonthPoint(BaseModel):
    month: str  # YYYY-MM
    expenses: Decimal  # net of refunds
    income: Decimal


class CategoryPoint(BaseModel):
    category_id: int | None
    name: str
    amount: Decimal
