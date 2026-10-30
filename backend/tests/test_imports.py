"""Statement import. Numbered tests match section 21 of the Koshio brief."""
import json
from decimal import Decimal

from conftest import add, make_account, register, summary
import samples


def preview(client, auth, account_id, data, name="statement.csv", **options):
    r = client.post("/imports/preview", headers=auth, data={"account_id": account_id, "options": json.dumps(options)},
                    files={"file": (name, data)})
    return r


def commit(client, auth, account_id, data, name="statement.csv", source="bank", overrides=None, **options):
    return client.post("/imports/commit", headers=auth, files={"file": (name, data)}, data={
        "account_id": account_id, "source_provider": source, "options": json.dumps(options),
        "overrides": json.dumps(overrides or {})})


def test_1_hundred_valid_rows_are_stored(client, auth):
    acc = make_account(client, auth, "Bank", "bank")
    r = commit(client, auth, acc, samples.many_rows(100))
    assert r.status_code == 201, r.text
    assert r.json()["records_imported"] == 100
    assert client.get("/transactions", headers=auth).json()["total"] == 100


def test_2_importing_the_same_statement_twice_adds_nothing(client, auth):
    acc = make_account(client, auth, "HDFC", "bank")
    first = commit(client, auth, acc, samples.hdfc_csv()).json()
    assert first["records_imported"] == 9
    p = preview(client, auth, acc, samples.hdfc_csv()).json()
    assert p["counts"]["duplicate"] == 9 and p["counts"]["ready"] == 0
    assert p["previous_import"]["id"] == first["id"]
    second = commit(client, auth, acc, samples.hdfc_csv()).json()
    assert second["records_imported"] == 0 and second["records_duplicate"] == 9
    assert second["status"] == "nothing_new"
    assert client.get("/transactions", headers=auth).json()["total"] == 9


def test_overlapping_statements_only_add_new_rows(client, auth):
    acc = make_account(client, auth, "Bank", "bank")
    sept = samples.signed_csv([("2026-09-28", "Rent", "-18000"), ("2026-09-30", "Tea", "-50")])
    both = samples.signed_csv([("2026-09-30", "Tea", "-50"), ("2026-10-02", "Fuel", "-3000")])
    commit(client, auth, acc, sept)
    r = commit(client, auth, acc, both).json()
    assert r["records_imported"] == 1 and r["records_duplicate"] == 1


def test_same_statement_into_another_account_is_not_a_duplicate(client, auth):
    a = make_account(client, auth, "A", "bank")
    b = make_account(client, auth, "B", "bank")
    commit(client, auth, a, samples.many_rows(3))
    assert commit(client, auth, b, samples.many_rows(3)).json()["records_imported"] == 3


def test_7_dates_in_different_formats(client, auth):
    acc = make_account(client, auth, "Bank", "bank")
    for data, expected in [
        (samples.signed_csv([("15/10/2026", "x", "-1"), ("31/10/2026", "y", "-1")]), "2026-10-15"),
        (samples.signed_csv([("2026-10-15", "x", "-1")]), "2026-10-15"),
        (samples.signed_csv([("15-Oct-2026", "x", "-1")]), "2026-10-15"),
        (samples.signed_csv([("15 Oct 26", "x", "-1")]), "2026-10-15"),
        (samples.signed_csv([("15/10/2026 14:32:10", "x", "-1")]), "2026-10-15"),
    ]:
        p = preview(client, auth, acc, data).json()
        assert p["rows"][0]["transaction_date"] == expected, (data, p["date_format"])


def test_7_ambiguous_dates_must_be_chosen(client, auth):
    acc = make_account(client, auth, "Bank", "bank")
    data = samples.signed_csv([("04/05/2026", "x", "-10"), ("06/07/2026", "y", "-20")])
    p = preview(client, auth, acc, data).json()
    assert p["date_format_ambiguous"] is True
    assert {"DD/MM/YYYY", "MM/DD/YYYY"} <= set(p["date_format_options"])
    r = commit(client, auth, acc, data)
    assert r.status_code == 422 and "date format" in r.json()["detail"]
    p = preview(client, auth, acc, data, date_format="MM/DD/YYYY").json()
    assert p["date_format_ambiguous"] is False and p["rows"][0]["transaction_date"] == "2026-04-05"
    assert commit(client, auth, acc, data, date_format="DD/MM/YYYY").status_code == 201
    dates = [t["transaction_date"] for t in client.get("/transactions", headers=auth).json()["items"]]
    assert sorted(dates) == ["2026-05-04", "2026-07-06"]


def test_7_future_dates_settle_the_format(client, auth):
    acc = make_account(client, auth, "Bank", "bank")
    # Read month-first, 10/12/2026 would be 12 Oct (past); day-first it's 10 Dec (future, impossible).
    data = samples.signed_csv([("09/12/2026", "x", "-1"), ("10/12/2026", "y", "-1")])
    p = preview(client, auth, acc, data).json()
    assert p["date_format"] == "MM/DD/YYYY" and p["date_format_ambiguous"] is False


def test_8_invalid_rows_are_reported_and_kept_not_lost(client, auth):
    acc = make_account(client, auth, "Bank", "bank")
    data = samples.signed_csv([
        ("21/10/2026", "Good one", "-100"),
        ("32/13/2026", "Bad date", "-50"),
        ("02/10/2026", "Bad amount", "-12abc"),
        ("03/10/2026", "No amount", ""),
        ("04/10/2026", "Good two", "200"),
        ("Total", "", "-150"),
    ])
    p = preview(client, auth, acc, data).json()
    assert p["counts"] == {"detected": 6, "ready": 2, "duplicate": 0, "invalid": 3, "unrecognised": 1}
    msgs = {r["row_number"]: r["message"] for r in p["rows"] if r["status"] != "ready"}
    assert "Date" in msgs[3] and "Amount" in msgs[4] and "No amount" in msgs[5]
    res = commit(client, auth, acc, data).json()
    assert res["records_imported"] == 2 and res["records_failed"] == 3 and res["status"] == "completed_with_issues"
    issues = client.get(f"/imports/{res['id']}/issues", headers=auth).json()
    assert len(issues) == 4 and issues[0]["raw"][1] == "Bad date"
    hist = client.get("/imports", headers=auth).json()[0]
    assert hist["open_issues"] == 3
    client.patch(f"/imports/issues/{issues[0]['id']}", headers=auth, json={"resolved": True})
    assert client.get("/imports", headers=auth).json()[0]["open_issues"] == 2


def test_11_identical_purchases_on_one_day_are_all_kept(client, auth):
    acc = make_account(client, auth, "Bank", "bank")
    data = samples.signed_csv([("15/10/2026", "TEA STALL", "-20")] * 3)
    r = commit(client, auth, acc, data).json()
    assert r["records_imported"] == 3 and r["records_duplicate"] == 0
    # ...and importing again still doesn't double them
    assert commit(client, auth, acc, data).json()["records_duplicate"] == 3
    assert Decimal(summary(client, auth)["total_expenses"]) == Decimal("60")


def test_13_unsupported_files_get_a_clear_message(client, auth):
    acc = make_account(client, auth, "Bank", "bank")
    r = preview(client, auth, acc, b"hello", name="notes.docx")
    assert r.status_code == 400 and "PDF, CSV and Excel" in r.json()["detail"]
    r = preview(client, auth, acc, b"<OFX>", name="statement.ofx")
    assert r.status_code == 400 and "aren't supported yet" in r.json()["detail"]
    r = preview(client, auth, acc, b"not really excel", name="fake.xlsx")
    assert r.status_code == 400 and "isn't an Excel" in r.json()["detail"]
    r = preview(client, auth, acc, b"", name="empty.csv")
    assert r.status_code == 400 and "empty" in r.json()["detail"]


def test_hdfc_statement_is_read_correctly(client, auth):
    acc = make_account(client, auth, "HDFC", "bank")
    p = preview(client, auth, acc, samples.hdfc_csv()).json()
    assert p["columns"][1] == "Narration" and p["header_row"] == 4
    assert p["counts"] == {"detected": 12, "ready": 9, "duplicate": 0, "invalid": 0, "unrecognised": 3}
    assert p["suggested_source"] == "bank" and p["date_from"] == "2026-10-01" and p["date_to"] == "2026-10-22"
    rows = {r["row_number"]: r for r in p["rows"]}
    assert rows[6]["transaction_type"] == "income" and rows[6]["amount"] == "92000.00"
    assert rows[7]["merchant_name"] == "Ratnadeep Super Market" and rows[7]["upi_reference"] == "427612345678"
    assert rows[8]["merchant_name"] == "Swiggy" and rows[8]["direction"] == "debit"
    assert rows[9]["transaction_type"] == "transfer"       # ATM withdrawal moves money to cash
    assert rows[10]["transaction_type"] == "card_payment"  # paying the card bill is not spending
    assert rows[14]["transaction_type"] == "refund"
    cats = {c["id"]: c["name"] for c in client.get("/categories", headers=auth).json()}
    assert cats[rows[7]["category_id"]] == "Groceries"
    assert cats[rows[8]["category_id"]] == "Food and restaurants"
    assert cats[rows[11]["category_id"]] == "Utilities"


def test_imported_card_bill_payment_does_not_count_as_spending(client, auth):
    bank = make_account(client, auth, "HDFC", "bank")
    card = make_account(client, auth, "SBI Card", "credit_card")
    commit(client, auth, bank, samples.hdfc_csv())
    commit(client, auth, card, samples.card_csv(), source="credit_card")
    s = summary(client, auth)
    # Bank spending 2340.50+640+1450+50+50 ; card 1899+3100+649+500 ; refunds 499 (bank) + 499 (card)
    assert Decimal(s["total_expenses"]) == Decimal("10678.50")
    assert Decimal(s["total_refunds"]) == Decimal("998.00")
    assert Decimal(s["total_income"]) == Decimal("92000.00")
    assert s["unreviewed_count"] == 15  # 9 bank rows + 6 card rows, all waiting for review


def test_card_statement_with_dr_cr_suffixes(client, auth):
    card = make_account(client, auth, "SBI Card", "credit_card")
    p = preview(client, auth, card, samples.card_csv()).json()
    types = [r["transaction_type"] for r in p["rows"]]
    assert types == ["expense", "expense", "card_payment", "refund", "expense", "fee"]
    assert p["suggested_source"] == "credit_card" and p["needs_amount_sign"] is True


def test_sbi_excel_statement(client, auth):
    acc = make_account(client, auth, "SBI", "bank")
    p = preview(client, auth, acc, samples.sbi_xlsx(), name="sbi.xlsx").json()
    assert p["counts"]["ready"] == 3 and p["date_format"] == "DD MMM YYYY"
    r = p["rows"]
    assert r[0]["merchant_name"] == "Zepto Marketplace" and r[0]["amount"] == "812.00"
    assert r[1]["merchant_name"] == "Ravi Kumar" and r[1]["direction"] == "credit"
    assert r[2]["transaction_type"] == "transfer"


def test_card_with_plain_positive_amounts_uses_sign_choice(client, auth):
    card = make_account(client, auth, "Card", "credit_card")
    data = samples.signed_csv([("13/10/2026", "SHOP", "1000"), ("14/10/2026", "REFUND SHOP", "-200")])
    rows = preview(client, auth, card, data).json()["rows"]
    assert [r["direction"] for r in rows] == ["debit", "credit"]
    rows = preview(client, auth, card, data, amount_sign="negative_is_debit").json()["rows"]
    assert [r["direction"] for r in rows] == ["credit", "debit"]


def test_column_mapping_can_be_corrected(client, auth):
    acc = make_account(client, auth, "Bank", "bank")
    data = b"When,What,Out,In\n13/10/2026,Lunch,250,\n14/10/2026,Refund,,100\n"
    p = preview(client, auth, acc, data).json()
    assert p["header_row"] is None and p["problems"]
    p = preview(client, auth, acc, data, header_row=0,
                mapping={"date": 0, "description": 1, "debit": 2, "credit": 3}).json()
    assert p["problems"] == [] and p["counts"]["ready"] == 2
    r = commit(client, auth, acc, data, header_row=0, mapping={"date": 0, "description": 1, "debit": 2, "credit": 3})
    assert r.json()["records_imported"] == 2


def test_overrides_skip_and_recategorise(client, auth):
    acc = make_account(client, auth, "Bank", "bank")
    cats = {c["name"]: c["id"] for c in client.get("/categories", headers=auth).json()}
    data = samples.signed_csv([("13/10/2026", "A", "-10"), ("14/10/2026", "B", "-20"), ("15/10/2026", "C", "-30")])
    r = commit(client, auth, acc, data, overrides={
        "2": {"skip": True}, "3": {"category_id": cats["Travel"]}, "4": {"transaction_type": "fee"}}).json()
    assert r["records_imported"] == 2 and r["records_skipped"] == 1
    items = {t["description"]: t for t in client.get("/transactions", headers=auth).json()["items"]}
    assert items["B"]["category_id"] == cats["Travel"] and items["C"]["transaction_type"] == "fee"
    assert items["B"]["origin"] == "import" and items["B"]["is_reviewed"] is False
    bad = commit(client, auth, acc, samples.signed_csv([("16/10/2026", "D", "-5")]),
                 overrides={"2": {"transaction_type": "income"}})
    assert bad.status_code == 422


def test_9_your_category_choice_is_used_on_future_imports(client, auth):
    acc = make_account(client, auth, "Bank", "bank")
    cats = {c["name"]: c["id"] for c in client.get("/categories", headers=auth).json()}
    add(client, auth, amount="300", transaction_type="expense", merchant_name="Sharma Kirana Store",
        category_id=cats["Family expenses"])
    data = samples.signed_csv([("16/10/2026", "UPI/DR/427700009999/SHARMA KIRANA STORE/SBIN/sharma@ybl/x", "-450")])
    row = preview(client, auth, acc, data).json()["rows"][0]
    assert row["merchant_name"] == "Sharma Kirana Store"
    assert row["category_id"] == cats["Family expenses"]  # beats the "kirana" -> Groceries keyword


def test_deleting_an_import_removes_its_transactions(client, auth):
    acc = make_account(client, auth, "Bank", "bank")
    add(client, auth, amount="5", transaction_type="expense")
    batch = commit(client, auth, acc, samples.many_rows(10)).json()
    assert client.get("/transactions", headers=auth).json()["total"] == 11
    assert client.delete(f"/imports/{batch['id']}", headers=auth).status_code == 204
    assert client.get("/transactions", headers=auth).json()["total"] == 1
    assert client.get("/imports", headers=auth).json() == []
    # and the same file can be imported again afterwards
    assert commit(client, auth, acc, samples.many_rows(10)).json()["records_imported"] == 10


def test_12_imports_are_private(client, two_users):
    a, b = two_users
    acc_a = make_account(client, a, "A bank", "bank")
    batch = commit(client, a, acc_a, samples.many_rows(5)).json()
    assert preview(client, b, acc_a, samples.many_rows(5)).status_code == 404
    assert commit(client, b, acc_a, samples.many_rows(5)).status_code == 404
    assert client.get("/imports", headers=b).json() == []
    assert client.get(f"/imports/{batch['id']}/issues", headers=b).status_code == 404
    assert client.delete(f"/imports/{batch['id']}", headers=b).status_code == 404
    assert client.get("/transactions", headers=a).json()["total"] == 5


def test_imports_need_sign_in(client):
    assert client.post("/imports/preview", files={"file": ("a.csv", b"x")}, data={"account_id": 1}).status_code == 401
    assert client.get("/imports").status_code == 401


def test_xls_that_is_really_an_html_table(client, auth):
    acc = make_account(client, auth, "ICICI", "bank")
    html = b"""<html><body><table>
    <tr><td>Statement of account</td></tr>
    <tr><th>Transaction Date</th><th>Transaction Remarks</th><th>Withdrawal Amount (INR )</th><th>Deposit Amount (INR )</th><th>Balance (INR )</th></tr>
    <tr><td>14/10/2026</td><td>UPI/428800001111/Payment/blinkit@icici/ICICI Bank</td><td>456.00</td><td></td><td>9,544.00</td></tr>
    <tr><td>16/10/2026</td><td>NEFT-SALARY</td><td></td><td>1,000.00</td><td>10,544.00</td></tr>
    </table></body></html>"""
    p = preview(client, auth, acc, html, name="OpTransactionHistory.xls").json()
    assert p["counts"]["ready"] == 2
    assert p["rows"][0]["merchant_name"] == "Blinkit" and p["rows"][0]["direction"] == "debit"
    assert p["rows"][1]["direction"] == "credit"


def test_semicolon_csv(client, auth):
    acc = make_account(client, auth, "Bank", "bank")
    data = "Date;Description;Debit;Credit\n14.10.2026;Shop;1.234,00;\n".replace("1.234,00", "1234.00").encode()
    p = preview(client, auth, acc, data).json()
    assert p["counts"]["ready"] == 1 and p["rows"][0]["amount"] == "1234.00"
