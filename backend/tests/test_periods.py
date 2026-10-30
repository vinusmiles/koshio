from datetime import date

import pytest

from app.periods import resolve


def test_financial_year_runs_april_to_march():
    assert resolve("fy_to_date", today=date(2026, 10, 24))[:2] == (date(2026, 4, 1), date(2026, 10, 24))
    assert resolve("fy_to_date", today=date(2027, 2, 10))[:2] == (date(2026, 4, 1), date(2027, 2, 10))
    assert resolve("fy_to_date", today=date(2026, 4, 1))[0] == date(2026, 4, 1)
    assert resolve("fy_to_date", today=date(2026, 3, 31))[0] == date(2025, 4, 1)


def test_previous_financial_year():
    s, e, label = resolve("previous_fy", today=date(2026, 10, 24))
    assert (s, e, label) == (date(2025, 4, 1), date(2026, 3, 31), "FY 2025–26")


def test_previous_month_across_year_end():
    assert resolve("previous_month", today=date(2027, 1, 15))[:2] == (date(2026, 12, 1), date(2026, 12, 31))
    assert resolve("previous_month", today=date(2028, 3, 5))[:2] == (date(2028, 2, 1), date(2028, 2, 29))


def test_last_n_months_include_current_month():
    assert resolve("last_3_months", today=date(2026, 2, 20))[0] == date(2025, 12, 1)
    assert resolve("last_6_months", today=date(2026, 10, 24))[0] == date(2026, 5, 1)


def test_custom_range_validation():
    with pytest.raises(ValueError):
        resolve("custom", date(2026, 5, 2), date(2026, 5, 1))
    with pytest.raises(ValueError):
        resolve("custom", date(2026, 5, 2), None)
    with pytest.raises(ValueError):
        resolve("nonsense")


def test_bad_period_is_a_clear_error(client, auth):
    r = client.get("/dashboard/summary", headers=auth,
                   params={"preset": "custom", "start": "2026-05-02", "end": "2026-05-01"})
    assert r.status_code == 422 and "start date" in r.json()["detail"]
