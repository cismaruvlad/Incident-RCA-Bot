"""SQLAlchemy ORM models for incidents and RCA results."""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    Enum as SAEnum,
    JSON,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from src.db.database import Base


class IncidentSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentStatus(str, enum.Enum):
    OPEN = "open"
    ANALYZING = "analyzing"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Incident(Base):
    """Represents an incident submitted for analysis."""

    __tablename__ = "incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(
        SAEnum(IncidentSeverity, name="incident_severity"),
        default=IncidentSeverity.MEDIUM,
    )
    status = Column(
        SAEnum(IncidentStatus, name="incident_status"),
        default=IncidentStatus.OPEN,
    )
    timeline = Column(JSON, nullable=True)  # List of timeline events
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    logs = relationship("IncidentLog", back_populates="incident", cascade="all, delete-orphan")
    alerts = relationship("IncidentAlert", back_populates="incident", cascade="all, delete-orphan")
    rca_results = relationship("RCAResult", back_populates="incident", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_incidents_status", "status"),
        Index("idx_incidents_created_at", "created_at"),
    )


class IncidentLog(Base):
    """Raw log entries associated with an incident."""

    __tablename__ = "incident_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    source = Column(String(200), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    level = Column(String(20), nullable=True)  # ERROR, WARN, INFO, DEBUG
    message = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=True)

    incident = relationship("Incident", back_populates="logs")

    __table_args__ = (
        Index("idx_logs_incident_id", "incident_id"),
        Index("idx_logs_timestamp", "timestamp"),
    )


class IncidentAlert(Base):
    """Alerts/monitoring triggers associated with an incident."""

    __tablename__ = "incident_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    alert_name = Column(String(300), nullable=False)
    source = Column(String(200), nullable=False)
    severity = Column(String(20), nullable=True)
    triggered_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    description = Column(Text, nullable=True)
    labels = Column(JSON, nullable=True)

    incident = relationship("Incident", back_populates="alerts")

    __table_args__ = (Index("idx_alerts_incident_id", "incident_id"),)


class RCAResult(Base):
    """Stores the RCA analysis output."""

    __tablename__ = "rca_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    root_cause = Column(Text, nullable=False)
    root_cause_category = Column(String(100), nullable=True)
    confidence_score = Column(String(10), nullable=True)
    affected_systems = Column(JSON, nullable=True)  # List of affected system names
    impact_analysis = Column(Text, nullable=True)
    prevention_plan = Column(Text, nullable=True)
    postmortem_summary = Column(Text, nullable=True)
    raw_llm_output = Column(JSON, nullable=True)
    ticket_id = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    incident = relationship("Incident", back_populates="rca_results")

    __table_args__ = (Index("idx_rca_incident_id", "incident_id"),)