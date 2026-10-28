"""Automated integration tests for FastAPI REST endpoints."""
import pytest
from fastapi.testclient import TestClient
from loyalty_ledger.api.main import app
from loyalty_ledger.db import init_db, SessionFactory
from loyalty_ledger.generator.data_generator import SyntheticDataGenerator
from loyalty_ledger.anomaly_detection.anomaly_injector import AnomalyInjector
from loyalty_ledger.domain.models import Customer

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_api_data():
    init_db()
    session = SessionFactory()
    try:
        if session.query(Customer).count() == 0:
            gen = SyntheticDataGenerator(seed=20261022)
            res = gen.generate_dataset(session=session, scale="starter")
            inj = AnomalyInjector(session=session, seed=20261022)
            inj.inject_anomalies(start_tx_idx=res["transactions_count"] + 1)
    finally:
        session.close()

def test_api_health():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"

def test_api_dashboard_summary():
    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["total_customers"] > 0
    assert data["total_orders"] > 0
    assert data["total_points_transactions"] > 0

def test_api_customers():
    res = client.get("/api/v1/customers?page=1&page_size=10")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 10
    assert data[0]["customer_id"].startswith("CUS-")

def test_api_orders():
    res = client.get("/api/v1/orders?page=1&page_size=5")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 5
    assert data[0]["order_id"].startswith("ORD-")

def test_api_validation_run():
    res = client.post("/api/v1/validation/run?mode=evaluation")
    assert res.status_code == 200
    data = res.json()
    assert data["total_checks"] == 20
    assert "findings" in data

def test_api_anomaly_evaluation():
    res = client.get("/api/v1/anomalies/evaluation")
    assert res.status_code == 200
    data = res.json()
    assert data["overall"]["f1_score"] == 1.0

def test_api_anomalies_and_by_id():
    res = client.get("/api/v1/anomalies")
    assert res.status_code == 200
    anomalies = res.json()
    assert len(anomalies) > 0
    first = anomalies[0]
    
    # Query specific anomaly
    res2 = client.get(f"/api/v1/anomalies/{first['issue_type']}")
    assert res2.status_code == 200
    assert res2.json()["issue_type"] == first["issue_type"]

def test_api_reports_summary():
    res = client.get("/api/v1/reports/summary")
    assert res.status_code == 200
    data = res.json()
    assert "evaluation" in data or "validation" in data or "dataset_manifest" in data

def test_api_tiers_and_rules():
    res = client.get("/api/v1/tiers")
    assert res.status_code == 200
    assert len(res.json()) >= 3
    
    res2 = client.get("/api/v1/rules")
    assert res2.status_code == 200
    assert len(res2.json()) >= 4

