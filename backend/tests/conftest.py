import os

os.environ.update(ENVIRONMENT="test", JWT_SECRET="test-secret-" + "x" * 40,
                  DATABASE_URL="sqlite://", CORS_ORIGINS="http://localhost:5173")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import Base, get_db, make_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.security import login_limiter  # noqa: E402

PASSWORD = "correct horse battery"


@pytest.fixture
def client():
    # Set TEST_DATABASE_URL to a throwaway Postgres database to run against Postgres.
    pg = os.environ.get("TEST_DATABASE_URL")
    if pg:
        engine = make_engine(pg.replace("postgresql://", "postgresql+psycopg://", 1))
        Base.metadata.drop_all(engine)
    else:
        engine = make_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    s = get_settings()
    s.allow_registration, s.allow_multiple_users = True, False
    login_limiter._failures.clear()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def register(client, email="asha@example.com"):
    r = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth(client):
    return register(client)


@pytest.fixture
def two_users(client):
    get_settings().allow_multiple_users = True
    return register(client, "a@example.com"), register(client, "b@example.com")


def make_account(client, headers, name, account_type, **extra):
    r = client.post("/accounts", headers=headers, json={"name": name, "account_type": account_type, **extra})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def add(client, headers, **fields):
    body = {"transaction_date": "2026-10-10", "payment_method": "upi", **fields}
    r = client.post("/transactions", headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def summary(client, headers, start="2026-10-01", end="2026-10-31"):
    r = client.get("/dashboard/summary", headers=headers,
                   params={"preset": "custom", "start": start, "end": end})
    assert r.status_code == 200, r.text
    return r.json()
