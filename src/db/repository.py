"""Data access layer for incidents and RCA results."""

from uuid import UUID
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import (
    Incident,
    IncidentLog,
    IncidentAlert,
    RCAResult,
    IncidentStatus,
)


class IncidentRepository:
    """Repository for incident CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_incident(
        self,
        title: str,
        description: Optional[str] = None,
        severity: str = "medium",
        timeline: Optional[list] = None,
    ) -> Incident:
        incident = Incident(
            title=title,
            description=description,
            severity=severity,
            timeline=timeline or [],
        )
        self.session.add(incident)
        await self.session.flush()
        return incident

    async def get_incident(self, incident_id: UUID) -> Optional[Incident]:
        result = await self.session.execute(
            select(Incident)
            .options(
                selectinload(Incident.logs),
                selectinload(Incident.alerts),
                selectinload(Incident.rca_results),
            )
            .where(Incident.id == incident_id)
        )
        return result.scalar_one_or_none()

    async def list_incidents(
        self, status: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> List[Incident]:
        query = select(Incident).order_by(Incident.created_at.desc())
        if status:
            query = query.where(Incident.status == status)
        query = query.limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_status(self, incident_id: UUID, status: IncidentStatus) -> Optional[Incident]:
        incident = await self.get_incident(incident_id)
        if incident:
            incident.status = status
            incident.updated_at = datetime.utcnow()
            await self.session.flush()
        return incident

    async def add_logs(self, incident_id: UUID, logs: List[dict]) -> List[IncidentLog]:
        log_entries = []
        for log_data in logs:
            log_entry = IncidentLog(
                incident_id=incident_id,
                source=log_data.get("source", "unknown"),
                timestamp=log_data.get("timestamp", datetime.utcnow()),
                level=log_data.get("level", "INFO"),
                message=log_data.get("message", ""),
                metadata_=log_data.get("metadata"),
            )
            self.session.add(log_entry)
            log_entries.append(log_entry)
        await self.session.flush()
        return log_entries

    async def add_alerts(self, incident_id: UUID, alerts: List[dict]) -> List[IncidentAlert]:
        alert_entries = []
        for alert_data in alerts:
            alert_entry = IncidentAlert(
                incident_id=incident_id,
                alert_name=alert_data.get("alert_name", "Unknown Alert"),
                source=alert_data.get("source", "unknown"),
                severity=alert_data.get("severity"),
                triggered_at=alert_data.get("triggered_at", datetime.utcnow()),
                resolved_at=alert_data.get("resolved_at"),
                description=alert_data.get("description"),
                labels=alert_data.get("labels"),
            )
            self.session.add(alert_entry)
            alert_entries.append(alert_entry)
        await self.session.flush()
        return alert_entries

    async def save_rca_result(self, incident_id: UUID, rca_data: dict) -> RCAResult:
        rca = RCAResult(
            incident_id=incident_id,
            root_cause=rca_data.get("root_cause", ""),
            root_cause_category=rca_data.get("root_cause_category"),
            confidence_score=rca_data.get("confidence_score"),
            affected_systems=rca_data.get("affected_systems", []),
            impact_analysis=rca_data.get("impact_analysis"),
            prevention_plan=rca_data.get("prevention_plan"),
            postmortem_summary=rca_data.get("postmortem_summary"),
            raw_llm_output=rca_data.get("raw_llm_output"),
            ticket_id=rca_data.get("ticket_id"),
        )
        self.session.add(rca)
        await self.session.flush()
        return rca

    async def get_rca_result(self, incident_id: UUID) -> Optional[RCAResult]:
        result = await self.session.execute(
            select(RCAResult)
            .where(RCAResult.incident_id == incident_id)
            .order_by(RCAResult.created_at.desc())
        )
        return result.scalar_one_or_none()