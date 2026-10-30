from conftest import add, make_account


def post(client, auth, **body):
    base = {"transaction_date": "2026-10-10", "payment_method": "upi", "transaction_type": "expense", "amount": "10"}
    return client.post("/transactions", headers=auth, json={**base, **body})


def test_amount_must_be_positive_with_two_decimals(client, auth):
    assert post(client, auth, amount="0").status_code == 422
    assert post(client, auth, amount="-50").status_code == 422
    assert post(client, auth, amount="10.005").status_code == 422
    assert post(client, auth, amount="10.5").status_code == 201


def test_direction_must_match_meaning(client, auth):
    assert post(client, auth, direction="credit").status_code == 422          # expense can't be money in
    assert post(client, auth, transaction_type="refund", direction="debit").status_code == 422
    assert post(client, auth, transaction_type="transfer").status_code == 422  # transfers need a direction
    assert post(client, auth).json()["direction"] == "debit"
    assert post(client, auth, transaction_type="income").json()["direction"] == "credit"


def test_only_last_four_digits_allowed(client, auth):
    r = client.post("/accounts", headers=auth, json={"name": "Card", "account_type": "credit_card",
                                                      "last4": "4111111111111111"})
    assert r.status_code == 422
    assert make_account(client, auth, "Card", "credit_card", last4="1111")


def test_new_user_gets_categories_and_cash_account(client, auth):
    names = {c["name"] for c in client.get("/categories", headers=auth).json()}
    assert {"Groceries", "Fuel", "Miscellaneous", "Salary", "Credit card bill payment"} <= names
    assert [a["name"] for a in client.get("/accounts", headers=auth).json()] == ["Cash"]


def test_edit_keeps_original_and_revalidates(client, auth):
    t = add(client, auth, amount="250", transaction_type="expense", merchant_name="  Big Bazar ")
    assert t["merchant_name"] == "Big Bazar" and t["origin"] == "manual"
    r = client.patch(f"/transactions/{t['id']}", headers=auth, json={"merchant_name": "Big Bazaar", "amount": "260"})
    assert r.status_code == 200 and r.json()["amount"] == "260.00"
    # changing the meaning flips the natural direction automatically
    r = client.patch(f"/transactions/{t['id']}", headers=auth, json={"transaction_type": "refund"})
    assert r.json()["direction"] == "credit"
    assert client.patch(f"/transactions/{t['id']}", headers=auth,
                        json={"direction": "debit"}).status_code == 422


def test_list_filters_search_and_paging(client, auth):
    for i in range(7):
        add(client, auth, amount=str(100 + i), transaction_type="expense",
            merchant_name="Swiggy" if i % 2 else "Zepto", transaction_date=f"2026-10-0{i + 1}")
    add(client, auth, amount="50000", transaction_type="income", payment_method="bank_transfer")
    r = client.get("/transactions", headers=auth, params={"q": "swig"}).json()
    assert r["total"] == 3
    r = client.get("/transactions", headers=auth, params={"transaction_type": "income"}).json()
    assert r["total"] == 1
    r = client.get("/transactions", headers=auth, params={"page_size": 3, "page": 3}).json()
    assert r["total"] == 8 and len(r["items"]) == 2
    r = client.get("/transactions", headers=auth, params={"sort": "amount_desc"}).json()
    assert r["items"][0]["amount"] == "50000.00"
    r = client.get("/transactions", headers=auth, params={"start": "2026-10-03", "end": "2026-10-04"}).json()
    assert r["total"] == 2


def test_account_with_transactions_cannot_be_deleted(client, auth):
    acc = make_account(client, auth, "Paytm", "wallet")
    t = add(client, auth, amount="5", transaction_type="expense", account_id=acc)
    assert client.delete(f"/accounts/{acc}", headers=auth).status_code == 409
    assert client.delete(f"/transactions/{t['id']}", headers=auth).status_code == 204
    assert client.delete(f"/accounts/{acc}", headers=auth).status_code == 204
