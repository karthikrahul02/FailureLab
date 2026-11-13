from fastapi.testclient import TestClient
from app.main import app


def test_control_is_protected():
    client = TestClient(app)
    response = client.put("/control/fault", json={"scenario": "latency_injection", "active": True, "intensity": 50})
    assert response.status_code == 403


def test_fault_can_be_configured_and_observed():
    client = TestClient(app)
    headers = {"x-lab-control-token": "local-testbed-control-token"}
    configured = client.put("/control/fault", headers=headers, json={"scenario": "service_unavailable", "active": True, "intensity": 100})
    assert configured.status_code == 200
    response_codes = [client.get("/api/checkout").status_code for _ in range(10)]
    assert 503 in response_codes
    assert client.get("/metrics").json()["failed_count"] > 0
    assert client.post("/control/reset", headers=headers).status_code == 200
