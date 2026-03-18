"""
Ticket/Issue creator — sends RCA results to external ticketing systems.
Supports webhook-based integration (Slack, Jira, PagerDuty, ServiceNow, etc.)
"""

import httpx
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import structlog

from src.config import get_settings

logger = structlog.get_logger(__name__)


class TicketCreator:
    """Creates tickets/issues from RCA results via webhooks."""

    def __init__(self, webhook_url: Optional[str] = None):
        settings = get_settings()
        self.webhook_url = webhook_url or settings.ticketing_webhook_url

    async def create_ticket(self, rca_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a ticket from RCA analysis results.

        In production, this would integrate with Jira, ServiceNow, Slack, etc.
        For the MVP, it posts to a configurable webhook endpoint.
        """
        ticket_payload = self._format_ticket(rca_output)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.webhook_url,
                    json=ticket_payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()

                logger.info(
                    "Ticket created successfully",
                    status_code=response.status_code,
                    webhook=self.webhook_url,
                )

                return {
                    "success": True,
                    "ticket_id": response.json().get("id", "unknown"),
                    "url": response.json().get("url", ""),
                    "status_code": response.status_code,
                }

        except httpx.HTTPStatusError as e:
            logger.error("Ticket creation failed (HTTP error)", error=str(e))
            return {"success": False, "error": f"HTTP {e.response.status_code}: {str(e)}"}
        except httpx.RequestError as e:
            logger.warning("Ticket creation failed (connection error)", error=str(e))
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error("Ticket creation failed (unexpected)", error=str(e))
            return {"success": False, "error": str(e)}

    def _format_ticket(self, rca_output: Dict[str, Any]) -> Dict[str, Any]:
        """Format RCA output into a ticket-compatible payload."""
        analysis = rca_output.get("analysis", {})
        rca = analysis.get("root_cause_analysis", {})
        impact = analysis.get("system_impact", {})
        prevention = analysis.get("prevention_plan", {})
        postmortem = analysis.get("postmortem", {})

        # Build affected systems list
        affected = [s.get("system_name", "unknown") for s in impact.get("affected_systems", [])]

        # Build action items from prevention plan
        all_actions = []
        for action in prevention.get("immediate_actions", []):
            all_actions.append(f"[{action.get('priority', 'P2')}] {action.get('action', '')}")
        for action in prevention.get("short_term_actions", []):
            all_actions.append(f"[{action.get('priority', 'P2')}] {action.get('action', '')}")

        # Compose description
        description_parts = [
            f"## Root Cause\n{rca.get('root_cause', 'Unknown')}",
            f"\n**Category**: {rca.get('root_cause_category', 'unknown')}",
            f"**Confidence**: {rca.get('confidence_score', 'unknown')}",
            f"\n## Affected Systems\n" + "\n".join(f"- {s}" for s in affected) if affected else "",
            f"\n## Impact\n{impact.get('user_impact', 'Unknown')}",
            f"\n## Blast Radius\n{impact.get('blast_radius', 'Unknown')}",
            f"\n## Action Items\n" + "\n".join(f"- {a}" for a in all_actions) if all_actions else "",
            f"\n## Postmortem\n{postmortem.get('executive_summary', '')}",
        ]

        return {
            "title": f"[RCA] {rca_output.get('incident_title', 'Incident')} - {rca.get('root_cause_category', 'Unknown')}",
            "description": "\n".join(description_parts),
            "severity": rca.get('confidence_score', 'medium'),
            "labels": [
                "rca",
                "auto-generated",
                rca.get("root_cause_category", "unknown"),
            ],
            "affected_systems": affected,
            "action_items": all_actions,
            "created_at": datetime.utcnow().isoformat(),
            "metadata": {
                "analysis_duration": rca_output.get("analysis_duration_seconds"),
                "rca_bot_version": "1.0.0",
            },
        }

    def format_slack_message(self, rca_output: Dict[str, Any]) -> Dict[str, Any]:
        """Format RCA output as a Slack message payload."""
        analysis = rca_output.get("analysis", {})
        rca = analysis.get("root_cause_analysis", {})
        impact = analysis.get("system_impact", {})
        postmortem = analysis.get("postmortem", {})

        affected = [s.get("system_name", "?") for s in impact.get("affected_systems", [])]

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🔍 RCA: {rca_output.get('incident_title', 'Incident')}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Root Cause:*\n{rca.get('root_cause', 'Unknown')[:300]}"},
                    {"type": "mrkdwn", "text": f"*Category:* {rca.get('root_cause_category', 'unknown')}"},
                    {"type": "mrkdwn", "text": f"*Confidence:* {rca.get('confidence_score', 'unknown')}"},
                    {"type": "mrkdwn", "text": f"*Affected:* {', '.join(affected[:5])}"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Executive Summary:*\n{postmortem.get('executive_summary', 'N/A')[:500]}",
                },
            },
        ]

        return {"blocks": blocks}