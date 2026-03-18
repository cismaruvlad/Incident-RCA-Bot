"""
Multi-step RCA Agent that orchestrates the full analysis pipeline.
Uses LangChain's agent framework to coordinate tools and reasoning.
"""

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage
from typing import Dict, Any, Optional
import json
import structlog

from src.config import get_settings
from src.engine.chains.root_cause_chain import run_root_cause_analysis
from src.engine.chains.impact_chain import run_impact_analysis
from src.engine.chains.prevention_chain import run_prevention_analysis
from src.engine.chains.postmortem_chain import run_postmortem_generation
from src.engine.memory.incident_memory import IncidentMemory
from src.engine.schemas.output_schemas import FullRCAOutput

logger = structlog.get_logger(__name__)


# ─── Agent Tools ────────────────────────────────────────────────────────────────

@tool
def analyze_log_patterns(logs_text: str) -> str:
    """
    Analyze log entries to identify error patterns, anomalies, and correlations.
    Input: Raw or summarized log text.
    Output: Pattern analysis summary.
    """
    lines = logs_text.strip().split("\n")
    error_lines = [l for l in lines if any(w in l.lower() for w in ["error", "exception", "fatal", "panic", "fail"])]
    warn_lines = [l for l in lines if any(w in l.lower() for w in ["warn", "timeout", "retry", "degraded"])]

    analysis = {
        "total_log_lines": len(lines),
        "error_count": len(error_lines),
        "warning_count": len(warn_lines),
        "error_samples": error_lines[:10],
        "warning_samples": warn_lines[:5],
        "patterns_detected": [],
    }

    # Detect common patterns
    if any("timeout" in l.lower() for l in lines):
        analysis["patterns_detected"].append("TIMEOUT: Network or service timeout detected")
    if any("oom" in l.lower() or "out of memory" in l.lower() for l in lines):
        analysis["patterns_detected"].append("OOM: Out of memory condition detected")
    if any("connection refused" in l.lower() for l in lines):
        analysis["patterns_detected"].append("CONNECTION_REFUSED: Service unreachable")
    if any("disk" in l.lower() and ("full" in l.lower() or "space" in l.lower()) for l in lines):
        analysis["patterns_detected"].append("DISK_FULL: Disk space exhaustion detected")
    if any("certificate" in l.lower() or "ssl" in l.lower() or "tls" in l.lower() for l in lines):
        analysis["patterns_detected"].append("TLS_ISSUE: Certificate or TLS problem detected")
    if any("deploy" in l.lower() or "release" in l.lower() or "rollout" in l.lower() for l in lines):
        analysis["patterns_detected"].append("DEPLOYMENT: Deployment-related activity detected")
    if any("rate limit" in l.lower() or "throttl" in l.lower() for l in lines):
        analysis["patterns_detected"].append("RATE_LIMITING: Rate limiting or throttling detected")

    return json.dumps(analysis, indent=2)


@tool
def correlate_alerts_timeline(alerts_text: str, timeline_text: str) -> str:
    """
    Correlate alerts with timeline events to identify the sequence of failures.
    Input: Alert summaries and timeline text.
    Output: Correlated event sequence.
    """
    correlation = {
        "analysis": (
            "Correlating alerts with timeline events to establish causal chain. "
            "Looking for: first alert trigger, cascading failures, resolution events."
        ),
        "alerts_data": alerts_text[:2000],
        "timeline_data": timeline_text[:2000],
        "recommendation": "Use the correlated data to trace the sequence from initial trigger to full impact.",
    }
    return json.dumps(correlation, indent=2)


@tool
def identify_affected_services(context: str) -> str:
    """
    Identify all services and systems mentioned in the incident context.
    Input: Full incident context text.
    Output: List of identified services with their roles.
    """
    # Simple service extraction heuristic
    common_services = [
        "api-gateway", "load-balancer", "database", "redis", "kafka",
        "elasticsearch", "nginx", "kubernetes", "docker", "postgres",
        "mysql", "mongodb", "rabbitmq", "consul", "vault", "prometheus",
        "grafana", "s3", "lambda", "ec2", "rds", "cloudfront", "cdn",
        "auth-service", "payment-service", "user-service", "notification-service",
        "order-service", "inventory-service", "search-service",
    ]

    context_lower = context.lower()
    found = [svc for svc in common_services if svc in context_lower]

    return json.dumps({
        "identified_services": found if found else ["Unable to auto-detect; review context manually"],
        "context_snippet": context[:1500],
    }, indent=2)


# ─── Agent Executor ─────────────────────────────────────────────────────────────

AGENT_SYSTEM_PROMPT = """You are an expert Incident Root Cause Analysis (RCA) agent.

Your job is to analyze production incidents by:
1. Examining logs for error patterns and anomalies
2. Correlating alerts with the incident timeline
3. Identifying all affected services
4. Using these findings to drive a comprehensive RCA

You have tools available to help with structured analysis. Use them to gather insights,
then synthesize your findings into a comprehensive assessment.

Always be thorough, specific, and evidence-based in your analysis."""


def create_rca_agent() -> AgentExecutor:
    """Create a multi-step agent for incident analysis orchestration."""
    settings = get_settings()

    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0.1,
        api_key=settings.openai_api_key,
    )

    tools = [
        analyze_log_patterns,
        correlate_alerts_timeline,
        identify_affected_services,
    ]

    prompt = ChatPromptTemplate.from_messages([
        ("system", AGENT_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_openai_functions_agent(llm, tools, prompt)

    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=6,
        return_intermediate_steps=True,
        handle_parsing_errors=True,
    )

    return executor


async def run_agent_pre_analysis(
    incident_context: str,
    memory: Optional[IncidentMemory] = None,
) -> Dict[str, Any]:
    """
    Run the agent for preliminary analysis before the structured chains.
    The agent uses tools to extract patterns, correlate data, and identify services.
    """
    logger.info("Running RCA agent pre-analysis")

    agent = create_rca_agent()

    chat_history = []
    if memory:
        mem_vars = memory.get_memory_variables()
        chat_history = mem_vars.get("chat_history", [])

    input_prompt = (
        f"Perform a preliminary analysis of this incident. Use your tools to:\n"
        f"1. Analyze the log patterns\n"
        f"2. Correlate alerts with the timeline\n"
        f"3. Identify affected services\n\n"
        f"Then provide a synthesis of your findings.\n\n"
        f"INCIDENT DATA:\n{incident_context}"
    )

    result = await agent.ainvoke({
        "input": input_prompt,
        "chat_history": chat_history,
    })

    logger.info("Agent pre-analysis complete")

    return {
        "output": result.get("output", ""),
        "intermediate_steps": [
            {
                "tool": step[0].tool,
                "input": str(step[0].tool_input)[:500],
                "output": str(step[1])[:500],
            }
            for step in result.get("intermediate_steps", [])
        ],
    }