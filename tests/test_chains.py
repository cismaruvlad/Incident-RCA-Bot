"""Tests for LangChain chains (mocked LLM calls)."""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from langchain_core.messages import AIMessage

from src.engine.schemas.output_schemas import (
    RootCauseAnalysis,
    SystemImpactReport,
    AffectedSystem,
    PreventionPlan,
    PreventionAction,
    PostmortemSummary,
)
from src.engine.chains.root_cause_chain import run_root_cause_analysis
from src.engine.chains.impact_chain import run_impact_analysis
from src.engine.chains.prevention_chain import run_prevention_analysis
from src.engine.chains.postmortem_chain import run_postmortem_generation


def _mock_rca_response():
    """Create a mock RootCauseAnalysis response."""
    return RootCauseAnalysis(
        root_cause="Database connection pool exhaustion caused by new batch processing feature holding connections for extended periods",
        root_cause_category="deployment",
        confidence_score="high",
        evidence=[
            "Log: 'Failed to acquire database connection: pool exhausted' at 14:00:12Z",
            "Alert: DatabaseConnectionPoolExhausted fired at 13:58:00Z",
            "Timeline: payment-service v2.3.1 deployed at 13:50:00Z with batch processing feature",
        ],
        reasoning=(
            "1. Deployment of v2.3.1 with batch processing feature at 13:50\n"
            "2. Connection pool warnings started at 13:55 (5 min after deploy)\n"
            "3. Pool exhaustion errors began at 14:00\n"
            "4. This indicates the new batch feature was consuming connections faster than they were released"
        ),
    )


def _mock_impact_response():
    """Create a mock SystemImpactReport response."""
    return SystemImpactReport(
        affected_systems=[
            AffectedSystem(
                system_name="payment-service",
                impact_type="outage",
                impact_severity="critical",
                description="Complete service outage - unable to process any payments",
            ),
            AffectedSystem(
                system_name="api-gateway",
                impact_type="degradation",
                impact_severity="high",
                description="Returning 503 errors for payment endpoints",
            ),
            AffectedSystem(
                system_name="order-service",
                impact_type="partial_failure",
                impact_severity="medium",
                description="Circuit breaker opened, orders queued",
            ),
        ],
        blast_radius="Payment processing pipeline and dependent order fulfillment",
        user_impact="Users unable to complete purchases for ~25 minutes",
        data_impact="Some transactions left in pending state; no data loss",
        duration_estimate="25 minutes (14:00 - 14:25 UTC)",
    )


def _mock_prevention_response():
    """Create a mock PreventionPlan response."""
    return PreventionPlan(
        immediate_actions=[
            PreventionAction(
                action="Increase DB connection pool size from 50 to 100",
                priority="P0",
                owner="Platform Team",
                timeline="Today",
            ),
        ],
        short_term_actions=[
            PreventionAction(
                action="Add connection pool monitoring and alerting at 80% threshold",
                priority="P1",
                owner="SRE Team",
                timeline="This week",
            ),
            PreventionAction(
                action="Add load testing for database-heavy features to CI pipeline",
                priority="P1",
                owner="Engineering Team",
                timeline="Next sprint",
            ),
        ],
        long_term_actions=[
            PreventionAction(
                action="Implement PgBouncer for connection pooling at infrastructure level",
                priority="P2",
                owner="Infrastructure Team",
                timeline="Next quarter",
            ),
        ],
        monitoring_improvements=[
            "Alert on connection pool usage > 80%",
            "Dashboard for active DB connections per service",
            "Canary deployment strategy for database-heavy changes",
        ],
    )


def _mock_postmortem_response():
    """Create a mock PostmortemSummary response."""
    return PostmortemSummary(
        title="Postmortem: Payment Service Outage - January 15, 2024",
        executive_summary=(
            "A deployment of payment-service v2.3.1 introduced a batch processing feature "
            "that exhausted the database connection pool, causing a 25-minute payment outage."
        ),
        timeline_summary=(
            "13:50 - Deployment of v2.3.1 | 13:55 - Pool warnings | "
            "14:00 - Full outage | 14:05 - Investigation started | "
            "14:15 - Root cause identified | 14:20 - Rollback | 14:25 - Recovery"
        ),
        root_cause_summary="New batch processing feature held database connections for too long, exhausting the pool.",
        impact_summary="25 minutes of payment processing outage affecting all customers.",
        resolution_summary="Rolled back to payment-service v2.3.0.",
        lessons_learned=[
            "Database-heavy features need load testing before deployment",
            "Connection pool monitoring should have tighter thresholds",
            "Batch processing should use dedicated connection pools",
        ],
        action_items=[
            "Increase connection pool size",
            "Add connection pool monitoring",
            "Implement PgBouncer",
            "Add load testing to CI pipeline",
        ],
    )


@pytest.mark.asyncio
class TestRootCauseChain:
    """Test root cause analysis chain with mocked LLM."""

    @patch("src.engine.chains.root_cause_chain.create_root_cause_chain")
    async def test_run_root_cause_analysis(self, mock_create_chain):
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = _mock_rca_response()
        mock_create_chain.return_value = mock_chain

        result = await run_root_cause_analysis("Test incident context")

        assert isinstance(result, RootCauseAnalysis)
        assert result.root_cause_category == "deployment"
        assert result.confidence_score == "high"
        assert len(result.evidence) > 0

    @patch("src.engine.chains.root_cause_chain.create_root_cause_chain")
    async def test_root_cause_has_reasoning(self, mock_create_chain):
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = _mock_rca_response()
        mock_create_chain.return_value = mock_chain

        result = await run_root_cause_analysis("Test context")

        assert len(result.reasoning) > 0
        assert "deploy" in result.reasoning.lower() or "batch" in result.reasoning.lower()


@pytest.mark.asyncio
class TestImpactChain:
    """Test impact analysis chain with mocked LLM."""

    @patch("src.engine.chains.impact_chain.create_impact_chain")
    async def test_run_impact_analysis(self, mock_create_chain):
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = _mock_impact_response()
        mock_create_chain.return_value = mock_chain

        result = await run_impact_analysis("Context", "Root cause data")

        assert isinstance(result, SystemImpactReport)
        assert len(result.affected_systems) == 3
        assert result.affected_systems[0].system_name == "payment-service"
        assert result.affected_systems[0].impact_severity == "critical"


@pytest.mark.asyncio
class TestPreventionChain:
    """Test prevention plan chain with mocked LLM."""

    @patch("src.engine.chains.prevention_chain.create_prevention_chain")
    async def test_run_prevention_analysis(self, mock_create_chain):
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = _mock_prevention_response()
        mock_create_chain.return_value = mock_chain

        result = await run_prevention_analysis("Context", "Root cause", "Impact")

        assert isinstance(result, PreventionPlan)
        assert len(result.immediate_actions) >= 1
        assert result.immediate_actions[0].priority == "P0"
        assert len(result.monitoring_improvements) > 0


@pytest.mark.asyncio
class TestPostmortemChain:
    """Test postmortem generation chain with mocked LLM."""

    @patch("src.engine.chains.postmortem_chain.create_postmortem_chain")
    async def test_run_postmortem_generation(self, mock_create_chain):
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = _mock_postmortem_response()
        mock_create_chain.return_value = mock_chain

        result = await run_postmortem_generation("Context", "Root cause", "Impact", "Prevention")

        assert isinstance(result, PostmortemSummary)
        assert "Payment Service" in result.title
        assert len(result.lessons_learned) > 0
        assert len(result.action_items) > 0