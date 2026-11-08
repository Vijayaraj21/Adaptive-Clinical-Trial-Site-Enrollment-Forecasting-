"""Service layer managing trial state, Bayesian forecasts, and what-if simulation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from backend.schemas import (
    DataIngestBatch,
    ForecastRequest,
    ForecastResponse,
    SitesResponse,
    TrialMetadataResponse,
    WhatIfResponse,
)
from src.data.ctgov import load_trial_metadata
from src.simulation.forecaster import AdaptiveTrialForecaster

logger = logging.getLogger(__name__)


class ForecastService:
    """Singleton service for trial forecasting state and business logic."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.forecaster = AdaptiveTrialForecaster(config_path)
        self.panel_path = Path("data/processed/weekly_site_panel.parquet")
        self.panel_df = self._load_panel()
        self.metadata = load_trial_metadata(config_path)

    def _load_panel(self) -> pd.DataFrame:
        """Load site panel from disk."""
        if not self.panel_path.exists():
            raise FileNotFoundError(f"Processed panel not found: {self.panel_path}")
        return pd.read_parquet(self.panel_path)

    def get_health(self) -> dict[str, Any]:
        """Health status and model status."""
        return {
            "status": "healthy",
            "version": "1.0.0",
            "trace_loaded": self.forecaster.has_trace,
            "model_type": "Hierarchical Bayesian Negative Binomial",
        }

    def get_trials(self) -> TrialMetadataResponse:
        """Trial protocol, participating countries, and site summaries."""
        proto = self.metadata.get("protocolSection", {})
        ident = proto.get("identificationModule", {})
        title = ident.get("briefTitle", "Adaptive Multi-Center Clinical Trial")
        nct_id = ident.get("nctId", "NCT04280705")

        countries = sorted(self.panel_df["country"].unique().tolist())
        total_sites = int(self.panel_df["site_id"].nunique())
        current_week = 40
        total_enrolled = int(self.panel_df[self.panel_df["week"] <= current_week]["enrolled_count"].sum())

        return TrialMetadataResponse(
            trial_id=nct_id,
            title=title,
            protocol=proto,
            total_sites=total_sites,
            countries=countries,
            current_week=current_week,
            total_enrolled=total_enrolled,
        )

    def get_sites(self, current_week: int = 40, target: int = 1200, deadline: int = 90) -> SitesResponse:
        """Site profiles, recruitment rates, and risk flags."""
        fc = self.forecaster.forecast(
            self.panel_df,
            current_week=current_week,
            target_enrollment=target,
            deadline_week=deadline,
        )

        sites = fc["sites"]
        return SitesResponse(
            current_week=current_week,
            target=target,
            deadline=deadline,
            total_sites=len(sites),
            at_risk_count=fc["at_risk_sites_count"],
            active_count=fc["active_sites_count"],
            sites=sites,
        )

    def get_site_details(self, site_id: str, current_week: int = 40) -> dict[str, Any]:
        """Retrieve longitudinal history, flow covariates, and performance for a specific site."""
        site_df = self.panel_df[self.panel_df["site_id"] == site_id].sort_values("week")
        if len(site_df) == 0:
            raise KeyError(f"Site {site_id} not found.")

        country = str(site_df["country"].iloc[0])
        tier = str(site_df["hospital_tier"].iloc[0])
        total_enrolled = int(site_df["enrolled_count"].sum())
        enrolled_current = int(site_df[site_df["week"] <= current_week]["enrolled_count"].sum())
        active_weeks = int(site_df["is_active"].sum())
        first_active_series = site_df[site_df["is_active"] == 1]["week"]
        activation_week = int(first_active_series.iloc[0]) if len(first_active_series) > 0 else 0

        history = [
            {
                "week": int(r["week"]),
                "enrolled": int(r["enrolled_count"]),
                "eligible_volume": int(r.get("eligible_volume", 0)),
                "is_active": int(r.get("is_active", 1)),
            }
            for _, r in site_df.iterrows()
        ]

        return {
            "site_id": site_id,
            "country": country,
            "hospital_tier": tier,
            "activation_week": activation_week,
            "active_weeks_count": active_weeks,
            "total_enrolled": total_enrolled,
            "enrolled_at_current_week": enrolled_current,
            "current_week": current_week,
            "history": history,
        }

    def generate_forecast(self, req: ForecastRequest) -> ForecastResponse:
        """Execute longitudinal Bayesian forecast with interventions."""
        flow_mult = 1.0 + (req.flow_change or 0.0)
        res = self.forecaster.forecast(
            self.panel_df,
            current_week=req.current_week or 40,
            target_enrollment=req.target or 1200,
            deadline_week=req.deadline or 90,
            flow_multiplier=flow_mult,
            closed_sites=req.closed or [],
            new_sites_count=req.new_sites or 0,
            n_draws=req.draws or 1000,
        )
        return ForecastResponse(**res)

    def generate_whatif(self, req: ForecastRequest) -> WhatIfResponse:
        """Compare baseline status quo vs policy intervention scenario."""
        # 1. Baseline: 0 flow change, 0 new sites, no closed sites
        base_req = ForecastRequest(
            current_week=req.current_week,
            target=req.target,
            deadline=req.deadline,
            flow_change=0.0,
            new_sites=0,
            closed=[],
            draws=req.draws,
        )
        baseline = self.generate_forecast(base_req)

        # 2. Scenario
        scenario = self.generate_forecast(req)

        delta_w = round(scenario.median_completion_week - baseline.median_completion_week, 1)
        delta_p = round(scenario.p_hit_by_deadline - baseline.p_hit_by_deadline, 3)

        desc_parts: list[str] = []
        if req.flow_change != 0.0:
            desc_parts.append(f"Hospital Flow: {req.flow_change:+0.0%}")
        if req.new_sites > 0:
            desc_parts.append(f"+{req.new_sites} New Sites")
        if req.closed:
            desc_parts.append(f"{len(req.closed)} Closed Sites")

        desc = " | ".join(desc_parts) if desc_parts else "Status Quo (No Interventions)"

        return WhatIfResponse(
            baseline=baseline,
            scenario=scenario,
            delta_completion_week=delta_w,
            delta_p_hit_by_deadline=delta_p,
            scenario_description=desc,
        )

    def ingest_new_data(self, batch: DataIngestBatch) -> dict[str, Any]:
        """Ingest new weekly records into the longitudinal panel and update forecasts."""
        new_records = [r.model_dump() for r in batch.records]
        new_df = pd.DataFrame(new_records)

        # Merge with existing panel
        combined = pd.concat([self.panel_df, new_df], ignore_index=True)
        # Drop duplicates on (site_id, week) keeping latest
        combined = combined.drop_duplicates(subset=["site_id", "week"], keep="last")
        combined = combined.sort_values(["site_id", "week"]).reset_index(drop=True)

        self.panel_df = combined
        self.panel_df.to_parquet(self.panel_path, index=False)
        logger.info("Ingested %d new records into panel.", len(new_records))

        latest_week = int(new_df["week"].max()) if len(new_df) > 0 else 40
        return {
            "status": "success",
            "ingested_count": len(new_records),
            "updated_total_rows": len(self.panel_df),
            "latest_week": latest_week,
        }

