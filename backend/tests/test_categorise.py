"""Automatic categories: shop-or-person, keywords, saved rules, AI suggestions and Quick sort."""
import json

import pytest

from conftest import add, make_account
import samples
from app import ai
from app.config import get_settings
from app.importer import classify


def cats(client, auth):
    return {c["name"]: c["id"] for c in client.get("/categories", headers=auth).json()}


def commit(client, auth, acc, data, name="s.csv"):
    r = client.post("/imports/commit", headers=auth, files={"file": (name, data)},
                    data={"account_id": acc, "source_provider": "bank"})
    assert r.status_code == 201, r.text
    return r.json()


def preview(client, auth, acc, data, name="s.csv"):
    r = client.post("/imports/preview", headers=auth, files={"file": (name, data)}, data={"account_id": acc})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def fake_ai(monkeypatch):
    """Stand-in for the AI: records what it was sent, answers from a fixed table."""
    sent = []
    table = {"Sri Lakshmi Enterprises": "Groceries", "Green Leaf Corner": "Food and restaurants",
             "Shaik Karishma": "Person", "Mystery Traders": "Unknown"}
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "test-key")

    def suggest(names, categories):
        sent.append(list(names))
        assert "Clothing and accessories" in categories and "Electronics" in categories
        return {n: table[n] for n in names if n in table}
    monkeypatch.setattr(ai, "suggest_categories", suggest)
    return sent


def test_new_categories_exist(client, auth):
    names = cats(client, auth)
    assert {"Clothing and accessories", "Electronics", "Healthcare", "Insurance", "Education"} <= set(names)


@pytest.mark.parametrize("text,expected", [
    ("ZUDIO HYDERABAD", "Clothing and accessories"), ("MYNTRA DESIGNS", "Clothing and accessories"),
    ("TANISHQ JEWELLERS", "Clothing and accessories"), ("CROMA RETAIL", "Electronics"),
    ("EMI PRINCIPAL - 1/3 ELECTRONICS", "Electronics"), ("STAR HEALTH RENEWAL PREMIUM", "Insurance"),
    ("SRI SAI MEDICALS", "Healthcare"), ("KENDRIYA VIDYALAYA FEES", "Education"),
    ("KARTHIKEYA FILLING STATION", "Fuel"), ("AMAZON PAY INDIA", "Shopping"),
])
def test_keywords(text, expected):
    by_name = {n: i for i, n in enumerate(["Clothing and accessories", "Electronics", "Insurance", "Healthcare",
                                            "Education", "Fuel", "Shopping", "Loan and EMI payments"])}
    cat, source = classify.guess_category(text, "expense", {}, None, by_name)
    assert {v: k for k, v in by_name.items()}[cat] == expected and source == "keyword"


@pytest.mark.parametrize("key,kind", [
    ("paytm.xx67c9y@pty", "shop"), ("xxxratpe.xxxxxx14135@fbpe", "shop"), ("vyapar.123@hdfcbank", "shop"),
    ("shop.rzp@rxaxis", "shop"), ("q123456789@ybl", "shop"), ("ravi.k@okicici", "person"),
    ("9876543210@ybl", "person"), ("xxxxx10294@ybl", None), (None, None),
])
def test_shop_or_person_from_upi_id(key, kind):
    assert classify.payee_kind_for(key, "upi") == kind


def test_payee_key_prefers_upi_id():
    assert classify.payee_key_for("KAYA (xxxxx10294@YBL)", "Paid to KAYA") == "xxxxx10294@ybl"
    assert classify.payee_key_for("KPN FARM FRESH", "Paid to KPN FARM FRESH") == "kpn farm fresh"
    assert classify.readable_name("xxxxxxxxOINT (xxxxx81755@ybl)") is None
    assert classify.readable_name("Zepto Marketplace") == "Zepto Marketplace"


def test_ai_fills_only_what_rules_and_keywords_could_not(client, auth, fake_ai):
    acc = make_account(client, auth, "PhonePe", "upi")
    data = samples.signed_csv([
        ("13/10/2026", "Paid to SRI LAKSHMI ENTERPRISES", "-40.45"),
        ("14/10/2026", "Paid to GREEN LEAF CORNER", "-415"),
        ("15/10/2026", "Paid to Shaik Karishma", "-15"),
        ("16/10/2026", "Paid to Mystery Traders", "-99"),
        ("17/10/2026", "Paid to SWIGGY", "-640"),                   # keyword handles this
        ("18/10/2026", "UPI/DR/427700001111/xxxxxxxxOINT/YESB/xxxxx81755@ybl/x", "-12"),  # masked: never sent
    ])
    p = preview(client, auth, acc, data)
    names = {v: k for k, v in cats(client, auth).items()}
    rows = {r["description"].split("/")[0]: r for r in p["rows"]}
    assert p["ai_used"] is True
    assert names[rows["Paid to SRI LAKSHMI ENTERPRISES"]["category_id"]] == "Groceries"
    assert rows["Paid to SRI LAKSHMI ENTERPRISES"]["category_source"] == "ai"
    assert rows["Paid to SRI LAKSHMI ENTERPRISES"]["merchant_name"] == "Sri Lakshmi Enterprises"
    assert names[rows["Paid to GREEN LEAF CORNER"]["category_id"]] == "Food and restaurants"
    assert rows["Paid to Shaik Karishma"]["category_id"] is None and rows["Paid to Shaik Karishma"]["payee_kind"] == "person"
    assert rows["Paid to Mystery Traders"]["category_id"] is None
    assert rows["Paid to SWIGGY"]["category_source"] == "keyword"
    # Only readable merchant names were sent: no amounts, dates, UPI IDs or masked names.
    sent = [n for batch in fake_ai for n in batch]
    assert sorted(sent) == sorted(["Sri Lakshmi Enterprises", "Green Leaf Corner", "Shaik Karishma", "Mystery Traders"])
    assert not any("@" in n or "xxx" in n.lower() or any(c.isdigit() for c in n) for n in sent)
    # Answers are cached: the import itself and later previews send nothing new.
    commit(client, auth, acc, data)
    preview(client, auth, acc, data)
    assert len(fake_ai) == 1


def test_ai_respects_the_off_switch_and_missing_key(client, auth, fake_ai, monkeypatch):
    acc = make_account(client, auth, "PhonePe", "upi")
    data = samples.signed_csv([("13/10/2026", "Paid to SRI LAKSHMI ENTERPRISES", "-40.45")])
    me = client.patch("/auth/me", headers=auth, json={"ai_categorise": False}).json()
    assert me["ai_available"] is True and me["ai_categorise"] is False
    assert preview(client, auth, acc, data)["rows"][0]["category_id"] is None and fake_ai == []
    client.patch("/auth/me", headers=auth, json={"ai_categorise": True})
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")
    assert client.get("/auth/me", headers=auth).json()["ai_available"] is False
    assert preview(client, auth, acc, data)["rows"][0]["category_id"] is None and fake_ai == []


def test_real_ai_call_failure_never_breaks_import(client, auth, monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "bad-key")
    import httpx

    def boom(*a, **k):
        raise httpx.ConnectError("no network")
    monkeypatch.setattr(httpx, "post", boom)
    assert ai.suggest_categories(["KPN FARM FRESH"], ["Groceries"]) == {}
    acc = make_account(client, auth, "PhonePe", "upi")
    p = preview(client, auth, acc, samples.signed_csv([("13/10/2026", "Paid to KPN FARM FRESH", "-40")]))
    assert p["counts"]["ready"] == 1 and p["ai_used"] is False


def test_quick_sort_groups_and_applies_to_past_and_future(client, auth):
    acc = make_account(client, auth, "BHIM", "upi")
    milk = "UPI/DR/4277000{:05d}/xxxxxxxxKAYA/YESB/xxxxx10294@ybl/pay"
    rows = [(f"{d:02d}/10/2026", milk.format(d), "-50") for d in range(13, 28)]
    rows += [("20/10/2026", "UPI/DR/427799990001/xxxxxxxxOINT/YESB/xxxxx81755@ybl/x", "-12"),
             ("21/10/2026", "UPI/DR/427799990002/xxxxxxxxOINT/YESB/xxxxx81755@ybl/x", "-12")]
    commit(client, auth, acc, samples.signed_csv(rows))
    g = client.get("/sorting/groups", headers=auth).json()
    assert g["group_count"] == 2 and g["payment_count"] == 17
    first = g["groups"][0]
    assert first["payee_key"] == "xxxxx10294@ybl" and first["count"] == 15
    assert first["typical_amount"] == "50.00" and first["total"] == "750.00"
    assert first["first_date"] == "2026-10-13" and first["last_date"] == "2026-10-27"
    c = cats(client, auth)
    r = client.post("/sorting/apply", headers=auth, json={"payee_key": "xxxxx10294@ybl", "category_id": c["Groceries"]})
    assert r.json() == {"updated": 15, "category": "Groceries"}
    g = client.get("/sorting/groups", headers=auth).json()
    assert g["group_count"] == 1 and g["groups"][0]["payee_key"] == "xxxxx81755@ybl"
    # Next month's statement: the saved rule categorises the same payee automatically.
    p = preview(client, auth, acc, samples.signed_csv([("13/11/2026", milk.format(99), "-50")]))
    assert p["rows"][0]["category_id"] == c["Groceries"] and p["rows"][0]["category_source"] == "rule"
    # Only spending categories, and only your own.
    r = client.post("/sorting/apply", headers=auth, json={"payee_key": "x@ybl", "category_id": c["Salary"]})
    assert r.status_code == 422
    assert client.get("/sorting/payee-count", headers=auth, params={"payee_key": "xxxxx10294@ybl"}).json() == {"count": 15}


def test_quick_sort_is_private(client, two_users):
    a, b = two_users
    acc = make_account(client, a, "BHIM", "upi")
    commit(client, a, acc, samples.signed_csv([("13/10/2026", "UPI/DR/427700000001/xxxxxxxxKAYA/YESB/xxxxx10294@ybl/p", "-50")]))
    assert client.get("/sorting/groups", headers=b).json()["group_count"] == 0
    cat_a = cats(client, a)["Groceries"]
    r = client.post("/sorting/apply", headers=b, json={"payee_key": "xxxxx10294@ybl", "category_id": cat_a})
    assert r.status_code == 404
    cat_b = cats(client, b)["Groceries"]
    assert client.post("/sorting/apply", headers=b,
                       json={"payee_key": "xxxxx10294@ybl", "category_id": cat_b}).json()["updated"] == 0
    assert client.get("/sorting/groups", headers=a).json()["group_count"] == 1


def test_hidden_receivers_are_never_grouped_as_one_payee(client, auth):
    acc = make_account(client, auth, "BHIM", "upi")
    rows = [("13/10/2026", "Bill or merchant payment (receiver not shown in statement)", "-500"),
            ("14/10/2026", "Bill or merchant payment (receiver not shown in statement)", "-120")]
    commit(client, auth, acc, samples.signed_csv(rows))
    items = client.get("/transactions", headers=auth).json()["items"]
    assert all(t["payee_key"] is None and t["merchant_name"] is None for t in items)
    assert client.get("/sorting/groups", headers=auth).json()["group_count"] == 0


def test_quick_sort_names_read_cleanly():
    from app.routers.sorting import _display_name
    assert _display_name("TEA (xxxratpe.xxxx33333@unitype)", "k") == "TEA"
    assert _display_name("KAYA (xxxxx10294@ybl)", "xxxxx10294@ybl") == "KAYA"
    assert _display_name("Kpn Farm Fresh", "kpn farm fresh") == "Kpn Farm Fresh"
    assert _display_name("xxxxxxxx (xxxxx1@ybl)", "xxxxx1@ybl") == "xxxxx1@ybl"
