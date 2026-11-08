"""FastAPI Application for Adaptive Clinical Trial Site Enrollment Forecasting."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.schemas import (
    DataIngestBatch,
    DemoUser,
    ForecastRequest,
    ForecastResponse,
    HealthResponse,
    LoginRequest,
    SitesResponse,
    TrialMetadataResponse,
    UpdatePasswordRequest,
    UserResponse,
    WhatIfResponse,
)
from backend.services.forecast_service import ForecastService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("backend")

# Demo & Registered Users Store
USERS_DB = {
    "vijay": {
        "password": "1704",
        "full_name": "Vijay (System Owner & Administrator)",
        "role": "admin",
        "email": "vijay@trial-operations.org",
        "title": "Principal Clinical Trial Director & System Owner",
        "description": "Full System Superuser: Unrestricted What-If simulation interventions, site control, protocol parameters, and data ingestion.",
        "permissions": ["*"],
    },
    "admin": {
        "password": "admin123",
        "full_name": "Vijayaraj (System Administrator)",
        "role": "admin",
        "email": "vijayaraj@trial-operations.org",
        "title": "Lead Clinical Trial Administrator & System Architect",
        "description": "Full System Superuser: What-If simulation interventions, site control, and batch data ingestion.",
        "permissions": ["*"],
    },
    "vijayaraj": {
        "password": "admin123",
        "full_name": "Vijayaraj (System Administrator)",
        "role": "admin",
        "email": "vijayaraj@trial-operations.org",
        "title": "Lead Clinical Trial Administrator & System Architect",
        "description": "Full System Superuser: What-If simulation interventions, site control, and batch data ingestion.",
        "permissions": ["*"],
    },
    "manager": {
        "password": "admin123",
        "full_name": "Dr. Marcus Vance",
        "role": "management",
        "email": "m.vance@trial-operations.org",
        "title": "Trial Operations Director",
        "description": "Management access: What-If simulation interventions, site toggling, and data ingestion.",
        "permissions": ["view_kpi", "view_forecast", "view_sites", "simulate_whatif", "modify_sites", "ingest_data"],
    },
    "user": {
        "password": "user123",
        "full_name": "Dr. Sarah Chen",
        "role": "user",
        "email": "sarah.chen@trial-site.org",
        "title": "Clinical Investigator & Site Lead",
        "description": "Read-only access to enrollment projections, Bayesian credible bounds, and site registry.",
        "permissions": ["view_kpi", "view_forecast", "view_sites"],
    },
    "investigator": {
        "password": "user123",
        "full_name": "Dr. Sarah Chen",
        "role": "user",
        "email": "sarah.chen@trial-site.org",
        "title": "Clinical Investigator & Site Lead",
        "description": "Read-only access to enrollment projections, Bayesian credible bounds, and site registry.",
        "permissions": ["view_kpi", "view_forecast", "view_sites"],
    },
}


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


@app.get("/api/sites/{site_id}", tags=["Sites"])
def get_site_details(site_id: str, current_week: int = Query(40, ge=1, le=104)) -> dict:
    """Retrieve detailed longitudinal records and hospital flow covariates for a specific site."""
    try:
        return service.get_site_details(site_id, current_week=current_week)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found.")
    except Exception as e:
        logger.error("Error fetching site details for %s: %s", site_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports/backtest", tags=["Reports"])
def get_backtest_report() -> list[dict]:
    """Retrieve benchmark backtest evaluation metrics across all models."""
    path = Path("reports/backtest_summary.json")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Backtest summary report not found.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/reports/diagnostics", tags=["Reports"])
def get_diagnostics_report() -> dict:
    """Retrieve Bayesian MCMC convergence diagnostics, LOO-CV and WAIC comparisons."""
    path = Path("reports/bayesian_diagnostics.json")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Bayesian diagnostics report not found.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/reports/eda", tags=["Reports"])
def get_eda_report() -> dict:
    """Retrieve Exploratory Data Analysis & Hospital Flow summary."""
    path = Path("reports/eda_summary.json")
    if not path.exists():
        raise HTTPException(status_code=404, detail="EDA report not found.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# Authentication Endpoints
@app.post("/api/auth/login", response_model=UserResponse, tags=["Authentication"])
def login(req: LoginRequest) -> UserResponse:
    """Authenticate User or Management credentials."""
    user = USERS_DB.get(req.username.lower())
    if not user or user["password"] != req.password:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return UserResponse(
        username=req.username.lower(),
        full_name=user["full_name"],
        role=user["role"],
        email=user["email"],
        token=f"token_{req.username.lower()}_{user['role']}",
        permissions=user["permissions"],
    )


@app.get("/api/auth/demo-users", response_model=list[DemoUser], tags=["Authentication"])
def get_demo_users() -> list[DemoUser]:
    """Retrieve pre-configured Admin, Management, and User credentials for front-end 1-click login."""
    return [
        DemoUser(
            username="Vijay",
            role="admin",
            full_name="Vijay (System Administrator)",
            title="Principal System Administrator & Owner",
            description="Full superuser privileges: parameter sandbox, site interventions, protocol updates, and data ingestion.",
        ),
        DemoUser(
            username="manager",
            role="management",
            full_name="Dr. Marcus Vance",
            title="Trial Operations Director (Management)",
            description="Management access: What-If simulation interventions, site toggling, and data ingestion.",
        ),
        DemoUser(
            username="investigator",
            role="user",
            full_name="Dr. Sarah Chen",
            title="Clinical Investigator (User)",
            description="Read-only access to enrollment projections, Bayesian credible bounds, and site registry.",
        ),
    ]


@app.post("/api/auth/change-password", tags=["Authentication"])
def change_password(req: UpdatePasswordRequest) -> dict:
    """Update password for an existing account."""
    uname = req.username.lower()
    user = USERS_DB.get(uname)
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")
    if user["password"] != req.old_password:
        raise HTTPException(status_code=401, detail="Current password incorrect.")
    user["password"] = req.new_password
    return {"status": "success", "message": f"Password successfully updated for user '{uname}'."}


@app.get("/api/auth/me", response_model=UserResponse, tags=["Authentication"])
def get_current_user(token: str | None = Query(None), authorization: str | None = Header(None)) -> UserResponse:
    """Validate current session token and return user profile."""
    auth_token = token or (authorization.replace("Bearer ", "") if authorization else None)
    if not auth_token:
        raise HTTPException(status_code=401, detail="No authorization token provided.")

    for uname, user in USERS_DB.items():
        if f"token_{uname}_{user['role']}" == auth_token:
            return UserResponse(
                username=uname,
                full_name=user["full_name"],
                role=user["role"],
                email=user["email"],
                token=auth_token,
                permissions=user["permissions"],
            )

    raise HTTPException(status_code=401, detail="Invalid or expired session token.")



# Mount Static Figures & Frontend
figures_dir = Path("reports/figures")
figures_dir.mkdir(parents=True, exist_ok=True)
app.mount("/reports/figures", StaticFiles(directory="reports/figures"), name="figures")

frontend_dir = Path("frontend")
frontend_dir.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)
