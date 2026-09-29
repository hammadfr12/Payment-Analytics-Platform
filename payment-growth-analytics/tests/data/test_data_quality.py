"""Data-quality tests against the generated dataset in DuckDB."""
from __future__ import annotations

import pytest

from src.common.queries import query_df
from src.config.settings import get_settings


@pytest.fixture(scope="module")
def settings():
    return get_settings()


def _one(sql, settings):
    return query_df(sql, settings=settings).iloc[0]


def test_transaction_id_unique(settings):
    r = _one("""
        SELECT COUNT(*) AS total,
               COUNT(DISTINCT transaction_id) AS distinct_ids
        FROM stg_transactions
    """, settings)
    assert int(r["total"]) == int(r["distinct_ids"]), "transaction_id must be unique"


def test_no_null_merchant_id(settings):
    r = _one("SELECT COUNT(*) AS n FROM fct_payment_performance WHERE merchant_id IS NULL",
             settings)
    assert int(r["n"]) == 0


def test_merchant_referential_integrity(settings):
    r = _one("""
        SELECT COUNT(*) AS n
        FROM fct_payment_performance f
        LEFT JOIN stg_merchants m ON f.merchant_id = m.merchant_id
        WHERE m.merchant_id IS NULL
    """, settings)
    assert int(r["n"]) == 0, "every transaction must map to a known merchant"


def test_valid_payment_methods(settings):
    valid = {"UPI", "Credit Card", "Debit Card", "Netbanking", "Wallet"}
    df = query_df("SELECT DISTINCT payment_method FROM stg_transactions", settings=settings)
    assert set(df["payment_method"]).issubset(valid)


def test_valid_status_values(settings):
    df = query_df("SELECT DISTINCT status FROM stg_transactions", settings=settings)
    assert set(df["status"]).issubset({"authorized", "failed"})


def test_positive_amounts(settings):
    r = _one("""
        SELECT COUNT(*) AS n FROM fct_payment_performance
        WHERE is_eligible = TRUE AND amount <= 0
    """, settings)
    assert int(r["n"]) == 0


def test_valid_dates(settings):
    r = _one("""
        SELECT COUNT(*) AS n FROM stg_transactions
        WHERE event_timestamp IS NULL
    """, settings)
    assert int(r["n"]) == 0


def test_no_impossible_authorization_timestamps(settings):
    """authorized_at (when present) must not precede event_timestamp by > 1 day
    and must not be in the far future."""
    r = _one("""
        SELECT COUNT(*) AS n FROM stg_transactions
        WHERE authorized_at IS NOT NULL
          AND (authorized_at < event_timestamp - INTERVAL 1 DAY
               OR authorized_at > event_timestamp + INTERVAL 1 DAY)
    """, settings)
    assert int(r["n"]) == 0


def test_authorized_matches_status(settings):
    """is_authorized and status must be consistent."""
    r = _one("""
        SELECT COUNT(*) AS n FROM stg_transactions
        WHERE (status = 'authorized' AND authorized_at IS NULL)
           OR (status = 'failed' AND authorized_at IS NOT NULL)
    """, settings)
    assert int(r["n"]) == 0


def test_known_industries(settings):
    valid = {"E-commerce", "Food Delivery", "Travel", "Fintech", "Grocery",
             "Fashion", "Electronics", "Quick Commerce", "Entertainment",
             "Healthcare", "Education", "Marketplaces"}
    df = query_df("SELECT DISTINCT industry FROM stg_merchants", settings=settings)
    assert set(df["industry"]).issubset(valid)


def test_checkout_events_valid_merchants(settings):
    r = _one("""
        SELECT COUNT(*) AS n FROM stg_checkout_events
        WHERE merchant_id NOT IN (SELECT merchant_id FROM stg_merchants)
    """, settings)
    assert int(r["n"]) == 0, "checkout events must reference known merchants"


def test_checkout_event_types_valid(settings):
    valid = {"checkout_started", "payment_attempted", "payment_success", "payment_failed"}
    df = query_df("SELECT DISTINCT event_type FROM stg_checkout_events", settings=settings)
    assert set(df["event_type"]).issubset(valid)
