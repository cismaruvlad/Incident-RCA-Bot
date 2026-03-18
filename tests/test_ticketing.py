"""Tests for the ticket creator."""

import pytest
import json
from unittest.mock import AsyncMock, patch
from src.ticketing.ticket_creator import TicketCreator


@pytest.fixture
def sample_rca_output():
    """Sample RCA output for ticket formatting."""
    return {
        "incident_title": "Payment Service Outage",
        "analysis": {
            "root_cause_analysis": {
                "root_cause": "Database connection pool exhaustion",
                "root_cause_category": "deployment",
                "confidence_score": "high",
                "evidence": ["Log: pool exhausted"],
                "reasoning": "Deployment caused issues",
            },
            "system_impact": {
                "affected_systems": [
                    {
                        "system_name": "payment-service",
                        "impact_type": "outage",
                        "impact_severity": "critical",
                        "description": "Complete outage",
                    },
                    {
                        "system_name": "api-gateway",
                        "impact_type": "degradation",
                        "impact_severity": "high",
                        "description": "503 errors",
                    },
                ],
                "blast_radius": "Payment processing",
                "user_impact": "Unable to pay",
                "data_impact": "None",
                "duration_estimate": "25 minutes",
            },
            "prevention_plan": {
                "immediate_actions": [
                    {"action": "Increase pool size", "priority": "P0", "owner": "Platform", "timeline": "Today"},
                ],
                "short_term_actions": [
                    {"action": "Add monitoring", "priority": "P1", "owner": "SRE", "timeline": "1 week"},
                ],
                "long_term_actions": [],
                "monitoring_improvements": ["Pool alerts"],
            },
            "postmortem": {
                "title": "Payment Outage Postmortem",
                "executive_summary": "Deployment caused DB pool exhaustion leading to 25-min outage",
                "timeline_summary": "Timeline",
                "root_cause_summary": "Pool exhaustion",
                "impact_summary": "25 min outage",
                "resolution_summary": "Rolled back",
                "lessons_learned": ["Load test"],
                "action_items": ["Increase pool"],
            },
        },
        "analysis_duration_seconds": 12.5,
    }


class TestTicketCreator:
    """Tests for TicketCreator."""

    def test_format_ticket(self, sample_rca_output):
        creator = TicketCreator(webhook_url="http://test.example.com/tickets")
        ticket = creator._format_ticket(sample_rca_output)

        assert "[RCA]" in ticket["title"]
        assert "Payment Service Outage" in ticket["title"]
        assert "deployment" in ticket["title"]
        assert "rca" in ticket["labels"]
        assert "auto-generated" in ticket["labels"]
        assert len(ticket["affected_systems"]) == 2
        assert "payment-service" in ticket["affected_systems"]
        assert len(ticket["action_items"]) >= 2
        assert "Database connection pool exhaustion" in ticket["description"]

    def test_format_slack_message(self, sample_rca_output):
        creator = TicketCreator(webhook_url="http://test.example.com/slack")
        slack_msg = creator.format_slack_message(sample_rca_output)

        assert "blocks" in slack_msg
        assert len(slack_msg["blocks"]) >= 2
        # Check header block
        header = slack_msg["blocks"][0]
        assert header["type"] == "header"
        assert "RCA" in header["text"]["text"]

    @pytest.mark.asyncio
    @patch("src.ticketing.ticket_creator.httpx.AsyncClient")
    async def test_create_ticket_success(self, MockClient, sample_rca_output):
        mock_response = AsyncMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "TICKET-456", "url": "https://example.com/TICKET-456"}
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client_instance

        creator = TicketCreator(webhook_url="http://test.example.com/tickets")
        result = await creator.create_ticket(sample_rca_output)

        assert result["success"] is True
        assert result["ticket_id"] == "TICKET-456"

    @pytest.mark.asyncio
    async def test_create_ticket_connection_error(self, sample_rca_output):
        """Test that connection errors are handled gracefully."""
        creator = TicketCreator(webhook_url="http://nonexistent.invalid/tickets")
        result = await creator.create_ticket(sample_rca_output)

        assert result["success"] is False
        assert "error" in result


# Need to import MagicMock at the top
from unittest.mock import MagicMock