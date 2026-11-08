# API Reference & Endpoints Guide

The Adaptive Clinical Trial Forecasting Engine provides a RESTful API powered by FastAPI with OpenAPI Swagger documentation accessible at `/docs` and ReDoc at `/redoc`.

Base URL: `http://localhost:8000`

---

## 1. Authentication Endpoints

### 1.1 Authenticate Session
`POST /api/auth/login`

**Request Body:**
```json
{
  "username": "vijayaraj",
  "password": "admin123"
}
```

**Response (200 OK):**
```json
{
  "username": "vijayaraj",
  "full_name": "Vijayaraj (System Administrator)",
  "role": "admin",
  "email": "vijayaraj@trial-operations.org",
  "token": "token_vijayaraj_admin",
  "permissions": ["*"]
}
```

### 1.2 Change Password
`POST /api/auth/change-password`

**Request Body:**
```json
{
  "username": "vijayaraj",
  "old_password": "admin123",
  "new_password": "MyNewSecurePassword456!"
}
```

---

## 2. Forecasting & Simulation Endpoints

### 2.1 Generate Forecast
`POST /api/forecast`

Generates longitudinal trajectory fan chart and completion week posterior probability density.

**Request Body:**
```json
{
  "current_week": 40,
  "target": 1200,
  "deadline": 90,
  "flow_change": 0.0,
  "new_sites": 0,
  "closed": [],
  "draws": 1000
}
```

**Response (200 OK):**
```json
{
  "trial_id": "NCT04280705",
  "current_week": 40,
  "target": 1200,
  "deadline": 90,
  "total_enrolled_to_date": 632,
  "p_hit_by_deadline": 0.92,
  "median_completion_week": 84,
  "active_sites_count": 40,
  "at_risk_sites_count": 6,
  "trajectory": {
    "weeks": [1, 2, "...", 104],
    "q10": [12, 28, "..."],
    "q50": [15, 34, "..."],
    "q90": [19, 41, "..."]
  }
}
```

### 2.2 What-If Policy Intervention Scenario
`POST /api/whatif`

Compares baseline status quo against a simulated policy scenario.

**Request Body:**
```json
{
  "current_week": 40,
  "target": 1200,
  "deadline": 90,
  "flow_change": 0.15,
  "new_sites": 3,
  "closed": ["SITE_003", "SITE_007"],
  "draws": 1000
}
```

---

## 3. Site Registry & Data Ingestion Endpoints

### 3.1 List Sites
`GET /api/sites?current_week=40&target=1200&deadline=90`

Returns per-site metrics, posterior rates, and risk flags.

### 3.2 Ingest Weekly Data Batch (Management & Admin)
`POST /api/update`

**Request Body:**
```json
{
  "records": [
    {
      "site_id": "SITE_001",
      "week": 41,
      "enrolled_count": 5,
      "eligible_volume": 52,
      "is_active": 1
    }
  ],
  "recalculate_forecast": true
}
```

---

## 4. Python SDK Example

```python
import requests

BASE_URL = "http://localhost:8000"

# 1. Login as Admin
login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
    "username": "vijayaraj",
    "password": "admin123"
}).json()
print("Authenticated as:", login_res["full_name"], "Role:", login_res["role"])

# 2. Run What-If Simulation
scenario = requests.post(f"{BASE_URL}/api/whatif", json={
    "current_week": 40,
    "target": 1200,
    "deadline": 90,
    "flow_change": 0.15,  # +15% patient flow surge
    "new_sites": 2,       # onboard 2 additional centers
    "closed": ["SITE_008"]
}).json()

print(f"Status Quo Completion: Week {scenario['baseline']['median_completion_week']}")
print(f"Simulated Scenario Completion: Week {scenario['scenario']['median_completion_week']}")
print(f"Timeline Weeks Saved: {scenario['delta_completion_week']} weeks")
```
