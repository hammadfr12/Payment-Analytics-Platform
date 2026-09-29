"""Unit tests for the RCA engine."""
from __future__ import annotations

import pytest

from src.rca.engine import run_rca, DIMENSIONS, LANGUAGE_NOTE
from src.config.settings import get_settings


@pytest.fixture(scope="module")
def settings():
    return get_settings()


@pytest.fixture(scope="module")
def nova_rca(settings):
    # final 2 weeks vs the 2 weeks before (matches the injected decline window)
    return run_rca("M0013", "2026-09-14", "2026-09-27",
                   "2026-08-31", "2026-09-13", settings=settings)


def test_rca_detects_decline(nova_rca):
    assert nova_rca.overall_delta_pp is not None
    assert nova_rca.overall_delta_pp < -3.0, "Nova's injected decline must be detected"


def test_rca_current_below_previous(nova_rca):
    assert nova_rca.overall_current_sr < nova_rca.overall_previous_sr


def test_rca_contribution_negative_for_decline(nova_rca):
    """Top contributors in a decline must have negative contributions."""
    assert len(nova_rca.top_contributors) > 0
    assert any(c["contribution"] < 0 for c in nova_rca.top_contributors)


def test_rca_identifies_android_contributor(nova_rca):
    """Scenario 2: Android+Debit Card deteriorates -> Android must be a contributor."""
    platforms = {c["segment"]: c for c in nova_rca.contributions
                 if c["dimension"] == "platform"}
    assert "Android" in platforms
    assert platforms["Android"]["delta_pp"] is not None
    assert platforms["Android"]["delta_pp"] < 0


def test_rca_identifies_debit_card_delta(nova_rca):
    """Debit Card must show a negative SR delta (worst method in scenario 2)."""
    methods = {c["segment"]: c for c in nova_rca.contributions
               if c["dimension"] == "payment_method"}
    assert "Debit Card" in methods
    assert methods["Debit Card"]["delta_pp"] < 0


def test_rca_has_all_dimensions(nova_rca):
    dims = {c["dimension"] for c in nova_rca.contributions}
    # at least the core multi-valued dimensions must be present
    for d in ["payment_method", "device", "platform", "issuer_bank"]:
        assert d in dims


def test_rca_language_is_non_causal(nova_rca):
    assert "not causation" in nova_rca.language_note.lower() or \
           "association" in nova_rca.language_note.lower()
    # must never claim causality in the note
    assert "caused by" not in nova_rca.language_note.lower()


def test_rca_volumes_consistent(nova_rca):
    assert nova_rca.total_volume_current > 0
    assert nova_rca.total_volume_previous > 0
