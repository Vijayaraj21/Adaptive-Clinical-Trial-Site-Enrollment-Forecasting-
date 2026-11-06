# Adaptive Clinical Trial Site Enrollment Forecasting

Hierarchical Bayesian enrollment forecasting with real-world hospital flow covariates, interactive What-If scenario simulations, role-based front-end management, and site performance risk monitoring.

---

## 🌟 Key Features

- **Hierarchical Bayesian Negative-Binomial Model**: Accommodates site-level heterogeneity, zero-inflation (never-enrolling sites), random site-level activation delays, and Fourier seasonal effects.
- **Hospital Flow Covariate Integration**: Incorporates real-world hospital volume proxies (eligible patient volumes, inpatient occupancy, ED flow) inspired by MIMIC-IV clinical data patterns.
- **Calibrated Uncertainty Projections**: Generates 50%, 80%, and 95% Bayesian credible interval fan charts and completion week posterior probability distributions.
- **Role-Based Front View (User vs Management)**:
  - 👨‍⚕️ **Clinical Investigator (`User` Mode)**: Read-only monitoring of enrollment trajectories, Bayesian credible envelopes, and site performance metrics.
  - 🛡️ **Trial Operations Director (`Management` Mode)**: Administrative control over What-If simulation interventions, patient flow shifts, early site terminations, and weekly data ingestion.
- **Interactive What-If Simulation Sandbox**: Dynamically simulates policy interventions:
  - Patient flow fluctuations ($\pm 30\%$)
  - Early closure of underperforming or non-compliant sites
  - Mid-trial addition of new investigation sites with ramp-up curves
- **Full-Stack Application**:
  - **Backend**: FastAPI RESTful API with validation, health checks, authentication, and adaptive ingestion endpoints.
  - **Frontend**: Responsive Dark/Light mode dashboard with vanilla JavaScript and SVG visualizations (no build steps required).

---

## 🔑 Demo Access Credentials

| Role | Username | Password | Full Name | Access Scope |
| :--- | :--- | :--- | :--- | :--- |
| **User (Investigator)** | `user` | `user123` | Dr. Sarah Chen | Read-only analytics, credible bounds, & site registry |
| **Management (Admin)** | `manager` | `admin123` | Dr. Marcus Vance | Full simulation sandbox, site toggling, and data ingestion |

---

## 📂 Project Structure

```
├── backend/                  # FastAPI web application, schemas, and services
│   ├── main.py               # Main app entrypoint, auth, and static mount
│   ├── schemas.py            # Pydantic request/response & auth models
│   └── services/             # Forecast service and state manager
├── frontend/                 # Interactive web dashboard
│   ├── index.html            # Dashboard structure, login modal, and controls
│   ├── app.js                # SVG fan chart, What-If simulation, auth, and site table logic
│   └── style.css             # Dark/Light theme styles, role badges, and modals
├── data/
│   ├── raw/                  # ClinicalTrials.gov metadata & synthetic raw datasets
│   └── processed/            # Multi-center longitudinal weekly site panel (Parquet & CSV)
├── src/
│   ├── data/                 # ClinicalTrials.gov API metadata & hospital flow generators
│   ├── features/             # Feature pipeline, Fourier harmonics, standardization
│   ├── models/               # Baselines & PyMC Hierarchical Bayesian models
│   └── simulation/           # Synthetic trial generator & Monte Carlo forecast engine
├── models_cache/             # Serialized NetCDF posterior traces (Model A/B/C)
├── reports/                  # Backtest metrics, summary JSONs, and diagnostic figures
│   └── figures/              # Trajectory fan charts, site heterogeneity, PPC comparison
├── tests/                    # Pytest test suite for API, features, and model baselines
├── config.yaml               # Experiment and simulation parameters
└── requirements.txt          # Python dependencies
```

---

## 🚀 Quick Start

### 1. Prerequisites & Environment Setup
Clone this repository and create a Python 3.11 virtual environment:

```bash
git clone https://github.com/Vijayaraj21/Adaptive-Clinical-Trial-Site-Enrollment-Forecasting-.git
cd Adaptive-Clinical-Trial-Site-Enrollment-Forecasting-

python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Launch the Application
Start the Uvicorn web server:

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser to:
- **Interactive Dashboard**: [http://localhost:8000/](http://localhost:8000/)
- **Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Specification**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🧪 Testing

Run the test suite using pytest:

```bash
pytest tests/ -v
```

---

## 📊 Model Comparison & Backtest Summary

| Model | MAE | RMSE | MAPE (%) | 80% Coverage | 95% Coverage |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Hierarchical Bayesian (Full Flow)** | **119.8** | **145.1** | **4.17%** | 56% | 81% |
| **Pooled Poisson Baseline** | 115.0 | 188.0 | 4.04% | 94% | 94% |
| **XGBoost Lag Baseline** | 123.7 | 180.1 | 4.81% | 81% | 100% |
| **Ablation: No Pooling** | 166.0 | 218.0 | 5.41% | 88% | 94% |
| **Ablation: No Flow Covariates** | 182.5 | 254.2 | 5.74% | 81% | 88% |
