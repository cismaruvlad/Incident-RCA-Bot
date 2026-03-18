"""Tests for the RCA engine components (unit tests that don't call OpenAI)."""

import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from src.engine.memory.incident_memory import IncidentMemory
from src.engine.schemas.output_schemas import (
    RootCauseAnalysis,
    SystemImpactReport,
    AffectedSystem,
    PreventionPlan,
    PreventionAction,
    PostmortemSummary,
    FullRCAOutput,
)
from src.engine.rca_engine import RCAEngine


class TestIncidentMemory:
    """Tests for the IncidentMemory class."""

    def test_set_and_get_context(self):
        memory = IncidentMemory()
        memory.set_incident_context(
            incident_title="Test Incident",
            logs_summary="Error logs here",
            alerts_summary="Critical alert fired",
            timeline_summary="14:00 - Alert triggered",
            monitoring_data="CPU at 95%",
        )

        ctx = memory.get_incident_context()
        assert ctx["incident_title"] == "Test Incident"
        assert ctx["logs_summary"] == "Error logs here"
        assert ctx["alerts_summary"] == "Critical alert fired"
        assert ctx["monitoring_data"] == "CPU at 95%"

    def test_save_and_get_step_result(self):
        memory = IncidentMemory()
        memory.set_incident_context(
            incident_title="Test",
            logs_summary="logs",
            alerts_summary="alerts",
            timeline_summary="timeline",
        )

        test_result = {"finding": "database issue"}
        memory.save_step_result("root_cause", test_result)

        retrieved = memory.get_step_result("root_cause")
        assert retrieved == test_result

    def test_get_nonexistent_step(self):
        memory = IncidentMemory()
        assert memory.get_step_result("nonexistent") is None

    def test_full_context_string(self):
        memory = IncidentMemory()
        memory.set_incident_context(
            incident_title="Outage",
            logs_summary="Connection refused",
            alerts_summary="HighErrorRate fired",
            timeline_summary="14:00 deploy, 14:05 errors",
        )

        context = memory.get_full_context_string()
        assert "Outage" in context
        assert "Connection refused" in context
        assert "HighErrorRate" in context

    def test_full_context_includes_step_results(self):
        memory = IncidentMemory()
        memory.set_incident_context(
            incident_title="Test",
            logs_summary="logs",
            alerts_summary="alerts",
            timeline_summary="timeline",
        )
        memory.save_step_result("root_cause", {"cause": "db failure"})

        context = memory.get_full_context_string()
        assert "root_cause" in context
        assert "db failure" in context

    def test_clear(self):
        memory = IncidentMemory()
        memory.set_incident_context(
            incident_title="Test",
            logs_summary="logs",
            alerts_summary="alerts",
            timeline_summary="timeline",
        )
        memory.save_step_result("test", {"data": "value"})

        memory.clear()
        assert memory.get_incident_context() == {}
        assert memory.get_step_result("test") is None

    def test_save_pydantic_model_step(self):
        memory = IncidentMemory()
        memory.set_incident_context(
            incident_title="Test",
            logs_summary="logs",
            alerts_summary="alerts",
            timeline_summary="timeline",
        )

        rca = RootCauseAnalysis(
            root_cause="Database connection pool exhaustion",
            root_cause_category="capacity",
            confidence_score="high",
            evidence=["Log line 1", "Alert fired"],
            reasoning="Step by step reasoning",
        )
        memory.save_step_result("root_cause", rca)

        retrieved = memory.get_step_result("root_cause")
        assert retrieved.root_cause == "Database connection pool exhaustion"

    def test_memory_variables(self):
        memory = IncidentMemory()
        memory.set_incident_context(
            incident_title="Test",
            logs_summary="logs",
            alerts_summary="alerts",
            timeline_summary="timeline",
        )

        variables = memory.get_memory_variables()
        assert "chat_history" in variables


class TestOutputSchemas:
    """Tests for Pydantic output schemas."""

    def test_root_cause_analysis_schema(self):
        rca = RootCauseAnalysis(
            root_cause="Connection pool exhausted due to long-running queries",
            root_cause_category="capacity",
            confidence_score="high",
            evidence=["Error log: pool exhausted", "Alert: connection pool > 90%"],
            reasoning="The deployment introduced batch queries that held connections too long",
        )
        data = rca.model_dump()
        assert data["root_cause_category"] == "capacity"
        assert len(data["evidence"]) == 2

    def test_system_impact_report_schema(self):
        report = SystemImpactReport(
            affected_systems=[
                AffectedSystem(
                    system_name="payment-service",
                    impact_type="outage",
                    impact_severity="critical",
                    description="Complete service outage",
                ),
                AffectedSystem(
                    system_name="api-gateway",
                    impact_type="degradation",
                    impact_severity="high",
                    description="Returning 503 for payment endpoints",
                ),
            ],
            blast_radius="Payment processing and downstream order fulfillment",
            user_impact="Users unable to complete purchases",
            data_impact="No data loss, but some transactions left in pending state",
            duration_estimate="25 minutes",
        )
        data = report.model_dump()
        assert len(data["affected_systems"]) == 2
        assert data["affected_systems"][0]["system_name"] == "payment-service"

    def test_prevention_plan_schema(self):
        plan = PreventionPlan(
            immediate_actions=[
                PreventionAction(
                    action="Increase connection pool size to 100",
                    priority="P0",
                    owner="Platform Team",
                    timeline="Immediately",
                )
            ],
            short_term_actions=[
                PreventionAction(
                    action="Add connection pool monitoring dashboard",
                    priority="P1",
                    owner="SRE Team",
                    timeline="1 week",
                )
            ],
            long_term_actions=[
                PreventionAction(
                    action="Implement connection pooling at infrastructure level (PgBouncer)",
                    priority="P2",
                    owner="Infrastructure Team",
                    timeline="Next quarter",
                )
            ],
            monitoring_improvements=[
                "Add alert for connection pool usage > 80%",
                "Add dashboard for active DB connections per service",
            ],
        )
        data = plan.model_dump()
        assert len(data["immediate_actions"]) == 1
        assert data["immediate_actions"][0]["priority"] == "P0"

    def test_postmortem_summary_schema(self):
        postmortem = PostmortemSummary(
            title="Payment Service Outage - Jan 15, 2024",
            executive_summary="A deployment introduced batch processing that exhausted DB connections.",
            timeline_summary="13:50 deploy, 13:55 warnings, 14:00 outage, 14:20 rollback, 14:25 recovery",
            root_cause_summary="New batch processing feature held DB connections too long.",
            impact_summary="25 minutes of payment processing outage.",
            resolution_summary="Rolled back to previous version.",
            lessons_learned=["Load test database-heavy features", "Add connection pool alerts"],
            action_items=["Increase pool size", "Add monitoring", "Load test before deploy"],
        )
        data = postmortem.model_dump()
        assert "Payment Service" in data["title"]

    def test_full_rca_output_schema(self):
        full = FullRCAOutput(
            root_cause_analysis=RootCauseAnalysis(
                root_cause="Test cause",
                root_cause_category="code_bug",
                confidence_score="medium",
                evidence=["ev1"],
                reasoning="reasoning",
            ),
            system_impact=SystemImpactReport(
                affected_systems=[],
                blast_radius="Limited",
                user_impact="Minor",
                data_impact="None",
                duration_estimate="5 min",
            ),
            prevention_plan=PreventionPlan(
                immediate_actions=[],
                short_term_actions=[],
                long_term_actions=[],
                monitoring_improvements=[],
            ),
            postmortem=PostmortemSummary(
                title="Test",
                executive_summary="Test summary",
                timeline_summary="Timeline",
                root_cause_summary="Cause",
                impact_summary="Impact",
                resolution_summary="Resolution",
                lessons_learned=[],
                action_items=[],
            ),
        )
        data = full.model_dump()
        assert "root_cause_analysis" in data
        assert "system_impact" in data
        assert "prevention_plan" in data
        assert "postmortem" in data


class TestRCAEngineDataPreparation:
    """Test the data preparation methods of RCAEngine (no LLM calls)."""

    def setup_method(self):
        self.engine = RCAEngine()

    def test_prepare_logs_from_structured(self, sample_logs):
        result = self.engine._prepare_logs(
            logs=sample_logs, raw_logs=None, otel_logs=None, otel_spans=None
        )
        assert "ERROR" in result or "Error" in result
        assert "payment-service" in result

    def test_prepare_logs_from_raw(self, sample_raw_logs):
        result = self.engine._prepare_logs(
            logs=None, raw_logs=sample_raw_logs, otel_logs=None, otel_spans=None
        )
        assert len(result) > 0
        assert "pool exhausted" in result.lower() or "error" in result.lower()

    def test_prepare_logs_from_otel(self, sample_otel_logs, sample_otel_spans):
        result = self.engine._prepare_logs(
            logs=None, raw_logs=None, otel_logs=sample_otel_logs, otel_spans=sample_otel_spans
        )
        assert len(result) > 0

    def test_prepare_logs_empty(self):
        result = self.engine._prepare_logs(
            logs=None, raw_logs=None, otel_logs=None, otel_spans=None
        )
        assert "No log data" in result

    def test_prepare_alerts(self, sample_alerts):
        result = self.engine._prepare_alerts(sample_alerts)
        assert "PaymentServiceErrorRate" in result
        assert "critical" in result.lower()

    def test_prepare_alerts_empty(self):
        result = self.engine._prepare_alerts(None)
        assert "No alert data" in result

    def test_prepare_timeline(self, sample_timeline):
        result = self.engine._prepare_timeline(sample_timeline)
        assert "deployed" in result.lower() or "deployment" in result.lower()
        assert len(result.split("\n")) > 3

    def test_prepare_timeline_empty(self):
        result = self.engine._prepare_timeline(None)
        assert "No timeline data" in result

    def test_prepare_combined_logs(self, sample_logs, sample_raw_logs, sample_otel_logs):
        """Test combining all log sources."""
        result = self.engine._prepare_logs(
            logs=sample_logs,
            raw_logs=sample_raw_logs,
            otel_logs=sample_otel_logs,
            otel_spans=None,
        )
        assert len(result) > 0
        # Should have merged entries from multiple sources
        assert "Error" in result or "ERROR" in result