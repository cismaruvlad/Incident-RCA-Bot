"""
Main RCA Engine — orchestrates the full multi-step analysis pipeline.

Pipeline:
1. Agent pre-analysis (tool-based pattern detection)
2. Root Cause Analysis chain
3. System Impact Analysis chain
4. Prevention Plan chain
5. Postmortem Summary chain

Each step feeds context into the next via IncidentMemory.
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import structlog

from src.engine.memory.incident_memory import IncidentMemory
from src.engine.agents.rca_agent import run_agent_pre_analysis
from src.engine.chains.root_cause_chain import run_root_cause_analysis
from src.engine.chains.impact_chain import run_impact_analysis
from src.engine.chains.prevention_chain import run_prevention_analysis
from src.engine.chains.postmortem_chain import run_postmortem_generation
from src.engine.schemas.output_schemas import FullRCAOutput
from src.ingestion.log_parser import LogParser
from src.ingestion.alert_parser import AlertParser
from src.ingestion.otel_collector import OTelLogCollector

logger = structlog.get_logger(__name__)


class RCAEngine:
    """
    Core engine that coordinates all RCA analysis steps.
    Implements the LangChain RCA Engine box from the architecture diagram.
    """

    def __init__(self):
        self.log_parser = LogParser()
        self.alert_parser = AlertParser()
        self.otel_collector = OTelLogCollector()
        self.memory = IncidentMemory()

    async def analyze(
        self,
        incident_title: str,
        incident_description: Optional[str] = None,
        logs: Optional[List[Dict[str, Any]]] = None,
        raw_logs: Optional[str] = None,
        alerts: Optional[List[Dict[str, Any]]] = None,
        timeline: Optional[List[Dict[str, Any]]] = None,
        otel_logs: Optional[List[Dict[str, Any]]] = None,
        otel_spans: Optional[List[Dict[str, Any]]] = None,
        monitoring_data: Optional[str] = None,
        run_agent: bool = True,
    ) -> Dict[str, Any]:
        """
        Run the full RCA analysis pipeline.

        Args:
            incident_title: Title of the incident
            incident_description: Optional description
            logs: Structured log entries
            raw_logs: Raw log text
            alerts: Alert data
            timeline: Timeline events
            otel_logs: OpenTelemetry log records
            otel_spans: OpenTelemetry span data
            monitoring_data: Additional monitoring context
            run_agent: Whether to run agent pre-analysis

        Returns:
            Complete RCA output dictionary
        """
        logger.info("Starting RCA analysis", incident=incident_title)
        start_time = datetime.utcnow()

        # ─── Step 0: Ingest and normalize data ──────────────────────────────
        logs_summary = self._prepare_logs(logs, raw_logs, otel_logs, otel_spans)
        alerts_summary = self._prepare_alerts(alerts)
        timeline_summary = self._prepare_timeline(timeline)

        # Initialize memory with incident context
        self.memory.clear()
        self.memory.set_incident_context(
            incident_title=incident_title,
            logs_summary=logs_summary,
            alerts_summary=alerts_summary,
            timeline_summary=timeline_summary,
            monitoring_data=monitoring_data,
        )

        incident_context = self.memory.get_full_context_string()

        # ─── Step 1: Agent pre-analysis (optional) ──────────────────────────
        agent_findings = ""
        if run_agent:
            try:
                agent_result = await run_agent_pre_analysis(incident_context, self.memory)
                agent_findings = agent_result.get("output", "")
                self.memory.save_step_result("agent_pre_analysis", agent_result)
                logger.info("Agent pre-analysis completed")
            except Exception as e:
                logger.warning("Agent pre-analysis failed, continuing without it", error=str(e))
                agent_findings = ""

        # Enrich context with agent findings
        enriched_context = incident_context
        if agent_findings:
            enriched_context += f"\n\n## Agent Pre-Analysis Findings\n{agent_findings}"

        # ─── Step 2: Root Cause Analysis ─────────────────────────────────────
        logger.info("Step 2: Running root cause analysis")
        root_cause_result = await run_root_cause_analysis(enriched_context)
        self.memory.save_step_result("root_cause_analysis", root_cause_result)
        root_cause_str = json.dumps(root_cause_result.model_dump(), indent=2, default=str)

        # ─── Step 3: System Impact Analysis ──────────────────────────────────
        logger.info("Step 3: Running impact analysis")
        impact_result = await run_impact_analysis(enriched_context, root_cause_str)
        self.memory.save_step_result("impact_analysis", impact_result)
        impact_str = json.dumps(impact_result.model_dump(), indent=2, default=str)

        # ─── Step 4: Prevention Plan ─────────────────────────────────────────
        logger.info("Step 4: Running prevention plan generation")
        prevention_result = await run_prevention_analysis(
            enriched_context, root_cause_str, impact_str
        )
        self.memory.save_step_result("prevention_plan", prevention_result)
        prevention_str = json.dumps(prevention_result.model_dump(), indent=2, default=str)

        # ─── Step 5: Postmortem Summary ──────────────────────────────────────
        logger.info("Step 5: Running postmortem generation")
        postmortem_result = await run_postmortem_generation(
            enriched_context, root_cause_str, impact_str, prevention_str
        )
        self.memory.save_step_result("postmortem", postmortem_result)

        # ─── Compile final output ────────────────────────────────────────────
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info("RCA analysis complete", elapsed_seconds=elapsed)

        full_output = FullRCAOutput(
            root_cause_analysis=root_cause_result,
            system_impact=impact_result,
            prevention_plan=prevention_result,
            postmortem=postmortem_result,
        )

        return {
            "incident_title": incident_title,
            "analysis": full_output.model_dump(),
            "agent_findings": agent_findings,
            "analysis_duration_seconds": elapsed,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _prepare_logs(
        self,
        logs: Optional[List[Dict[str, Any]]],
        raw_logs: Optional[str],
        otel_logs: Optional[List[Dict[str, Any]]],
        otel_spans: Optional[List[Dict[str, Any]]],
    ) -> str:
        """Parse and summarize all log sources into a text summary."""
        all_entries = []

        if logs:
            all_entries.extend(self.log_parser.parse_structured_logs(logs))
        if raw_logs:
            all_entries.extend(self.log_parser.parse_raw_logs(raw_logs))
        if otel_logs:
            all_entries.extend(self.otel_collector.parse_otel_logs(otel_logs))
        if otel_spans:
            all_entries.extend(self.otel_collector.parse_otel_spans(otel_spans))

        if not all_entries:
            return "No log data provided."

        # Sort by timestamp
        all_entries.sort(key=lambda x: x.get("timestamp", datetime.min))

        # Summarize: prioritize errors and warnings, limit total size
        error_entries = [e for e in all_entries if e.get("level") in ("ERROR", "CRITICAL", "FATAL")]
        warn_entries = [e for e in all_entries if e.get("level") == "WARN"]
        info_entries = [e for e in all_entries if e.get("level") not in ("ERROR", "CRITICAL", "FATAL", "WARN")]

        lines = [f"Total log entries: {len(all_entries)}"]
        lines.append(f"Error entries: {len(error_entries)}")
        lines.append(f"Warning entries: {len(warn_entries)}")
        lines.append("")

        if error_entries:
            lines.append("### Error Logs (most relevant)")
            for entry in error_entries[:30]:
                ts = entry.get("timestamp", "")
                if isinstance(ts, datetime):
                    ts = ts.isoformat()
                lines.append(f"[{ts}] [{entry.get('level')}] [{entry.get('source')}] {entry.get('message', '')}")

        if warn_entries:
            lines.append("\n### Warning Logs")
            for entry in warn_entries[:15]:
                ts = entry.get("timestamp", "")
                if isinstance(ts, datetime):
                    ts = ts.isoformat()
                lines.append(f"[{ts}] [{entry.get('level')}] [{entry.get('source')}] {entry.get('message', '')}")

        if info_entries and len(error_entries) + len(warn_entries) < 10:
            lines.append("\n### Info Logs (sample)")
            for entry in info_entries[:10]:
                ts = entry.get("timestamp", "")
                if isinstance(ts, datetime):
                    ts = ts.isoformat()
                lines.append(f"[{ts}] [{entry.get('level')}] [{entry.get('source')}] {entry.get('message', '')}")

        return "\n".join(lines)

    def _prepare_alerts(self, alerts: Optional[List[Dict[str, Any]]]) -> str:
        """Parse and summarize alerts into a text summary."""
        if not alerts:
            return "No alert data provided."

        parsed = self.alert_parser.parse_alerts(alerts)

        lines = [f"Total alerts: {len(parsed)}\n"]
        for alert in parsed:
            triggered = alert.get("triggered_at", "")
            if isinstance(triggered, datetime):
                triggered = triggered.isoformat()
            resolved = alert.get("resolved_at")
            if isinstance(resolved, datetime):
                resolved = resolved.isoformat()

            lines.append(
                f"- **{alert.get('alert_name')}** [{alert.get('severity', 'unknown')}] "
                f"from {alert.get('source', 'unknown')}\n"
                f"  Triggered: {triggered} | Resolved: {resolved or 'Ongoing'}\n"
                f"  Description: {alert.get('description', 'N/A')}"
            )

        return "\n".join(lines)

    def _prepare_timeline(self, timeline: Optional[List[Dict[str, Any]]]) -> str:
        """Format timeline events into a readable summary."""
        if not timeline:
            return "No timeline data provided."

        lines = [f"Total timeline events: {len(timeline)}\n"]

        # Sort by timestamp if present
        sorted_events = sorted(
            timeline,
            key=lambda x: x.get("timestamp", x.get("time", "")),
        )

        for i, event in enumerate(sorted_events, 1):
            ts = event.get("timestamp") or event.get("time", "Unknown time")
            description = event.get("description") or event.get("event") or event.get("message", "")
            event_type = event.get("type", "")
            source = event.get("source", "")

            line = f"{i}. [{ts}]"
            if event_type:
                line += f" ({event_type})"
            if source:
                line += f" [{source}]"
            line += f" {description}"
            lines.append(line)

        return "\n".join(lines)