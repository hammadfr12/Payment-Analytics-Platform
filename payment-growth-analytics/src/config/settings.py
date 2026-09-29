"""Central configuration for the Payment Growth Analytics Platform.

All tunable values are read from environment variables (with sensible defaults)
so the project is reproducible without a `.env` file and overridable with one.
No secrets are stored here or anywhere in the codebase.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

try:
    from pydantic_settings import BaseSettings  # type: ignore

    _HAVE_PYDANTIC_SETTINGS = True
except Exception:  # pragma: no cover - fallback when optional dep missing
    _HAVE_PYDANTIC_SETTINGS = False


def _project_root() -> Path:
    # src/config/settings.py -> repo root is 3 parents up
    return Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    """Typed configuration container."""

    # --- Generation scale ---
    n_merchants: int = 150
    n_weeks: int = 10
    txns_per_day_per_merchant: int = 100
    random_seed: int = 42

    # --- Paths ---
    project_root: Path = field(default_factory=_project_root)
    duckdb_path: Path = field(default=None)  # type: ignore[assignment]
    raw_dir: Path = field(default=None)  # type: ignore[assignment]
    generated_dir: Path = field(default=None)  # type: ignore[assignment]
    hyper_path: Path = field(default=None)  # type: ignore[assignment]

    # --- Benchmark thresholds ---
    benchmark_min_txns: int = 500
    benchmark_min_peers: int = 5

    # --- Opportunity thresholds ---
    opp_sr_decline_pp: float = 1.5
    opp_benchmark_gap_pp: float = 2.0
    opp_min_txns: int = 200
    opp_error_spike_pp: float = 2.0
    opp_concentrated_share: float = 0.25

    # --- API / Streamlit ---
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    streamlit_port: int = 8501

    def __post_init__(self) -> None:
        self.project_root = _project_root()
        self.duckdb_path = self.project_root / "data" / "processed" / "payment_growth.duckdb"
        self.raw_dir = self.project_root / "data" / "raw"
        self.generated_dir = self.project_root / "data" / "generated"
        self.hyper_path = self.project_root / "tableau" / "extracts" / "payment_growth.hyper"

    # --- Reference data (fixed vocabularies) ---
    @property
    def industries(self) -> List[str]:
        return [
            "E-commerce", "Food Delivery", "Travel", "Fintech", "Grocery",
            "Fashion", "Electronics", "Quick Commerce", "Entertainment",
            "Healthcare", "Education", "Marketplaces",
        ]

    @property
    def payment_methods(self) -> List[str]:
        return ["UPI", "Credit Card", "Debit Card", "Netbanking", "Wallet"]

    @property
    def devices(self) -> List[str]:
        return ["Mobile", "Desktop", "Tablet"]

    @property
    def platforms(self) -> List[str]:
        return ["Android", "iOS", "Web"]

    @property
    def issuer_banks(self) -> List[str]:
        return [
            "HDFC", "ICICI", "SBI", "Axis", "Kotak", "Yes Bank",
            "IDFC First", "American Express", "Citi", "Standard Chartered",
        ]

    @property
    def countries(self) -> List[str]:
        return ["IN", "US", "AE", "SG"]

    @property
    def mccs(self) -> List[str]:
        # 25 MCCs spanning the industries
        return [
            "5411", "5499", "5912", "5812", "5814", "4112", "4131", "4789",
            "4511", "4722", "4723", "4900", "5310", "5311", "5651", "5661",
            "5691", "5732", "5942", "5945", "5946", "5947", "6051", "7298",
            "7372",
        ]

    @property
    def card_types(self) -> List[str]:
        return ["Credit", "Debit", "Prepaid"]

    @property
    def payment_types(self) -> List[str]:
        return ["OneTime", "EMI", "Recurring", "Saved"]


def _load_env_file(path: Path) -> None:
    """Minimal .env loader (no dependency on python-dotenv at import time)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def get_settings() -> Settings:
    """Build a Settings instance from environment + .env file."""
    _load_env_file(_project_root() / ".env")
    s = Settings(
        n_merchants=int(os.environ.get("PGA_N_MERCHANTS", 150)),
        n_weeks=int(os.environ.get("PGA_N_WEEKS", 10)),
        txns_per_day_per_merchant=int(os.environ.get("PGA_TXNS_PER_DAY_PER_MERCHANT", 100)),
        random_seed=int(os.environ.get("PGA_RANDOM_SEED", 42)),
        benchmark_min_txns=int(os.environ.get("PGA_BENCHMARK_MIN_TXNS", 500)),
        benchmark_min_peers=int(os.environ.get("PGA_BENCHMARK_MIN_PEERS", 5)),
        opp_sr_decline_pp=float(os.environ.get("PGA_OPP_SR_DECLINE_PP", 1.5)),
        opp_benchmark_gap_pp=float(os.environ.get("PGA_OPP_BENCHMARK_GAP_PP", 2.0)),
        opp_min_txns=int(os.environ.get("PGA_OPP_MIN_TXNS", 200)),
        opp_error_spike_pp=float(os.environ.get("PGA_OPP_ERROR_SPIKE_PP", 2.0)),
        opp_concentrated_share=float(os.environ.get("PGA_OPP_CONCENTRATED_SHARE", 0.25)),
        api_host=os.environ.get("PGA_API_HOST", "127.0.0.1"),
        api_port=int(os.environ.get("PGA_API_PORT", 8000)),
        streamlit_port=int(os.environ.get("PGA_STREAMLIT_PORT", 8501)),
    )
    return s
