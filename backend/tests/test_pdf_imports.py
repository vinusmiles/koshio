"""PDF statements: UPI apps, password-protected cards, banks."""
import json
from decimal import Decimal
from pathlib import Path

from conftest import make_account, summary
import samples

FIX = Path(__file__).parent / "fixtures"


def pdf(name):
    return (FIX / name).read_bytes()


def preview(client, auth, acc, name, password=None):
    data = {"account_id": acc}
    if password is not None:
        data["password"] = password
    return client.post("/imports/preview", headers=auth, data=data, files={"file": (name, pdf(name))})


def commit(client, auth, acc, name, source, password=None, file_bytes=None, filename=None):
    data = {"account_id": acc, "source_provider": source}
    if password is not None:
        data["password"] = password
    return client.post("/imports/commit", headers=auth, data=data,
                       files={"file": (filename or name, file_bytes or pdf(name))})


def cat_names(client, auth):
    return {c["id"]: c["name"] for c in client.get("/categories", headers=auth).json()}


def test_phonepe_statement(client, auth):
    """Built from the real PhonePe layout (names and numbers invented)."""
    acc = make_account(client, auth, "PhonePe", "upi")
    p = preview(client, auth, acc, "phonepe.pdf").json()
    assert p["suggested_source"] == "phonepe" and p["problems"] == []
    assert p["counts"] == {"detected": 11, "ready": 10, "duplicate": 0, "invalid": 0, "unrecognised": 1}
    rows = {r["merchant_name"] or r["description"]: r for r in p["rows"] if r["status"] == "ready"}
    names = cat_names(client, auth)
    swiggy = rows["Swiggy"]
    assert (swiggy["amount"], swiggy["direction"], swiggy["upi_reference"]) == ("640.00", "debit", "427798765432")
    assert swiggy["transaction_date"] == "2026-10-05" and swiggy["time"] == "19:32:00"
    assert swiggy["funding_source"] == "XXXX123456"
    assert names[swiggy["category_id"]] == "Food and restaurants"
    assert rows["Ravi Kumar"]["direction"] == "credit" and rows["Ravi Kumar"]["transaction_type"] == "income"
    assert rows["Zepto Marketplace Private Limited"]["amount"] == "1234.50"
    assert rows["Asha Verma"]["transaction_type"] == "expense"                      # "Requested by" collect request
    assert rows["Add money UPI Lite"]["transaction_type"] == "transfer"            # topping up UPI Lite isn't spending
    assert rows["Xxxxxxxxxx55"]["transaction_type"] == "transfer"                  # "Transfer to XXXXXXXXXX55"
    assert rows["Xxxxxxxxxx55"]["transaction_date"] == "2026-09-30"                # "Sept 30, 2026"
    assert names[rows["FASTag Recharge for TS00AB0000"]["category_id"]] == "Travel"
    roppen = rows["Roppen Transportation Services Private Limited"]                # name wrapped onto a 2nd line
    assert roppen["amount"] == "35.00" and roppen["funding_source"] == "UPI Lite"
    failed = next(r for r in p["rows"] if r["status"] == "unrecognised")
    assert "Not a completed payment" in failed["message"]
    r = commit(client, auth, acc, "phonepe.pdf", "phonepe").json()
    assert r["records_imported"] == 10
    items = {t["merchant_name"]: t for t in client.get("/transactions", headers=auth).json()["items"]}
    assert items["Swiggy"]["payment_method"] == "upi" and items["Swiggy"]["source_provider"] == "phonepe"
    # A masked card number as the payer means a RuPay credit card was used over UPI.
    assert items["Zepto Marketplace Private Limited"]["payment_method"] == "credit_card"
    assert items["Zepto Marketplace Private Limited"]["funding_source"] == "652111XXXXXXXX77"


def test_bhim_statement(client, auth):
    """Built from the real BHIM layout (names and numbers invented)."""
    acc = make_account(client, auth, "BHIM", "upi")
    p = preview(client, auth, acc, "bhim.pdf").json()
    assert p["suggested_source"] == "bhim"
    assert p["counts"] == {"detected": 10, "ready": 9, "duplicate": 0, "invalid": 0, "unrecognised": 1}
    ready = [r for r in p["rows"] if r["status"] == "ready"]
    assert ready[0]["merchant_name"] == "MART (xxxxx11111@ybl)" and ready[0]["time"] == "06:46:48"
    assert ready[1]["funding_source"] == "AXIS BANK RUPAY CREDIT CARD 652111XXXXXXXX77"
    assert ready[2]["transaction_type"] == "transfer"          # to your own UPI ID
    assert {r["amount"] for r in ready} >= {"90.00", "15.00"}   # two rows run together on one line
    names = cat_names(client, auth)
    upstox = next(r for r in ready if "pstox" in (r["merchant_name"] or ""))
    assert names[upstox["category_id"]] == "Investments"
    # Receiver hidden: from a bank account it's a credit card bill; from a card it's another bill.
    card_bill = next(r for r in ready if r["amount"] == "638.39")
    assert card_bill["transaction_type"] == "card_payment"
    assert names[card_bill["category_id"]] == "Credit card bill payment"
    other_bill = next(r for r in ready if r["amount"] == "500.00")
    assert other_bill["transaction_type"] == "expense"
    cashback = next(r for r in ready if r["direction"] == "credit")
    assert cashback["transaction_type"] == "refund" and cashback["amount"] == "37.00"
    b = commit(client, auth, acc, "bhim.pdf", "bhim").json()
    assert b["records_imported"] == 9
    methods = {t["amount"]: t["payment_method"] for t in client.get("/transactions", headers=auth).json()["items"]}
    assert methods["70.00"] == "credit_card" and methods["50.00"] == "upi"


def test_google_pay_statement(client, auth):
    acc = make_account(client, auth, "Google Pay", "upi")
    p = preview(client, auth, acc, "gpay.pdf").json()
    assert p["suggested_source"] == "other_upi" and p["counts"]["ready"] == 3
    assert [r["merchant_name"] for r in p["rows"]] == ["Swiggy", "Ravi Kumar", "Tsspdcl"]
    assert [r["direction"] for r in p["rows"]] == ["debit", "credit", "debit"]


def test_card_pdf_needs_its_password(client, auth):
    card = make_account(client, auth, "HDFC Card", "credit_card")
    r = preview(client, auth, card, "card_hdfc.pdf")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "pdf_password_required"
    r = preview(client, auth, card, "card_hdfc.pdf", password="WRONG123")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "pdf_password_wrong"
    p = preview(client, auth, card, "card_hdfc.pdf", password="ASHA0503").json()
    assert p["suggested_source"] == "credit_card" and p["counts"]["ready"] == 7
    types = [r["transaction_type"] for r in p["rows"]]
    assert types == ["expense", "expense", "card_payment", "refund", "expense", "fee", "fee"]
    assert p["rows"][0]["merchant_name"] == "Amazon Pay India Pvt Ltd Bangalore"
    assert p["rows"][4]["time"] == "19:32:00"
    # Summary lines (due date, total due, credit limit) are not taken as transactions.
    assert all(r["amount"] not in ("6148.00", "310.00", "200000.00") for r in p["rows"])
    b = commit(client, auth, card, "card_hdfc.pdf", "credit_card", password="ASHA0503").json()
    assert b["records_imported"] == 7
    s = summary(client, auth)
    assert Decimal(s["total_expenses"]) == Decimal("6238.00")  # 1899+3100+649+500+90
    assert Decimal(s["total_refunds"]) == Decimal("499.00")
    # The password is never stored anywhere.
    hist = json.dumps(client.get("/imports", headers=auth).json())
    issues = json.dumps(client.get(f"/imports/{b['id']}/issues", headers=auth).json())
    assert "ASHA0503" not in hist + issues


def test_bank_pdf_uses_running_balance_for_direction(client, auth):
    acc = make_account(client, auth, "SBI", "bank")
    p = preview(client, auth, acc, "bank_sbi.pdf").json()
    assert p["suggested_source"] == "bank" and p["counts"]["ready"] == 4
    r = p["rows"]
    assert [x["direction"] for x in r] == ["debit", "credit", "debit", "credit"]
    assert r[0]["merchant_name"] == "Zepto Marketplace" and r[0]["upi_reference"] == "427700001111"
    assert r[2]["transaction_type"] == "transfer" and r[3]["transaction_type"] == "income"


def test_same_upi_payment_from_bank_and_phonepe_is_not_counted_twice(client, auth):
    bank = make_account(client, auth, "HDFC Savings", "bank")
    upi = make_account(client, auth, "PhonePe", "upi")
    client.post("/imports/commit", headers=auth, data={"account_id": bank, "source_provider": "bank"},
                files={"file": ("hdfc.csv", samples.hdfc_csv())})
    before = Decimal(summary(client, auth)["total_expenses"])
    p = preview(client, auth, upi, "phonepe.pdf").json()
    dupes = [r for r in p["rows"] if r["status"] == "duplicate"]
    # Swiggy and the first Chai Point carry the same UPI references as the bank statement.
    assert {r["upi_reference"] for r in dupes} == {"427798765432", "428399887766"}
    assert "HDFC Savings" in dupes[0]["message"]
    commit(client, auth, upi, "phonepe.pdf", "phonepe")
    after = Decimal(summary(client, auth)["total_expenses"])
    # Only the payments not already in the bank statement are added:
    # Zepto 1234.50 + second Chai Point 50 + Asha 450 + FASTag 1000 + Roppen 35. Top-ups and transfers don't count.
    assert after - before == Decimal("2769.50")


def test_reimporting_a_pdf_adds_nothing(client, auth):
    acc = make_account(client, auth, "PhonePe", "upi")
    commit(client, auth, acc, "phonepe.pdf", "phonepe")
    r = commit(client, auth, acc, "phonepe.pdf", "phonepe").json()
    assert r["records_imported"] == 0 and r["records_duplicate"] == 10


def test_scanned_and_fake_pdfs_get_clear_messages(client, auth):
    acc = make_account(client, auth, "Bank", "bank")
    r = preview(client, auth, acc, "scanned.pdf")
    assert r.status_code == 400 and "no text" in r.json()["detail"] and "original file" in r.json()["detail"]
    r = client.post("/imports/preview", headers=auth, data={"account_id": acc},
                    files={"file": ("statement.pdf", b"hello, not a pdf")})
    assert r.status_code == 400 and "isn't a PDF" in r.json()["detail"]
    r = client.post("/imports/preview", headers=auth, data={"account_id": acc},
                    files={"file": ("statement.pdf", b"%PDF-1.7 broken")})
    assert r.status_code == 400 and "couldn't be opened" in r.json()["detail"]


def test_axis_card_statement_with_cashback_column(client, auth):
    """Built from the real Axis ACE layout (details invented). The amount is the first
    Dr/Cr number; the 'Cashback earned' column after it must be ignored."""
    card = make_account(client, auth, "Axis ACE", "credit_card")
    p = preview(client, auth, card, "card_axis.pdf", password="TEST1234").json()
    assert p["counts"]["ready"] == 7 and p["counts"]["invalid"] == 0
    got = [(r["amount"], r["direction"], r["transaction_type"]) for r in p["rows"]]
    assert got == [
        ("550.00", "debit", "interest"),        # EMI interest
        ("99.00", "debit", "fee"),              # GST
        ("12000.00", "debit", "expense"),       # EMI principal
        ("450.00", "debit", "expense"),         # not the 18.00 cashback beside it
        ("15000.00", "credit", "card_payment"), # BBPS payment received
        ("5000.00", "credit", "card_payment"),
        ("300.00", "credit", "refund"),         # cashback credit
    ]
    names = cat_names(client, auth)
    # The card prints the merchant category (ELECTRONICS), so the EMI counts as Electronics spending.
    assert names[p["rows"][2]["category_id"]] == "Electronics"
    commit(client, auth, card, "card_axis.pdf", "credit_card", password="TEST1234")
    s = summary(client, auth, start="2026-09-01", end="2026-09-30")
    assert Decimal(s["total_expenses"]) == Decimal("13099.00")  # 550 + 99 + 12000 + 450
    assert Decimal(s["total_refunds"]) == Decimal("300.00")


def test_candidate_passwords_are_tried_in_memory(client, auth):
    """The website can send its guesses (built on the device from a saved name and date
    of birth); the server tries each one and reports which worked, never echoing it."""
    card = make_account(client, auth, "HDFC Card", "credit_card")
    guesses = ["asha0503", "05031990", "ASHA0503", "050319901111"]
    r = client.post("/imports/preview", headers=auth, files={"file": ("card_hdfc.pdf", pdf("card_hdfc.pdf"))},
                    data={"account_id": card, "passwords": json.dumps(guesses)})
    assert r.status_code == 200, r.text
    assert r.json()["password_index"] == 2 and r.json()["counts"]["ready"] == 7
    assert "ASHA0503" not in r.text
    # None of the guesses work: the website then asks you to type it.
    r = client.post("/imports/preview", headers=auth, files={"file": ("card_hdfc.pdf", pdf("card_hdfc.pdf"))},
                    data={"account_id": card, "passwords": json.dumps(["nope1234", "NOPE1234"])})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "pdf_password_wrong"
    # A typed password is tried first, then the guesses.
    r = client.post("/imports/preview", headers=auth, files={"file": ("card_hdfc.pdf", pdf("card_hdfc.pdf"))},
                    data={"account_id": card, "password": "ASHA0503", "passwords": json.dumps(["x1234567"])})
    assert r.json()["password_index"] == 0
    # Limits.
    r = client.post("/imports/preview", headers=auth, files={"file": ("card_hdfc.pdf", pdf("card_hdfc.pdf"))},
                    data={"account_id": card, "passwords": json.dumps([f"p{i:07d}" for i in range(21)])})
    assert r.status_code == 422
    r = client.post("/imports/preview", headers=auth, files={"file": ("card_hdfc.pdf", pdf("card_hdfc.pdf"))},
                    data={"account_id": card, "passwords": "not json"})
    assert r.status_code == 422
    # Unlocked PDFs ignore guesses.
    upi = make_account(client, auth, "PhonePe", "upi")
    r = client.post("/imports/preview", headers=auth, files={"file": ("phonepe.pdf", pdf("phonepe.pdf"))},
                    data={"account_id": upi, "passwords": json.dumps(["ASHA0503"])})
    assert r.status_code == 200 and r.json()["password_index"] == 0
