"""API routes for incident management and RCA analysis."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.db.database import get_session
from src.db.repository import IncidentRepository
from src.db.models import IncidentStatus
from src.engine.rca_engine import RCAEngine
from src.ticketing.ticket_creator import TicketCreator

logger = structlog.get_logger(__name__)
router = APIRouter()


# ─── Request/Response Schemas ───────────────────────────────────────────────────

class TimelineEvent(BaseModel):
    timestamp: str = Field(..., description="ISO format timestamp")
    description: str = Field(..., description="Event description")
    type: Optional[str] = Field(None, description="Event type (alert, action, observation)")
    source: Optional[str] = None


class LogEntry(BaseModel):
    timestamp: Optional[str] = None
    level: Optional[str] = None
    source: Optional[str] = None
    message: str
    metadata: Optional[Dict[str, Any]] = None


class AlertEntry(BaseModel):
    alert_name: str
    source: str = "unknown"
    severity: Optional[str] = None
    triggered_at: Optional[str] = None
    resolved_at: Optional[str] = None
    description: Optional[str] = None
    labels: Optional[Dict[str, Any]] = None


class CreateIncidentRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    severity: str = Field(default="medium", pattern="^(critical|high|medium|low)$")
    timeline: Optional[List[TimelineEvent]] = None
    logs: Optional[List[LogEntry]] = None
    raw_logs: Optional[str] = None
    alerts: Optional[List[AlertEntry]] = None
    monitoring_data: Optional[str] = None
    otel_logs: Optional[List[Dict[str, Any]]] = None
    otel_spans: Optional[List[Dict[str, Any]]] = None

    model_config = {"json_schema_extra": {
        "example": {
            "title": "Payment Service Outage",
            "description": "Payment processing stopped working at 14:00 UTC",
            "severity": "critical",
            "timeline": [
                {"timestamp": "2024-01-15T14:00:00Z", "description": "First customer complaint received", "type": "observation"},
                {"timestamp": "2024-01-15T14:02:00Z", "description": "PagerDuty alert fired for payment-service error rate", "type": "alert"},
                {"timestamp": "2024-01-15T14:05:00Z", "description": "On-call engineer acknowledged", "type": "action"},
                {"timestamp": "2024-01-15T14:15:00Z", "description": "Identified database connection pool exhaustion", "type": "observation"},
                {"timestamp": "2024-01-15T14:20:00Z", "description": "Restarted payment-service pods", "type": "action"},
                {"timestamp": "2024-01-15T14:25:00Z", "description": "Service recovered", "type": "observation"},
            ],
            "logs": [
                {"timestamp": "2024-01-15T14:00:12Z", "level": "ERROR", "source": "payment-service", "message": "Failed to acquire database connection: pool exhausted"},
                {"timestamp": "2024-01-15T14:00:15Z", "level": "ERROR", "source": "payment-service", "message": "Transaction timeout after 30s waiting for DB connection"},
                {"timestamp": "2024-01-15T13:55:00Z", "level": "WARN", "source": "payment-service", "message": "Database connection pool utilization at 95%"},
                {"timestamp": "2024-01-15T13:50:00Z", "level": "INFO", "source": "deployment-pipeline", "message": "Deployed payment-service v2.3.1 with new batch processing feature"},
                {"timestamp": "2024-01-15T14:01:00Z", "level": "ERROR", "source": "api-gateway", "message": "Upstream payment-service returning 503"},
            ],
            "alerts": [
                {"alert_name": "PaymentServiceErrorRate", "source": "prometheus", "severity": "critical", "triggered_at": "2024-01-15T14:02:00Z", "description": "Error rate > 50% for payment-service"},
                {"alert_name": "DatabaseConnectionPoolExhausted", "source": "prometheus", "severity": "warning", "triggered_at": "2024-01-15T13:58:00Z", "description": "Connection pool usage > 90%"},
            ],
        }
    }}


class AnalyzeIncidentRequest(BaseModel):
    """Request to analyze an already-created incident."""
    create_ticket: bool = Field(default=False, description="Create a ticket after analysis")
    run_agent: bool = Field(default=True, description="Run agent pre-analysis step")


class AnalyzeDirectRequest(CreateIncidentRequest):
    """Direct analysis without persisting to DB first."""
    create_ticket: bool = False
    run_agent: bool = True


class IncidentResponse(BaseModel):
    id: str
    title: str
    severity: str
    status: str
    created_at: str


class RCAResultResponse(BaseModel):
    incident_id: str
    analysis: Dict[str, Any]
    agent_findings: Optional[str] = None
    analysis_duration_seconds: float
    ticket_result: Optional[Dict[str, Any]] = None


# ─── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/incidents", response_model=IncidentResponse, status_code=201)
async def create_incident(
    request: CreateIncidentRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a new incident record."""
    repo = IncidentRepository(session)

    timeline_dicts = [t.model_dump() for t in request.timeline] if request.timeline else []

    incident = await repo.create_incident(
        title=request.title,
        description=request.description,
        severity=request.severity,
        timeline=timeline_dicts,
    )

    # Add logs
    if request.logs:
        log_dicts = [l.model_dump() for l in request.logs]
        await repo.add_logs(incident.id, log_dicts)

    # Add alerts
    if request.alerts:
        alert_dicts = [a.model_dump() for a in request.alerts]
        await repo.add_alerts(incident.id, alert_dicts)

    await session.commit()

    return IncidentResponse(
        id=str(incident.id),
        title=incident.title,
        severity=incident.severity.value if hasattr(incident.severity, 'value') else incident.severity,
        status=incident.status.value if hasattr(incident.status, 'value') else incident.status,
        created_at=incident.created_at.isoformat(),
    )


@router.get("/incidents", response_model=List[IncidentResponse])
async def list_incidents(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    """List incidents with optional status filter."""
    repo = IncidentRepository(session)
    incidents = await repo.list_incidents(status=status, limit=limit, offset=offset)

    return [
        IncidentResponse(
            id=str(i.id),
            title=i.title,
            severity=i.severity.value if hasattr(i.severity, 'value') else str(i.severity),
            status=i.status.value if hasattr(i.status, 'value') else str(i.status),
            created_at=i.created_at.isoformat(),
        )
        for i in incidents
    ]


@router.get("/incidents/{incident_id}")
async def get_incident(
    incident_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get full incident details including logs, alerts, and RCA results."""
    repo = IncidentRepository(session)
    incident = await repo.get_incident(incident_id)

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    return {
        "id": str(incident.id),
        "title": incident.title,
        "description": incident.description,
        "severity": incident.severity.value if hasattr(incident.severity, 'value') else str(incident.severity),
        "status": incident.status.value if hasattr(incident.status, 'value') else str(incident.status),
        "timeline": incident.timeline,
        "created_at": incident.created_at.isoformat(),
        "logs": [
            {
                "id": str(log.id),
                "source": log.source,
                "timestamp": log.timestamp.isoformat(),
                "level": log.level,
                "message": log.message,
            }
            for log in (incident.logs or [])
        ],
        "alerts": [
            {
                "id": str(alert.id),
                "alert_name": alert.alert_name,
                "source": alert.source,
                "severity": alert.severity,
                "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
                "description": alert.description,
            }
            for alert in (incident.alerts or [])
        ],
        "rca_results": [
            {
                "id": str(rca.id),
                "root_cause": rca.root_cause,
                "root_cause_category": rca.root_cause_category,
                "confidence_score": rca.confidence_score,
                "affected_systems": rca.affected_systems,
                "postmortem_summary": rca.postmortem_summary,
                "ticket_id": rca.ticket_id,
                "created_at": rca.created_at.isoformat(),
            }
            for rca in (incident.rca_results or [])
        ],
    }


@router.post("/incidents/{incident_id}/analyze", response_model=RCAResultResponse)
async def analyze_incident(
    incident_id: UUID,
    request: AnalyzeIncidentRequest,
    session: AsyncSession = Depends(get_session),
):
    """Run RCA analysis on an existing incident."""
    repo = IncidentRepository(session)
    incident = await repo.get_incident(incident_id)

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Update status
    await repo.update_status(incident_id, IncidentStatus.ANALYZING)

    # Prepare data for engine
    logs_data = [
        {
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "level": log.level,
            "source": log.source,
            "message": log.message,
            "metadata": log.metadata_,
        }
        for log in (incident.logs or [])
    ]

    alerts_data = [
        {
            "alert_name": alert.alert_name,
            "source": alert.source,
            "severity": alert.severity,
            "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "description": alert.description,
            "labels": alert.labels,
        }
        for alert in (incident.alerts or [])
    ]

    # Run RCA engine
    engine = RCAEngine()
    try:
        rca_output = await engine.analyze(
            incident_title=incident.title,
            incident_description=incident.description,
            logs=logs_data,
            alerts=alerts_data,
            timeline=incident.timeline,
            run_agent=request.run_agent,
        )
    except Exception as e:
        logger.error("RCA analysis failed", error=str(e), incident_id=str(incident_id))
        await repo.update_status(incident_id, IncidentStatus.OPEN)
        raise HTTPException(status_code=500, detail=f"RCA analysis failed: {str(e)}")

    # Create ticket if requested
    ticket_result = None
    if request.create_ticket:
        try:
            ticket_creator = TicketCreator()
            ticket_result = await ticket_creator.create_ticket(rca_output)
        except Exception as e:
            logger.warning("Ticket creation failed", error=str(e))
            ticket_result = {"success": False, "error": str(e)}

    # Save results to database
    analysis = rca_output.get("analysis", {})
    rca_data = {
        "root_cause": analysis.get("root_cause_analysis", {}).get("root_cause", "Unknown"),
        "root_cause_category": analysis.get("root_cause_analysis", {}).get("root_cause_category"),
        "confidence_score": analysis.get("root_cause_analysis", {}).get("confidence_score"),
        "affected_systems": [
            s.get("system_name") for s in analysis.get("system_impact", {}).get("affected_systems", [])
        ],
        "impact_analysis": analysis.get("system_impact", {}).get("blast_radius"),
        "prevention_plan": str(analysis.get("prevention_plan", {})),
        "postmortem_summary": analysis.get("postmortem", {}).get("executive_summary"),
        "raw_llm_output": analysis,
        "ticket_id": ticket_result.get("ticket_id") if ticket_result and ticket_result.get("success") else None,
    }

    await repo.save_rca_result(incident_id, rca_data)
    await repo.update_status(incident_id, IncidentStatus.RESOLVED)
    await session.commit()

    return RCAResultResponse(
        incident_id=str(incident_id),
        analysis=analysis,
        agent_findings=rca_output.get("agent_findings"),
        analysis_duration_seconds=rca_output.get("analysis_duration_seconds", 0),
        ticket_result=ticket_result,
    )


@router.post("/analyze", response_model=RCAResultResponse)
async def analyze_direct(request: AnalyzeDirectRequest):
    """
    Direct analysis endpoint — submit incident data and get RCA results
    without persisting to the database. Useful for quick one-off analyses.
    """
    logs_data = [l.model_dump() for l in request.logs] if request.logs else None
    alerts_data = [a.model_dump() for a in request.alerts] if request.alerts else None
    timeline_data = [t.model_dump() for t in request.timeline] if request.timeline else None

    engine = RCAEngine()
    try:
        rca_output = await engine.analyze(
            incident_title=request.title,
            incident_description=request.description,
            logs=logs_data,
            raw_logs=request.raw_logs,
            alerts=alerts_data,
            timeline=timeline_data,
            otel_logs=request.otel_logs,
            otel_spans=request.otel_spans,
            monitoring_data=request.monitoring_data,
            run_agent=request.run_agent,
        )
    except Exception as e:
        logger.error("Direct RCA analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"RCA analysis failed: {str(e)}")

    # Optional ticket creation
    ticket_result = None
    if request.create_ticket:
        try:
            ticket_creator = TicketCreator()
            ticket_result = await ticket_creator.create_ticket(rca_output)
        except Exception as e:
            ticket_result = {"success": False, "error": str(e)}

    return RCAResultResponse(
        incident_id="direct-analysis",
        analysis=rca_output.get("analysis", {}),
        agent_findings=rca_output.get("agent_findings"),
        analysis_duration_seconds=rca_output.get("analysis_duration_seconds", 0),
        ticket_result=ticket_result,
    )


@router.get("/incidents/{incident_id}/rca")
async def get_rca_result(
    incident_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get the latest RCA result for an incident."""
    repo = IncidentRepository(session)
    rca = await repo.get_rca_result(incident_id)

    if not rca:
        raise HTTPException(status_code=404, detail="No RCA result found for this incident")

    return {
        "id": str(rca.id),
        "incident_id": str(rca.incident_id),
        "root_cause": rca.root_cause,
        "root_cause_category": rca.root_cause_category,
        "confidence_score": rca.confidence_score,
        "affected_systems": rca.affected_systems,
        "impact_analysis": rca.impact_analysis,
        "prevention_plan": rca.prevention_plan,
        "postmortem_summary": rca.postmortem_summary,
        "ticket_id": rca.ticket_id,
        "full_analysis": rca.raw_llm_output,
        "created_at": rca.created_at.isoformat(),
    }