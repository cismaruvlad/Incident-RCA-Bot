"""Structured output schemas for LangChain chains (structured output)."""

from pydantic import BaseModel, Field
from typing import List, Optional


class RootCauseAnalysis(BaseModel):
    """Structured root cause analysis output."""

    root_cause: str = Field(
        description="A clear, concise description of the most probable root cause of the incident."
    )
    root_cause_category: str = Field(
        description=(
            "Category of the root cause. One of: "
            "infrastructure, deployment, configuration, code_bug, dependency, "
            "capacity, network, security, human_error, external, unknown"
        )
    )
    confidence_score: str = Field(
        description="Confidence level: high, medium, or low"
    )
    evidence: List[str] = Field(
        description="List of specific log entries, alerts, or timeline events that support this root cause."
    )
    reasoning: str = Field(
        description="Step-by-step reasoning that led to this root cause determination."
    )


class AffectedSystem(BaseModel):
    """A single affected system."""

    system_name: str = Field(description="Name of the affected system or service.")
    impact_type: str = Field(
        description="Type of impact: outage, degradation, data_loss, latency, partial_failure"
    )
    impact_severity: str = Field(description="Severity: critical, high, medium, low")
    description: str = Field(description="Description of how this system was affected.")


class SystemImpactReport(BaseModel):
    """System impact analysis output."""

    affected_systems: List[AffectedSystem] = Field(
        description="List of all systems/services affected by the incident."
    )
    blast_radius: str = Field(
        description="Description of the overall blast radius — how far the impact spread."
    )
    user_impact: str = Field(
        description="Description of the end-user impact."
    )
    data_impact: str = Field(
        description="Any data loss or data integrity issues."
    )
    duration_estimate: str = Field(
        description="Estimated duration of impact."
    )


class PreventionAction(BaseModel):
    """A single prevention action item."""

    action: str = Field(description="Specific action to take.")
    priority: str = Field(description="Priority: P0, P1, P2, P3")
    owner: str = Field(description="Suggested team or role to own this action.")
    timeline: str = Field(description="Suggested timeline for completion.")


class PreventionPlan(BaseModel):
    """Prevention plan output."""

    immediate_actions: List[PreventionAction] = Field(
        description="Actions to take immediately to prevent recurrence."
    )
    short_term_actions: List[PreventionAction] = Field(
        description="Actions for the next 1-2 weeks."
    )
    long_term_actions: List[PreventionAction] = Field(
        description="Strategic improvements for the next quarter."
    )
    monitoring_improvements: List[str] = Field(
        description="Suggestions for improved monitoring and alerting."
    )


class PostmortemSummary(BaseModel):
    """Complete postmortem document output."""

    title: str = Field(description="Postmortem title.")
    executive_summary: str = Field(description="2-3 sentence executive summary.")
    timeline_summary: str = Field(description="Chronological summary of key events.")
    root_cause_summary: str = Field(description="Summary of the root cause.")
    impact_summary: str = Field(description="Summary of impact.")
    resolution_summary: str = Field(description="How the incident was resolved.")
    lessons_learned: List[str] = Field(description="Key lessons learned.")
    action_items: List[str] = Field(description="Follow-up action items.")


class FullRCAOutput(BaseModel):
    """Complete RCA output combining all analyses."""

    root_cause_analysis: RootCauseAnalysis
    system_impact: SystemImpactReport
    prevention_plan: PreventionPlan
    postmortem: PostmortemSummary