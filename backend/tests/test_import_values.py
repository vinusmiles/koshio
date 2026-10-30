from datetime import date
from decimal import Decimal

import pytest

from app.importer import classify, values


@pytest.mark.parametrize("text,amount,hint", [
    ("1,23,456.78", "123456.78", None), ("₹ 2,000", "2000.00", None), ("Rs. 99.5", "99.50", None),
    ("500.00 Dr", "500.00", "debit"), ("500.00 CR", "500.00", "credit"), ("(250.00)", "-250.00", None),
    ("-1,000", "-1000.00", None), ("1000-", "-1000.00", None), ("INR 75", "75.00", None),
])
def test_amounts(text, amount, hint):
    assert values.parse_amount(text) == (Decimal(amount), hint)


@pytest.mark.parametrize("text", ["", "-", "0.00", "  "])
def test_empty_amounts(text):
    assert values.parse_amount(text) == (None, None)


def test_bad_amount_raises():
    with pytest.raises(ValueError):
        values.parse_amount("12abc")


def test_date_detection():
    today = date(2026, 10, 24)
    assert values.detect_date_format(["31/10/2026", "01/10/2026"], today)[0] == "DD/MM/YYYY"
    assert values.detect_date_format(["10/21/2026"], today)[0] == "MM/DD/YYYY"
    fmt, opts = values.detect_date_format(["04/05/2026"], today)
    assert values.is_ambiguous(opts)
    assert values.parse_date("05-Oct-26", "DD MMM YY") == date(2026, 10, 5)
    assert values.parse_date("2026-10-05T09:15:00", "YYYY-MM-DD") == date(2026, 10, 5)
    assert values.split_time("05/10/2026 02:15 PM") == ("05/10/2026", "14:15:00")


@pytest.mark.parametrize("text,name,ref", [
    ("UPI/DR/427700001111/ZEPTO MARKETPLACE/YESB/zepto@ybl/order", "Zepto Marketplace", "427700001111"),
    ("UPI-SWIGGY-swiggy@icici-ICIC0DC0099-427798765432-Order", "Swiggy", "427798765432"),
    ("UPI/427712341234/Payment from Ph/zomato@hdfcbank/HDFC BANK", "Zomato", "427712341234"),
    ("NEFT CR-ICIC0000001-ONEBEAT", None, None),
])
def test_upi_narrations(text, name, ref):
    assert classify.extract_upi(text) == (name, ref)


def test_type_guesses():
    assert classify.guess_type("debit", "NWD-XXXX-ATM", "bank") == "transfer"
    assert classify.guess_type("debit", "CRED CLUB CREDIT CARD BILL", "bank") == "card_payment"
    assert classify.guess_type("credit", "PAYMENT RECEIVED THANK YOU", "credit_card") == "card_payment"
    assert classify.guess_type("credit", "MERCHANT REVERSAL", "credit_card") == "refund"
    assert classify.guess_type("debit", "ANNUAL FEE", "credit_card") == "fee"
    assert classify.guess_type("debit", "UPI-SWIGGY", "bank") == "expense"
    assert classify.guess_type("credit", "SALARY", "bank") == "income"
