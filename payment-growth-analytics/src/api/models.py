"""Pydantic response models for the FastAPI service."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    duckdb_path: str
    tables: List[str]


class KpiCard(BaseModel):
    metric: str
    value: Optional[float]
    unit: str = "percent"  # or "count", "currency"
    definition: str


class OverviewResponse(BaseModel):
    start_date: str
    end_date: str
    kpis: List[KpiCard]
    sample_txn_count: int
    data_quality_warning: Optional[str] = None


class MerchantMetricsResponse(BaseModel):
    merchant_id: str
    merchant_name: str
    industry: str
    start_date: str
    end_date: str
    success_rate: Optional[float]
    previous_success_rate: Optional[float]
    sr_delta_pp: Optional[float]
    tpv: float
    transaction_count: int
    aov: Optional[float]
    failure_rate: Optional[float]
    benchmark_sr: Optional[float]
    benchmark_gap_pp: Optional[float]
    benchmark_status: str
    peer_count: int
    sample_txn_count: int


class TrendPoint(BaseModel):
    period: str
    success_rate: Optional[float]
    tpv: float
    transaction_count: int


class TrendResponse(BaseModel):
    grain: str
    merchant_id: Optional[str]
    points: List[TrendPoint]


class PaymentMethodRow(BaseModel):
    payment_method: str
    success_rate: Optional[float]
    tpv: float
    transaction_count: int
    tpv_share_pct: Optional[float]


class PaymentMethodResponse(BaseModel):
    merchant_id: Optional[str]
    rows: List[PaymentMethodRow]


class RcaSegment(BaseModel):
    dimension: str
    segment: str
    current_sr: Optional[float]
    previous_sr: Optional[float]
    delta_pp: Optional[float]
    contribution: float
    share_of_decline: float
    volume_current: int
    volume_previous: int


class RcaResponse(BaseModel):
    merchant_id: str
    current_period: str
    previous_period: str
    overall_current_sr: Optional[float]
    overall_previous_sr: Optional[float]
    overall_delta_pp: Optional[float]
    top_contributors: List[RcaSegment]
    language_note: str


class BenchmarkResponse(BaseModel):
    merchant_id: str
    industry: str
    country: str
    payment_method: Optional[str]
    merchant_sr: Optional[float]
    benchmark_sr: Optional[float]
    gap_pp: Optional[float]
    peer_count: int
    sample_txn_count: int
    benchmark_status: str
    methodology: str


class OpportunityResponse(BaseModel):
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


class OpportunityListResponse(BaseModel):
    count: int
    opportunities: List[OpportunityResponse]


class ErrorResponse(BaseModel):
    detail: str
    code: str = "error"
