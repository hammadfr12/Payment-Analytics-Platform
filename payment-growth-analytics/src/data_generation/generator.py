"""Deterministic synthetic payment data generator.

Produces:
  - merchants               (dimension)
  - payment_transactions    (fact)
  - checkout_events         (fact, funnel)
  - error_codes             (dimension)
  - payment_methods         (dimension)
  - calendar                (dimension, derived from txn range)

Five controlled scenarios are injected so the RCA / opportunity engines and
regression tests have ground truth to find:

  S1  NOVA_FASHION (E-commerce)   3-5 pp SR decline in the final 2 weeks
  S2  Android + Debit Card        deteriorates for NOVA in the final 2 weeks
  S3  One issuer (HDFC)           error spike on NOVA in the final 2 weeks
  S4  BUDGET_GROCERY (Grocery)    consistently 3-4 pp below its industry
  S5  SWIFT_TRAVEL (Travel)       unusually strong SR improvement (+3 pp)

All randomness is seeded for reproducibility. Output is Parquet under data/raw.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from src.common.logging import log
from src.config.settings import Settings, get_settings


# ---------------------------------------------------------------------------
# Reference vocabularies & error catalog
# ---------------------------------------------------------------------------

ERROR_CATALOG: List[Dict] = [
    # (error_code, error_category, description, owner_team, base_rate)
    {"error_code": "E001", "error_category": "Issuer Decline",   "description": "Do not honour",                "owner_team": "Issuer",   "base_rate": 0.30},
    {"error_code": "E002", "error_category": "Issuer Decline",   "description": "Insufficient funds",           "owner_team": "Issuer",   "base_rate": 0.18},
    {"error_code": "E003", "error_category": "Network",          "description": "Network timeout",             "owner_team": "Network",  "base_rate": 0.12},
    {"error_code": "E004", "error_category": "Network",          "description": "Gateway unreachable",         "owner_team": "Network",  "base_rate": 0.06},
    {"error_code": "E005", "error_category": "Authentication",   "description": "Invalid card",                "owner_team": "Risk",     "base_rate": 0.10},
    {"error_code": "E006", "error_category": "Authentication",   "description": "3DS authentication failed",   "owner_team": "Risk",     "base_rate": 0.08},
    {"error_code": "E007", "error_category": "Risk Block",       "description": "Fraud suspected",             "owner_team": "Risk",     "base_rate": 0.05},
    {"error_code": "E008", "error_category": "Risk Block",       "description": "Velocity check failed",       "owner_team": "Risk",     "base_rate": 0.04},
    {"error_code": "E009", "error_category": "System",           "description": "Down for maintenance",        "owner_team": "Platform", "base_rate": 0.03},
    {"error_code": "E010", "error_category": "System",           "description": "Internal error",             "owner_team": "Platform", "base_rate": 0.02},
    {"error_code": "E011", "error_category": "User Drop-off",    "description": "User abandoned",              "owner_team": "Checkout", "base_rate": 0.01},
    {"error_code": "E012", "error_category": "Issuer Decline",   "description": "Exceeds withdrawal limit",    "owner_team": "Issuer",   "base_rate": 0.01},
]

# Industry baseline success rates (the "healthy" level)
INDUSTRY_BASE_SR: Dict[str, float] = {
    "E-commerce": 0.952, "Food Delivery": 0.948, "Travel": 0.930, "Fintech": 0.965,
    "Grocery": 0.958, "Fashion": 0.950, "Electronics": 0.945, "Quick Commerce": 0.940,
    "Entertainment": 0.955, "Healthcare": 0.962, "Education": 0.948, "Marketplaces": 0.935,
}

# Industry-typical average order values (INR)
INDUSTRY_AOV: Dict[str, float] = {
    "E-commerce": 1400, "Food Delivery": 380, "Travel": 6200, "Fintech": 2100,
    "Grocery": 920, "Fashion": 1850, "Electronics": 7200, "Quick Commerce": 260,
    "Entertainment": 540, "Healthcare": 3100, "Education": 8800, "Marketplaces": 1100,
}

# Payment-method baseline SR modifiers (relative to industry baseline)
METHOD_SR_MOD: Dict[str, float] = {
    "UPI": 0.012, "Credit Card": 0.000, "Debit Card": -0.018,
    "Netbanking": -0.030, "Wallet": -0.008,
}

# Device SR modifiers
DEVICE_SR_MOD: Dict[str, float] = {"Mobile": 0.000, "Desktop": 0.010, "Tablet": -0.005}

# Platform SR modifiers
PLATFORM_SR_MOD: Dict[str, float] = {"Android": -0.006, "iOS": 0.008, "Web": 0.004}


@dataclass
class ScenarioConfig:
    """Container for the injected anomalies so they are addressable by tests."""
    nova_merchant_id: str = "M0013"          # Nova Fashion
    budget_merchant_id: str = "M0042"        # Budget Grocery
    swift_merchant_id: str = "M0077"         # Swift Travel
    spike_issuer: str = "HDFC"
    spike_error_category: str = "Issuer Decline"
    decline_weeks: int = 2                   # final N weeks of the range


# ---------------------------------------------------------------------------
# Merchant generation
# ---------------------------------------------------------------------------

FANTASY_PREFIXES = [
    "Nova", "Swift", "Budget", "Urban", "Prime", "Bright", "Cloud", "Peak",
    "Rapid", "Luxe", "Easy", "Smart", "Fresh", "Quick", "Gold", "Silver",
    "Metro", "Vista", "Orbit", "Zenith", "Pixel", "Apex", "Bloom", "Craft",
    "Daily", "Vivid", "Nimbus", "Pulse", "Quartz", "Ridge", "Stellar", "Tidal",
]
INDUSTRY_SUFFIX: Dict[str, str] = {
    "E-commerce": "Mart", "Food Delivery": "Eats", "Travel": "Trips", "Fintech": "Pay",
    "Grocery": "Grocer", "Fashion": "Fashion", "Electronics": "Tech", "Quick Commerce": "Now",
    "Entertainment": "Play", "Healthcare": "Health", "Education": "Learn", "Marketplaces": "Bazaar",
}
SEGMENTS = ["SMB", "Mid-Market", "Enterprise"]
ACCOUNT_MANAGERS = ["Aarav Sharma", "Diya Patel", "Vivaan Gupta", "Ananya Reddy",
                    "Reyansh Iyer", "Ishita Nair", "Arjun Mehta", "Saanvi Verma"]


def build_merchants(s: Settings, rng: np.random.Generator) -> Tuple[pd.DataFrame, ScenarioConfig]:
    """Build the merchant dimension with deterministic, addressable scenario merchants."""
    n = s.n_merchants
    industries = s.industries
    mccs = s.mccs

    # Even-ish distribution across industries, at least 8 per industry for benchmarking
    industry_assign = []
    while len(industry_assign) < n:
        industry_assign.extend(industries)
    industry_assign = industry_assign[:n]
    rng.shuffle(industry_assign)

    rows = []
    used_names = set()
    # Reserve specific scenario merchants at fixed IDs for ground truth
    # M0013 -> Nova Fashion (E-commerce), M0042 -> Budget Grocery, M0077 -> Swift Travel
    forced = {
        "M0013": ("Nova Fashion", "E-commerce"),
        "M0042": ("Budget Grocer", "Grocery"),
        "M0077": ("Swift Trips", "Travel"),
    }

    for i in range(1, n + 1):
        mid = f"M{i:04d}"
        industry = industry_assign[i - 1]
        if mid in forced:
            name, industry = forced[mid]
        else:
            # deterministic-ish unique name
            prefix = FANTASY_PREFIXES[(i * 7) % len(FANTASY_PREFIXES)]
            suffix = INDUSTRY_SUFFIX[industry]
            name = f"{prefix} {suffix}"
            guard = 0
            while name in used_names and guard < 50:
                name = f"{prefix} {suffix} {i}"
                guard += 1
        used_names.add(name)
        mcc = mccs[(i * 3) % len(mccs)]
        segment = SEGMENTS[min(2, int(i / (n / 3)))]
        am = ACCOUNT_MANAGERS[i % len(ACCOUNT_MANAGERS)]
        country = "IN" if i % 5 != 0 else s.countries[i % len(s.countries)]
        onboarded = pd.Timestamp("2023-01-01") + pd.Timedelta(days=int(rng.integers(0, 365 * 2)))
        rows.append({
            "merchant_id": mid,
            "merchant_name": name,
            "industry": industry,
            "mcc": mcc,
            "merchant_segment": segment,
            "account_manager": am,
            "country": country,
            "onboarded_at": onboarded,
        })

    df = pd.DataFrame(rows)

    # Assign the forced industry for scenario merchants in the dataframe
    df.loc[df["merchant_id"] == "M0013", "industry"] = "E-commerce"
    df.loc[df["merchant_id"] == "M0042", "industry"] = "Grocery"
    df.loc[df["merchant_id"] == "M0077", "industry"] = "Travel"

    # Ensure at least benchmark_min_peers merchants per industry for benchmarking to work.
    counts = df["industry"].value_counts()
    log("merchant_generation", total=len(df), industry_counts=counts.to_dict())
    return df, ScenarioConfig()


# ---------------------------------------------------------------------------
# Transaction generation (vectorised)
# ---------------------------------------------------------------------------

def _merchant_base_sr(merchant_row: pd.Series) -> float:
    """Baseline SR for a merchant given its industry."""
    base = INDUSTRY_BASE_SR.get(merchant_row["industry"], 0.94)
    # small per-merchant jitter baked into merchant id deterministically
    mid_num = int(merchant_row["merchant_id"][1:])
    jitter = ((mid_num * 13) % 17 - 8) * 0.0015  # +-0.012
    return float(np.clip(base + jitter, 0.80, 0.99))


def _scenario_adjustment(
    mid: str,
    industry: str,
    method: str,
    device: str,
    platform: str,
    issuer: str,
    day_index: int,
    total_days: int,
    sc: ScenarioConfig,
) -> float:
    """Return an additive SR adjustment for the controlled scenarios.

    Only affects the final `decline_weeks` weeks (day_index near the end) for
    S1/S2/S3, and a persistent gap for S4, and an improvement for S5.
    """
    adj = 0.0
    in_decline_window = day_index >= (total_days - sc.decline_weeks * 7)

    # S1: Nova Fashion overall decline in final weeks
    if mid == sc.nova_merchant_id and in_decline_window:
        adj -= 0.040  # -4 pp

    # S2: Android + Debit Card deteriorates for Nova
    if mid == sc.nova_merchant_id and platform == "Android" and method == "Debit Card" and in_decline_window:
        adj -= 0.060  # additional -6 pp -> strongly concentrated

    # S3: HDFC issuer error spike for Nova in final weeks
    if mid == sc.nova_merchant_id and issuer == sc.spike_issuer and in_decline_window:
        adj -= 0.045  # additional -4.5 pp on HDFC

    # S4: Budget Grocery consistently below industry
    if mid == sc.budget_merchant_id:
        adj -= 0.035  # persistent -3.5 pp

    # S5: Swift Travel strong improvement in final weeks
    if mid == sc.swift_merchant_id and in_decline_window:
        adj += 0.030  # +3 pp improvement

    return adj


def generate_transactions(
    merchants: pd.DataFrame, s: Settings, sc: ScenarioConfig, rng: np.random.Generator
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Vectorised generation of transactions + checkout funnel events.

    Strategy: loop over merchants (150), and for each merchant build ALL
    transactions across ALL days in one vectorized pass using tiled arrays.
    This avoids the O(merchants*days) tiny-DataFrame construction that was
    the previous bottleneck.
    """
    methods = s.payment_methods
    devices = s.devices
    issuers = s.issuer_banks

    end_date = pd.Timestamp("2026-09-27")  # fixed reference "today"
    start_date = end_date - pd.Timedelta(days=s.n_weeks * 7 - 1)
    dates = pd.date_range(start_date, end_date, freq="D")
    total_days = len(dates)
    per_day = s.txns_per_day_per_merchant

    # Precompute per-day multipliers (weekend + trend)
    dows = dates.dayofweek.to_numpy()
    weekend_mult = np.where(dows >= 5, 1.18, 1.0)
    trend_mult = 1.0 + 0.10 * (np.arange(total_days) / total_days)
    day_mult = weekend_mult * trend_mult
    per_day_counts = (per_day * day_mult).astype(int)  # array[total_days]

    # Probability vectors
    method_p = np.array([0.50, 0.22, 0.18, 0.06, 0.04])  # UPI, CC, DC, NB, Wallet
    device_p = np.array([0.70, 0.22, 0.08])
    issuer_p = np.ones(len(issuers)) / len(issuers)
    pay_type_p = np.array([0.78, 0.08, 0.10, 0.04])
    err_weights = np.array([e["base_rate"] for e in ERROR_CATALOG])
    err_weights = err_weights / err_weights.sum()
    err_codes = [e["error_code"] for e in ERROR_CATALOG]

    # Precompute modifier lookup arrays for vectorized application
    method_mod = np.array([METHOD_SR_MOD[m] for m in methods])      # idx -> mod
    device_mod = np.array([DEVICE_SR_MOD[d] for d in devices])
    platform_mod_map = {"Android": PLATFORM_SR_MOD["Android"],
                        "iOS": PLATFORM_SR_MOD["iOS"], "Web": PLATFORM_SR_MOD["Web"]}

    country_of = dict(zip(merchants["merchant_id"], merchants["country"]))
    merchant_base = {r["merchant_id"]: _merchant_base_sr(r) for _, r in merchants.iterrows()}

    txn_frames = []

    for _, mrow in merchants.iterrows():
        mid = mrow["merchant_id"]
        industry = mrow["industry"]
        base_sr = merchant_base[mid]

        # total transactions for this merchant across all days
        counts = per_day_counts  # same for all merchants
        total_n = int(counts.sum())
        if total_n <= 0:
            continue

        # Build day_index by repeating each day index counts[di] times
        day_idx = np.repeat(np.arange(total_days), counts)
        n = total_n

        # Sample attributes for all n transactions of this merchant
        m_idx = rng.choice(len(methods), size=n, p=method_p)
        d_idx = rng.choice(len(devices), size=n, p=device_p)
        # platform: mobile -> Android/iOS, else Web
        mobile_mask = d_idx == 0
        plat = np.full(n, "Web", dtype=object)
        mobile_plat = rng.choice(["Android", "iOS"], size=mobile_mask.sum(),
                                 p=[0.55, 0.45])
        plat[mobile_mask] = mobile_plat
        iss_idx = rng.choice(len(issuers), size=n, p=issuer_p)

        chosen_methods = np.array(methods)[m_idx]
        chosen_devices = np.array(devices)[d_idx]
        chosen_issuers = np.array(issuers)[iss_idx]

        # SR vector: base + method + device + platform modifiers + noise
        sr_vec = np.full(n, base_sr, dtype=float)
        sr_vec += method_mod[m_idx]
        sr_vec += device_mod[d_idx]
        sr_vec += np.array([platform_mod_map[p] for p in plat])
        sr_vec += rng.normal(0, 0.004, size=n)

        # Scenario adjustments — vectorized using boolean masks
        in_decline = day_idx >= (total_days - sc.decline_weeks * 7)
        is_nova = mid == sc.nova_merchant_id
        is_budget = mid == sc.budget_merchant_id
        is_swift = mid == sc.swift_merchant_id
        if is_nova:
            sr_vec[in_decline] -= 0.040
            nova_dc_android = in_decline & (plat == "Android") & (chosen_methods == "Debit Card")
            sr_vec[nova_dc_android] -= 0.060
            nova_hdfc = in_decline & (chosen_issuers == sc.spike_issuer)
            sr_vec[nova_hdfc] -= 0.045
        if is_budget:
            sr_vec -= 0.035
        if is_swift:
            sr_vec[in_decline] += 0.030
        sr_vec = np.clip(sr_vec, 0.05, 0.999)

        success = rng.random(n) < sr_vec

        # Amounts ~ lognormal around industry AOV
        aov = INDUSTRY_AOV.get(industry, 1200.0)
        amounts = np.round(rng.lognormal(mean=np.log(aov), sigma=0.5, size=n), 2)

        # card_type
        card_type = np.full(n, "Prepaid", dtype=object)
        card_type[chosen_methods == "Credit Card"] = "Credit"
        card_type[chosen_methods == "Debit Card"] = "Debit"
        pay_type = rng.choice(s.payment_types, size=n, p=pay_type_p)

        # error codes only for failures
        err_choice = rng.choice(err_codes, size=n, p=err_weights)
        err_final = np.where(success, None, err_choice)

        # timestamps: base day + random seconds
        date_arr = dates[day_idx].to_numpy().astype("datetime64[s]")
        secs = rng.integers(0, 86400, size=n).astype("timedelta64[s]")
        event_ts = date_arr + secs
        auth_offset = rng.integers(1, 30, size=n).astype("timedelta64[s]")
        authorized_ts = np.where(success, event_ts + auth_offset,
                                 np.datetime64("NaT", "s"))
        status = np.where(success, "authorized", "failed")

        # IDs: built with a single list comprehension over n rows
        k_within_day = np.concatenate([np.arange(c) for c in counts])
        day_str = day_idx.astype(str)
        k_str = k_within_day.astype(str)
        prefix_t = f"T_{mid}_"
        prefix_s = f"S_{mid}_"
        txn_ids = np.array([prefix_t + ds + "_" + ks for ds, ks in zip(day_str, k_str)])
        sess_ids = np.array([prefix_s + ds + "_" + ks for ds, ks in zip(day_str, k_str)])

        txn_df = pd.DataFrame({
            "transaction_id": txn_ids,
            "merchant_id": mid,
            "event_timestamp": event_ts,
            "amount": amounts,
            "currency": "INR",
            "payment_method": chosen_methods,
            "payment_type": pay_type,
            "card_type": card_type,
            "issuer_bank": chosen_issuers,
            "industry": industry,
            "mcc": mrow["mcc"],
            "device": chosen_devices,
            "platform": plat,
            "country": country_of.get(mid, "IN"),
            "status": status,
            "error_code": err_final,
            "authorized_at": authorized_ts,
            "checkout_session_id": sess_ids,
        })
        txn_frames.append(txn_df)

    transactions = pd.concat(txn_frames, ignore_index=True)

    # Build checkout funnel events vectorized across ALL transactions
    checkout = _build_checkout_events_vectorized(transactions, rng)
    log("transaction_generation", transactions=len(transactions),
        checkout_events=len(checkout), days=total_days, merchants=len(merchants))
    return transactions, checkout


# ---------------------------------------------------------------------------
# Dimension builders
# ---------------------------------------------------------------------------

def build_error_codes_df() -> pd.DataFrame:
    return pd.DataFrame([
        {"error_code": e["error_code"], "error_category": e["error_category"],
         "description": e["description"], "owner_team": e["owner_team"]}
        for e in ERROR_CATALOG
    ])


def build_payment_methods_df(s: Settings) -> pd.DataFrame:
    rows = []
    for m in s.payment_methods:
        if m == "UPI":
            rows.append({"payment_method": m, "payment_type": "OneTime", "card_type": None})
        elif m == "Credit Card":
            rows.append({"payment_method": m, "payment_type": "OneTime", "card_type": "Credit"})
        elif m == "Debit Card":
            rows.append({"payment_method": m, "payment_type": "OneTime", "card_type": "Debit"})
        elif m == "Netbanking":
            rows.append({"payment_method": m, "payment_type": "OneTime", "card_type": None})
        elif m == "Wallet":
            rows.append({"payment_method": m, "payment_type": "OneTime", "card_type": None})
    return pd.DataFrame(rows)


def build_calendar_df(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    dates = pd.date_range(start.normalize(), end.normalize(), freq="D")
    df = pd.DataFrame({"date": dates})
    df["week_start"] = dates - pd.to_timedelta(dates.dayofweek, unit="D")
    df["month_start"] = dates.to_period("M").to_timestamp()
    df["quarter"] = dates.quarter
    df["year"] = dates.year
    return df


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _build_checkout_events_vectorized(
    transactions: pd.DataFrame, rng: np.random.Generator
) -> pd.DataFrame:
    """Build the checkout funnel events for every transaction in one pass.

    Each transaction maps to one checkout_session_id and emits 3 events:
    checkout_started (at a random time on the txn's day), payment_attempted
    (+20s), and payment_success/payment_failed (+45s).
    """
    n = len(transactions)
    if n == 0:
        return pd.DataFrame(columns=["event_id", "checkout_session_id", "merchant_id",
                                     "event_timestamp", "event_type", "device",
                                     "platform", "payment_method"])
    # base "started" time: random hour:minute within the txn's event day
    day_floor = transactions["event_timestamp"].dt.normalize()
    seconds_into_day = rng.integers(0, 86400, size=n)
    started_ts = day_floor + pd.to_timedelta(seconds_into_day, unit="s")

    # repeat each session 3x for the 3 event types
    rep = np.repeat(np.arange(n), 3)
    sessions = transactions.iloc[rep].reset_index(drop=True)
    base_ts = pd.to_datetime(np.repeat(started_ts.values, 3))
    # offsets: 0, 20, 45 repeated per session
    offsets = np.tile([0, 20, 45], n)
    event_ts = base_ts + pd.to_timedelta(offsets, unit="s")
    event_types = np.tile(
        np.array(["checkout_started", "payment_attempted", "PAY_TERM"]), n
    )
    # fill the 3rd event type per session from success/fail
    success = (transactions["status"].values == "authorized")
    third = np.where(success, "payment_success", "payment_failed")
    event_types = np.where(event_types == "PAY_TERM",
                           np.repeat(third, 3), event_types)

    checkout = pd.DataFrame({
        "checkout_session_id": sessions["checkout_session_id"].values,
        "merchant_id": sessions["merchant_id"].values,
        "event_timestamp": event_ts,
        "event_type": event_types,
        "device": sessions["device"].values,
        "platform": sessions["platform"].values,
        "payment_method": sessions["payment_method"].values,
    })
    checkout["event_id"] = [f"E{i:09d}" for i in range(len(checkout))]
    checkout = checkout[["event_id", "checkout_session_id", "merchant_id",
                         "event_timestamp", "event_type", "device", "platform",
                         "payment_method"]]
    return checkout


def generate_all(s: Settings | None = None) -> Dict[str, pd.DataFrame]:
    """Run the full generator and return a dict of DataFrames."""
    s = s or get_settings()
    rng = np.random.default_rng(s.random_seed)

    merchants, sc = build_merchants(s, rng)
    transactions, checkout = generate_transactions(merchants, s, sc, rng)

    error_codes = build_error_codes_df()
    payment_methods = build_payment_methods_df(s)
    start = transactions["event_timestamp"].min().normalize()
    end = transactions["event_timestamp"].max().normalize()
    calendar = build_calendar_df(start, end)

    return {
        "merchants": merchants,
        "payment_transactions": transactions,
        "checkout_events": checkout,
        "error_codes": error_codes,
        "payment_methods": payment_methods,
        "calendar": calendar,
    }


def write_parquet(data: Dict[str, pd.DataFrame], out_dir: Path) -> Dict[str, Path]:
    """Write each DataFrame to Parquet; return the mapping of name -> path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: Dict[str, Path] = {}
    for name, df in data.items():
        p = out_dir / f"{name}.parquet"
        df.to_parquet(p, index=False)
        paths[name] = p
        log("write_parquet", name=name, rows=len(df), path=str(p))
    return paths


def main() -> None:
    s = get_settings()
    log("generation_start", n_merchants=s.n_merchants, n_weeks=s.n_weeks,
        seed=s.random_seed)
    data = generate_all(s)
    paths = write_parquet(data, s.raw_dir)
    # also write a small scenario manifest for tests/docs
    sc = ScenarioConfig()
    import json
    manifest = {
        "generated_at": pd.Timestamp.now().isoformat(),
        "seed": s.random_seed,
        "n_merchants": s.n_merchants,
        "n_weeks": s.n_weeks,
        "scenario_merchants": {
            "sr_decline": sc.nova_merchant_id,
            "consistent_underperformer": sc.budget_merchant_id,
            "strong_improvement": sc.swift_merchant_id,
        },
        "scenario_params": {
            "spike_issuer": sc.spike_issuer,
            "spike_error_category": sc.spike_error_category,
            "decline_weeks": sc.decline_weeks,
        },
        "tables": {k: str(v) for k, v in paths.items()},
    }
    man_path = s.generated_dir / "scenario_manifest.json"
    man_path.parent.mkdir(parents=True, exist_ok=True)
    man_path.write_text(json.dumps(manifest, indent=2))
    log("generation_complete", tables=list(paths.keys()),
        manifest=str(man_path))
    print(f"Generated {len(paths)} tables in {s.raw_dir}")
    for name, p in paths.items():
        print(f"  {name}: {len(data[name])} rows -> {p}")


if __name__ == "__main__":
    main()
