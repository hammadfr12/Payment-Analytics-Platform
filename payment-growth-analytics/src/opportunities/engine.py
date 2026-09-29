"""Opportunity engine — transparent rules-based detection.

Rules (configurable via Settings):
  RULE_SR_DECLINE        SR delta <= -opp_sr_decline_pp AND txn_count >= opp_min_txns
  RULE_BENCHMARK_GAP     merchant_sr <= benchmark_sr - opp_benchmark_gap_pp
                        AND benchmark_status = VALID
  RULE_ERROR_SPIKE       an error category's failure share rises >= opp_error_spike_pp
  RULE_CONCENTRATED_SEG  a single segment explains >= opp_concentrated_share of
                        the observed decline (from RCA contribution)

Each generated opportunity carries the full evidence schema required by the PRD.
`confidence` reflects EVIDENCE QUALITY (sample size, benchmark validity, rule
agreement) — NOT causal certainty.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd

from src.analytics.benchmark import benchmark_merchant, BenchmarkResult
from src.common.queries import query_df
from src.config.settings import Settings, get_settings
from src.rca.engine import run_rca, RcaResult


SEVERITY_CRITICAL = "Critical"
SEVERITY_ATTENTION = "Attention"
SEVERITY_OPPORTUNITY = "Opportunity"


@dataclass
class Opportunity:
    opportunity_id: str
    merchant_id: str
    merchant_name: str
    opportunity_type: str
    severity: str
    metric: str
    current_value: Optional[float]
    previous_value: Optional[float]
    benchmark_value: Optional[float]
    delta: Optional[float]
    gap: Optional[float]
    affected_volume: int
    primary_dimension: str
    supporting_evidence: str
    recommended_next_step: str
    confidence: str
    created_at: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _confidence_label(score: float) -> str:
    if score >= 0.75:
        return "High"
    if score >= 0.5:
        return "Medium"
    return "Low"


def _merchant_name(mid: str, settings: Settings) -> str:
    df = query_df("SELECT merchant_name FROM stg_merchants WHERE merchant_id = ?",
                  [mid], settings=settings)
    return str(df.iloc[0]["merchant_name"]) if not df.empty else mid


def _latest_two_weeks(settings: Settings):
    """Return (current_start, current_end, previous_start, previous_end) for
    the latest 2 weeks vs the 2 weeks before, based on the data's max date."""
    df = query_df("SELECT MAX(event_date) AS maxd, MIN(event_date) AS mind "
                  "FROM fct_payment_performance", settings=settings)
    maxd = pd.to_datetime(df.iloc[0]["maxd"]).date()
    current_end = maxd
    current_start = current_end - pd.Timedelta(days=13)
    previous_end = current_start - pd.Timedelta(days=1)
    previous_start = previous_end - pd.Timedelta(days=13)
    return (str(current_start), str(current_end),
            str(previous_start), str(previous_end))


def _rule_sr_decline(rca: RcaResult, bench: BenchmarkResult, s: Settings,
                     merchant_name: str) -> Optional[Opportunity]:
    if rca.overall_delta_pp is None or rca.overall_delta_pp > -s.opp_sr_decline_pp:
        return None
    if rca.total_volume_current < s.opp_min_txns:
        return None
    # primary dimension from top contributor
    primary = "overall"
    top_seg = None
    if rca.top_contributors:
        tc = rca.top_contributors[0]
        primary = f"{tc['dimension']}={tc['segment']}"
        top_seg = tc
    sev = SEVERITY_CRITICAL if rca.overall_delta_pp <= -3.0 else SEVERITY_ATTENTION
    evidence = (f"SR fell {rca.overall_delta_pp:.2f} pp WoW "
                f"({rca.overall_previous_sr:.2f}% -> {rca.overall_current_sr:.2f}%) "
                f"on {rca.total_volume_current} eligible txns. "
                f"Top contributor: {primary} (share {top_seg['share_of_decline']:.0%})" if top_seg
                else f"SR fell {rca.overall_delta_pp:.2f} pp WoW on {rca.total_volume_current} txns.")
    score = 0.6 + min(0.3, abs(rca.overall_delta_pp) / 20.0)
    if bench.benchmark_status == "VALID":
        score += 0.1
    return Opportunity(
        opportunity_id=f"OP_{uuid.uuid4().hex[:10].upper()}",
        merchant_id=rca.merchant_id, merchant_name=merchant_name,
        opportunity_type="RULE_SR_DECLINE", severity=sev, metric="success_rate",
        current_value=rca.overall_current_sr, previous_value=rca.overall_previous_sr,
        benchmark_value=bench.benchmark_sr, delta=rca.overall_delta_pp,
        gap=bench.gap_pp, affected_volume=rca.total_volume_current,
        primary_dimension=primary, supporting_evidence=evidence,
        recommended_next_step="Investigate the top contributing segment and issuer/error patterns.",
        confidence=_confidence_label(min(score, 1.0)), created_at=_now_iso(),
    )


def _rule_benchmark_gap(bench: BenchmarkResult, rca: RcaResult, s: Settings,
                        merchant_name: str) -> Optional[Opportunity]:
    if bench.benchmark_status != "VALID":
        return None
    if bench.gap_pp is None or bench.gap_pp > -s.opp_benchmark_gap_pp:
        return None
    sev = SEVERITY_CRITICAL if bench.gap_pp <= -3.0 else SEVERITY_OPPORTUNITY
    evidence = (f"Merchant SR {bench.merchant_sr:.2f}% is {bench.gap_pp:.2f} pp below the "
                f"{bench.industry}/{bench.country} industry benchmark {bench.benchmark_sr:.2f}% "
                f"(peers={bench.peer_count}, sample txns={bench.sample_txn_count}).")
    score = 0.5 + min(0.3, abs(bench.gap_pp) / 15.0) + 0.15  # benchmark valid bonus
    return Opportunity(
        opportunity_id=f"OP_{uuid.uuid4().hex[:10].upper()}",
        merchant_id=bench.merchant_id, merchant_name=merchant_name,
        opportunity_type="RULE_BENCHMARK_GAP", severity=sev, metric="success_rate",
        current_value=bench.merchant_sr, previous_value=None,
        benchmark_value=bench.benchmark_sr, delta=None, gap=bench.gap_pp,
        affected_volume=bench.merchant_txn_count,
        primary_dimension=f"industry={bench.industry}",
        supporting_evidence=evidence,
        recommended_next_step="Compare per-method/device SR against peers; prioritise the largest gap.",
        confidence=_confidence_label(min(score, 1.0)), created_at=_now_iso(),
    )


def _rule_error_spike(rca: RcaResult, s: Settings, merchant_name: str) -> Optional[Opportunity]:
    """Fire if an error category's failure share rose >= opp_error_spike_pp."""
    if not rca.contributions:
        return None
    cat = None
    best_delta = 0.0
    for c in rca.contributions:
        if c["dimension"] != "error_category":
            continue
        if c["delta_pp"] is None:
            continue
        if c["delta_pp"] > best_delta and c["delta_pp"] >= s.opp_error_spike_pp:
            best_delta = c["delta_pp"]
            cat = c
    if cat is None:
        return None
    sev = SEVERITY_ATTENTION if best_delta >= s.opp_error_spike_pp else SEVERITY_OPPORTUNITY
    evidence = (f"Error category '{cat['segment']}' failure share rose {cat['delta_pp']:.2f} pp "
                f"({cat['previous_sr']:.2f}% -> {cat['current_sr']:.2f}% of eligible txns).")
    score = 0.55 + min(0.25, best_delta / 10.0)
    return Opportunity(
        opportunity_id=f"OP_{uuid.uuid4().hex[:10].upper()}",
        merchant_id=rca.merchant_id, merchant_name=merchant_name,
        opportunity_type="RULE_ERROR_SPIKE", severity=sev, metric="error_share",
        current_value=cat["current_sr"], previous_value=cat["previous_sr"],
        benchmark_value=None, delta=cat["delta_pp"], gap=None,
        affected_volume=cat["volume_current"],
        primary_dimension=f"error_category={cat['segment']}",
        supporting_evidence=evidence,
        recommended_next_step="Check issuer/network status and recent changes for this error category.",
        confidence=_confidence_label(min(score, 1.0)), created_at=_now_iso(),
    )


def _rule_concentrated_segment(rca: RcaResult, s: Settings, merchant_name: str) -> Optional[Opportunity]:
    """Fire if a single segment explains >= opp_concentrated_share of the decline."""
    if rca.overall_delta_pp is None or rca.overall_delta_pp >= 0:
        return None
    if not rca.top_contributors:
        return None
    tc = rca.top_contributors[0]
    if tc["share_of_decline"] < s.opp_concentrated_share:
        return None
    sev = SEVERITY_ATTENTION if tc["share_of_decline"] >= 0.5 else SEVERITY_OPPORTUNITY
    evidence = (f"Segment {tc['dimension']}={tc['segment']} explains "
                f"{tc['share_of_decline']:.0%} of the observed SR decline "
                f"(segment SR {tc['previous_sr']:.2f}% -> {tc['current_sr']:.2f}%, "
                f"delta {tc['delta_pp']:.2f} pp).")
    score = 0.6 + min(0.25, tc["share_of_decline"])
    return Opportunity(
        opportunity_id=f"OP_{uuid.uuid4().hex[:10].upper()}",
        merchant_id=rca.merchant_id, merchant_name=merchant_name,
        opportunity_type="RULE_CONCENTRATED_SEGMENT", severity=sev, metric="success_rate",
        current_value=tc["current_sr"], previous_value=tc["previous_sr"],
        benchmark_value=None, delta=tc["delta_pp"], gap=None,
        affected_volume=tc["volume_current"],
        primary_dimension=f"{tc['dimension']}={tc['segment']}",
        supporting_evidence=evidence,
        recommended_next_step=(f"Focus investigation on {tc['dimension']}={tc['segment']} "
                               f"and its issuer/error sub-segments."),
        confidence=_confidence_label(min(score, 1.0)), created_at=_now_iso(),
    )


def detect_opportunities(settings: Optional[Settings] = None) -> List[Opportunity]:
    """Run all rules for all merchants over the latest 2-week vs prior 2-week window."""
    s = settings or get_settings()
    cur_s, cur_e, prv_s, prv_e = _latest_two_weeks(s)
    merchants = query_df("SELECT merchant_id FROM stg_merchants ORDER BY merchant_id",
                         settings=s)
    opps: List[Opportunity] = []

    for mid in merchants["merchant_id"].tolist():
        name = _merchant_name(mid, s)
        try:
            rca = run_rca(mid, cur_s, cur_e, prv_s, prv_e, settings=s)
            bench = benchmark_merchant(mid, start_date=cur_s, end_date=cur_e,
                                       payment_method="ALL", settings=s)
        except Exception:
            continue

        for rule_fn in (_rule_sr_decline, _rule_benchmark_gap, _rule_error_spike,
                        _rule_concentrated_segment):
            try:
                # each rule has a different signature
                if rule_fn is _rule_benchmark_gap:
                    o = rule_fn(bench, rca, s, name)
                elif rule_fn is _rule_error_spike or rule_fn is _rule_concentrated_segment:
                    o = rule_fn(rca, s, name)
                else:
                    o = rule_fn(rca, bench, s, name)
            except Exception:
                o = None
            if o is not None:
                opps.append(o)

    return opps


def opportunities_to_df(opps: List[Opportunity]) -> pd.DataFrame:
    if not opps:
        return pd.DataFrame(columns=list(Opportunity.__dataclass_fields__.keys()))
    return pd.DataFrame([asdict(o) for o in opps])


def store_opportunities(opps: List[Opportunity], settings: Optional[Settings] = None) -> None:
    """Persist opportunities to the opportunity_candidates table (overwrite)."""
    s = settings or get_settings()
    from src.common.db import connect
    df = opportunities_to_df(opps)
    con = connect(s)
    try:
        con.execute("DROP TABLE IF EXISTS opportunities_final")
        con.register("opp_df", df)
        con.execute("CREATE TABLE opportunities_final AS SELECT * FROM opp_df")
        con.unregister("opp_df")
    finally:
        con.close()


def load_opportunities_df(settings: Optional[Settings] = None) -> pd.DataFrame:
    """Read persisted opportunities from DuckDB; regenerate+persist if missing.

    Converts NaN -> None for JSON safety.
    """
    import numpy as np
    s = settings or get_settings()
    from src.common.queries import list_tables
    tables = list_tables(s)
    if "opportunities_final" not in tables:
        opps = detect_opportunities(settings=s)
        store_opportunities(opps, settings=s)
    df = query_df("SELECT * FROM opportunities_final", settings=s)
    df = df.replace({np.nan: None, pd.NA: None, float("nan"): None})
    return df
