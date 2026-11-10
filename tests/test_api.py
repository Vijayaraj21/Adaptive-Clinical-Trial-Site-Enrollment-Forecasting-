"""Unit and integration tests for FastAPI backend endpoints."""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ok", "healthy"]
    assert "trace_loaded" in data


def test_trials_endpoint():
    response = client.get("/api/trials")
    assert response.status_code == 200
    data = response.json()
    assert data["total_sites"] == 40
    assert "trial_id" in data


def test_sites_endpoint():
    response = client.get("/api/sites?current_week=40&target=1200&deadline=90")
    assert response.status_code == 200
    data = response.json()
    assert len(data["sites"]) == 40
    assert "at_risk_count" in data


def test_forecast_endpoint():
    payload = {
        "current_week": 40,
        "target": 1200,
        "deadline": 90,
        "flow_change": 0.15,
        "new_sites": 2,
        "closed": ["SITE_001"],
        "draws": 200,
    }
    response = client.post("/api/forecast", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "forecast_fan" in data
    assert len(data["forecast_fan"]["q50"]) > 0
    assert "p_hit_by_deadline" in data
    assert 0.0 <= data["p_hit_by_deadline"] <= 1.0


def test_whatif_endpoint():
    payload = {
        "current_week": 40,
        "target": 1200,
        "deadline": 90,
        "flow_change": -0.20,
        "new_sites": 0,
        "closed": [],
        "draws": 200,
    }
    response = client.post("/api/whatif", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "baseline" in data
    assert "scenario" in data
    assert "delta_completion_week" in data


def test_update_endpoint():
    payload = {
        "records": [
            {
                "site_id": "SITE_001",
                "week": 41,
                "enrolled_count": 3,
                "eligible_volume": 45,
                "is_active": 1,
            }
        ],
        "recalculate_forecast": True,
    }
    response = client.post("/api/update", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["ingested_count"] == 1


def test_auth_login_vijay():
    # Dedicated Vijay Superuser
    resp = client.post("/api/auth/login", json={"username": "Vijay", "password": "1704"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "admin"
    assert "Vijay" in data["full_name"]
    assert "token" in data
    assert "*" in data["permissions"]


def test_auth_login_management():
    # Management / Operations
    resp = client.post("/api/auth/login", json={"username": "manager", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "management"
    assert "simulate_whatif" in data["permissions"]


def test_auth_login_investigator_removed():
    # Verify removed investigator / user accounts return 401 Unauthorized
    resp = client.post("/api/auth/login", json={"username": "investigator", "password": "user123"})
    assert resp.status_code == 401
    resp2 = client.post("/api/auth/login", json={"username": "user", "password": "user123"})
    assert resp2.status_code == 401


def test_auth_login_invalid():
    resp = client.post("/api/auth/login", json={"username": "wrong", "password": "bad"})
    assert resp.status_code == 401


def test_auth_demo_users():
    resp = client.get("/api/auth/demo-users")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    roles = [u["role"] for u in data]
    assert "admin" in roles and "management" in roles
    assert "user" not in roles

