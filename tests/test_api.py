"""
Contract and Integration Tests for FastAPI Endpoints.
"""

import pytest
import httpx
from httpx import ASGITransport
from main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["tickets_loaded"] >= 500
        assert data["accounts_loaded"] >= 50


@pytest.mark.asyncio
async def test_dashboard_endpoint():
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert "SupportTAM AI Platform" in response.text
        assert "Tab 1: Ticket Triage Studio" in response.text


@pytest.mark.asyncio
async def test_triage_endpoint_p1():
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "subject": "Production Database Connection Timeout across US-East cluster",
            "body": "All API nodes are returning 500 errors. Customers cannot log in. Immediate escalation needed."
        }
        response = await client.post("/api/v1/triage", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["urgency"] == "P1"
        assert "product_area" in data
        assert "recommended_team" in data
        assert "draft_response" in data


@pytest.mark.asyncio
async def test_tam_brief_endpoint():
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/tam-brief/ACC-3336")
        assert response.status_code == 200
        data = response.json()
        assert data["account_id"] == "ACC-3336"
        assert "executive_summary" in data
        assert "open_risks" in data
        assert "recommended_talking_points" in data
