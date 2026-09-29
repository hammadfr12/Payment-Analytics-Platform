"""Unit tests for the opportunity engine rules."""
from __future__ import annotations

import pytest

from src.opportunities.engine import (
    detect_opportunities, _rule_sr_decline, _rule_benchmark_gap,
    _rule_error_spike, _rule_concentrated_segment, Opportunity,
)
from src.analytics.benchmark import benchmark_merchant
from src.rca.engine import run_rca
from src.config.settings import get_settings


@pytest.fixture(scope="module")
def settings():
    return get_settings()


@pytest.fixture(scope="module")
def all_opportunities(settings):
    return detect_opportunities(settings=settings)


def test_opportunities_generated(all_opportunities):
    assert len(all_opportunities) > 0


def test_opportunity_schema_complete(all_opportunities):
    required = {"opportunity_id", "merchant_id", "opportunity_type", "severity",
                "metric", "current_value", "previous_value", "benchmark_value",
                "delta", "gap", "affected_volume", "primary_dimension",
                "supporting_evidence", "recommended_next_step", "confidence",
                "created_at"}
    for o in all_opportunities:
        fields = set(o.__dataclass_fields__.keys())
        assert required.issubset(fields)


def test_severity_values_valid(all_opportunities):
    for o in all_opportunities:
        assert o.severity in ("Critical", "Attention", "Opportunity")


def test_confidence_values_valid(all_opportunities):
    for o in all_opportunities:
        assert o.confidence in ("High", "Medium", "Low")


def test_every_opportunity_has_evidence_and_next_step(all_opportunities):
    for o in all_opportunities:
        assert o.supporting_evidence and len(o.supporting_evidence) > 10
        assert o.recommended_next_step and len(o.recommended_next_step) > 5


def test_nova_has_sr_decline_opportunity(all_opportunities):
    nova = [o for o in all_opportunities if o.merchant_id == "M0013"]
    types = {o.opportunity_type for o in nova}
    assert "RULE_SR_DECLINE" in types, "Nova's decline must produce an SR_DECLINE opportunity"


def test_nova_has_benchmark_gap_opportunity(all_opportunities):
    nova = [o for o in all_opportunities if o.merchant_id == "M0013"]
    types = {o.opportunity_type for o in nova}
    assert "RULE_BENCHMARK_GAP" in types


def test_budget_grocer_flagged_for_benchmark_gap(all_opportunities):
    bg = [o for o in all_opportunities if o.merchant_id == "M0042"]
    types = {o.opportunity_type for o in bg}
    assert "RULE_BENCHMARK_GAP" in types, "consistent underperformer must be flagged"


def test_swift_travel_not_flagged_for_decline(all_opportunities):
    """Swift Travel improves -> must not get an SR_DECLINE opportunity."""
    swift = [o for o in all_opportunities if o.merchant_id == "M0077"]
    types = {o.opportunity_type for o in swift}
    assert "RULE_SR_DECLINE" not in types


def test_opportunity_ids_unique(all_opportunities):
    ids = [o.opportunity_id for o in all_opportunities]
    assert len(ids) == len(set(ids))
