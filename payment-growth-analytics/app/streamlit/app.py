"""Streamlit reference application for the Payment Growth Analytics Platform.

Six tabs: Overview, Merchant Performance, Benchmarking, RCA Explorer,
Opportunity Center, Data Quality. All numbers come from DuckDB via the shared
query helpers — nothing is hard-coded.
"""
from __future__ import annotations

import numbers

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.common.queries import query_df
from src.config.settings import get_settings
from src.analytics.benchmark import benchmark_merchant
from src.opportunities.engine import _latest_two_weeks
from src.rca.engine import run_rca

st.set_page_config(page_title="Payment Growth Analytics", page_icon="💳",
                   layout="wide")

# --- Shared look & feel ---
PALETTE = {"primary": "#5B2C91", "accent": "#FF6B35", "good": "#1A936F",
           "bad": "#C44536", "neutral": "#6C757D", "bg": "#F7F7FB"}
TITLE = "Payment Growth Analytics Platform"
SUBTITLE = "Synthetic/demo data • Decision-support product • Monitor → Benchmark → Diagnose → Act"


@st.cache_data(ttl=60)
def _settings():
    return get_settings()


@st.cache_data(ttl=60)
def _merchants_df():
    return query_df("SELECT merchant_id, merchant_name, industry FROM stg_merchants ORDER BY merchant_name")


@st.cache_data(ttl=60)
def _default_dates():
    s = _settings()
    df = query_df("SELECT MAX(event_date) AS maxd, MIN(event_date) AS mind "
                  "FROM fct_payment_performance", settings=s)
    return str(df.iloc[0]["mind"])[:10], str(df.iloc[0]["maxd"])[:10]


def _kpi_card(label, value, sub=None, color=PALETTE["primary"]):
    """Render a compact KPI card. Counts get thousands separators, not decimals."""
    if value is None:
        val_str = "—"
    elif isinstance(value, bool):
        val_str = str(value)
    elif isinstance(value, numbers.Integral):
        val_str = f"{int(value):,}"
    elif isinstance(value, numbers.Real):
        val_str = f"{float(value):,.2f}"
    else:
        val_str = str(value)
    # Long values (e.g. 1,155,150) shrink so they stay on one line inside the card.
    size = 26 if len(val_str) <= 8 else 21
    st.markdown(
        f"""<div style='border:1px solid #E0E0E0;border-radius:10px;padding:14px 16px;
        background:white;overflow:hidden;'>
        <div style='color:{color};font-size:12px;font-weight:600;text-transform:uppercase;
        letter-spacing:.4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>{label}</div>
        <div style='font-size:{size}px;font-weight:700;color:#1A1A2E;margin-top:6px;
        white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>{val_str}</div>
        <div style='color:#888;font-size:11px;margin-top:2px;white-space:nowrap;overflow:hidden;
        text-overflow:ellipsis;'>{sub or ''}</div></div>""",
        unsafe_allow_html=True,
    )


def _trend_df(grain="week", merchant_id=None, start=None, end=None):
    s = _settings()
    period_col = "event_date" if grain == "day" else "week_start"
    m = f"AND merchant_id = '{merchant_id}'" if merchant_id else ""
    return query_df(f"""
        SELECT {period_col} AS period,
               SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END) AS auth,
               SUM(CASE WHEN is_eligible   THEN 1 ELSE 0 END) AS elig,
               SUM(CASE WHEN is_eligible   THEN amount ELSE 0 END) AS tpv
        FROM fct_payment_performance
        WHERE is_eligible = TRUE
          AND event_date >= '{start}' AND event_date <= '{end}' {m}
        GROUP BY {period_col} ORDER BY {period_col}
    """, settings=s)


def _style_fig(fig):
    fig.update_layout(
        font=dict(family="Inter, system-ui, sans-serif", size=13, color="#1A1A2E"),
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", y=-0.2),
    )
    fig.update_xaxes(gridcolor="#EEE", zeroline=False)
    fig.update_yaxes(gridcolor="#EEE", zeroline=False)
    return fig


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(f"### 💳 {TITLE}")
    st.caption(SUBTITLE)
    s = _settings()
    dmin, dmax = _default_dates()
    start = st.date_input("Start date", pd.to_datetime(dmin))
    end = st.date_input("End date", pd.to_datetime(dmax))
    st.caption(f"Seed: {s.random_seed} • Merchants: {s.n_merchants}")
    st.divider()
    st.caption("All data is **synthetic**. See `docs/` for methodology.")

start_s, end_s = str(start), str(end)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tabs = st.tabs(["Overview", "Merchant Performance", "Benchmarking",
                "RCA Explorer", "Opportunity Center", "Data Quality"])

# --- Overview ---
with tabs[0]:
    st.header("Overview")
    df = query_df(f"""
        SELECT
          SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END) AS auth,
          SUM(CASE WHEN is_eligible   THEN 1 ELSE 0 END) AS elig,
          SUM(CASE WHEN is_failed     THEN 1 ELSE 0 END) AS fail,
          SUM(CASE WHEN is_eligible   THEN amount ELSE 0 END) AS tpv,
          SUM(CASE WHEN is_authorized THEN amount ELSE 0 END) AS suc_tpv,
          COUNT(DISTINCT transaction_id) AS txn
        FROM fct_payment_performance
        WHERE is_eligible = TRUE AND event_date >= '{start_s}' AND event_date <= '{end_s}'
    """, settings=s)
    r = df.iloc[0]
    auth, elig, fail = int(r["auth"]), int(r["elig"]), int(r["fail"])
    sr = 100.0 * auth / elig if elig else None
    fr = 100.0 * fail / elig if elig else None
    aov = float(r["suc_tpv"]) / auth if auth else None
    cc = query_df(f"""
        SELECT COUNT(DISTINCT checkout_session_id) AS started,
               COUNT(DISTINCT CASE WHEN success THEN checkout_session_id END) AS succ
        FROM fct_checkout_conversion
        WHERE session_date >= '{start_s}' AND session_date <= '{end_s}'
    """, settings=s)
    conv = 100.0 * int(cc.iloc[0]["succ"]) / int(cc.iloc[0]["started"]) if int(cc.iloc[0]["started"]) else None

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: _kpi_card("Success Rate", round(sr, 2), "% authorized/eligible", PALETTE["primary"])
    with c2: _kpi_card("TPV", round(float(r["tpv"]) / 1e7, 2), "₹ Cr (synthetic)", PALETTE["accent"])
    with c3: _kpi_card("Transactions", int(r["txn"]), "eligible", PALETTE["neutral"])
    with c4: _kpi_card("AOV", round(aov, 2), "₹ per success", PALETTE["good"])
    with c5: _kpi_card("Checkout Conv.", round(conv, 2), "% sessions", PALETTE["primary"])
    with c6: _kpi_card("Failure Rate", round(fr, 2), "% failed/eligible", PALETTE["bad"])

    tdf = _trend_df("week", None, start_s, end_s)
    tdf["sr"] = 100.0 * tdf["auth"] / tdf["elig"].replace(0, pd.NA)
    st.subheader("SR & TPV Trend")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tdf["period"], y=tdf["sr"], name="SR %",
                             line=dict(color=PALETTE["primary"], width=3)))
    fig.add_trace(go.Scatter(x=tdf["period"], y=tdf["tpv"] / 1e7, name="TPV (₹ Cr)",
                             yaxis="y2", line=dict(color=PALETTE["accent"], width=2, dash="dot")))
    fig.update_layout(yaxis=dict(title="SR %"), yaxis2=dict(title="TPV ₹ Cr", overlaying="y", side="right"))
    st.plotly_chart(_style_fig(fig), width="stretch")

    # payment method mix
    pm = query_df(f"""
        SELECT payment_method,
               SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END) AS auth,
               SUM(CASE WHEN is_eligible   THEN 1 ELSE 0 END) AS elig,
               SUM(CASE WHEN is_eligible THEN amount ELSE 0 END) AS tpv
        FROM fct_payment_performance
        WHERE is_eligible = TRUE AND event_date >= '{start_s}' AND event_date <= '{end_s}'
        GROUP BY payment_method
    """, settings=s)
    fig2 = px.pie(pm, values="tpv", names="payment_method", title="Payment Method Mix (TPV share)",
                  color_discrete_sequence=px.colors.qualitative.Pastel)
    st.plotly_chart(_style_fig(fig2), width="stretch")

    # top opportunities
    from src.opportunities.engine import load_opportunities_df
    opps = load_opportunities_df(s)
    if not opps.empty:
        st.subheader("Top Opportunities")
        top = opps.sort_values("affected_volume", ascending=False).head(5)
        st.dataframe(top[["opportunity_id", "merchant_name", "opportunity_type",
                          "severity", "delta", "gap", "primary_dimension"]],
                     width="stretch", hide_index=True)


# --- Merchant Performance ---
with tabs[1]:
    st.header("Merchant Performance")
    mdf = _merchants_df()
    mid = st.selectbox("Select merchant", mdf["merchant_id"],
                       format_func=lambda x: f"{mdf.loc[mdf['merchant_id']==x,'merchant_name'].iloc[0]} ({x})")
    mrow = mdf[mdf["merchant_id"] == mid].iloc[0]
    st.caption(f"Industry: {mrow['industry']}")

    mdfx = query_df(f"""
        SELECT SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END) AS auth,
               SUM(CASE WHEN is_eligible   THEN 1 ELSE 0 END) AS elig,
               SUM(CASE WHEN is_authorized THEN amount ELSE 0 END) AS suc_tpv,
               SUM(CASE WHEN is_eligible   THEN amount ELSE 0 END) AS tpv,
               COUNT(DISTINCT transaction_id) AS txn
        FROM fct_payment_performance
        WHERE merchant_id='{mid}' AND is_eligible=TRUE
          AND event_date>='{start_s}' AND event_date<='{end_s}'
    """, settings=s)
    rr = mdfx.iloc[0]
    a, e = int(rr["auth"]), int(rr["elig"])
    msr = 100.0 * a / e if e else None
    maov = float(rr["suc_tpv"]) / a if a else None
    b = benchmark_merchant(mid, start_date=start_s, end_date=end_s, settings=s)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: _kpi_card("SR", round(msr, 2), "%", PALETTE["primary"])
    with c2: _kpi_card("TPV", round(float(rr["tpv"]) / 1e7, 2), "₹ Cr", PALETTE["accent"])
    with c3: _kpi_card("AOV", round(maov, 2), "₹", PALETTE["good"])
    with c4: _kpi_card("Benchmark SR", round(b.benchmark_sr, 2) if b.benchmark_sr else None,
                       f"{b.peer_count} peers", PALETTE["neutral"])
    with c5: _kpi_card("Gap", round(b.gap_pp, 2) if b.gap_pp else 0.0,
                       f"{b.benchmark_status}", PALETTE["bad"] if b.gap_pp and b.gap_pp < 0 else PALETTE["good"])

    mtdf = _trend_df("week", mid, start_s, end_s)
    if not mtdf.empty:
        mtdf["sr"] = 100.0 * mtdf["auth"] / mtdf["elig"].replace(0, pd.NA)
        st.subheader("SR Trend")
        fig = px.line(mtdf, x="period", y="sr", markers=True,
                      color_discrete_sequence=[PALETTE["primary"]])
        st.plotly_chart(_style_fig(fig), width="stretch")

    # payment method table
    pm = query_df(f"""
        SELECT payment_method,
               SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END) AS auth,
               SUM(CASE WHEN is_eligible   THEN 1 ELSE 0 END) AS elig,
               SUM(CASE WHEN is_eligible THEN amount ELSE 0 END) AS tpv
        FROM fct_payment_performance
        WHERE merchant_id='{mid}' AND is_eligible=TRUE
          AND event_date>='{start_s}' AND event_date<='{end_s}'
        GROUP BY payment_method
    """, settings=s)
    pm["success_rate"] = 100.0 * pm["auth"] / pm["elig"].replace(0, pd.NA)
    pm["share_pct"] = 100.0 * pm["tpv"] / pm["tpv"].sum()
    st.subheader("Payment Method Breakdown")
    st.dataframe(pm[["payment_method", "success_rate", "tpv", "share_pct", "auth", "elig"]],
                 width="stretch", hide_index=True)

    # device/platform
    dev = query_df(f"""
        SELECT device, platform,
               SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END) AS auth,
               SUM(CASE WHEN is_eligible   THEN 1 ELSE 0 END) AS elig
        FROM fct_payment_performance
        WHERE merchant_id='{mid}' AND is_eligible=TRUE
          AND event_date>='{start_s}' AND event_date<='{end_s}'
        GROUP BY device, platform
    """, settings=s)
    dev["sr"] = 100.0 * dev["auth"] / dev["elig"].replace(0, pd.NA)
    fig = px.bar(dev, x="device", y="sr", color="platform", barmode="group",
                 color_discrete_sequence=px.colors.qualitative.Pastel)
    st.plotly_chart(_style_fig(fig), width="stretch")


# --- Benchmarking ---
with tabs[2]:
    st.header("Benchmarking")
    mdf = _merchants_df()
    bmid = st.selectbox("Merchant", mdf["merchant_id"], key="bm_mid",
                        format_func=lambda x: f"{mdf.loc[mdf['merchant_id']==x,'merchant_name'].iloc[0]} ({x})")
    b = benchmark_merchant(bmid, start_date=start_s, end_date=end_s, settings=s)
    c1, c2, c3, c4 = st.columns(4)
    with c1: _kpi_card("Merchant SR", round(b.merchant_sr, 2) if b.merchant_sr else None, "%", PALETTE["primary"])
    with c2: _kpi_card("Benchmark SR", round(b.benchmark_sr, 2) if b.benchmark_sr else None, "%", PALETTE["neutral"])
    with c3: _kpi_card("Gap", round(b.gap_pp, 2) if b.gap_pp else 0.0, "pp", PALETTE["bad"] if b.gap_pp and b.gap_pp < 0 else PALETTE["good"])
    with c4: _kpi_card("Peers", b.peer_count, f"sample {b.sample_txn_count:,}", PALETTE["neutral"])

    st.info(f"**Methodology:** {b.methodology}")
    st.caption(f"Status: **{b.benchmark_status}** • Industry: {b.industry} • Country: {b.country}")

    # all-merchant benchmark scatter
    allb = []
    for x in mdf["merchant_id"].tolist():
        try:
            allb.append(benchmark_merchant(x, start_date=start_s, end_date=end_s, settings=s))
        except Exception:
            pass
    import dataclasses
    ab = pd.DataFrame([dataclasses.asdict(x) for x in allb])
    fig = px.scatter(ab, x="benchmark_sr", y="merchant_sr", color="industry",
                     hover_name="merchant_id", title="Merchant SR vs Industry Benchmark")
    fig.add_shape(type="line", x0=ab["benchmark_sr"].min(), y0=ab["benchmark_sr"].min(),
                  x1=ab["benchmark_sr"].max(), y1=ab["benchmark_sr"].max(),
                  line=dict(color="#CCC", dash="dash"))
    st.plotly_chart(_style_fig(fig), width="stretch")


# --- RCA Explorer ---
with tabs[3]:
    st.header("RCA Explorer")
    mdf = _merchants_df()
    rmid = st.selectbox("Merchant", mdf["merchant_id"], key="rca_mid",
                        format_func=lambda x: f"{mdf.loc[mdf['merchant_id']==x,'merchant_name'].iloc[0]} ({x})")
    cs, ce, ps, pe = _latest_two_weeks(s)
    st.caption(f"Current: {cs} → {ce}  •  Previous: {ps} → {pe}")
    try:
        rca = run_rca(rmid, cs, ce, ps, pe, settings=s)
    except Exception as e:
        st.error(f"RCA failed: {e}")
        rca = None
    if rca:
        c1, c2, c3 = st.columns(3)
        with c1: _kpi_card("Previous SR", round(rca.overall_previous_sr, 2) if rca.overall_previous_sr else None, "%", PALETTE["neutral"])
        with c2: _kpi_card("Current SR", round(rca.overall_current_sr, 2) if rca.overall_current_sr else None, "%", PALETTE["primary"])
        with c3: _kpi_card("Delta", round(rca.overall_delta_pp, 2) if rca.overall_delta_pp else None, "pp", PALETTE["bad"] if rca.overall_delta_pp and rca.overall_delta_pp < 0 else PALETTE["good"])
        st.info(rca.language_note)

        cdf = pd.DataFrame(rca.top_contributors)
        if not cdf.empty:
            st.subheader("Top Contributors")
            # The stored field is `share_of_decline`, but the same math applies to an
            # improvement; label the axis by the direction actually observed.
            direction = "decline" if (rca.overall_delta_pp or 0) < 0 else "movement"
            fig = px.bar(cdf.sort_values("contribution"), x="contribution",
                         y=[f"{d}={s}" for d, s in zip(cdf["dimension"], cdf["segment"])],
                         orientation="h", color="share_of_decline",
                         color_continuous_scale="Viridis",
                         labels={"y": "segment", "contribution": "contribution (pp)",
                                 "share_of_decline": f"share of {direction}"})
            st.plotly_chart(_style_fig(fig), width="stretch")
            st.dataframe(cdf[["dimension", "segment", "previous_sr", "current_sr",
                              "delta_pp", "contribution", "share_of_decline",
                              "volume_current"]],
                         width="stretch", hide_index=True)


# --- Opportunity Center ---
with tabs[4]:
    st.header("Opportunity Center")
    from src.opportunities.engine import load_opportunities_df
    opps = load_opportunities_df(s)
    f1, f2, f3 = st.columns(3)
    sev = f1.selectbox("Severity", ["All", "Critical", "Attention", "Opportunity"])
    otype = f2.selectbox("Type", ["All"] + sorted(opps["opportunity_type"].unique().tolist()) if not opps.empty else ["All"])
    ind = f3.selectbox("Industry", ["All"] + sorted(opps.merge(mdf, on="merchant_id")["industry"].unique().tolist()) if not opps.empty else ["All"])
    fodf = opps.copy()
    if sev != "All": fodf = fodf[fodf["severity"] == sev]
    if otype != "All": fodf = fodf[fodf["opportunity_type"] == otype]
    if ind != "All":
        fodf = fodf.merge(mdf[["merchant_id", "industry"]], on="merchant_id")
        fodf = fodf[fodf["industry"] == ind]
    st.caption(f"{len(fodf)} opportunities")
    for _, o in fodf.head(20).iterrows():
        col = PALETTE["bad"] if o["severity"] == "Critical" else (PALETTE["accent"] if o["severity"] == "Attention" else PALETTE["good"])
        with st.container(border=True):
            mc1, mc2 = st.columns([3, 1])
            with mc1:
                st.markdown(f"**{o['merchant_name']}** • `{o['opportunity_type']}`")
                st.caption(o["supporting_evidence"])
                st.markdown(f"**Next step:** {o['recommended_next_step']}")
            with mc2:
                st.markdown(
                    f"<div style='color:{col};font-weight:700;font-size:17px;'>{o['severity']}</div>"
                    f"<div style='color:#888;font-size:12px;margin-bottom:8px;'>"
                    f"confidence: {o['confidence']}</div>",
                    unsafe_allow_html=True,
                )
                measures = []
                if o.get("delta") is not None:
                    measures.append(f"**Delta** {o['delta']:.2f} pp")
                if o.get("gap") is not None:
                    measures.append(f"**Gap** {o['gap']:.2f} pp")
                if measures:
                    st.markdown("  \n".join(measures))


# --- Data Quality ---
with tabs[5]:
    st.header("Data Quality")
    dq = query_df("""
        SELECT
          (SELECT COUNT(*) FROM raw_payment_transactions) AS raw_txns,
          (SELECT COUNT(*) FROM stg_merchants) AS merchants,
          (SELECT COUNT(DISTINCT transaction_id) FROM fct_payment_performance) AS distinct_txns,
          (SELECT COUNT(*) FROM fct_payment_performance WHERE merchant_id IS NULL) AS null_merchant,
          (SELECT COUNT(*) FROM fct_payment_performance WHERE is_eligible=TRUE AND amount<=0) AS nonpos_amount,
          (SELECT COUNT(*) FROM stg_checkout_events WHERE merchant_id NOT IN (SELECT merchant_id FROM stg_merchants)) AS orphan_checkout
    """, settings=s)
    r = dq.iloc[0]
    c1, c2, c3 = st.columns(3)
    with c1: _kpi_card("Raw Transactions", int(r["raw_txns"]), "rows", PALETTE["primary"])
    with c2: _kpi_card("Distinct Txn IDs", int(r["distinct_txns"]), "uniqueness", PALETTE["good"])
    with c3: _kpi_card("Merchants", int(r["merchants"]), "dimension", PALETTE["neutral"])
    c1, c2, c3 = st.columns(3)
    with c1: _kpi_card("Null Merchants", int(r["null_merchant"]), "violations", PALETTE["bad"])
    with c2: _kpi_card("Non-positive Amounts", int(r["nonpos_amount"]), "violations", PALETTE["bad"])
    with c3: _kpi_card("Orphan Checkout", int(r["orphan_checkout"]), "violations", PALETTE["bad"])
    st.success("All data-quality checks passing for synthetic dataset." if int(r["null_merchant"]) == 0 and int(r["nonpos_amount"]) == 0 else "Data-quality issues detected.")
