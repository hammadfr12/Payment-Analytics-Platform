"""Regression tests: the intentionally-injected synthetic scenarios must be
discoverable by the RCA / benchmark / opportunity engines with known answers.

Ground truth (see src/data_generation/generator.py ScenarioConfig):
  S1  NOVA_FASHION (M0013, E-commerce)   3-5 pp SR decline in final 2 weeks
  S2  Android + Debit Card               deteriorates for Nova in final 2 weeks
  S3  HDFC issuer                        error spike for Nova in final 2 weeks
  S4  BUDGET_GROCER (M0042, Grocery)     consistently below its industry
  S5  SWIFT_TRIPS (M0077, Travel)        strong SR improvement
"""
from __future__ import annotations

import pytest

from src.analytics.benchmark import benchmark_merchant
from src.config.settings import get_settings
from src.opportunities.engine import detect_opportunities, _latest_two_weeks
from src.rca.engine import run_rca

s = get_settings()

pytestmark = pytest.mark.skipif(
    not s.duckdb_path.exists(),
    reason="DuckDB not built; run `make run-pipeline` first",
)

CUR_S, CUR_E, PRV_S, PRV_E = _latest_two_weeks(s)


def test_scenario1_nova_sr_decline_detected():
    """Nova's SR must decline >= 3 pp in the final two weeks."""
    rca = run_rca("M0013", CUR_S, CUR_E, PRV_S, PRV_E, settings=s)
    assert rca.overall_delta_pp is not None
    assert rca.overall_delta_pp <= -3.0, (
        f"Nova SR decline of {rca.overall_delta_pp:.2f} pp is below the 3 pp threshold"
    )


def test_scenario2_android_is_major_contributor():
    """Android must appear among Nova's top contributors to the decline."""
    rca = run_rca("M0013", CUR_S, CUR_E, PRV_S, PRV_E, settings=s)
    platforms = {c["segment"]: c for c in rca.contributions if c["dimension"] == "platform"}
    assert "Android" in platforms
    android = platforms["Android"]
    assert android["delta_pp"] < 0, "Android SR must fall"
    # Android should be a material contributor (its share of the platform dim)
    assert android["share_of_decline"] > 0


def test_scenario2_debit_card_is_major_contributor():
    rca = run_rca("M0013", CUR_S, CUR_E, PRV_S, PRV_E, settings=s)
    methods = {c["segment"]: c for c in rca.contributions if c["dimension"] == "payment_method"}
    assert "Debit Card" in methods
    assert methods["Debit Card"]["delta_pp"] < 0


def test_scenario3_issuer_error_spike_detected():
    """HDFC must show a materially worse SR delta than the average issuer."""
    rca = run_rca("M0013", CUR_S, CUR_E, PRV_S, PRV_E, settings=s)
    issuers = {c["segment"]: c for c in rca.contributions if c["dimension"] == "issuer_bank"}
    assert "HDFC" in issuers
    assert issuers["HDFC"]["delta_pp"] < -3.0, "HDFC issuer spike must show a large negative delta"


def test_scenario4_budget_grocer_below_benchmark():
    b = benchmark_merchant("M0042", start_date=CUR_S, end_date=CUR_E,
                           payment_method="ALL", settings=s)
    assert b.benchmark_status == "VALID"
    assert b.gap_pp is not None and b.gap_pp <= -2.0, (
        f"Budget Grocer gap {b.gap_pp} not below -2 pp"
    )


def test_scenario5_swift_travel_improved():
    """Swift Travel's SR must improve in the final two weeks."""
    rca = run_rca("M0077", CUR_S, CUR_E, PRV_S, PRV_E, settings=s)
    assert rca.overall_delta_pp is not None
    assert rca.overall_delta_pp > 0, "Swift Travel should show improvement"


def test_opportunity_engine_flags_nova():
    opps = detect_opportunities(settings=s)
    nova_types = {o.opportunity_type for o in opps if o.merchant_id == "M0013"}
    assert "RULE_SR_DECLINE" in nova_types
    assert "RULE_BENCHMARK_GAP" in nova_types


def test_opportunity_engine_does_not_flag_swift_for_decline():
    opps = detect_opportunities(settings=s)
    swift_types = {o.opportunity_type for o in opps if o.merchant_id == "M0077"}
    assert "RULE_SR_DECLINE" not in swift_types
