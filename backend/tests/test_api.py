import time

def test_health(client):
    response=client.get("/health")
    assert response.status_code==200
    assert response.json()["status"]=="ok"

def test_dashboard(client):
    response=client.get("/api/v1/dashboard/summary")
    assert response.status_code==200
    assert response.json()["healthy_services"]>=5

def test_create_experiment_and_report(client):
    response=client.post("/api/v1/experiments",json={"name":"Payment latency resilience test","target":"payments","scenario":"latency_injection","duration_seconds":20,"intensity":65,"hypothesis":"Payment requests should remain bounded."})
    assert response.status_code==202
    experiment_id=response.json()["id"]
    for _ in range(60):
        result=client.get(f"/api/v1/experiments/{experiment_id}").json()
        if result["status"] in {"COMPLETED","FAILED","ABORTED"}: break
        time.sleep(.03)
    assert result["status"]=="COMPLETED"
    assert result["resilience_score"] is not None
    assert len(result["metrics"])>=8
    pdf=client.get(f"/api/v1/experiments/{experiment_id}/report.pdf")
    assert pdf.status_code==200 and pdf.content.startswith(b"%PDF")

def test_ec2_real_scenario_not_allowed_in_local_mode(client):
    response=client.post("/api/v1/experiments",json={"name":"Guardrail test","target":"lab-ec2","scenario":"ec2_stop","duration_seconds":30,"intensity":50})
    assert response.status_code==400

def test_input_validation(client):
    response=client.post("/api/v1/experiments",json={"name":"x","target":"db","scenario":"latency_injection","duration_seconds":500,"intensity":50})
    assert response.status_code==422


def test_compare_completed_experiments(client):
    ids = []
    for name, scenario in [("Baseline test", "latency_injection"), ("Recovery test", "queue_backlog")]:
        response = client.post("/api/v1/experiments", json={
            "name": name,
            "target": "payments",
            "scenario": scenario,
            "duration_seconds": 10,
            "intensity": 35,
        })
        assert response.status_code == 202
        ids.append(response.json()["id"])
    completed = set()
    for _ in range(120):
        for experiment_id in ids:
            item = client.get(f"/api/v1/experiments/{experiment_id}").json()
            if item["status"] == "COMPLETED":
                completed.add(experiment_id)
        if len(completed) == 2:
            break
        time.sleep(.02)
    assert len(completed) == 2
    comparison = client.post("/api/v1/experiments/compare", json={"experiment_ids": ids})
    assert comparison.status_code == 200
    assert len(comparison.json()) == 2
