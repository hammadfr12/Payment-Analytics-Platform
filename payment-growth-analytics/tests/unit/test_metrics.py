"""Unit tests for the centralized metric definitions."""
from __future__ import annotations

import math

import pandas as pd
import pytest

from src.analytics.metrics import (
    success_rate, failure_rate, tpv, transaction_count, aov,
    payment_method_share, pp_delta, pct_delta, checkout_conversion, safe_div,
)


def test_success_rate_basic():
    assert success_rate(95, 100) == pytest.approx(95.0)


def test_success_rate_zero_denominator_returns_none():
    assert success_rate(0, 0) is None
    assert success_rate(5, 0) is None


def test_success_rate_negative_denominator_returns_none():
    assert success_rate(5, -10) is None


def test_failure_rate_basic():
    assert failure_rate(5, 100) == pytest.approx(5.0)


def test_failure_rate_zero_denominator():
    assert failure_rate(0, 0) is None


def test_tpv_sums_amounts():
    s = pd.Series([100.0, 200.5, 300.0])
    assert tpv(s) == pytest.approx(600.5)


def test_tpv_empty():
    assert tpv(pd.Series([], dtype=float)) == 0.0


def test_transaction_count_distinct():
    s = pd.Series(["a", "b", "a", "c", "b"])
    assert transaction_count(s) == 3


def test_aov_basic():
    assert aov(1000.0, 10) == pytest.approx(100.0)


def test_aov_zero_count_returns_none():
    assert aov(1000.0, 0) is None
    assert aov(0.0, 0) is None


def test_payment_method_share_basic():
    assert payment_method_share(250.0, 1000.0) == pytest.approx(25.0)


def test_payment_method_share_zero_total_returns_none():
    assert payment_method_share(10.0, 0.0) is None


def test_pp_delta_basic():
    assert pp_delta(95.0, 97.0) == pytest.approx(-2.0)


def test_pp_delta_none_inputs():
    assert pp_delta(None, 97.0) is None
    assert pp_delta(95.0, None) is None


def test_pct_delta_basic():
    assert pct_delta(110.0, 100.0) == pytest.approx(10.0)


def test_pct_delta_previous_zero_returns_none():
    assert pct_delta(10.0, 0.0) is None


def test_pct_delta_negative_previous():
    # (90 - 100)/100 * 100 = -10
    assert pct_delta(90.0, 100.0) == pytest.approx(-10.0)


def test_checkout_conversion_basic():
    assert checkout_conversion(950, 1000) == pytest.approx(95.0)


def test_checkout_conversion_zero_started():
    assert checkout_conversion(0, 0) is None


def test_safe_div_protects_zero():
    assert safe_div(10, 0) is None
    assert safe_div(10, 2) == pytest.approx(5.0)
    assert safe_div(None, 2) is None
