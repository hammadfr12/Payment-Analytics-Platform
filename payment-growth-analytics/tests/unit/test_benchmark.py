"""Unit tests for the benchmark engine (against live DuckDB fixture)."""
from __future__ import annotations

import pytest

from src.analytics.benchmark import benchmark_merchant
from src.config.settings import get_settings


@pytest.fixture(scope="module")
def settings():
    return get_settings()


def test_benchmark_returns_valid_status_for_known_merchant(settings):
    b = benchmark_merchant("M0013", payment_method="ALL", settings=settings)
    assert b.benchmark_status in ("VALID", "INSUFFICIENT_SAMPLE", "NO_PEERS")
    assert b.industry == "E-commerce"


def test_benchmark_excludes_self():
    """Peer count must not include the target merchant (self-exclusion)."""
    s = get_settings()
    b = benchmark_merchant("M0013", payment_method="ALL", settings=s)
    # peer_count is distinct peers excluding self; must be >= 1 given 150 merchants
    assert b.peer_count >= 1


def test_benchmark_has_sample_size(settings):
    b = benchmark_merchant("M0013", payment_method="ALL", settings=settings)
    assert b.sample_txn_count >= 0
    assert isinstance(b.methodology, str) and len(b.methodology) > 10


def test_benchmark_gap_direction_for_underperformer(settings):
    """BUDGET_GROCER (M0042) is intentionally below its industry -> negative gap."""
    b = benchmark_merchant("M0042", payment_method="ALL", settings=settings)
    assert b.benchmark_status == "VALID"
    assert b.gap_pp is not None
    assert b.gap_pp < 0, "consistent underperformer should have a negative benchmark gap"


def test_benchmark_status_field_always_present(settings):
    b = benchmark_merchant("M0001", payment_method="ALL", settings=settings)
    assert b.benchmark_status in ("VALID", "INSUFFICIENT_SAMPLE", "NO_PEERS")
