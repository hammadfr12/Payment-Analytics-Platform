"""Root-Cause-Analysis (contribution decomposition) engine.

Compares a CURRENT vs PREVIOUS period for a merchant and decomposes the
overall SR movement into contributions by dimension. For every dimension
value we compute:

  current_metric, previous_metric, delta (pp),
  volume_current, volume_previous,
  contribution  (share of the *merchant's total* SR movement attributable
                 to this segment, combining volume weight and rate movement).

Methodology (documented in docs/rca_methodology.md):
  overall_delta = current_SR - previous_SR            (merchant level)
  For a segment s with share w_s = vol_s / total_vol (within each period),
  the segment's contribution to overall_delta is approximated by the
  *mix-adjusted rate effect*:

      contribution_s = w_s_prev * (SR_s_current - SR_s_previous)

  summed across all segments of a dimension ~= overall_delta (to the extent
  the mix is stable). We also report the pure mix effect separately when
  useful. This is a decomposition heuristic, NOT causal inference.

Language: we use "contributor", "associated movement", "concentrated decline",
"observed pattern" — never "caused by" / "root cause" unless causal evidence
exists (it does not, here).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

import pandas as pd

from src.common.queries import query_df
from src.config.settings import Settings, get_settings


DIMENSIONS = [
    "payment_method",
    "payment_type",
    "card_type",
    "issuer_bank",
    "device",
    "platform",
    "error_category",
    "industry",
    "mcc",
    "country",
]


@dataclass
class SegmentContribution:
    dimension: str
    segment: str
    current_sr: Optional[float]
    previous_sr: Optional[float]
    delta_pp: Optional[float]
    volume_current: int
    volume_previous: int
    contribution: float          # pp of overall movement attributable here
    share_of_decline: float      # contribution / sum(abs(contribution)) for the dim
    sample_warning: Optional[str]


@dataclass
class RcaResult:
    merchant_id: str
    current_period_start: str
    current_period_end: str
    previous_period_start: str
    previous_period_end: str
    overall_current_sr: Optional[float]
    overall_previous_sr: Optional[float]
    overall_delta_pp: Optional[float]
    total_volume_current: int
    total_volume_previous: int
    contributions: List[dict]   # list of SegmentContribution asdict
    top_contributors: List[dict]
    language_note: str


LANGUAGE_NOTE = (
    "Contributions describe association, not causation. A segment listed as a "
    "'major contributor' moved in the same direction as the overall metric and "
    "explains a material share of the observed movement; it is not asserted to "
    "be the cause. Investigate further before acting."
)


def _segment_sr(df: pd.DataFrame, dim_col: str) -> pd.DataFrame:
    """Per-segment eligible/authorized counts and SR for the given dimension."""
    if dim_col not in df.columns:
        return pd.DataFrame()
    g = df.groupby(dim_col).agg(
        eligible=("is_eligible", "sum"),
        authorized=("is_authorized", "sum"),
    ).reset_index()
    g["sr"] = g.apply(
        lambda r: (100.0 * r["authorized"] / r["eligible"]) if r["eligible"] > 0 else None,
        axis=1,
    )
    return g


def _segment_error_rate(df: pd.DataFrame, dim_col: str) -> pd.DataFrame:
    """For the error_category dimension: per-category failure volume & failure share.

    Metric = failure share % = (failures in this category) / (total eligible
    transactions across ALL categories) * 100. This captures how much of the
    merchant's overall payment population is being lost to each error category,
    so a spike in a category shows up as a rising failure share and a negative
    contribution to overall SR.
    """
    if dim_col not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df["is_failed"] = (~df["is_authorized"]) & df["is_eligible"]
    df[dim_col] = df[dim_col].fillna("No Error")
    total_elig = int(df["is_eligible"].sum())
    g = df.groupby(dim_col).agg(
        eligible=("is_eligible", "sum"),
        failed=("is_failed", "sum"),
    ).reset_index()
    g["authorized"] = g["eligible"] - g["failed"]
    # failure share = category failures / total eligible * 100
    g["sr"] = g.apply(
        lambda r: (100.0 * r["failed"] / total_elig) if total_elig > 0 else None,
        axis=1,
    )
    return g


def run_rca(
    merchant_id: str,
    current_start: str,
    current_end: str,
    previous_start: str,
    previous_end: str,
    settings: Optional[Settings] = None,
) -> RcaResult:
    """Run RCA for one merchant across the 10 required dimensions."""
    s = settings or get_settings()

    base_sql = """
        SELECT payment_method, payment_type, card_type, issuer_bank,
               device, platform, industry, mcc, txn_country AS country,
               error_code,
               is_eligible, is_authorized
        FROM fct_payment_performance
        WHERE merchant_id = ? AND is_eligible = TRUE
          AND event_date BETWEEN ? AND ?
    """
    # fetch current + previous via positional params
    from src.common.db import connect
    ccon = connect(s, read_only=True)
    try:
        cur_df = ccon.execute(base_sql, [merchant_id, current_start, current_end]).df()
        prev_df = ccon.execute(base_sql, [merchant_id, previous_start, previous_end]).df()
    finally:
        ccon.close()

    # error_category: join via dim_error_codes
    def add_err_cat(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            df["error_category"] = pd.Series(dtype=object)
            return df
        ec = query_df("SELECT error_code, error_category FROM dim_error_codes", settings=s)
        return df.merge(ec, on="error_code", how="left")

    cur_df = add_err_cat(cur_df)
    prev_df = add_err_cat(prev_df)

    overall_cur = (100.0 * cur_df["is_authorized"].sum() / cur_df["is_eligible"].sum()) \
        if cur_df["is_eligible"].sum() > 0 else None
    overall_prev = (100.0 * prev_df["is_authorized"].sum() / prev_df["is_eligible"].sum()) \
        if prev_df["is_eligible"].sum() > 0 else None
    overall_delta = (overall_cur - overall_prev) if (overall_cur is not None and overall_prev is not None) else None

    total_vol_cur = int(cur_df["is_eligible"].sum())
    total_vol_prev = int(prev_df["is_eligible"].sum())

    all_contribs: List[dict] = []

    for dim in DIMENSIONS:
        col = dim
        is_error_dim = dim == "error_category"
        if is_error_dim:
            cg = _segment_error_rate(cur_df, col)
            pg = _segment_error_rate(prev_df, col)
        else:
            cg = _segment_sr(cur_df, col)
            pg = _segment_sr(prev_df, col)
        if cg.empty and pg.empty:
            continue
        merged = pg.merge(cg, on=col, how="outer", suffixes=("_prev", "_cur")).fillna(0)
        for _, r in merged.iterrows():
            seg = str(r[col]) if r[col] is not None and r[col] != "" else "UNKNOWN"
            vol_cur = int(r["eligible_cur"])
            vol_prev = int(r["eligible_prev"])
            if is_error_dim:
                # metric = failure share (%) of total eligible; delta = increase
                # in failure share. contribution to SR = -(delta) since more
                # failures reduce overall SR directly.
                sr_cur = r["sr_cur"] if "sr_cur" in r and pd.notna(r["sr_cur"]) else None
                sr_prev = r["sr_prev"] if "sr_prev" in r and pd.notna(r["sr_prev"]) else None
                delta = (sr_cur - sr_prev) if (sr_cur is not None and sr_prev is not None) else None
                contribution = -delta if delta is not None else 0.0
            else:
                sr_cur = (100.0 * r["authorized_cur"] / r["eligible_cur"]) if r["eligible_cur"] > 0 else None
                sr_prev = (100.0 * r["authorized_prev"] / r["eligible_prev"]) if r["eligible_prev"] > 0 else None
                delta = (sr_cur - sr_prev) if (sr_cur is not None and sr_prev is not None) else None
                w_prev = (vol_prev / total_vol_prev) if total_vol_prev > 0 else 0.0
                contribution = w_prev * delta if delta is not None else 0.0
            warn = None
            if vol_cur < 50 or vol_prev < 50:
                warn = "low_sample(<50 txns in one period)"
            metric_label = "failure_rate_pct" if is_error_dim else "success_rate_pct"
            all_contribs.append(asdict(SegmentContribution(
                dimension=dim, segment=seg, current_sr=sr_cur, previous_sr=sr_prev,
                delta_pp=delta, volume_current=vol_cur, volume_previous=vol_prev,
                contribution=contribution, share_of_decline=0.0, sample_warning=warn,
            )))

    # share_of_decline within each dimension = |contribution| / sum(|contributions|) for that dim
    contrib_df = pd.DataFrame(all_contribs)
    if not contrib_df.empty:
        abs_sums = contrib_df.groupby("dimension")["contribution"].transform(lambda x: x.abs().sum())
        contrib_df["share_of_decline"] = contrib_df["contribution"].abs().where(abs_sums > 0, 0) / abs_sums.where(abs_sums > 0, 1)
        all_contribs = contrib_df.to_dict(orient="records")

    # top contributors: segments whose contribution moves in the SAME direction
    # as the overall delta, ranked by absolute contribution magnitude.
    # Exclude dimensions that have only ONE distinct value for this merchant
    # (country/mcc/industry are constants per merchant and just echo the total).
    if not contrib_df.empty and overall_delta is not None:
        direction = -1 if overall_delta < 0 else 1
        # drop single-valued dimensions
        dim_counts = contrib_df.groupby("dimension")["segment"].nunique()
        multi_dims = dim_counts[dim_counts > 1].index.tolist()
        contrib_df_multi = contrib_df[contrib_df["dimension"].isin(multi_dims)].copy()
        same_dir = contrib_df_multi[
            ((direction < 0) & (contrib_df_multi["contribution"] < 0)) |
            ((direction > 0) & (contrib_df_multi["contribution"] > 0))
        ].copy()
        if same_dir.empty:
            same_dir = contrib_df_multi.copy()
        same_dir["abs_contrib"] = same_dir["contribution"].abs()
        top = same_dir.sort_values("abs_contrib", ascending=False).head(10)
        top_contributors = top.to_dict(orient="records")
    else:
        top_contributors = []

    return RcaResult(
        merchant_id=merchant_id,
        current_period_start=current_start, current_period_end=current_end,
        previous_period_start=previous_start, previous_period_end=previous_end,
        overall_current_sr=overall_cur, overall_previous_sr=overall_prev,
        overall_delta_pp=overall_delta,
        total_volume_current=total_vol_cur, total_volume_previous=total_vol_prev,
        contributions=all_contribs, top_contributors=top_contributors,
        language_note=LANGUAGE_NOTE,
    )
