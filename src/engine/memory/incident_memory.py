"""LangChain memory for maintaining context across multi-step RCA analysis."""

from langchain.memory import ConversationBufferMemory
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from typing import Dict, Any, Optional
import json


class IncidentMemory:
    """
    Manages conversational memory for the RCA analysis pipeline.
    Maintains context across multiple chain invocations so each step
    can reference findings from previous steps (LangChain memory concept).
    """

    def __init__(self):
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="output",
        )
        self._incident_context: Dict[str, Any] = {}
        self._step_results: Dict[str, Any] = {}

    def set_incident_context(
        self,
        incident_title: str,
        logs_summary: str,
        alerts_summary: str,
        timeline_summary: str,
        monitoring_data: Optional[str] = None,
    ):
        """Store the incident context for reference by all chains."""
        self._incident_context = {
            "incident_title": incident_title,
            "logs_summary": logs_summary,
            "alerts_summary": alerts_summary,
            "timeline_summary": timeline_summary,
            "monitoring_data": monitoring_data or "No additional monitoring data.",
        }

        # Add initial context to memory
        context_message = (
            f"INCIDENT CONTEXT:\n"
            f"Title: {incident_title}\n\n"
            f"LOGS:\n{logs_summary}\n\n"
            f"ALERTS:\n{alerts_summary}\n\n"
            f"TIMELINE:\n{timeline_summary}\n\n"
            f"MONITORING DATA:\n{monitoring_data or 'N/A'}"
        )
        self.memory.chat_memory.add_message(
            SystemMessage(content=context_message)
        )

    def save_step_result(self, step_name: str, result: Any):
        """Save the result of an analysis step for use by subsequent steps."""
        self._step_results[step_name] = result

        # Serialize for memory
        if hasattr(result, "model_dump"):
            result_str = json.dumps(result.model_dump(), indent=2, default=str)
        elif isinstance(result, dict):
            result_str = json.dumps(result, indent=2, default=str)
        else:
            result_str = str(result)

        self.memory.chat_memory.add_message(
            HumanMessage(content=f"Completed analysis step: {step_name}")
        )
        self.memory.chat_memory.add_message(
            AIMessage(content=f"Results for {step_name}:\n{result_str}")
        )

    def get_step_result(self, step_name: str) -> Optional[Any]:
        """Retrieve result from a previous step."""
        return self._step_results.get(step_name)

    def get_incident_context(self) -> Dict[str, Any]:
        """Return the raw incident context."""
        return self._incident_context

    def get_full_context_string(self) -> str:
        """Build a comprehensive context string for LLM prompts."""
        ctx = self._incident_context
        parts = [
            f"# Incident: {ctx.get('incident_title', 'Unknown')}",
            f"\n## Logs\n{ctx.get('logs_summary', 'N/A')}",
            f"\n## Alerts\n{ctx.get('alerts_summary', 'N/A')}",
            f"\n## Timeline\n{ctx.get('timeline_summary', 'N/A')}",
            f"\n## Monitoring Data\n{ctx.get('monitoring_data', 'N/A')}",
        ]

        # Include previous step results
        if self._step_results:
            parts.append("\n## Previous Analysis Results")
            for step, result in self._step_results.items():
                if hasattr(result, "model_dump"):
                    parts.append(f"\n### {step}\n{json.dumps(result.model_dump(), indent=2, default=str)}")
                else:
                    parts.append(f"\n### {step}\n{result}")

        return "\n".join(parts)

    def get_memory_variables(self) -> Dict[str, Any]:
        """Return memory variables for chain injection."""
        return self.memory.load_memory_variables({})

    def clear(self):
        """Reset memory."""
        self.memory.clear()
        self._incident_context.clear()
        self._step_results.clear()