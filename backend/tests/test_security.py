from conftest import PASSWORD, add, make_account, register


def test_everything_private_needs_sign_in(client):
    for path in ("/transactions", "/accounts", "/categories", "/dashboard/summary", "/auth/me"):
        assert client.get(path).status_code == 401
    assert client.get("/transactions", headers={"Authorization": "Bearer forged.token.value"}).status_code == 401


def test_signup_closes_after_first_account(client):
    assert client.get("/auth/status").json()["registration_open"] is True
    register(client)
    assert client.get("/auth/status").json()["registration_open"] is False
    r = client.post("/auth/register", json={"email": "intruder@example.com", "password": PASSWORD})
    assert r.status_code == 403


def test_login_and_lockout(client):
    register(client)
    assert client.post("/auth/login", json={"email": "ASHA@example.com", "password": PASSWORD}).status_code == 200
    for _ in range(5):
        assert client.post("/auth/login", json={"email": "asha@example.com", "password": "wrong"}).status_code == 401
    r = client.post("/auth/login", json={"email": "asha@example.com", "password": PASSWORD})
    assert r.status_code == 429


def test_short_password_rejected(client):
    r = client.post("/auth/register", json={"email": "x@example.com", "password": "short"})
    assert r.status_code == 422


def test_12_cannot_touch_another_users_records(client, two_users):
    a, b = two_users
    acc_a = make_account(client, a, "A Bank", "bank")
    txn_a = add(client, a, amount="999", transaction_type="expense", account_id=acc_a)

    assert client.get(f"/transactions/{txn_a['id']}", headers=b).status_code == 404
    assert client.patch(f"/transactions/{txn_a['id']}", headers=b, json={"amount": "1"}).status_code == 404
    assert client.delete(f"/transactions/{txn_a['id']}", headers=b).status_code == 404
    assert client.patch(f"/accounts/{acc_a}", headers=b, json={"name": "mine"}).status_code == 404
    assert client.delete(f"/accounts/{acc_a}", headers=b).status_code == 404
    assert client.get("/transactions", headers=b).json()["total"] == 0
    # B cannot attach A's account or category to B's own transaction either.
    r = client.post("/transactions", headers=b, json={
        "transaction_date": "2026-10-10", "amount": "5", "transaction_type": "expense",
        "payment_method": "upi", "account_id": acc_a})
    assert r.status_code == 404
    cat_a = client.get("/categories", headers=a).json()[0]["id"]
    r = client.post("/transactions", headers=b, json={
        "transaction_date": "2026-10-10", "amount": "5", "transaction_type": "expense",
        "payment_method": "upi", "category_id": cat_a})
    assert r.status_code == 404
    # A's data is untouched.
    assert client.get(f"/transactions/{txn_a['id']}", headers=a).json()["amount"] == "999.00"


def test_security_headers(client):
    r = client.get("/health")
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
