"""FastAPI Application for Adaptive Clinical Trial Site Enrollment Forecasting."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.schemas import (
    DataIngestBatch,
    ForecastRequest,
    ForecastResponse,
    HealthResponse,
    SitesResponse,
    TrialMetadataResponse,
    WhatIfResponse,
)
from backend.services.forecast_service import ForecastService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("backend")

app = FastAPI(
    title="Adaptive Clinical Trial Enrollment Forecasting API",
    description="Hierarchical Bayesian enrollment forecasting with real-world hospital flow covariates.",
    version="1.0.0",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singleton Forecast Service
service = ForecastService()


@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def get_health() -> HealthResponse:
    """System health check and cached model status."""
    return HealthResponse(**service.get_health())


@app.get("/api/trials", response_model=TrialMetadataResponse, tags=["Trials"])
def get_trials() -> TrialMetadataResponse:
    """Retrieve trial protocol, metadata, and participating sites."""
    try:
        return service.get_trials()
    except (RuntimeError, ValueError, KeyError, OSError) as e:
        logger.error("Error retrieving trial metadata: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sites", response_model=SitesResponse, tags=["Sites"])
def get_sites(
    current_week: int = Query(40, ge=1, le=104),
    target: int = Query(1200, ge=100),
    deadline: int = Query(90, ge=10, le=104),
) -> SitesResponse:
    """Retrieve per-site recruitment metrics, posterior rates, and risk flags."""
    try:
        return service.get_sites(current_week=current_week, target=target, deadline=deadline)
    except (RuntimeError, ValueError, KeyError, OSError) as e:
        logger.error("Error fetching sites: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/forecast", response_model=ForecastResponse, tags=["Forecasting"])
def create_forecast(req: ForecastRequest) -> ForecastResponse:
    """Generate longitudinal Bayesian forecast with credible intervals and completion date densities."""
    try:
        return service.generate_forecast(req)
    except (RuntimeError, ValueError, KeyError, OSError) as e:
        logger.error("Error generating forecast: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/whatif", response_model=WhatIfResponse, tags=["What-If Simulation"])
def create_whatif_scenario(req: ForecastRequest) -> WhatIfResponse:
    """Compare baseline status quo against policy intervention scenario (site closures, additions, flow shifts)."""
    try:
        return service.generate_whatif(req)
    except (RuntimeError, ValueError, KeyError, OSError) as e:
        logger.error("Error running what-if scenario: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/update", tags=["Adaptive Ingestion"])
def ingest_weekly_data(batch: DataIngestBatch) -> dict:
    """Ingest new weekly records into the longitudinal panel and update forecasts."""
    try:
        return service.ingest_new_data(batch)
    except (RuntimeError, ValueError, KeyError, OSError) as e:
        logger.error("Error ingesting data: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# Mount Static Frontend
frontend_dir = Path("frontend")
frontend_dir.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)
