"""Core money rules. Numbered tests match section 21 of the Koshio brief."""
from decimal import Decimal

from conftest import add, make_account, summary


def D(x):
    return Decimal(str(x))


def test_4_card_purchase_and_card_repayment_counts_once(client, auth):
    bank = make_account(client, auth, "HDFC Savings", "bank")
    card = make_account(client, auth, "HDFC Card", "credit_card", last4="1234")
    add(client, auth, amount="10000.00", transaction_type="expense",
        payment_method="credit_card", account_id=card, merchant_name="Electronics store")
    add(client, auth, amount="10000.00", transaction_type="card_payment", direction="debit",
        payment_method="bank_transfer", account_id=bank, counterparty_account_id=card)
    s = summary(client, auth)
    assert D(s["total_expenses"]) == D("10000.00")
    assert D(s["net_expenses"]) == D("10000.00")
    assert D(s["net_cash_flow"]) == D("-10000.00")


def test_5_refund_reduces_spending(client, auth):
    add(client, auth, amount="2000", transaction_type="expense", merchant_name="Shop")
    add(client, auth, amount="500", transaction_type="refund", merchant_name="Shop")
    s = summary(client, auth)
    assert D(s["total_expenses"]) == D("2000")
    assert D(s["total_refunds"]) == D("500")
    assert D(s["net_expenses"]) == D("1500")


def test_6_transfer_between_own_accounts_is_neither_expense_nor_income(client, auth):
    a = make_account(client, auth, "SBI", "bank")
    b = make_account(client, auth, "ICICI", "bank")
    add(client, auth, amount="25000", transaction_type="transfer", direction="debit",
        payment_method="bank_transfer", account_id=a, counterparty_account_id=b)
    add(client, auth, amount="25000", transaction_type="transfer", direction="credit",
        payment_method="bank_transfer", account_id=b, counterparty_account_id=a)
    s = summary(client, auth)
    assert D(s["total_expenses"]) == 0 and D(s["total_income"]) == 0
    assert D(s["net_cash_flow"]) == 0
    assert s["transaction_count"] == 2


def test_income_fees_and_net_cash_flow(client, auth):
    add(client, auth, amount="80000", transaction_type="income", payment_method="bank_transfer")
    add(client, auth, amount="1200.50", transaction_type="expense")
    add(client, auth, amount="236", transaction_type="fee", payment_method="credit_card")
    add(client, auth, amount="300", transaction_type="reimbursement")
    s = summary(client, auth)
    assert D(s["total_income"]) == D("80300")
    assert D(s["total_expenses"]) == D("1436.50")
    assert D(s["net_cash_flow"]) == D("78863.50")


def test_paise_are_exact(client, auth):
    for _ in range(10):
        add(client, auth, amount="0.10", transaction_type="expense")
    assert D(summary(client, auth)["total_expenses"]) == D("1.00")


def test_period_boundaries_are_inclusive(client, auth):
    add(client, auth, amount="100", transaction_type="expense", transaction_date="2026-10-01")
    add(client, auth, amount="200", transaction_type="expense", transaction_date="2026-10-31")
    add(client, auth, amount="400", transaction_type="expense", transaction_date="2026-11-01")
    assert D(summary(client, auth)["total_expenses"]) == D("300")


def test_rows_marked_duplicate_are_not_counted(client, auth):
    """Groundwork for test 3 (Phase 4): a confirmed duplicate never inflates totals."""
    from app.db import get_db
    from app.main import app
    from app.models import Transaction
    first = add(client, auth, amount="2000", transaction_type="expense", merchant_name="ABC Supermarket")
    second = add(client, auth, amount="2000", transaction_type="expense", merchant_name="ABC SUPERMARKET")
    db = next(app.dependency_overrides[get_db]())
    db.get(Transaction, second["id"]).duplicate_of_id = first["id"]
    db.commit()
    assert D(summary(client, auth)["total_expenses"]) == D("2000")


def test_11_same_amount_same_day_purchases_are_all_kept(client, auth):
    for _ in range(3):
        add(client, auth, amount="50", transaction_type="expense", merchant_name="Tea stall")
    s = summary(client, auth)
    assert s["transaction_count"] == 3 and D(s["total_expenses"]) == D("150")


def test_unreviewed_count(client, auth):
    add(client, auth, amount="10", transaction_type="expense", is_reviewed=False)
    add(client, auth, amount="10", transaction_type="expense")
    assert summary(client, auth)["unreviewed_count"] == 1


def test_14_card_outstanding_is_always_labelled_estimate(client, auth):
    s = summary(client, auth)
    assert s["credit_card_outstanding"]["amount"] is None
    assert s["credit_card_outstanding"]["is_estimate"] is True

    bank = make_account(client, auth, "Bank", "bank")
    card = make_account(client, auth, "Card", "credit_card")
    add(client, auth, amount="5000", transaction_type="expense", payment_method="credit_card", account_id=card)
    add(client, auth, amount="700", transaction_type="refund", payment_method="credit_card", account_id=card)
    add(client, auth, amount="3000", transaction_type="card_payment", direction="debit",
        payment_method="bank_transfer", account_id=bank, counterparty_account_id=card)
    out = summary(client, auth)["credit_card_outstanding"]
    assert D(out["amount"]) == D("1300")
    assert out["is_estimate"] is True and "estimate" in out["note"].lower()


def test_category_breakdown_nets_refunds(client, auth):
    cats = {c["name"]: c["id"] for c in client.get("/categories", headers=auth).json()}
    g = cats["Groceries"]
    add(client, auth, amount="3000", transaction_type="expense", category_id=g)
    add(client, auth, amount="400", transaction_type="refund", category_id=g)
    add(client, auth, amount="999", transaction_type="expense")
    rows = client.get("/dashboard/categories", headers=auth,
                      params={"preset": "custom", "start": "2026-10-01", "end": "2026-10-31"}).json()
    assert rows[0] == {"category_id": g, "name": "Groceries", "amount": "2600.00"}
    assert rows[1]["name"] == "Uncategorised" and D(rows[1]["amount"]) == D("999")


def test_monthly_series_has_twelve_months(client, auth):
    rows = client.get("/dashboard/monthly", headers=auth).json()
    assert len(rows) == 12
    assert all(D(r["expenses"]) == 0 for r in rows)
