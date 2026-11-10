# System Architecture & Technical Design

This document describes the software and data architecture of the **Adaptive Clinical Trial Enrollment Forecasting Platform**.

```mermaid
flowchart TD
    subgraph Data Layer
        CTGov[ClinicalTrials.gov Protocol Metadata] --> Ingest[Data Ingestion Pipeline]
        MIMIC[Hospital Flow Covariates Engine] --> Ingest
        Ingest --> Panel[Longitudinal Site-Week Panel]
        Panel --> Cache[(NetCDF Trace Cache)]
    end

    subgraph Biostatistical Inference Engine
        Cache --> BayesEngine[Hierarchical Bayesian PyMC Engine]
        BayesEngine --> MonteCarlo[Monte Carlo Posterior Forecaster]
        MonteCarlo --> Posteriors[Credible Envelopes: q10, q50, q90]
        MonteCarlo --> Histograms[Completion Week Probabilities]
        MonteCarlo --> RiskScorer[Site Risk Classifier]
    end

    subgraph Service Layer (FastAPI Backend)
        ForecastService[Singleton ForecastService]
        Posteriors --> ForecastService
        Histograms --> ForecastService
        RiskScorer --> ForecastService
        AuthService[RBAC Authentication Service]
        WhatIfEngine[Simulation Intervention Sandbox]
    end

    subgraph Presentation Layer (Frontend Dashboard)
        SlidingDrawer[Sliding Left Dashboard Drawer]
        FanChart[SVG Fan Chart with Credible Bands]
        PlayEngine[Animated Trajectory Playback]
        GaugeMeter[Trial Health & Velocity Gauge]
        WhatIfUI[Interactive Intervention Sliders]
        GeoRibbon[Global Multi-Center Geo-Distribution]
    end

    ForecastService --> SlidingDrawer
    ForecastService --> FanChart
    ForecastService --> PlayEngine
    ForecastService --> GaugeMeter
    WhatIfEngine <--> WhatIfUI
    ForecastService --> GeoRibbon
```

---

## 1. Key Architectural Components

### 1.1 Backend Service Layer (FastAPI)
- **Singleton `ForecastService`**: Loads the pre-compiled MCMC posterior draws (`models_cache/model_a_trace.nc`) and raw trial metadata into memory on startup, ensuring sub-50ms query latency for simulation and forecasting requests.
- **RESTful Endpoints**:
  - `GET /api/health`: System health and cached model diagnostics.
  - `GET /api/trials`: Protocol details (NCT ID, eligibility, target enrollment).
  - `GET /api/sites`: Per-site posterior rates, credible intervals, and risk classification.
  - `POST /api/forecast`: Standard status-quo Bayesian projection.
  - `POST /api/whatif`: Counterfactual policy simulation (closures, flow shocks, new sites).
  - `POST /api/update`: Ingestion endpoint for weekly site observation updates.
  - `POST /api/auth/login`: Role-based authentication (Admin, Management, User).
  - `POST /api/auth/change-password`: Administrative credential management.

### 1.2 Frontend Architecture (Zero-Build Vanilla Web App)
- **Zero Build Tooling Dependency**: Direct vanilla ES6+ JavaScript and modern CSS custom properties—no Node.js build step or complex frontend bundlers required.
- **Reactive SVG Visualization Engine**: Directly renders fan charts, completion week histograms, and site timelines using native inline vector graphics `<svg>`, ensuring razor-sharp rendering on all high-DPI screens.
- **Sliding Left Corner Dashboard**: Dockable command drawer providing persistent navigation, micro-KPI pulses, synchronized quick-sliders, and account controls.
- **Audio Feedback Synthesizer**: Utilizes the native Web Audio API to deliver responsive clinical sound feedback without external sound asset dependencies.

### 1.3 Role-Based Access Control (RBAC)
- **System Owner & Administrator (Vijay / Vijayaraj - Admin)**: Dedicated superuser scope (`*`) with permissions to modify simulation parameters, toggle sites, ingest longitudinal panel records, and manage account credentials.
- **Trial Operations Director (Management)**: Simulation sandbox, flow shift multipliers, and operational site intervention scope.
- **Guest / Observer**: Read-only monitoring scope for trajectory overviews and site registry.

