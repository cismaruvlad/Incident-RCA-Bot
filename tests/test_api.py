"""Tests for the FastAPI application and routes."""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from uuid import uuid4

from src.api.app import app


@pytest.fixture
def sample_incident_payload():
    """Full incident creation payload."""
    return {
        "title": "Payment Service Outage",
        "description": "Payment processing stopped working",
        "severity": "critical",
        "timeline": [
            {
                "timestamp": "2024-01-15T14:00:00Z",
                "description": "First customer complaint",
                "type": "observation",
            },
            {
                "timestamp": "2024-01-15T14:02:00Z",
                "description": "Alert fired",
                "type": "alert",
            },
        ],
        "logs": [
            {
                "timestamp": "2024-01-15T14:00:12Z",
                "level": "ERROR",
                "source": "payment-service",
                "message": "Failed to acquire database connection: pool exhausted",
            },
        ],
        "alerts": [
            {
                "alert_name": "PaymentServiceErrorRate",
                "source": "prometheus",
                "severity": "critical",
                "triggered_at": "2024-01-15T14:02:00Z",
                "description": "Error rate > 50%",
            },
        ],
    }


@pytest.fixture
def mock_rca_output():
    """Mock RCA engine output."""
    return {
        "incident_title": "Payment Service Outage",
        "analysis": {
            "root_cause_analysis": {
                "root_cause": "Database connection pool exhaustion",
                "root_cause_category": "deployment",
                "confidence_score": "high",
                "evidence": ["Log: pool exhausted"],
                "reasoning": "The deployment caused connection issues",
            },
            "system_impact": {
                "affected_systems": [
                    {
                        "system_name": "payment-service",
                        "impact_type": "outage",
                        "impact_severity": "critical",
                        "description": "Complete outage",
                    }
                ],
                "blast_radius": "Payment processing",
                "user_impact": "Unable to pay",
                "data_impact": "None",
                "duration_estimate": "25 minutes",
            },
            "prevention_plan": {
                "immediate_actions": [
                    {
                        "action": "Increase pool size",
                        "priority": "P0",
                        "owner": "Platform",
                        "timeline": "Today",
                    }
                ],
                "short_term_actions": [],
                "long_term_actions": [],
                "monitoring_improvements": ["Add pool monitoring"],
            },
            "postmortem": {
                "title": "Payment Outage Postmortem",
                "executive_summary": "Deployment caused DB pool exhaustion",
                "timeline_summary": "Timeline of events",
                "root_cause_summary": "Pool exhaustion",
                "impact_summary": "25 min outage",
                "resolution_summary": "Rolled back",
                "lessons_learned": ["Load test before deploy"],
                "action_items": ["Increase pool size"],
            },
        },
        "agent_findings": "Pre-analysis found connection pool issues",
        "analysis_duration_seconds": 15.3,
        "timestamp": "2024-01-15T15:00:00Z",
    }


@pytest.mark.asyncio
class TestHealthCheck:
    """Test health check endpoint."""

    async def test_health(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "incident-rca-bot"


@pytest.mark.asyncio
class TestDirectAnalysis:
    """Test the direct analysis endpoint (no DB required)."""

    @patch("src.api.routes.RCAEngine")
    async def test_analyze_direct(self, MockEngine, sample_incident_payload, mock_rca_output):
        # Setup mock
        mock_engine_instance = AsyncMock()
        mock_engine_instance.analyze.return_value = mock_rca_output
        MockEngine.return_value = mock_engine_instance

        payload = {**sample_incident_payload, "run_agent": False}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "analysis" in data
        assert data["analysis"]["root_cause_analysis"]["root_cause_category"] == "deployment"
        assert data["analysis"]["root_cause_analysis"]["confidence_score"] == "high"
        assert len(data["analysis"]["system_impact"]["affected_systems"]) > 0
        assert data["analysis_duration_seconds"] > 0

    @patch("src.api.routes.RCAEngine")
    async def test_analyze_direct_with_raw_logs(self, MockEngine, mock_rca_output):
        mock_engine_instance = AsyncMock()
        mock_engine_instance.analyze.return_value = mock_rca_output
        MockEngine.return_value = mock_engine_instance

        payload = {
            "title": "Test Incident",
            "raw_logs": "2024-01-15T14:00:00Z ERROR [svc] Something failed\n2024-01-15T14:01:00Z ERROR [svc] Connection refused",
            "run_agent": False,
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 200

    @patch("src.api.routes.RCAEngine")
    async def test_analyze_direct_minimal(self, MockEngine, mock_rca_output):
        """Test with minimal payload — just a title."""
        mock_engine_instance = AsyncMock()
        mock_engine_instance.analyze.return_value = mock_rca_output
        MockEngine.return_value = mock_engine_instance

        payload = {"title": "Something broke", "run_agent": False}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 200

    @patch("src.api.routes.RCAEngine")
    async def test_analyze_direct_engine_failure(self, MockEngine):
        """Test error handling when engine fails."""
        mock_engine_instance = AsyncMock()
        mock_engine_instance.analyze.side_effect = Exception("LLM API error")
        MockEngine.return_value = mock_engine_instance

        payload = {"title": "Failing incident", "run_agent": False}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 500
        assert "RCA analysis failed" in response.json()["detail"]

    async def test_analyze_direct_empty_title(self):
        """Test validation: empty title should fail."""
        payload = {"title": "", "run_agent": False}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
class TestTicketing:
    """Test ticket creation functionality."""

    @patch("src.api.routes.TicketCreator")
    @patch("src.api.routes.RCAEngine")
    async def test_analyze_with_ticket_creation(
        self, MockEngine, MockTicketCreator, sample_incident_payload, mock_rca_output
    ):
        # Setup RCA engine mock
        mock_engine_instance = AsyncMock()
        mock_engine_instance.analyze.return_value = mock_rca_output
        MockEngine.return_value = mock_engine_instance

        # Setup ticket creator mock
        mock_ticket_instance = AsyncMock()
        mock_ticket_instance.create_ticket.return_value = {
            "success": True,
            "ticket_id": "TICKET-123",
            "url": "https://jira.example.com/TICKET-123",
        }
        MockTicketCreator.return_value = mock_ticket_instance

        payload = {**sample_incident_payload, "create_ticket": True, "run_agent": False}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["ticket_result"]["success"] is True
        assert data["ticket_result"]["ticket_id"] == "TICKET-123"