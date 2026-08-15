"""
Contract and Integration Tests for FastAPI Endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["tickets_loaded"] >= 500
    assert data["accounts_loaded"] >= 50


def test_dashboard_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "Support &amp; TAM AI Platform" in response.text or "Support & TAM AI Platform" in response.text
    assert "Tab 1: Ticket Triage Studio" in response.text


def test_triage_endpoint_p1():
    payload = {
        "subject": "Production Database Connection Timeout across US-East cluster",
        "body": "All API nodes are returning 500 errors. Customers cannot log in. Immediate escalation needed."
    }
    response = client.post("/api/v1/triage", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["urgency"] == "P1"
    assert "product_area" in data
    assert "recommended_team" in data
    assert "draft_response" in data


def test_tam_brief_endpoint():
    response = client.get("/api/v1/tam-brief/ACC-3336")
    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] == "ACC-3336"
    assert "executive_summary" in data
    assert "open_risks" in data
    assert "recommended_talking_points" in data


def test_run_evals_endpoint():
    response = client.post("/api/v1/run-evals", json={"run_adversarial": True})
    assert response.status_code == 200
    data = response.json()
    assert data["total_tests"] >= 10
    assert data["passed_tests"] > 0
    assert data["average_score"] >= 0.80
