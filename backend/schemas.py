"""Pydantic schemas for the Clinical Trial Enrollment Forecasting API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    trace_loaded: bool
    model_type: str = "Hierarchical Negative Binomial"


class SiteProfile(BaseModel):
    site_id: str
    country: str
    hospital_tier: str
    enrolled_to_date: int
    posterior_mean_rate: float
    rate_ci_80: list[float]
    p_at_risk: float
    is_at_risk: bool
    status: str  # "HEALTHY", "AT_RISK", "CLOSED"


class SitesResponse(BaseModel):
    current_week: int
    target: int
    deadline: int
    total_sites: int
    at_risk_count: int
    active_count: int
    sites: list[SiteProfile]


class TrialMetadataResponse(BaseModel):
    trial_id: str
    title: str
    protocol: dict[str, Any]
    total_sites: int
    countries: list[str]
    current_week: int
    total_enrolled: int


class ForecastRequest(BaseModel):
    current_week: int | None = Field(default=40, ge=1, le=104)
    target: int | None = Field(default=1200, ge=100)
    deadline: int | None = Field(default=90, ge=10, le=104)
    flow_change: float | None = Field(default=0.0, ge=-0.5, le=0.5)  # e.g. -0.2 to +0.2 (-20% to +20%)
    new_sites: int | None = Field(default=0, ge=0, le=20)
    closed: list[str] | None = Field(default_factory=list)
    draws: int | None = Field(default=1000, ge=100, le=5000)


class FanQuantiles(BaseModel):
    weeks: list[int]
    q025: list[float]
    q10: list[float]
    q25: list[float]
    q50: list[float]
    q75: list[float]
    q90: list[float]
    q975: list[float]


class HistogramBin(BaseModel):
    week: int
    count: int


class ForecastResponse(BaseModel):
    current_week: int
    target: int
    deadline: int
    total_enrolled_to_date: int
    p_hit_by_deadline: float
    median_completion_week: float
    at_risk_sites_count: int
    active_sites_count: int
    observed_history: list[dict[str, Any]]
    forecast_fan: FanQuantiles
    completion_histogram: list[HistogramBin]
    sites: list[SiteProfile]


class WhatIfResponse(BaseModel):
    baseline: ForecastResponse
    scenario: ForecastResponse
    delta_completion_week: float
    delta_p_hit_by_deadline: float
    scenario_description: str


class DataIngestRow(BaseModel):
    site_id: str
    week: int
    enrolled_count: int
    eligible_volume: int
    admissions: int | None = None
    ed_visits: int | None = None
    occupancy_proxy: float | None = None
    is_active: int | None = 1


class DataIngestBatch(BaseModel):
    records: list[DataIngestRow]
    recalculate_forecast: bool = True
