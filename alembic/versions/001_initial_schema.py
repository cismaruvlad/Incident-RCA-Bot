"""Initial schema.

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    incident_severity = sa.Enum("critical", "high", "medium", "low", name="incident_severity")
    incident_status = sa.Enum("open", "analyzing", "resolved", "closed", name="incident_status")
    incident_severity.create(op.get_bind(), checkfirst=True)
    incident_status.create(op.get_bind(), checkfirst=True)

    # Incidents table
    op.create_table(
        "incidents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("severity", incident_severity, default="medium"),
        sa.Column("status", incident_status, default="open"),
        sa.Column("timeline", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_incidents_status", "incidents", ["status"])
    op.create_index("idx_incidents_created_at", "incidents", ["created_at"])

    # Incident logs table
    op.create_table(
        "incident_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "incident_id",
            UUID(as_uuid=True),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("level", sa.String(20), nullable=True),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("metadata", JSON, nullable=True),
    )
    op.create_index("idx_logs_incident_id", "incident_logs", ["incident_id"])
    op.create_index("idx_logs_timestamp", "incident_logs", ["timestamp"])

    # Incident alerts table
    op.create_table(
        "incident_alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "incident_id",
            UUID(as_uuid=True),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alert_name", sa.String(300), nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("triggered_at", sa.DateTime, nullable=False),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("labels", JSON, nullable=True),
    )
    op.create_index("idx_alerts_incident_id", "incident_alerts", ["incident_id"])

    # RCA results table
    op.create_table(
        "rca_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "incident_id",
            UUID(as_uuid=True),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("root_cause", sa.Text, nullable=False),
        sa.Column("root_cause_category", sa.String(100), nullable=True),
        sa.Column("confidence_score", sa.String(10), nullable=True),
        sa.Column("affected_systems", JSON, nullable=True),
        sa.Column("impact_analysis", sa.Text, nullable=True),
        sa.Column("prevention_plan", sa.Text, nullable=True),
        sa.Column("postmortem_summary", sa.Text, nullable=True),
        sa.Column("raw_llm_output", JSON, nullable=True),
        sa.Column("ticket_id", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_rca_incident_id", "rca_results", ["incident_id"])


def downgrade() -> None:
    op.drop_table("rca_results")
    op.drop_table("incident_alerts")
    op.drop_table("incident_logs")
    op.drop_table("incidents")
    op.execute("DROP TYPE IF EXISTS incident_severity")
    op.execute("DROP TYPE IF EXISTS incident_status")