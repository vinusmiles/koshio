from sqlalchemy.orm import Session

from .models import Account, Category

EXPENSE_CATEGORIES = [
    "Groceries", "Food and restaurants", "Travel", "Fuel", "Shopping", "Clothing and accessories",
    "Electronics", "Utilities",
    "Rent and housing", "Healthcare", "Education", "Entertainment", "Insurance",
    "Investments", "Loan and EMI payments", "Subscriptions", "Personal care",
    "Family expenses", "Miscellaneous",
]
INCOME_CATEGORIES = ["Salary", "Interest and dividends", "Other income"]
TRANSFER_CATEGORIES = ["Transfer between my accounts", "Credit card bill payment"]


def ensure_categories(db: Session, user_id: int) -> None:
    """Add any default categories this user doesn't have yet (for categories added in updates)."""
    have = {n for (n,) in db.query(Category.name).filter(Category.user_id == user_id).all()}
    for kind, names in (("expense", EXPENSE_CATEGORIES), ("income", INCOME_CATEGORIES),
                        ("transfer", TRANSFER_CATEGORIES)):
        db.add_all(Category(user_id=user_id, name=n, kind=kind, is_system=True) for n in names if n not in have)


def seed_new_user(db: Session, user_id: int) -> None:
    for kind, names in (("expense", EXPENSE_CATEGORIES), ("income", INCOME_CATEGORIES),
                        ("transfer", TRANSFER_CATEGORIES)):
        db.add_all(Category(user_id=user_id, name=n, kind=kind, is_system=True) for n in names)
    db.add(Account(user_id=user_id, name="Cash", account_type="cash"))
